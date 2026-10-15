"""Read only typed land-combat memberships, guarded against mixed snapshots."""
import struct
from native_handle import HANDLE_SIGNATURES, resolve_native_handle
from runtime_gui import GuiSnapshotChanged


def read_country_land_combats(reader, country, world):
    r, guards = reader, []
    def read(address, size):
        data = r.read(address, size)
        if data is None or len(data) != size:
            raise RuntimeError('Combat field unreadable')
        guards.append((address, data))
        return data
    def scalar(fmt, address):
        return struct.unpack(fmt, read(address, struct.calcsize(fmt)))[0]
    def ptr(address):
        return scalar('<Q', address)
    def typed(address, vt, name):
        if not address or ptr(address) != r.base + vt or r.typename(address) != name:
            raise RuntimeError('Combat object type mismatch')
    def vector(address):
        data, capacity, count = struct.unpack('<QII', read(address, 16))
        if not 0 <= count <= capacity <= 100000:
            raise RuntimeError('Combat vector extent invalid')
        values = struct.unpack('<' + 'Q' * count, read(data, count * 8)) if count else ()
        if any(not x for x in values) or len(set(values)) != count:
            raise RuntimeError('Null or duplicate combat member')
        return values
    def identity(address, subobject, first=None):
        a, b = struct.unpack('<II', read(address + subobject + 8, 8))
        if not a or not b or (first is not None and a != first) or resolve_native_handle(r.base, read, a, b) != address + subobject:
            raise GuiSnapshotChanged('Combat native ID binding changed')
        return f'{a}:{b}'
    for address, code in HANDLE_SIGNATURES.items():
        expected = bytes.fromhex(code)
        if read(r.base + address, len(expected)) != expected:
            raise RuntimeError('Native handle implementation changed')
    typed(country, 0x27e7360, '.?AVCCountry@@')
    if ptr(r.base + 0x332f260) != world:
        raise GuiSnapshotChanged('Combat world changed')
    tag, tick = scalar('<I', country + 8), scalar('<i', world + 0x468)
    if not tag:
        raise RuntimeError('Combat country tag invalid')
    manager = world + 0x260
    typed(manager, 0x2950688, '.?AVCCombatManager@@')
    managed = set(vector(manager + 8))
    province_array = ptr(world + 0x2b0)
    province_count = scalar('<i', world + 0x2bc)
    if not 1 <= province_count <= 100000:
        raise RuntimeError('Combat province list extent invalid')
    owned = vector(country + 0x290)
    owned_set, unit_data, combats = set(owned), {}, {}
    def unit(address):
        if address in unit_data:
            return unit_data[address]
        typed(address, 0x295a2b0, '.?AVCArmy@@')
        if ptr(address + 0x10) != r.base + 0x295a490:
            raise RuntimeError('Combat unit gameobject type mismatch')
        row = {'unit_id': identity(address, 0x10),
               'country_tag_native': scalar('<I', address + 0x1d8)}
        if not row['country_tag_native'] or ((address in owned_set) != (row['country_tag_native'] == tag)):
            raise RuntimeError('Combat unit country inventory inconsistent')
        unit_data[address] = row
        return row
    for address in owned:
        row = unit(address)
        references = vector(address + 0x1a8)
        row['combat_ids'] = []
        for combat in references:
            if combat not in managed:
                raise RuntimeError('Unit combat missing from native world manager')
            typed(combat, 0x29a83d8, '.?AVCLandCombat@@')
            if ptr(combat + 0x10) != r.base + 0x29a84b8:
                raise RuntimeError('Land combat gameobject type mismatch')
            combat_id = identity(combat, 0x10)
            row['combat_ids'].append(combat_id)
            if combat not in combats:
                sides, seen = [], set()
                for side_ptr in (ptr(combat + 0x28), ptr(combat + 0x30)):
                    typed(side_ptr, 0x29a82c0, '.?AVCLandCombatant@@')
                    members = vector(side_ptr + 0x20)
                    for member in members:
                        if member in seen or combat not in vector(member + 0x1a8):
                            raise GuiSnapshotChanged('Combat membership is not bidirectional')
                        seen.add(member)
                    sides.append({'units': [{key: unit(member)[key] for key in ('unit_id', 'country_tag_native')} for member in members]})
                province = ptr(combat + 0x38)
                province_id = scalar('<i', province + 0xa4)
                if not 1 <= province_id < province_count or ptr(province_array + province_id * 8) != province:
                    raise GuiSnapshotChanged('Combat province binding changed')
                combats[combat] = {'combat_id': combat_id, 'province_id': province_id, 'sides': sides, '_members': seen}
            if address not in combats[combat]['_members']:
                raise GuiSnapshotChanged('Owned unit absent from its listed combat sides')
    for combat in combats.values():
        del combat['_members']
    if any(r.read(address, len(value)) != value for address, value in guards):
        raise GuiSnapshotChanged('Combat membership changed during read')
    return {'country_tag_native': tag, 'native_tick': tick,
            'units': [unit_data[address] for address in owned], 'combats': list(combats.values()),
            'native_world_manager_verified': True, 'bidirectional_membership_verified': True,
            'side_roles_verified': False, 'process_writes': False,
            'uses_keyboard_or_mouse': False, 'atomic_game_frame': False,
            'attack_eligibility_verified': False, 'combat_result_verified': False}
