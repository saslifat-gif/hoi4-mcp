"""Isolated read-only candidate. Static layouts are pinned; live readback is pending.

This returns observed manager-list membership and the engine's per-ID/target
random execution counters. It does not label a decision eligible, active,
completed, affordable, or paid, and does not provide a complete decision catalog.
"""
import struct
from runtime_gui import GuiSnapshotChanged, decode_std_string

DECISION_SIGNATURES = {
    0x6cf4d0: '488b81a00f0000c3',
    0x6cf890: '488b81900f0000c3',
    0x72ddbe: '48638154010000',
    0x72dde0: '498bad48010000',
    0x72dded: '488b4d08',
    0x737f2d: 'ff44d010',
    0x7232e9: '498d8e20010000',
    0x170612: '48890567e81b03',
    0x725f79: '4c8d7128',
}

def read_country_decision_observations(reader, country, world, *, include_registry=False):
    """Caller supplies an executable-hash-pinned NativeGuiReader and world binding."""
    guards = []
    def read(address, size):
        data = reader.read(address, size)
        if data is None or len(data) != size:
            raise RuntimeError('Native decision memory unreadable')
        guards.append((address, data))
        return data
    def ptr(address):
        return struct.unpack('<Q', read(address, 8))[0]
    def typed(address, rva, name):
        if ptr(address) != reader.base + rva or reader.typename(address) != name:
            raise RuntimeError('Native decision object type mismatch')
    def vector(address, stride):
        data, capacity, count = struct.unpack('<Qii', read(address, 16))
        if not 0 <= count <= capacity <= 100000:
            raise RuntimeError('Native decision vector extent invalid')
        return data, count, read(data, count * stride) if count else b''
    for rva, code in DECISION_SIGNATURES.items():
        expected = bytes.fromhex(code)
        if read(reader.base + rva, len(expected)) != expected:
            raise RuntimeError('Native decision implementation changed')
    if ptr(reader.base + 0x332f260) != world:
        raise GuiSnapshotChanged('Decision world changed')
    if reader.typename(country) != '.?AVCCountry@@':
        raise RuntimeError('Native decision country type mismatch')
    read(country, 12)
    tick = struct.unpack('<i', read(world + 0x468, 4))[0]
    manager = ptr(country + 0xfa0)
    typed(manager, 0x27eb5c0, '.?AVCDecisionStatus@@')
    if ptr(manager + 8) != country:
        raise RuntimeError('Native decision country binding mismatch')
    politics = ptr(country + 0xf90)
    pp = struct.unpack('<q', read(politics + 0xe0, 8))[0]
    _, listed_count, listed_bytes = vector(manager + 0x40, 8)
    listed = list(struct.unpack('<' + 'Q' * listed_count, listed_bytes))
    if len(set(listed)) != listed_count:
        raise RuntimeError('Duplicate native decision list pointer')
    _, counter_count, counter_bytes = vector(manager + 0x148, 24)
    definitions, identities = {}, {}
    def definition(address):
        if address in definitions:
            return definitions[address]
        typed(address, 0x27eb3d0, '.?AVCDecision@@')
        value = decode_std_string(read, address + 0x120, 255)
        if value['status'] != 'read' or not value['raw_text']:
            raise RuntimeError('Native decision identity unreadable or empty')
        key = value['raw_text']
        if key in identities and identities[key] != address:
            raise RuntimeError('Ambiguous native decision identity')
        identities[key] = address
        row = {'decision_id': key,
               'native_id_hash': struct.unpack('<I', read(address + 0x140, 4))[0],
               'listed_in_manager_40': address in listed}
        definitions[address] = row
        return row
    registry_count = None
    if include_registry:
        database = ptr(reader.base + 0x332ee80)
        typed(database, 0x27eb640, '.?AVCDecisionDatabase@@')
        _, registry_count, raw_registry = vector(database + 0x28, 8)
        registry = list(struct.unpack('<' + 'Q' * registry_count, raw_registry))
        if not registry or len(set(registry)) != registry_count:
            raise RuntimeError('Native decision registry null sentinel or pointers invalid')
        typed(registry[0], 0x27ebcf0, '.?AV?$TNullObject@VCDecision@@V1@@@')
        if read(registry[0] + 0x118, 1) != b'\x00':
            raise RuntimeError('Native decision registry null sentinel changed')
        for address in registry[1:]:
            if read(address + 0x118, 1) == b'\x00':
                raise RuntimeError('Native decision registry definition disabled')
            definition(address)
    for address in listed:
        definition(address)
    counters, seen = [], set()
    for index in range(counter_count):
        vtable, address, count, target = struct.unpack_from('<QQiI', counter_bytes, index * 24)
        if vtable != reader.base + 0x27eb570:
            raise RuntimeError('Native decision counter type mismatch')
        if count < 0:
            raise RuntimeError('Negative native decision execution counter')
        row = definition(address)
        key = (row['decision_id'], target)
        if key in seen:
            raise RuntimeError('Duplicate native decision counter key')
        seen.add(key)
        counters.append({'decision_id': key[0], 'native_target_tag': target,
                         'native_execution_counter': count})
    if any(reader.read(address, len(data)) != data for address, data in guards):
        raise GuiSnapshotChanged('Native decision state changed during read')
    return {'decisions': list(definitions.values()), 'execution_counters': counters,
            'native_tick': tick, 'political_power_raw': pp,
            'listed_count': listed_count, 'counter_count': counter_count,
            'scope': 'country_manager_40_and_random_execution_counters',
            'native_registry_included': bool(include_registry),
            'registry_count_including_sentinel': registry_count,
            'complete_catalog_verified': False, 'eligibility_verified': False,
            'cost_verified': False, 'effects_verified': False,
            'counter_persistence_verified': False, 'live_verified': False,
            'process_writes': False, 'uses_keyboard_or_mouse': False}
