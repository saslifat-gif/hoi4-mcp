"""Conservative equipment allowlist from the installed base scripts.

Active DLC/mod overlays are unresolved. No guessed IDs or arbitrary effects.
"""
import hashlib
import re
from pathlib import Path
from script_parser import parse_script, scalar

IDENTIFIER = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,119}\Z')
MILITARY_TYPES = {'infantry', 'artillery', 'anti_air', 'anti_tank',
                  'armor', 'motorized', 'mechanized'}


def build_catalog(game_root):
    root = Path(game_root)
    definitions = {}; unlocks = {}; hashes = {}
    for directory, category in [('common/units/equipment', 'equipment'),
                                ('common/technologies', 'technology')]:
        files = sorted((root / directory).glob('*.txt'))
        if not files:
            raise ValueError('Installed scripts missing: ' + directory)
        for path in files:
            raw = path.read_bytes(); source = path.relative_to(root).as_posix()
            hashes[source] = hashlib.sha256(raw).hexdigest()
            nodes = parse_script(raw.decode('utf-8-sig'))
            wrapper = 'equipments' if category == 'equipment' else 'technologies'
            for outer in nodes:
                if outer['key'] != wrapper or outer['children'] is None:
                    continue
                for node in outer['children']:
                    key = node['key']; children = node['children']
                    if children is None or not isinstance(key, str) or not IDENTIFIER.fullmatch(key):
                        continue
                    if category == 'equipment':
                        if key in definitions:
                            raise ValueError('Ambiguous equipment definition: ' + key)
                        definitions[key] = {'nodes': children, 'source': source}
                    else:
                        for part in children:
                            if part['key'] == 'enable_equipments' and part['children'] is not None:
                                for item in part['children']:
                                    if item['key'] is None and item['children'] is None:
                                        unlocks.setdefault(item['value'], set()).add(key)
    result = {}; excluded = {}
    for key, definition in definitions.items():
        nodes = definition['nodes']
        if scalar(nodes, 'is_archetype') == 'yes':
            continue
        lineage = []; current = key
        while current:
            if current in lineage:
                raise ValueError('Equipment inheritance cycle: ' + key)
            lineage.append(current)
            if current not in definitions:
                break
            current = scalar(definitions[current]['nodes'], 'parent') or scalar(definitions[current]['nodes'], 'archetype')
        inherited = [definitions[x]['nodes'] for x in lineage if x in definitions]
        unresolved = sorted({part['key'] for group in inherited for part in group
                             if part['key'] in ('module_slots','can_be_produced','allowed','allow','dlc_allowed')})
        if unresolved:
            excluded[key] = {'reason':'unresolved_design_or_production_restriction','fields':unresolved}
            continue
        types = [scalar(n, 'type') for n in inherited]
        equipment_type = next((v for v in types if v is not None), None)
        # Only land military-factory types whose source field is understood.
        if equipment_type not in MILITARY_TYPES:
            continue
        active = scalar(nodes, 'active')
        required = sorted(unlocks.get(key, set()))
        if active != 'yes' and not required:
            continue
        result[key] = {'factory_kind': 'military', 'base_active': active == 'yes',
                       'unlock_technologies_any': required, 'source': definition['source'],
                       'source_sha256': hashes[definition['source']]}
    # Cost/eligibility rules for supported buildings must be pinned too.
    for path in sorted((root/'common/buildings').glob('*.txt')):
        hashes[path.relative_to(root).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    return {'equipment': result, 'excluded_equipment': excluded, 'source_hashes': hashes,
            'source_scope': 'installed_base_only', 'active_overlay_verified': False}


def equipment_guard(catalog, equipment, factories):
    if not isinstance(equipment, str) or not IDENTIFIER.fullmatch(equipment):
        raise ValueError('Invalid equipment ID')
    entry = catalog.get('equipment', {}).get(equipment)
    if not entry or entry.get('factory_kind') != 'military':
        raise ValueError('Equipment is absent from the verified base allowlist')
    if type(entry.get('base_active')) is not bool or not isinstance(entry.get('unlock_technologies_any'),list):
        raise ValueError('Invalid catalog availability fields')
    technologies = entry.get('unlock_technologies_any', [])
    if any(not isinstance(t, str) or not IDENTIFIER.fullmatch(t) for t in technologies):
        raise ValueError('Invalid catalog technology ID')
    if not entry.get('base_active') and not technologies:
        raise ValueError('Equipment availability is unresolved')
    unlock = 'always = yes' if entry.get('base_active') else 'OR = { ' + ' '.join('has_tech = ' + t for t in technologies) + ' }'
    return f'num_of_available_military_factories > {factories - 1}\n{unlock}'


def construction_state_guard(country, building, levels):
    """Shared checks for the supported state factories; the engine owns queue costs."""
    if not re.fullmatch(r'[A-Z]{3}',country):raise ValueError('Invalid country')
    if building not in ('industrial_complex','arms_factory','dockyard'):raise ValueError('Unsupported building')
    if type(levels) is not int or not 1<=levels<=5:raise ValueError('Invalid levels')
    restrictions=[]
    if building=='dockyard':restrictions.append('is_coastal = yes')
    if building=='arms_factory':restrictions.append('is_demilitarized_zone = no')
    return '\n'.join(restrictions+[f'is_owned_and_controlled_by = {country}',
        f'can_construct_building = {building}',
        f'free_building_slots = {{ building = {building} size > {levels-1} include_locked = no }}'])
