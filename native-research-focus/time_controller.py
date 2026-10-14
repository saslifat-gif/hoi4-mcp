"""Idempotent semantic time requests to the paused-safe native frame callback."""
import json,re,hashlib,ctypes,time
from direct_controller import atomic_text
DLL_SHA='42dc6c4430a6e20effdcee4701d8ab6c952642d213bc4f06c72026ec0e866653'
def read_native_json(path):
 # Windows can briefly deny opens while the native writer atomically replaces a file.
 # Retry reads only; commands and malformed observations are never retried here.
 for attempt in range(6):
  try:return json.loads(path.read_text(encoding="utf-8"))
  except PermissionError:
   if attempt==5:raise
   time.sleep(.02)

class TimeController:
 def __init__(self,native):self.native=native;self.root=native.native;self.path=self.root/'time-ledger.json'
 def status(self):
  o=self.native.check()
  if (self.root/'time-error.json').exists():raise RuntimeError('Native time callback failed')
  if hashlib.sha256((self.root/'hoi4-native-time.dll').read_bytes()).hexdigest()!=DLL_SHA:raise RuntimeError('Time backend changed')
  d=read_native_json(self.root/'time-status.json')
  if d['session_id']!=self.native.config['session_id'] or d['pid']!=self.native.config['process_identity']['pid'] or d['world']!=o['world']:raise RuntimeError('Time observation binding mismatch')
  k=ctypes.WinDLL('kernel32');k.GetTickCount64.restype=ctypes.c_ulonglong
  if not 0<=k.GetTickCount64()-d['heartbeat_ms']<=5000:raise RuntimeError('Time callback heartbeat is stale')
  return d
 def load(self):
  d=json.loads(self.path.read_text()) if self.path.exists() else {'session_id':self.native.config['session_id'],'requests':{}}
  if d['session_id']!=self.native.config['session_id']:raise RuntimeError('Time ledger binding mismatch')
  return d
 def receipt(self,rid):
  if not isinstance(rid,str) or not re.fullmatch('[a-f0-9]{32}',rid):raise ValueError('32-hex request ID required')
  self.status();d=self.load()
  if rid not in d['requests']:raise ValueError('Unknown time request')
  p=self.root/f'time-receipt-{rid}.json'
  if not p.exists():return {'request_id':rid,'stage':'pending'}
  r=read_native_json(p)
  if r['session_id']!=d['session_id'] or r['request_id']!=rid:raise RuntimeError('Time receipt binding mismatch')
  return r
 def submit(self,rid,kind,value):
  if not isinstance(rid,str) or not re.fullmatch('[a-f0-9]{32}',rid):raise ValueError('32-hex request ID required')
  if kind=='pause':
   if type(value)!=bool:raise ValueError('paused must be boolean')
  elif kind=='speed':
   if type(value)!=int or not 1<=value<=5:raise ValueError('Speed is an integer 1..5')
  elif kind=='alert':
   if type(value)!=int or not 0<=value<=81:raise ValueError('Native global-alert kind must be 0..81')
  else:raise ValueError('Unsupported time command')
  command={'kind':kind,'value':value}
  with self.native.transaction():
   self.status();d=self.load()
   if rid in d['requests']:
    if d['requests'][rid]!=command:raise ValueError('Request ID payload mismatch')
    return self.receipt(rid)
   if not self.native.load()['armed']:raise RuntimeError('Native interface is disarmed')
   for old in d['requests']:
    if self.receipt(old)['stage'] not in ('time_verified','alert_refreshed','rejected'):raise RuntimeError('Reconcile unresolved time command first')
   if len(d['requests'])>=64:raise RuntimeError('Time command limit reached')
   d['requests'][rid]=command;atomic_text(self.path,json.dumps(d,indent=2))
   atomic_text(self.root/'time-request.txt',f"{d['session_id']}|{rid}|{kind}|{int(value)}")
  return self.receipt(rid)
