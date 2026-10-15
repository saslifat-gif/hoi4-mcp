"""Pinned read-only deployment inventory. Dynamic engine eligibility is not simulated."""
import struct
from native_handle import HANDLE_SIGNATURES, resolve_native_handle
from runtime_gui import GuiSnapshotChanged


def read_country_deployment(reader, country, world):
    r = reader
    guards = []

    def read(address, size):
        data = r.read(address, size)
        if data is None or len(data) != size:
            raise RuntimeError('Deployment field unreadable')
        guards.append((address, data))
        return data

    def scalar(fmt, address):
        return struct.unpack(fmt, read(address, struct.calcsize(fmt)))[0]

    def ptr(address):
        return scalar('<Q', address)

    def typed(address, vt, name):
        if not address or ptr(address) != r.base + vt or r.typename(address) != name:
            raise RuntimeError('Deployment object type mismatch')

    def vector(address, width=8):
        data, capacity, count = struct.unpack('<QII', read(address, 16))
        if not 0 <= count <= capacity <= 100000:
            raise RuntimeError('Deployment vector extent invalid')
        return read(data, width * count) if count else b''

    def pointers(address):
        raw = vector(address)
        values = struct.unpack('<' + 'Q' * (len(raw) // 8), raw)
        if any(not x for x in values) or len(set(values)) != len(values):
            raise RuntimeError('Null or duplicate deployment member')
        return values

    def identity(address):
        first, second = struct.unpack('<II', read(address + 8, 8))
        if not first or not second or resolve_native_handle(r.base, read, first, second) != address:
            raise GuiSnapshotChanged('Deployment ID binding changed')
        return f'{first}:{second}'

    for address, code in HANDLE_SIGNATURES.items():
        expected = bytes.fromhex(code)
        if read(r.base + address, len(expected)) != expected:
            raise RuntimeError('Native handle implementation changed')
    typed(country, 0x27e7360, '.?AVCCountry@@')
    if ptr(r.base + 0x332f260) != world:
        raise GuiSnapshotChanged('Deployment world changed')
    tick = scalar('<i', world + 0x468)
    tag = scalar('<I', country + 8)
    if not tag:
        raise RuntimeError('Deployment country tag invalid')
    manager = ptr(country + 0xf70)
    typed(manager, 0x295fc38, '.?AVCDeploymentStatus@@')
    rows, seen_lines, seen_entries = [], set(), set()
    for conveyor in pointers(manager + 0x48):
        typed(conveyor, 0x295e100, '.?AVCMilitaryDeploymentConveyor@@')
        template = ptr(conveyor + 0x20)
        # ce7400 -> template+18 -> b97140(+1d4), irrespective of template display name.
        typed(template, 0x294f5b0, '.?AVCReferencedDivisionTemplate@@')
        if scalar('<I', template + 0x1ec) != tag:
            raise RuntimeError('Deployment conveyor belongs to another country')
        template_id = identity(template)
        row = {'conveyor_id': identity(conveyor), 'template_id': template_id,
               'province_id': scalar('<i', conveyor + 0x4c), 'lines': []}
        for line in pointers(conveyor + 0x78):
            typed(line, 0x295e0a8, '.?AVCMilitaryDeploymentLine@@')
            if line in seen_lines or ptr(line + 0x38) != conveyor:
                raise RuntimeError('Deployment line ownership inconsistent')
            seen_lines.add(line)
            item = {'line_id': identity(line), 'completed_count': scalar('<i', line + 0x28),
                    'current_entry': None, 'native_deploy_eligible': None}
            entry = ptr(line + 0x30)
            if entry:
                typed(entry, 0x295e020, '.?AVCMilitaryDeployment@@')
                if ptr(entry + 0xb8) != line or entry in seen_entries:
                    raise RuntimeError('Deployment current-entry ownership inconsistent')
                seen_entries.add(entry)
                # Containers have a vptr first, followed by data/capacity/count at +8.
                equipment = vector(entry + 0x28, 24)
                amounts = [struct.unpack_from('<q', equipment, i + 16)[0]
                           for i in range(0, len(equipment), 24)]
                manpower = vector(entry + 0x78)
                men = sum(struct.unpack_from('<i', manpower, i + 4)[0]
                          for i in range(0, len(manpower), 8))
                men = (men + 2**31) % 2**32 - 2**31  # Native c69830 int32 arithmetic.
                item['current_entry'] = {
                    'equipment_quantities_raw': amounts, 'equipment_nonempty': any(amounts),
                    'manpower': men, 'manpower_positive': men > 0,
                    'training_raw': scalar('<q', entry + 0x60),
                    'capacity_status_raw': scalar('<B', entry + 0xc0),
                    'capacity_status_active': bool(scalar('<B', entry + 0xc4)),
                    'training_threshold': None, 'location_eligible': None}
            row['lines'].append(item)
        rows.append(row)
    if any(r.read(address, len(data)) != data for address, data in guards):
        raise GuiSnapshotChanged('Deployment inventory changed during read')
    return {'country_tag_native': tag, 'native_tick': tick, 'conveyors': rows,
            'country_to_manager_binding_verified': True,
            'command_eligibility_verified': False, 'process_writes': False,
            'uses_keyboard_or_mouse': False, 'atomic_game_frame': False}


def read_country_division_templates(reader, country, world):
    """CCountry's owned CReferencedDivisionTemplate inventory; raw native names."""
    r, guards = reader, []
    def read(address, size):
        value = r.read(address, size)
        if value is None or len(value) != size:
            raise RuntimeError('Division template field unreadable')
        guards.append((address, value))
        return value
    def scalar(fmt, address):
        return struct.unpack(fmt, read(address, struct.calcsize(fmt)))[0]
    def ptr(address):
        return scalar('<Q', address)
    def string(address):
        raw = read(address, 32)
        length, capacity = struct.unpack_from('<QQ', raw, 16)
        if not 0 <= length <= capacity <= 65536:
            raise RuntimeError('Division template name extent invalid')
        payload = read(struct.unpack_from('<Q', raw)[0], length) if capacity > 15 else raw[:length]
        return payload.decode('utf-8', errors='replace')
    for address, code in HANDLE_SIGNATURES.items():
        expected = bytes.fromhex(code)
        if read(r.base + address, len(expected)) != expected:
            raise RuntimeError('Native handle implementation changed')
    if ptr(country) != r.base + 0x27e7360 or r.typename(country) != '.?AVCCountry@@':
        raise RuntimeError('Division template country type mismatch')
    if ptr(r.base + 0x332f260) != world:
        raise GuiSnapshotChanged('Division template world changed')
    tag = scalar('<I', country + 8)
    tick = scalar('<i', world + 0x468)
    data, capacity, count = struct.unpack('<QII', read(country + 0x1b8, 16))
    if not tag or not 0 <= count <= capacity <= 100000:
        raise RuntimeError('Division template list extent invalid')
    members = struct.unpack('<' + 'Q' * count, read(data, count * 8)) if count else ()
    if any(not p for p in members) or len(set(members)) != count:
        raise RuntimeError('Null or duplicate division template')
    rows = []
    for item in members:
        if ptr(item) != r.base + 0x294f5b0 or r.typename(item) != '.?AVCReferencedDivisionTemplate@@':
            raise RuntimeError('Division template type mismatch')
        first, second = struct.unpack('<II', read(item + 8, 8))
        if not first or not second or resolve_native_handle(r.base, read, first, second) != item:
            raise GuiSnapshotChanged('Division template ID binding changed')
        if scalar('<I', item + 0x1ec) != tag:
            raise RuntimeError('Division template belongs to another country')
        rows.append({'template_id': f'{first}:{second}', 'explicit_name_raw': string(item + 0x20),
                     'automatic_name_key_raw': string(item + 0x40),
                     'native_create_eligible': None})
    if any(r.read(address, len(value)) != value for address, value in guards):
        raise GuiSnapshotChanged('Division template inventory changed during read')
    return {'country_tag_native': tag, 'native_tick': tick, 'templates': rows,
            'country_inventory_verified': True, 'command_eligibility_verified': False,
            'process_writes': False, 'uses_keyboard_or_mouse': False, 'atomic_game_frame': False}
