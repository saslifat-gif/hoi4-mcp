"""Committed engine frames, correlated native validation and explicit as-of data."""
import math,re
from decimal import Decimal,InvalidOperation
from peacetime_script import SCALARS,RESOURCE_FIELDS,BUILDINGS
HEX=re.compile(r'[a-f0-9]{32}\Z')
DATE=re.compile(r'\[(\d{4}\.\d{2}\.\d{2}\.\d{2})\]')
def number(value,integer=False):
 try:d=Decimal(value)
 except InvalidOperation:raise ValueError('Invalid engine numeric value')
 if not d.is_finite():raise ValueError('Non-finite engine numeric value')
 if integer:
  if d!=d.to_integral_value() or abs(d)>1000000000:raise ValueError('Invalid engine integer')
  return int(d)
 f=float(d)
 if not math.isfinite(f):raise ValueError('Out-of-range numeric value')
 return f

def state_scope_id(value):
 # Dynamic state arrays hold signed 32-bit tagged scope references in the
 # raw fixed-point value, rather than ordinary numeric state IDs.
 raw=Decimal(value)*100000
 if not raw.is_finite() or raw!=raw.to_integral_value() or not -(1<<31)<=raw<(1<<31):raise ValueError('Invalid state scope reference')
 bits=int(raw)&0xffffffff
 if bits>>30!=3 or not bits&0x3fffffff:raise ValueError('Unexpected state scope type')
 return bits&0x3fffffff

def parse_frame(log,sid,rid,catalog):
 if not HEX.fullmatch(sid) or not HEX.fullmatch(rid):raise ValueError('Invalid read identity')
 prefix=f'CODEX_PEACETIME|{sid}|{rid}|';frame=None;committed=None
 for line in log.splitlines():
  p=line.find(prefix)
  if p<0:continue
  payload=line[p+len(prefix):];parts=payload.split('|');kind=parts[0];values={}
  for part in parts[1:]:
   if '=' not in part:raise ValueError('Invalid peacetime field')
   k,v=part.split('=',1)
   if k in values:raise ValueError('Duplicate peacetime field')
   values[k]=v
  if 'frame_marker' not in values:raise ValueError('Missing snapshot tick')
  tick=number(values['frame_marker'],True)
  if tick!=1:raise ValueError('Invalid frame marker')
  dates=DATE.findall(line)
  if not dates:raise ValueError('Missing engine date')
  date=dates[-1]
  if kind=='BEGIN':
   if committed is not None:raise ValueError('Duplicate committed read request')
   frame={'frame_marker':tick,'game_date':date,'resources':{},'owned_states':[],'construction':[],'production':[]};continue
  if frame is None:raise ValueError('Peacetime record without begin')
  if tick!=frame['frame_marker'] or date!=frame['game_date']:raise ValueError('Mixed game updates in read frame')
  if kind=='DATA':
   if 'scalars' in frame or set(values)!={'frame_marker',*SCALARS}:raise ValueError('Invalid economy scalar fields')
   integer_keys={k for k in SCALARS if k.endswith('_total') or k.endswith('_available') or k in ('civilian_available_for_projects','owned_state_count')}
   frame['scalars']={k:number(values[k],k in integer_keys) for k in SCALARS}
  elif kind=='RESOURCE':
   resource=values.get('id')
   if resource not in catalog['resources'] or resource in frame['resources'] or set(values)!={'frame_marker','id',*RESOURCE_FIELDS}:raise ValueError('Invalid resource row')
   frame['resources'][resource]={k:number(values[k]) for k in RESOURCE_FIELDS}
  elif kind=='STATE':
   if set(values)!={'frame_marker','id'}:raise ValueError('Invalid owned-state row')
   state=state_scope_id(values['id'])
   if state in frame['owned_states']:raise ValueError('Duplicate owned state')
   frame['owned_states'].append(state)
  elif kind=='CONSTRUCTION':
   if set(values)!={'frame_marker','state','building','max_levels'}:raise ValueError('Invalid construction row')
   state=state_scope_id(values['state']);levels=number(values['max_levels'],True);building=values['building']
   if state not in frame['owned_states'] or not 1<=levels<=5 or building not in BUILDINGS:raise ValueError('Invalid supported construction choice')
   row={'state_id':state,'building':building,'max_levels':levels}
   if any(x['state_id']==state and x['building']==building for x in frame['construction']):raise ValueError('Duplicate construction choice')
   if state<=10000:frame['construction'].append(row)
  elif kind=='PRODUCTION':
   if set(values)!={'frame_marker','id'} or values['id'] not in catalog['equipment_ids'] or values['id'] in frame['production']:raise ValueError('Invalid production row')
   frame['production'].append(values['id'])
  elif kind=='END':
   if set(values)!={'frame_marker'} or 'scalars' not in frame or set(frame['resources'])!=set(catalog['resources']):raise ValueError('Incomplete economy frame')
   if len(frame['owned_states'])!=frame['scalars']['owned_state_count']:raise ValueError('Incomplete owned-state enumeration')
   committed=frame;frame=None
  else:raise ValueError('Unknown peacetime record')
 return committed

def merge_frame(frame,choices,config,rid):
 if choices.get('stage')!='validated':raise RuntimeError('Native availability validation failed: '+str(choices.get('reason')))
 if choices.get('session_id')!=config['session_id'] or choices.get('request_id')!=rid or choices.get('pid')!=config['process_identity']['pid']:raise RuntimeError('Native choice binding mismatch')
 if type(choices.get('native_tick')) is not int:raise RuntimeError('Missing native sample clock')
 for category in ('research','focuses'):
  rows=choices.get(category)
  if not isinstance(rows,list) or not rows or len({x['id'] for x in rows})!=len(rows):raise RuntimeError('Invalid native choice catalog')
  for x in rows:
   if type(x.get('available')) is not bool or type(x.get('engine_allowed')) is not bool or (x['available'] and not x['engine_allowed']):raise RuntimeError('Invalid native availability result')
 empty=choices['empty_research_slots'];busy=choices['focus_busy']
 if not isinstance(empty,list) or len(set(empty))!=len(empty) or any(type(s)!=int or not 1<=s<=16 for s in empty) or type(busy)!=bool:raise RuntimeError('Invalid native slot guards')
 if (not empty and any(x['available'] for x in choices['research'])) or (busy and any(x['available'] for x in choices['focuses'])):raise RuntimeError('Native command slot guard mismatch')
 construction=frame['construction'];capacity=[]
 if config.get('native_construction'):
  rows=choices.get('construction_capacity')
  if not isinstance(rows,list) or choices.get('construction_state_count')!=len(frame['owned_states']) or len(rows)!=3*len(frame['owned_states']):raise RuntimeError('Incomplete native construction capacity')
  by_key={}
  for x in rows:
   key=(x['state_id'],x['building'])
   if key in by_key or x['state_id'] not in frame['owned_states'] or x['building'] not in BUILDINGS:raise RuntimeError('Invalid native capacity identity')
   for field in ('built','built_and_queued','queued','queue_adjusted_limit','remaining'):
    if type(x.get(field)) is not int or not 0<=x[field]<=10000:raise RuntimeError('Invalid native queued level')
   if x['built_and_queued']!=x['built']+x['queued'] or x['remaining']!=max(0,x['queue_adjusted_limit']-x['built_and_queued']):raise RuntimeError('Inconsistent native queue capacity')
   by_key[key]=x
  capacity=rows
  construction=[{**x,'max_levels':min(5,by_key[(x['state_id'],x['building'])]['remaining'])} for x in construction if by_key[(x['state_id'],x['building'])]['remaining']>0]
 v=frame['scalars'];max_factories=max(0,min(15,v['military_available']))
 if frame['production'] and not max_factories:raise RuntimeError('Production choices contradict available factories')
 return {'request_id':rid,'status':'ready','sample_consistent':True,'as_of_game_date':frame['game_date'],'native_tick':choices['native_tick'],
  'political_power':{'current':v['political_power'],'daily_change':v['political_power_daily']},
  'factories':{'civilian':{'total':v['civilian_total'],'available':v['civilian_available'],'available_for_projects':v['civilian_available_for_projects']},
   'military':{'total':v['military_total'],'available':v['military_available']},'dockyards':{'total':v['dockyards_total'],'available':v['dockyards_available']}},
  'fuel':{'stored_thousands':v['fuel_thousands'],'capacity_thousands':v['fuel_capacity_thousands'],'ratio':v['fuel_ratio']},
  'resources':frame['resources'],'owned_state_ids':frame['owned_states'],
  'available_choices':{'research':{'validation':'native_selection_validator_and_backend_guard','empty_slots':empty,'choices':choices['research']},
   'national_focus':{'validation':'native_selection_validator_and_backend_guard','active_focus_blocks_replacement':busy,'choices':choices['focuses']},
   'construction':{'validation':'native_queued_capacity_and_engine_guard' if config.get('native_construction') else 'supported_command_engine_guard','choices':construction,'capacity':capacity,'normal_player_equivalence_verified':False},
   'production':{'validation':'supported_command_engine_guard','catalog_scope':'installed_base_equipment','active_overlay_verified':bool(config.get('content_binding',{}).get('snapshot',{}).get('active_overlay_verified')),'choices':[{'equipment':x,'max_factories':max_factories} for x in frame['production']]}},
  'requires_command_revalidation':True,'uses_keyboard_or_mouse':False,'source':'game_script_and_native_validators'}
