"""Source-bound command preparation. Native politics execution is not implemented."""
import re
from script_parser import scalar
from script_definitions import read_definitions

FIELDS={'law':{'group','law'},'advisor':{'character','slot'},
        'decision':{'category','decision','target_country'},'trade':{'partner_country','resource','factories'}}

def prepare_command(game_root,country,command):
 if not isinstance(command,dict) or command.get('kind') not in FIELDS:raise ValueError('Unknown political command')
 kind=command['kind']
 if set(command)!={'kind',*FIELDS[kind]}:raise ValueError('Unexpected or missing command fields')
 for key,value in command.items():
  if key=='factories':
   if type(value)!=int or not 1<=value<=0x7fffffff:raise ValueError('Trade factories must be a positive 32-bit integer')
  elif key=='target_country' and value is None:continue
  elif not isinstance(value,str) or not 1<=len(value)<=159:raise ValueError('Exact script identifiers required')
 for key in ('partner_country','target_country'):
  value=command.get(key)
  if value is not None and not re.fullmatch('[A-Z][A-Z0-9]{2}',value):raise ValueError('A three-character country tag is required')
 def definition(category,path):
  matches=[row for row in read_definitions(game_root,category,path[-1])['definitions'] if row['script_path']==path]
  if len(matches)!=1:raise ValueError('Missing or ambiguous installed definition: '+':'.join(path))
  return matches[0]
 if kind=='law':
  reference=definition('ideas',[command['group']]);children=reference['definition']['children']
  if scalar(children,'law')!='yes':raise ValueError('Idea group is not declared as a law group')
  selected=[node for node in children if node['key']==command['law'] and node['children'] is not None]
  if len(selected)!=1:raise ValueError('Missing or ambiguous law in the requested group')
 elif kind=='advisor':
  reference=definition('characters',[command['character']])
  selected=[node for node in reference['definition']['children'] if node['key']=='advisor' and node['children'] is not None and scalar(node['children'],'slot')==command['slot']]
  if len(selected)!=1:raise ValueError('Missing or ambiguous advisor role in the requested slot')
 elif kind=='decision':
  # Keep the category context too; category visibility is not a decision field.
  reference=definition('decisions',[command['category']])
  selected=[node for node in reference['definition']['children'] if node['key']==command['decision'] and node['children'] is not None]
  if len(selected)!=1:raise ValueError('Missing or ambiguous decision in the requested category')
 else:
  if command['partner_country']==country:raise ValueError('Trade partner must be another country')
  reference=definition('resources',[command['resource']]);selected=[reference['definition']]
 return {'stage':'prepared_not_executed','country':country,'command':dict(command),
         'source_reference':reference,'selected_definition':selected[0],
         'native_execution_implemented':False,'runtime_availability_verified':False,
         'native_identity_verified':False,'active_overlay_verified':False,
         'cost_verified':False,'uses_keyboard_or_mouse':False,'gameplay_changed':False}
