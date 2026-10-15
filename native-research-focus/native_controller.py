"""Semantic requests to the build-pinned native test backend. No input fallback."""
import contextlib,hashlib,json,os,re,threading
from pathlib import Path
from direct_controller import atomic_text
from direct_process import process_identity
from read_native_state import read_state
from native_json import read_receipt
DLL_SHA='ea4c632ab61bfe03315b952a9d5ee28b9c7c45b1d48b2428e0c9a0646a096cc0'

def selection_command(request_id,kind,identifier,slot):
 if not re.fullmatch('[0-9a-f]{32}',request_id):raise ValueError('32 lowercase hexadecimal characters required')
 if kind not in ('research','focus','cancel','combatstop','move','attack','law','advisor','decision','armygroup','theater','trade','queue','deployloc','deploy') or not isinstance(identifier,str):raise ValueError('Canonical command ID required')
 if kind=='theater' and identifier=='new':pass
 elif kind in ('cancel','combatstop','move','attack','armygroup','theater','queue','deployloc','deploy'):
  if not re.fullmatch('[1-9][0-9]{0,9}:[1-9][0-9]{0,9}',identifier) or any(int(v)>0xffffffff for v in identifier.split(':')):raise ValueError('Canonical two-word native unit ID required')
 elif kind=='trade':
  if not re.fullmatch('[A-Z0-9]{3}:[a-z][a-z0-9_]{0,63}',identifier):raise ValueError('Exact partner country and resource IDs required')
 elif kind=='advisor':
  if len(identifier)>159 or not re.fullmatch('[A-Za-z0-9_-]+:[A-Za-z0-9_-]+',identifier):raise ValueError('Exact character and advisor-role IDs required')
 elif kind=='decision':
  if not re.fullmatch('[A-Za-z0-9_.-]{1,159}',identifier):raise ValueError('Exact ordinary decision ID required')
 elif kind=='law':
  if len(identifier)>159 or not re.fullmatch('[A-Za-z0-9_]+:[A-Za-z0-9_]+',identifier):raise ValueError('Exact law group and law IDs required')
 elif not re.fullmatch('[A-Za-z0-9_]{1,159}',identifier):raise ValueError('Canonical technology/focus ID required')
 if type(slot)!=int or (kind=='research' and not 1<=slot<=16) or (kind in ('focus','cancel','combatstop','law','advisor','decision','queue','deploy') and slot!=0) or (kind in ('move','attack','deployloc') and not 1<=slot<=0x7fffffff) or (kind in ('armygroup','theater') and not 1<=slot<=64) or (kind=='trade' and not 1<=slot<=1000):raise ValueError('Research slot or movement province ID invalid; focus/cancel/law/advisor require zero')
 return {'kind':kind,'id':identifier,'slot':slot}

class NativeController:
 def __init__(self,session_file,identity=process_identity):
  self.path=Path(session_file);self.config=json.loads(self.path.read_text());self.native=self.path.parent/'native';self.ledger=self.native/'selection-ledger.json';self.identity=identity;self.lock=threading.RLock()
  if self.config['country'] not in ('GER','ITA') or self.config['mode']!='singleplayer_test' or not self.config.get('process_identity'):raise RuntimeError('Bound supported-country test campaign required')
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
  if o.get('country_code')!=c['country']:raise RuntimeError('Native callback country binding mismatch')
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
  return {'session_id':d['session_id'],'armed':d['armed'],'native_callback':o,'requests':list(d['requests']),'military_orders':list(d.get('military_orders',{})),'prepared_politics':list(d.get('prepared_politics',{})),'experimental':True,'uses_keyboard_or_mouse':False,'requires_unpaused_game':True}
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
  r=read_receipt(p)
  if r['session_id']!=d['session_id'] or r['request_id']!=request_id:raise RuntimeError('Native receipt mismatch')
  observed=self.native/f'deployment-observation-{request_id}.json'
  if observed.exists():
   result=read_receipt(observed)
   digest=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':')).encode()).hexdigest()
   if result['session_id']!=d['session_id'] or result['request_id']!=request_id or result['native_receipt_sha256']!=digest or result['command']!=d['requests'][request_id]:raise RuntimeError('Deployment observation binding mismatch')
   return result
  return r
 def reconcile_deployment(self,request_id):
  from time_controller import TimeController
  from deployment_reconcile import verify_created_queue
  with self.transaction():
   self.check();d=self.load()
   if d['armed'] or not TimeController(self).status()['paused']:raise RuntimeError('Paused disarmed session required')
   current=self.receipt(request_id)
   if current['stage']=='deployment_observed':return current
   command=d['requests'][request_id]
   if command['kind']!='queue' or current!={'session_id':d['session_id'],'request_id':request_id,'stage':'execution_uncertain'}:raise RuntimeError('Only an original bare queue intent can be reconciled')
   report=read_receipt(self.native/f'deployment-execution-{request_id}.json')
   if report['session_id']!=d['session_id'] or report['operation']!='queue' or report['payload']!={'request_id':request_id,'template_id':command['id']}:raise RuntimeError('Pre-action report binding mismatch')
   after=self.deployment_snapshot();units=self.military_snapshot()
   verified=verify_created_queue(report['before'],after,command['id'],report['units_before'],units)
   result={'session_id':d['session_id'],'request_id':request_id,'stage':'deployment_observed','native_stage':'execution_uncertain','command':command,'native_receipt_sha256':hashlib.sha256(json.dumps(current,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'receipt_source':'independent_read_only_reconciliation','outcome_verified':True,'uses_keyboard_or_mouse':False,'process_writes':False,'after':after,'units_after':units,**verified}
   atomic_text(self.native/f'deployment-observation-{request_id}.json',json.dumps(result,indent=2));return result
 def submit(self,request_id,kind,identifier,slot=0):
  command=selection_command(request_id,kind,identifier,slot)
  with self.transaction():
   o=self.check();d=self.load()
   if request_id in d['requests']:
    if d['requests'][request_id]!=command:raise ValueError('Request ID already belongs to different payload')
    return self.receipt(request_id)
   batches=d.get('military_orders',{})
   if request_id in d.get('theater_payloads',{}) and kind!='theater':raise ValueError('Request ID is reserved for theater assignment')
   if request_id in batches or request_id in d.get('prepared_politics',{}):raise ValueError('Request ID is already reserved')
   for batch in batches.values():
    if request_id in batch['request_ids']:
     if 'result' in batch:raise ValueError('Request ID is reserved by a closed military order')
     payload=batch['command'];i=batch['request_ids'].index(request_id)
     expected={'kind':payload['kind'],'id':payload['unit_ids'][i],'slot':payload['province_id'] if payload['kind']=='move' else 0}
     if command!=expected:raise ValueError('Request ID is reserved for different unit orders')
   if any('result' not in batch and request_id not in batch['request_ids'] for batch in batches.values()):raise RuntimeError('Reconcile the active military order first')
   reservation=d.get('army_group_payloads',{}).get(request_id)
   if reservation is not None and kind!='armygroup':raise ValueError('Request ID is reserved for army-group creation')
   if kind=='armygroup':
    if reservation is None or reservation['theatre_id']!=identifier or len(reservation['unit_ids'])!=slot:raise RuntimeError('Owned unit payload required')
    expected=d['session_id']+'|'+request_id+'|'+','.join(reservation['unit_ids'])
    if (self.native/f'army-units-{request_id}.txt').read_text()!=expected:raise RuntimeError('Owned unit payload changed')
   if kind=='theater':
    reservation=d.get('theater_payloads',{}).get(request_id)
    if reservation is None or reservation['target']!=identifier or len(reservation['group_ids'])!=slot:raise RuntimeError('Owned group payload required')
    expected=d['session_id']+'|'+request_id+'|'+','.join(reservation['group_ids'])
    if (self.native/f'theater-groups-{request_id}.txt').read_text()!=expected:raise RuntimeError('Owned group payload changed')
   if not d['armed']:raise RuntimeError('Native interface is disarmed')
   for rid in d['requests']:
    r=self.receipt(rid)
    if r['stage'] not in ('selection_verified','military_verified','law_verified','advisor_verified','decision_verified','army_group_verified','theater_verified','trade_verified','deployment_verified','deployment_observed','rejected'):raise RuntimeError('Reconcile the unresolved request before another action')
   if len(d['requests'])>=64:raise RuntimeError('Session request limit reached')
   d['world']=o['world'];d['requests'][request_id]=command;self.save(d)
   atomic_text(self.native/'request.txt',f"{d['session_id']}|{request_id}|{kind}|{identifier}|{slot}")
  return self.receipt(request_id)
 def create_army_group(self,request_id,theatre_id,unit_ids):
  if not isinstance(unit_ids,list) or not 1<=len(unit_ids)<=64:raise ValueError('Provide 1..64 native unit IDs')
  command=selection_command(request_id,'armygroup',theatre_id,len(unit_ids))
  for unit in unit_ids:selection_command(request_id,'move',unit,1)
  if len(set(unit_ids))!=len(unit_ids):raise ValueError('Duplicate unit IDs')
  payload={'theatre_id':theatre_id,'unit_ids':list(unit_ids)}
  with self.transaction():
   self.check();d=self.load();reserved=d.setdefault('army_group_payloads',{})
   if request_id in reserved:
    if reserved[request_id]!=payload:raise ValueError('Request ID already belongs to different unit-group creation')
    if request_id in d['requests']:return self.receipt(request_id)
   else:
    if request_id in d.get('theater_payloads',{}) or request_id in d['requests'] or request_id in d.get('military_orders',{}) or request_id in d.get('prepared_politics',{}) or any(request_id in batch['request_ids'] for batch in d.get('military_orders',{}).values()):raise ValueError('Request ID is already reserved')
    if not d['armed']:raise RuntimeError('Native interface is disarmed')
    reserved[request_id]=payload;self.save(d)
   path=self.native/f'army-units-{request_id}.txt';expected=d['session_id']+'|'+request_id+'|'+','.join(unit_ids)
   if path.exists():
    if path.read_text()!=expected:raise RuntimeError('Owned unit payload changed')
   else:atomic_text(path,expected)
  return self.submit(request_id,command['kind'],command['id'],command['slot'])

 def assign_theater(self,request_id,group_ids,theater_id=None):
  if not isinstance(group_ids,list) or not 1<=len(group_ids)<=64:raise ValueError('Provide 1..64 native group IDs')
  target='new' if theater_id is None else theater_id
  command=selection_command(request_id,'theater',target,len(group_ids))
  for group in group_ids:selection_command(request_id,'cancel',group,0)
  if len(set(group_ids))!=len(group_ids):raise ValueError('Duplicate group IDs')
  payload={'target':target,'group_ids':list(group_ids)}
  with self.transaction():
   self.check();d=self.load();reserved=d.setdefault('theater_payloads',{})
   if request_id in reserved:
    if reserved[request_id]!=payload:raise ValueError('Request ID already belongs to different theater assignment')
    if request_id in d['requests']:return self.receipt(request_id)
   else:
    if request_id in d['requests'] or request_id in d.get('army_group_payloads',{}) or request_id in d.get('military_orders',{}) or request_id in d.get('prepared_politics',{}) or any(request_id in batch['request_ids'] for batch in d.get('military_orders',{}).values()):raise ValueError('Request ID is already reserved')
    if not d['armed']:raise RuntimeError('Native interface is disarmed')
    reserved[request_id]=payload;self.save(d)
   path=self.native/f'theater-groups-{request_id}.txt';expected=d['session_id']+'|'+request_id+'|'+','.join(group_ids)
   if path.exists():
    if path.read_text()!=expected:raise RuntimeError('Owned group payload changed')
   else:atomic_text(path,expected)
  return self.submit(request_id,command['kind'],command['id'],command['slot'])

 def orders_group_snapshot(self):
  from runtime_gui import WindowsProcess,NativeGuiReader
  from orders_group_reader import read_country_group_units
  observation=self.check();exe=Path(self.config['game_root'])/'hoi4.exe'
  process=WindowsProcess(self.config['process_identity'],exe)
  try:
   reader=NativeGuiReader(process,hashlib.sha256(exe.read_bytes()).hexdigest())
   result=read_country_group_units(reader,int(observation['country'],16),int(observation['world'],16))
   process.guard();result['session_id']=self.config['session_id'];return result
  finally:process.close()

 def order_units(self,request_id,order,unit_ids,province_id=None):
  """Sequential orders, not atomic: retain partial results and every child ID."""
  if order not in ('move','cancel'):raise ValueError('order must be move or cancel')
  if not isinstance(unit_ids,list) or not 1<=len(unit_ids)<=16:raise ValueError('Provide 1..16 native unit IDs')
  if order=='cancel' and province_id is not None:raise ValueError('Cancellation has no destination')
  slot=province_id if order=='move' else 0
  for unit in unit_ids:selection_command(request_id,order,unit,slot)
  if len(set(unit_ids))!=len(unit_ids):raise ValueError('Duplicate unit IDs')
  payload={'kind':order,'unit_ids':list(unit_ids),'province_id':province_id}
  with self.transaction():
   observation=self.check();d=self.load();batches=d.setdefault('military_orders',{})
   if request_id in d.get('theater_payloads',{}) or request_id in d.get('army_group_payloads',{}):raise ValueError('Request ID is reserved for army-group creation')
   if request_id in batches:
    batch=batches[request_id]
    if batch['command']!=payload:raise ValueError('Request ID already belongs to different orders')
   else:
    if request_id in d['requests'] or request_id in d.get('prepared_politics',{}) or any(request_id in batch['request_ids'] for batch in batches.values()):raise ValueError('Request ID already belongs to another command')
    if any('result' not in batch for batch in batches.values()):raise RuntimeError('Reconcile the active military order first')
    if not d['armed']:raise RuntimeError('Native interface is disarmed')
    if len(d['requests'])+len(unit_ids)>64:raise RuntimeError('Session request limit reached')
    if any(self.receipt(rid)['stage'] not in ('selection_verified','military_verified','law_verified','advisor_verified','decision_verified','army_group_verified','theater_verified','trade_verified','deployment_verified','deployment_observed','rejected') for rid in d['requests']):raise RuntimeError('Reconcile the unresolved request before another action')
    owned={unit['unit_id'] for unit in self.military_snapshot()['units']}
    if not set(unit_ids)<=owned:raise ValueError('Every unit must belong to the current country')
    batch={'command':payload,'request_ids':[hashlib.sha256(f'{request_id}:{i}'.encode()).hexdigest()[:32] for i in range(len(unit_ids))]}
    batches[request_id]=batch;d['world']=observation['world'];self.save(d)
   if 'result' in batch:return batch['result']
  completed=[]
  result={'request_id':request_id,'order':payload,'child_request_ids':batch['request_ids'],'completed_request_ids':completed,'atomic':False,'uses_keyboard_or_mouse':False}
  for unit,rid in zip(unit_ids,batch['request_ids']):
   # submit itself reconciles an existing ID and never republishes it.
   receipt=self.submit(rid,order,unit,slot)
   if receipt['stage']=='pending':return dict(result,stage='pending',active_request_id=rid)
   if receipt['stage']!='military_verified':
    result.update(stage='stopped_rejected' if receipt['stage']=='rejected' else 'stopped_uncertain',active_request_id=rid,receipt=receipt);break
   completed.append(rid)
  else:
   snapshot=self.military_snapshot();units={unit['unit_id']:unit for unit in snapshot['units']}
   def matches(unit):
    if order=='cancel':return unit['destination_province_id'] is None and unit['movement_path_count']==0
    return unit['movement_path_target_province_id']==province_id or (unit['movement_path_count']==0 and unit['current_province_id']==province_id)
   verified=all(unit in units and matches(units[unit]) for unit in unit_ids)
   result.update(stage='orders_verified' if verified else 'stopped_postcondition_failed',native_tick=snapshot['native_tick'],units=[units[unit] for unit in unit_ids if unit in units],arrival_verified=False)
  with self.transaction():
   self.check();d=self.load();record=d['military_orders'][request_id]
   if 'result' not in record:record['result']=result;self.save(d)
   return record['result']

 def prepare_politics(self,request_id,command):
  """Offline preparation only; does not check a running process or publish input."""
  from politics_commands import prepare_command
  if not isinstance(request_id,str) or not re.fullmatch('[0-9a-f]{32}',request_id):raise ValueError('Invalid request ID')
  with self.transaction():
   d=self.load();prepared=d.setdefault('prepared_politics',{})
   if request_id in prepared:
    if prepared[request_id]['command']!=command:raise ValueError('Request ID already belongs to a different command')
    return prepared[request_id]
   batches=d.get('military_orders',{})
   if request_id in d.get('theater_payloads',{}) or request_id in d['requests'] or request_id in batches or request_id in d.get('army_group_payloads',{}) or any(request_id in batch['request_ids'] for batch in batches.values()):raise ValueError('Request ID already belongs to another command')
   result=prepare_command(self.config['game_root'],self.config['country'],command)
   result.update(request_id=request_id,session_id=d['session_id'],source_freshness='as_of_preparation')
   prepared[request_id]=result;self.save(d);return result

 def snapshot(self):
  self.check();return read_state(self.path)

 def combat_snapshot(self):
  from runtime_gui import WindowsProcess,NativeGuiReader
  from combat_reader import read_country_land_combats
  observation=self.check();exe=Path(self.config['game_root'])/'hoi4.exe'
  process=WindowsProcess(self.config['process_identity'],exe)
  try:
   reader=NativeGuiReader(process,hashlib.sha256(exe.read_bytes()).hexdigest())
   result=read_country_land_combats(reader,int(observation['country'],16),int(observation['world'],16))
   process.guard();result['session_id']=self.config['session_id'];return result
  finally:process.close()

 def military_snapshot(self):
  from runtime_gui import WindowsProcess,NativeGuiReader
  from military_reader import read_unit_ids
  observation=self.check();exe=Path(self.config['game_root'])/'hoi4.exe'
  digest=hashlib.sha256(exe.read_bytes()).hexdigest()
  process=WindowsProcess(self.config['process_identity'],exe)
  try:
   reader=NativeGuiReader(process,digest)
   result=read_unit_ids(reader,int(observation['country'],16),int(observation['world'],16))
   process.guard();result['session_id']=self.config['session_id'];return result
  finally:process.close()

 def idea_snapshot(self,identifier=None):
  from runtime_gui import WindowsProcess,NativeGuiReader
  from politics_reader import read_country_ideas
  observation=self.check();exe=Path(self.config['game_root'])/'hoi4.exe'
  process=WindowsProcess(self.config['process_identity'],exe)
  try:
   result=read_country_ideas(NativeGuiReader(process,hashlib.sha256(exe.read_bytes()).hexdigest()),int(observation['country'],16),int(observation['world'],16),identifier)
   process.guard();result.pop('idea_pointers',None);result.pop('definition_pointers',None);result['session_id']=self.config['session_id'];return result
  finally:process.close()

 def advisor_snapshot(self):
  from runtime_gui import WindowsProcess,NativeGuiReader
  from advisor_reader import read_country_advisors
  observation=self.check();exe=Path(self.config['game_root'])/'hoi4.exe'
  process=WindowsProcess(self.config['process_identity'],exe)
  try:
   result=read_country_advisors(NativeGuiReader(process,hashlib.sha256(exe.read_bytes()).hexdigest()),int(observation['country'],16),int(observation['world'],16))
   process.guard();result['session_id']=self.config['session_id'];return result
  finally:process.close()

 def decision_snapshot(self,include_registry=False):
  if type(include_registry)!=bool:raise ValueError('include_registry must be boolean')
  from runtime_gui import WindowsProcess,NativeGuiReader
  from decision_reader import read_country_decision_observations
  observation=self.check();exe=Path(self.config['game_root'])/'hoi4.exe'
  process=WindowsProcess(self.config['process_identity'],exe)
  try:
   reader=NativeGuiReader(process,hashlib.sha256(exe.read_bytes()).hexdigest())
   result=read_country_decision_observations(reader,int(observation['country'],16),int(observation['world'],16),include_registry=include_registry)
   process.guard();result['session_id']=self.config['session_id'];return result
  finally:process.close()

 def deployed_unit_snapshot(self,unit_id):
  from runtime_gui import WindowsProcess,NativeGuiReader
  from deployed_unit_reader import read_deployed_unit
  observation=self.check();exe=Path(self.config['game_root'])/'hoi4.exe'
  process=WindowsProcess(self.config['process_identity'],exe)
  try:
   reader=NativeGuiReader(process,hashlib.sha256(exe.read_bytes()).hexdigest())
   result=read_deployed_unit(reader,int(observation['country'],16),int(observation['world'],16),unit_id)
   process.guard();result['session_id']=self.config['session_id'];return result
  finally:process.close()

 def deployment_snapshot(self,templates=False):
  from runtime_gui import WindowsProcess,NativeGuiReader
  from deployment_reader import read_country_deployment,read_country_division_templates
  observation=self.check();exe=Path(self.config['game_root'])/'hoi4.exe'
  process=WindowsProcess(self.config['process_identity'],exe)
  try:
   reader=NativeGuiReader(process,hashlib.sha256(exe.read_bytes()).hexdigest())
   read=read_country_division_templates if templates else read_country_deployment
   result=read(reader,int(observation['country'],16),int(observation['world'],16))
   process.guard();result['session_id']=self.config['session_id'];return result
  finally:process.close()

 def trade_snapshot(self,partner_country):
  from runtime_gui import WindowsProcess,NativeGuiReader
  from country_binding import read_country_binding
  from trade_reader import read_trade_bindings
  observation=self.check();exe=Path(self.config['game_root'])/'hoi4.exe'
  process=WindowsProcess(self.config['process_identity'],exe)
  try:
   reader=NativeGuiReader(process,hashlib.sha256(exe.read_bytes()).hexdigest())
   world=int(observation['world'],16);country=int(observation['country'],16)
   partner=read_country_binding(reader,world,partner_country)
   result=read_trade_bindings(reader,country,partner['country_id'])
   process.guard();result.update(session_id=self.config['session_id'],partner_country=partner_country,partner_native_tag=partner['native_tag'],process_writes=False,uses_keyboard_or_mouse=False)
   return result
  finally:process.close()

 def tooltip_result_assets(self,request_id):
  from time_controller import TimeController
  from runtime_gui import WindowsProcess,NativeGuiReader
  from inline_assets import read_inline_assets
  clock=TimeController(self);receipt=clock.receipt(request_id)
  command=clock.load()['requests'][request_id]
  if command['kind']!='tooltipquery' or receipt['stage']!='tooltip_result_generated':raise RuntimeError('Completed native tooltip result required')
  if any(receipt.get(k)!=command[k] for k in ('source','name')):raise RuntimeError('Native tooltip selector mismatch')
  self.check();exe=Path(self.config['game_root'])/'hoi4.exe';process=WindowsProcess(self.config['process_identity'],exe)
  try:
   reader=NativeGuiReader(process,hashlib.sha256(exe.read_bytes()).hexdigest())
   core=reader.current_tooltip();widget=int(core['widget_id'],16)
   channels={key:read_inline_assets(reader,widget,raw_text=receipt['raw_'+key]) for key in ('title','body','auxiliary')}
   process.guard()
   return {'session_id':self.config['session_id'],'request_id':request_id,'native_receipt':receipt,'channels':channels,'font_reference':'current_engine_CoreToolTip_font','core_updated':False,'native_result_rendered':False,'process_writes':False,'uses_keyboard_or_mouse':False}
  finally:process.close()

 def regional_alert_cache(self):
  from runtime_gui import WindowsProcess,NativeGuiReader
  from regional_cache import read_regional_cache
  self.check();exe=Path(self.config['game_root'])/'hoi4.exe'
  process=WindowsProcess(self.config['process_identity'],exe)
  try:
   reader=NativeGuiReader(process,hashlib.sha256(exe.read_bytes()).hexdigest())
   result=read_regional_cache(reader);process.guard();result['session_id']=self.config['session_id'];return result
  finally:process.close()

 def tooltip_assets(self):
  from runtime_gui import WindowsProcess,NativeGuiReader,GuiSnapshotChanged
  from inline_assets import read_inline_assets
  observation=self.check();exe=Path(self.config['game_root'])/'hoi4.exe'
  process=WindowsProcess(self.config['process_identity'],exe)
  try:
   reader=NativeGuiReader(process,hashlib.sha256(exe.read_bytes()).hexdigest())
   before=reader.current_tooltip();assets=read_inline_assets(reader,int(before['widget_id'],16));after=reader.current_tooltip()
   if (before['widget_id']!=after['widget_id'] or before['buffers']!=after['buffers'] or
       assets['raw_text']!=after['buffers']['rendered_buffer']['raw_text']):
    raise GuiSnapshotChanged('Tooltip changed during asset binding read')
   process.guard()
   return {'session_id':self.config['session_id'],'tooltip':after,'formatting':assets,
    'process_writes':False,'uses_keyboard_or_mouse':False,'atomic_game_frame':False}
  finally:process.close()

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
    if self.receipt(rid)['stage'] not in ('selection_verified','military_verified','law_verified','advisor_verified','decision_verified','army_group_verified','theater_verified','trade_verified','deployment_verified','deployment_observed','rejected'):raise RuntimeError('Reconcile pending gameplay before requesting a new read')
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
