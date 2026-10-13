"""Semantic requests to the build-pinned native test backend. No input fallback."""
import contextlib,hashlib,json,os,re,threading
from pathlib import Path
from direct_controller import atomic_text
from direct_process import process_identity
from read_native_state import read_state
DLL_SHA='dffc6a1fee8c4bfcf3ea477db60adbf171636ba75b3c84e82d60a55b348c85b6'

class NativeController:
 def __init__(self,session_file,identity=process_identity):
  self.path=Path(session_file);self.config=json.loads(self.path.read_text());self.native=self.path.parent/'native';self.ledger=self.native/'selection-ledger.json';self.identity=identity;self.lock=threading.RLock()
  if self.config['country']!='GER' or self.config['mode']!='singleplayer_test' or not self.config.get('process_identity'):raise RuntimeError('Bound Germany test campaign required')
 @contextlib.contextmanager
 def transaction(self):
  with self.lock:
   lockfile=self.native/'selection.lock'
   fd=os.open(lockfile,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
   try:yield
   finally:os.close(fd);lockfile.unlink()
 def check(self):
  c=self.config
  if self.identity(c['process_identity']['pid'])!=c['process_identity']:raise RuntimeError('Bound game process changed or exited')
  if hashlib.sha256((self.native/'hoi4-native-selection.dll').read_bytes()).hexdigest()!=DLL_SHA:raise RuntimeError('Native backend changed')
  if (self.native/'native-error.json').exists():raise RuntimeError('Native backend reported an exception; execution disabled')
  o=json.loads((self.native/'native-observation.json').read_text())
  if o['session_id']!=c['session_id'] or o['pid']!=c['process_identity']['pid'] or not o.get('selection_commands_enabled'):raise RuntimeError('Native callback handshake not ready')
  if self.ledger.exists():
   bound=self.load().get('world')
   if bound and bound!=o['world']:raise RuntimeError('Game world changed; prepare a new session')
  return o
 def load(self):
  d=json.loads(self.ledger.read_text()) if self.ledger.exists() else {'session_id':self.config['session_id'],'armed':False,'requests':{}}
  if d['session_id']!=self.config['session_id']:raise RuntimeError('Ledger session mismatch')
  return d
 def save(self,d):atomic_text(self.ledger,json.dumps(d,indent=2))
 def status(self):
  o=self.check();d=self.load()
  return {'session_id':d['session_id'],'armed':d['armed'],'native_callback':o,'requests':list(d['requests']),'experimental':True,'uses_keyboard_or_mouse':False,'requires_unpaused_game':True}
 def arm(self,enabled):
  if type(enabled)!=bool:raise ValueError('enabled must be boolean')
  with self.transaction():
   self.check();d=self.load();d['armed']=enabled;self.save(d)
   if not enabled:
    for name in ('request.txt','time-request.txt'):(self.native/name).unlink(missing_ok=True)
  return {'armed':enabled,'pending_requests_retained':True,'in_flight_execution_may_already_have_started':not enabled}
 def receipt(self,request_id):
  if not re.fullmatch('[0-9a-f]{32}',request_id):raise ValueError('Invalid request ID')
  self.check();d=self.load()
  if request_id not in d['requests']:raise ValueError('Unknown request ID')
  p=self.native/f'receipt-{request_id}.json'
  if not p.exists():return {'request_id':request_id,'stage':'pending','command':d['requests'][request_id]}
  r=json.loads(p.read_text())
  if r['session_id']!=d['session_id'] or r['request_id']!=request_id:raise RuntimeError('Native receipt mismatch')
  return r
 def submit(self,request_id,kind,identifier,slot=0):
  if not re.fullmatch('[0-9a-f]{32}',request_id):raise ValueError('32 lowercase hexadecimal characters required')
  if kind not in ('research','focus') or not isinstance(identifier,str) or not re.fullmatch('[A-Za-z0-9_]{1,159}',identifier):raise ValueError('Canonical technology/focus ID required')
  if type(slot)!=int or (kind=='research' and not 1<=slot<=16) or (kind=='focus' and slot!=0):raise ValueError('Research slot is 1-based; focus has no slot')
  command={'kind':kind,'id':identifier,'slot':slot}
  with self.transaction():
   o=self.check();d=self.load()
   if request_id in d['requests']:
    if d['requests'][request_id]!=command:raise ValueError('Request ID already belongs to different payload')
    return self.receipt(request_id)
   if not d['armed']:raise RuntimeError('Native interface is disarmed')
   for rid in d['requests']:
    r=self.receipt(rid)
    if r['stage'] not in ('selection_verified','rejected'):raise RuntimeError('Reconcile the unresolved request before another action')
   if len(d['requests'])>=64:raise RuntimeError('Session request limit reached')
   d['world']=o['world'];d['requests'][request_id]=command;self.save(d)
   atomic_text(self.native/'request.txt',f"{d['session_id']}|{request_id}|{kind}|{identifier}|{slot}")
  return self.receipt(request_id)
 def snapshot(self):
  self.check();return read_state(self.path)

 def peacetime_snapshot(self,request_id):
  """Queue/reconcile one immutable, read-only snapshot through the existing engine transport."""
  from bind_session import verify_sources
  from direct_controller import DirectController
  from peacetime_reader import parse_frame,merge_frame
  if not re.fullmatch('[0-9a-f]{32}',request_id):raise ValueError('32 lowercase hexadecimal characters required')
  with self.transaction():
   observation=self.check();cfg=self.config
   if 'peacetime_catalog_path' not in cfg:raise RuntimeError('Peacetime reader is not installed for this binding')
   cp=Path(cfg['peacetime_catalog_path'])
   if hashlib.sha256(cp.read_bytes()).hexdigest()!=cfg['peacetime_catalog_sha256']:raise RuntimeError('Peacetime catalog changed')
   catalog=json.loads(cp.read_text());game=Path(cfg['game_root'])
   for name,digest in catalog['source_hashes'].items():
    source=(game/name).resolve()
    if not source.is_relative_to(game.resolve()) or hashlib.sha256(source.read_bytes()).hexdigest()!=digest:raise RuntimeError('Peacetime source changed')
   if hashlib.sha256((self.native/'hoi4-native-choices.dll').read_bytes()).hexdigest()!=catalog['choices_dll_sha256']:raise RuntimeError('Native choice module changed')
   eq=verify_sources(cfg);eq['peacetime']=catalog
   # Avoid publishing a caller while a native gameplay request is unresolved.
   for rid in self.load()['requests']:
    if self.receipt(rid)['stage'] not in ('selection_verified','rejected'):raise RuntimeError('Reconcile pending gameplay before requesting a new read')
   core=DirectController(cfg['effect_path'],cfg['log_path'],cfg['state_path'],country=cfg['country'],process_guard=self.check,hook_path=cfg['hook_path'],session_id=cfg['session_id'],catalog=eq)
   known=request_id in dict(core.state['commands'])
   delivery=core.submit({'kind':'snapshot'},request_id)
   if delivery['status']=='delivery_uncertain':return {'request_id':request_id,'status':'delivery_uncertain','delivery':delivery,'uses_keyboard_or_mouse':False}
   frame=parse_frame(Path(cfg['log_path']).read_text(errors='replace'),cfg['session_id'],request_id,catalog)
   choice_file=self.native/f'choices-{request_id}.json'
   if frame is None or not choice_file.exists():return {'request_id':request_id,'status':'pending','requires_unpaused_game':True,'uses_keyboard_or_mouse':False}
   choices=json.loads(choice_file.read_text())
   if choices.get('world')!=observation['world']:raise RuntimeError('Peacetime sample belongs to another world')
   result=merge_frame(frame,choices,cfg,request_id);result['cached_request']=known;result['snapshot_is_immutable']=True
   self.check();return result
