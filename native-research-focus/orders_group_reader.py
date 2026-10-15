"""Read-only CTheatre group membership; caller must supply its bound manager."""
import struct
from native_handle import HANDLE_SIGNATURES, resolve_native_handle
from runtime_gui import GuiSnapshotChanged

GROUP_TYPES = {0x29522b0: ('.?AVCOrdersGroup@@', 'orders_group', 0),
               0x2952348: ('.?AVCArmyGroup@@', 'army_group', 1)}


def read_orders_groups(reader, country, world, theatre):
    r = reader
    guards = []

    def read(address, size):
        data = r.read(address, size)
        if data is None or len(data) != size:
            raise RuntimeError('Native group field unreadable')
        guards.append((address, data))
        return data

    def scalar(fmt, address):
        return struct.unpack(fmt, read(address, struct.calcsize(fmt)))[0]

    def ptr(address):
        return scalar('<Q', address)

    def vector(address):
        data, capacity, count = struct.unpack('<QII', read(address, 16))
        if not 0 <= count <= capacity <= 100000:
            raise RuntimeError('Native group list extent invalid')
        entries = struct.unpack('<' + 'Q' * count, read(data, 8 * count)) if count else ()
        if any(not v for v in entries) or len(set(entries)) != count:
            raise RuntimeError('Null or duplicate native group list entry')
        return entries

    def identity(address):
        first, second = struct.unpack('<II', read(address + 8, 8))
        if not first or not second or resolve_native_handle(r.base, read, first, second) != address:
            raise GuiSnapshotChanged('Group ID no longer resolves to its listed object')
        return f'{first}:{second}'

    for address, code in HANDLE_SIGNATURES.items():
        expected = bytes.fromhex(code)
        if read(r.base + address, len(expected)) != expected:
            raise RuntimeError('Native handle implementation changed')
    if ptr(r.base + 0x332f260) != world:
        raise RuntimeError('Bound military world changed')
    read(country, 8)
    if r.typename(country) != '.?AVCCountry@@':
        raise RuntimeError('Native group country type mismatch')
    tag = scalar('<I', country + 8)
    tick = scalar('<i', world + 0x468)
    if not tag or ptr(theatre) != r.base + 0x2975a48 or r.typename(theatre) != '.?AVCTheatre@@':
        raise RuntimeError('Native theatre manager type mismatch')
    if scalar('<I', theatre + 0x48) != tag:
        raise RuntimeError('Theatre manager belongs to another country')
    manager_id = identity(theatre)
    groups = vector(theatre + 0xb0)
    theaters = vector(theatre + 0xc8)
    theater_ids, memberships = {}, {}
    for item in theaters:
        if ptr(item) != r.base + 0x29e5c50 or r.typename(item) != '.?AVCTheaterGroup@@':
            raise RuntimeError('Native theater group type mismatch')
        if ptr(item + 0x18) != theatre:
            raise RuntimeError('Theater group belongs to another manager')
        theater_ids[item] = identity(item)
        for member in vector(item + 0x48):
            if member not in groups or member in memberships:
                raise RuntimeError('Native theater member list is inconsistent')
            memberships[member] = item
    rows = []
    ids = set()
    for group in groups:
        binding = GROUP_TYPES.get(ptr(group) - r.base)
        if not binding or r.typename(group) != binding[0]:
            raise RuntimeError('Native orders group type mismatch')
        if scalar('<I', group + 0x3c) != tag or ptr(group + 0x40) != theatre:
            raise RuntimeError('Orders group belongs to another country or manager')
        if scalar('<B', group + 0x39) != binding[2]:
            raise RuntimeError('Native orders group subtype mismatch')
        group_id = identity(group)
        if group_id in ids:
            raise RuntimeError('Duplicate native orders group ID')
        ids.add(group_id)
        parent = ptr(group + 0x180)
        if parent != memberships.get(group, 0):
            raise GuiSnapshotChanged('Theater membership is not bidirectional')
        rows.append({'group_id': group_id, 'kind': binding[1],
                     'theater_id': theater_ids.get(parent),
                     'country_membership_verified': True})
    if any(r.read(address, len(data)) != data for address, data in guards):
        raise GuiSnapshotChanged('Native group identity changed during read')
    return {'country_tag_native': tag, 'native_tick': tick, 'theatre_id': manager_id, 'groups': rows,
            'theater_ids': list(theater_ids.values()), 'uses_keyboard_or_mouse': False,
            'process_writes': False, 'atomic_game_frame': False,
            'country_to_manager_binding_verified': False,
            'command_eligibility_verified': False}


def read_country_orders_groups(reader, country, world):
    """Enumerate CCountry's native CTheatre inventory before reading groups."""
    from types import SimpleNamespace
    guards = []

    def read(address, size):
        data = reader.read(address, size)
        if data is None or len(data) != size:
            raise RuntimeError('Country theatre inventory unreadable')
        guards.append((address, data))
        return data

    if struct.unpack('<Q', read(country, 8))[0] != reader.base + 0x27e7360 or reader.typename(country) != '.?AVCCountry@@':
        raise RuntimeError('Native group country type mismatch')
    if struct.unpack('<Q', read(reader.base + 0x332f260, 8))[0] != world:
        raise RuntimeError('Bound military world changed')
    tag = struct.unpack('<I', read(country + 8, 4))[0]
    tick = struct.unpack('<i', read(world + 0x468, 4))[0]
    data, capacity, count = struct.unpack('<QII', read(country + 0x168, 16))
    if not tag or not 0 <= count <= capacity <= 100000:
        raise RuntimeError('Country theatre inventory extent invalid')
    managers = struct.unpack('<' + 'Q' * count, read(data, count * 8)) if count else ()
    if any(not m for m in managers) or len(set(managers)) != count:
        raise RuntimeError('Null or duplicate country theatre manager')
    bound_reader = SimpleNamespace(base=reader.base, read=read, typename=reader.typename)
    snapshots = [read_orders_groups(bound_reader, country, world, manager) for manager in managers]
    if any(reader.read(address, len(value)) != value for address, value in guards):
        raise GuiSnapshotChanged('Country theatre inventory changed during read')
    for snapshot in snapshots:
        snapshot['country_to_manager_binding_verified'] = True
    return {'country_tag_native': tag, 'native_tick': tick, 'theatres': snapshots,
            'country_to_manager_binding_verified': True, 'atomic_game_frame': False,
            'process_writes': False, 'uses_keyboard_or_mouse': False,
            'command_eligibility_verified': False}


def read_country_group_units(reader, country, world):
    """Independent unit/group reciprocity; native member entries are unit+b8."""
    from types import SimpleNamespace
    guards = []

    def read(address, size):
        data = reader.read(address, size)
        if data is None or len(data) != size:
            raise RuntimeError('Native unit/group field unreadable')
        guards.append((address, data))
        return data

    def ptr(address):
        return struct.unpack('<Q', read(address, 8))[0]

    def vector(address):
        data, capacity, count = struct.unpack('<QII', read(address, 16))
        if not 0 <= count <= capacity <= 100000:
            raise RuntimeError('Native unit/group vector extent invalid')
        entries = struct.unpack('<' + 'Q' * count, read(data, 8 * count)) if count else ()
        if any(not item for item in entries) or len(set(entries)) != count:
            raise RuntimeError('Null or duplicate native unit/group entry')
        return entries

    bound = SimpleNamespace(base=reader.base, read=read, typename=reader.typename)
    result = read_country_orders_groups(bound, country, world)
    groups = {}
    managers = vector(country + 0x168)
    for manager, snapshot in zip(managers, result['theatres']):
        listed = vector(manager + 0xb0)
        for group, row in zip(listed, snapshot['groups']):
            if group in groups:
                raise RuntimeError('Group appears in multiple country managers')
            groups[group] = row
    unit_rows, units_by_interface, assigned_members = [], {}, {}
    for unit in vector(country + 0x290):
        if ptr(unit) != reader.base + 0x295a2b0 or ptr(unit + 0x10) != reader.base + 0x295a490 or ptr(unit + 0xb8) != reader.base + 0x295a500 or reader.typename(unit) != '.?AVCArmy@@':
            raise RuntimeError('Native unit type mismatch')
        first, second = struct.unpack('<II', read(unit + 0x18, 8))
        if not first or not second or resolve_native_handle(reader.base, read, first, second) != unit + 0x10:
            raise GuiSnapshotChanged('Unit ID no longer resolves to its game object')
        parent = ptr(unit + 0xc0)
        if parent and (parent not in groups or groups[parent]['kind'] != 'orders_group'):
            raise RuntimeError('Unit orders group is outside its country inventory')
        row = {'unit_id': f'{first}:{second}', 'orders_group_id': groups[parent]['group_id'] if parent else None,
               'unit_owner_tag_native': struct.unpack('<I', read(unit + 0x1d8, 4))[0]}
        unit_rows.append(row)
        units_by_interface[unit + 0xb8] = (unit, parent, row)
    for group, row in groups.items():
        if row['kind'] == 'army_group':
            children = vector(group + 0x230)
            if any(child not in groups or ptr(child + 0x1b8) != group for child in children):
                raise GuiSnapshotChanged('Army group child membership is not reciprocal')
            row['member_group_ids'] = [groups[child]['group_id'] for child in children]
            continue
        parent = ptr(group + 0x1b8)
        if parent and (parent not in groups or groups[parent]['kind'] != 'army_group' or group not in vector(parent + 0x230)):
            raise GuiSnapshotChanged('Orders group parent membership is not reciprocal')
        row['army_group_id'] = groups[parent]['group_id'] if parent else None
        row['unit_ids'] = []
        for interface in vector(group + 0x50):
            if interface not in units_by_interface:
                raise RuntimeError('Group member is not an owned listed unit interface')
            unit, actual_parent, unit_row = units_by_interface[interface]
            if actual_parent != group or unit in assigned_members:
                raise GuiSnapshotChanged('Unit/group membership is not reciprocal')
            assigned_members[unit] = group
            row['unit_ids'].append(unit_row['unit_id'])
    for unit, parent, row in units_by_interface.values():
        if parent and assigned_members.get(unit) != parent:
            raise GuiSnapshotChanged('Assigned unit missing from its native group members')
    if any(reader.read(address, len(data)) != data for address, data in guards):
        raise GuiSnapshotChanged('Native unit/group membership changed during read')
    result['units'] = unit_rows
    result['native_unit_group_binding_verified'] = True
    return result
