"""Read-only, request-correlated engine sampler for supported peacetime commands."""
import re
from command_catalog import equipment_guard, construction_state_guard
ID=re.compile(r'[A-Za-z][A-Za-z0-9_]{0,119}\Z')
HEX=re.compile(r'[a-f0-9]{32}\Z')
SCALARS={'political_power':'political_power','political_power_daily':'political_power_daily',
 'civilian_total':'num_of_civilian_factories','civilian_available':'num_of_available_civilian_factories',
 'civilian_available_for_projects':'num_of_civilian_factories_available_for_projects',
 'military_total':'num_of_military_factories','military_available':'num_of_available_military_factories',
 'dockyards_total':'num_of_naval_factories','dockyards_available':'num_of_available_naval_factories',
 'fuel_thousands':'fuel_k','fuel_capacity_thousands':'max_fuel_k','fuel_ratio':'fuel_ratio',
 'owned_state_count':'num_owned_states'}
RESOURCE_FIELDS={'surplus':'resource','produced':'resource_produced','consumed':'resource_consumed','imported':'resource_imported','exported':'resource_exported'}
BUILDINGS=('industrial_complex','arms_factory','dockyard')
def render_frame(sid,rid,read_catalog,equipment_catalog):
 if not HEX.fullmatch(sid) or not HEX.fullmatch(rid):raise ValueError('Invalid read identity')
 resources=read_catalog['resources']
 if not resources or len(resources)>32 or len(set(resources))!=len(resources) or any(not ID.fullmatch(x) for x in resources):raise ValueError('Invalid resource catalog')
 prefix=f'CODEX_PEACETIME|{sid}|{rid}|'
 tick='1'
 lines=['# Read frame identity is the immutable request ID; frame marker is not game time.',f'log = "{prefix}BEGIN|frame_marker={tick}"']
 for key,token in SCALARS.items():lines.append(f'set_temp_variable = {{ codex_peace_{key} = {token} }}')
 values='|'.join(f'{key}=[?codex_peace_{key}]' for key in SCALARS)
 lines.append(f'log = "{prefix}DATA|frame_marker={tick}|{values}"')
 for resource in resources:
  for key,token in RESOURCE_FIELDS.items():lines.append(f'set_temp_variable = {{ codex_peace_{key} = {token}@{resource} }}')
  values='|'.join(f'{key}=[?codex_peace_{key}]' for key in RESOURCE_FIELDS)
  lines.append(f'log = "{prefix}RESOURCE|frame_marker={tick}|id={resource}|{values}"')
 lines.append('for_each_loop = { array = owned_states value = codex_peace_state')
 lines.append(f'log = "{prefix}STATE|frame_marker={tick}|id=[?codex_peace_state]"')
 for building in BUILDINGS:
  guard=construction_state_guard('GER',building,1)
  lines.append(f'''if = {{ limit = {{ var:codex_peace_state = {{ {guard} }} }}
log = "{prefix}CONSTRUCTION|frame_marker={tick}|state=[?codex_peace_state]|building={building}|max_levels=1" }}''')
 lines.append('}')
 for equipment in sorted(equipment_catalog['equipment']):
  guard=equipment_guard(equipment_catalog,equipment,1)
  lines.append(f'if = {{ limit = {{ {guard} }} log = "{prefix}PRODUCTION|frame_marker={tick}|id={equipment}" }}')
 lines.append(f'log = "{prefix}END|frame_marker={tick}"')
 return '\n'.join(lines)
