"""Idempotent semantic time requests to the paused-safe native frame callback."""
import json,re,hashlib,ctypes,time
from direct_controller import atomic_text
DLL_SHA='7fe17d984f068fbd31abbfda511e5798c363c824eb663f3b0a41554c14c9e4e3'
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
 def receipt(self,rid,*,observe_window=False):
  if not isinstance(rid,str) or not re.fullmatch('[a-f0-9]{32}',rid):raise ValueError('32-hex request ID required')
  self.status();d=self.load()
  if rid not in d['requests']:raise ValueError('Unknown time request')
  failed=d.get('publication_failures',{}).get(rid)
  if failed:
   if (self.root/f'time-receipt-{rid}.json').exists():raise RuntimeError('Conflicting native and failed-publication receipts')
   return {'session_id':d['session_id'],'request_id':rid,'stage':'rejected','reason':'request_publication_failed','receipt_source':'controller_atomic_publication','native_execution_attempted':False,**failed}
  p=self.root/f'time-receipt-{rid}.json'
  if not p.exists():return {'request_id':rid,'stage':'pending'}
  r=read_native_json(p)
  if r['session_id']!=d['session_id'] or r['request_id']!=rid:raise RuntimeError('Time receipt binding mismatch')
  observed=self.root/f'window-observation-{rid}.json'
  if observed.exists():
   result=read_native_json(observed)
   if result['session_id']!=d['session_id'] or result['request_id']!=rid:raise RuntimeError('Window observation binding mismatch')
   return result
  if observe_window and r['stage']=='execution_uncertain' and r.get('reason')=='window_state_unverified' and d['requests'][rid]['kind']=='worldtension':
   # The engine's close fade can outlive the immediate callback read. Observe
   # its pinned owner without applying the action again; retain native evidence.
   from runtime_gui import capture_live_ui
   sample=capture_live_ui(self.native.path,self.native.config['game_root'],source='interface/worldtensionwindowpopup.gui',native_type='CContainerWindow',engine_state='any',limit=100)
   windows=[x for x in sample['matches'] if x.get('native_popup',{}).get('status')=='native_window_state']
   if not sample['truncated'] and len(windows)==1 and windows[0]['native_popup']['engine_local_shown']==d['requests'][rid]['value']:
    result={**r,'stage':'window_observed','native_stage':r['stage'],'after_shown':d['requests'][rid]['value'],'observed_unix':sample['captured_end_unix'],'widget_id':windows[0]['widget_id'],'readback_binding':'CWorldTensionPopUpWindow.container','readback_process_writes':False,'uses_keyboard_or_mouse':False}
    atomic_text(observed,json.dumps(result,indent=2));return result
  return r
 def submit(self,rid,kind,value,*,selector=None):
  if not isinstance(rid,str) or not re.fullmatch('[a-f0-9]{32}',rid):raise ValueError('32-hex request ID required')
  if kind in ('pause','worldtension'):
   if type(value)!=bool:raise ValueError('paused must be boolean')
  elif kind=='worldview':
   if type(value)!=int or value not in (0,4):raise ValueError('World-tension view must be 0 or 4')
  elif kind=='speed':
   if type(value)!=int or not 1<=value<=5:raise ValueError('Speed is an integer 1..5')
  elif kind=='alert':
   if type(value)!=int or not 0<=value<=81:raise ValueError('Native global-alert kind must be 0..81')
  elif kind=='save':
   if type(value)!=int or value!=0:raise ValueError('Owned save command requires zero value')
  elif kind in ('tooltip','tooltipquery'):
   if type(value)!=int or value!=0 or not isinstance(selector,dict) or set(selector)!={'source','name'}:raise ValueError('Exact tooltip source/name required')
   for text in selector.values():
    if not isinstance(text,str) or not 1<=len(text.encode('utf-8'))<=512 or any(ord(c)<32 or c=='|' for c in text):raise ValueError('Invalid tooltip selector')
  else:raise ValueError('Unsupported time command')
  command={'kind':kind,'value':value}
  if selector is not None:
   if kind not in ('tooltip','tooltipquery'):raise ValueError('Selector is only supported for tooltip generation')
   command.update(selector)
  with self.native.transaction():
   self.status();d=self.load()
   if rid in d['requests']:
    if d['requests'][rid]!=command:raise ValueError('Request ID payload mismatch')
    return self.receipt(rid,observe_window=kind=='worldtension')
   if not self.native.load()['armed']:raise RuntimeError('Native interface is disarmed')
   for old in d['requests']:
    if self.receipt(old)['stage'] not in ('time_verified','alert_refreshed','window_verified','window_observed','tooltip_generated','tooltip_result_generated','save_file_observed','rejected'):raise RuntimeError('Reconcile unresolved time command first')
   if len(d['requests'])>=64:raise RuntimeError('Time command limit reached')
   d['requests'][rid]=command;atomic_text(self.path,json.dumps(d,indent=2))
   try:
    if kind in ('tooltip','tooltipquery'):atomic_text(self.root/f'tooltip-selector-{rid}.txt',f"{d['session_id']}|{rid}|{selector['source']}\n{selector['name']}")
    atomic_text(self.root/'time-request.txt',f"{d['session_id']}|{rid}|{kind}|{int(value)}")
   except PermissionError as error:
    d.setdefault('publication_failures',{})[rid]={'winerror':getattr(error,'winerror',None)}
    atomic_text(self.path,json.dumps(d,indent=2))
  return self.receipt(rid)
