"""Pinned, isolated read-only candidate; no engine calls and no eligibility claim.

Caller must pin executable hash and country resolution. Native serializer proves required_cic/lended_cic field names; delivery remains
an uninterpreted fixed-point value, not claimed resource units.
"""
import struct


def read_trade_bindings(reader, importer, exporter):
    guards = []
    def read(p, n):
        if not p or n < 0:
            raise RuntimeError('Invalid trade memory address')
        b = reader.read(p, n)
        if b is None or len(b) != n:
            raise RuntimeError('Unreadable trade memory')
        guards.append((p, b))
        return b
    def unpack(fmt, p):
        return struct.unpack(fmt, read(p, struct.calcsize(fmt)))
    def ptr(p):
        return unpack('<Q', p)[0]
    def u32(p):
        return unpack('<I', p)[0]
    def typed(p, rva):
        if ptr(p) != reader.base + rva:
            raise RuntimeError('Trade native type mismatch')
    def vector(p, stride, limit=65536):
        data, cap, count = unpack('<Qii', p)
        if not 0 <= count <= cap <= limit:
            raise RuntimeError('Trade vector extent mismatch')
        return read(data, count * stride) if count else b''
    def pointers(p):
        raw = vector(p, 8)
        values = list(struct.unpack('<' + 'Q' * (len(raw)//8), raw))
        if len(set(values)) != len(values):
            raise RuntimeError('Duplicate trade vector pointer')
        return values
    actors = []
    for country in (importer, exporter):
        if reader.typename(country) != '.?AVCCountry@@':
            raise RuntimeError('Trade country type mismatch')
        tag = u32(country + 8)
        manager = ptr(country + 0x11f8)
        typed(manager, 0x295c4b0)
        if u32(manager + 0x20) != tag:
            raise RuntimeError('Trade country owner mismatch')
        actors.append((tag, manager))
    (importer_tag, im), (exporter_tag, em) = actors
    if importer_tag == exporter_tag:
        raise RuntimeError('Trade actor and partner must differ')
    # Native24bc260's already-initialized token cache, 32-byte CString slots.
    # Do not scan the much larger dynamic registry or invoke its lazy initializer.
    if read(reader.base+0x35e1ab0,1)!=b'\1':
        raise RuntimeError('Native token name cache is not initialized')
    max_token=u32(reader.base+0x35e1ab4)
    names_table=ptr(reader.base+0x35e1ae0)
    if max_token>1000000 or not names_table:
        raise RuntimeError('Native token cache extent invalid')
    def token_name(token):
        if token>max_token:return None
        address=names_table+32*token
        header=read(address,32);length,capacity=struct.unpack_from('<QQ',header,16)
        if not 1<=length<=512 or length>capacity or capacity>65536:
            raise RuntimeError('Native token string extent invalid')
        data=ptr(address) if capacity>15 else address
        raw=read(data,length+1)
        if raw[-1:]!=b'\0' or b'\0' in raw[:-1]:
            raise RuntimeError('Native token string terminator invalid')
        return raw[:-1].decode('utf-8',errors='strict')
    db = ptr(reader.base + 0x332f088)
    typed(db, 0x2943b18)
    defs = pointers(db + 0x28)
    if not defs:
        raise RuntimeError('Resource registry sentinel missing')
    typed(defs[0], 0x2943b48)
    if read(defs[0] + 0x10, 1) != b'\0':
        raise RuntimeError('Resource null sentinel mismatch')
    names, resources = set(), {}
    for p in defs[1:]:
        typed(p, 0x2951508)
        if read(p + 0x10, 1) != b'\1':
            raise RuntimeError('Resource validity mismatch')
        token = u32(p + 8)
        name = token_name(token)
        index = u32(p + 0xd8)
        if not name or name in names or index != defs.index(p):
            raise RuntimeError('Resource identity or registry index mismatch')
        names.add(name)
        resources[p] = {'resource_id': name, 'native_token': token,
                        'native_index': index, 'native_base_rate_raw': unpack('<q', p + 0xe0)[0]}
    imports = pointers(im + 0x740)
    export_vectors = ptr(em + 0x728)
    records, seen = [], set()
    for record in imports:
        typed(record, 0x295c410)
        owner = ptr(record + 0x80)
        if owner != em:
            continue
        if u32(record + 0x88) != importer_tag:
            raise RuntimeError('Trade importer binding mismatch')
        resource = ptr(record + 0x90)
        if resource not in resources:
            raise RuntimeError('Trade resource binding mismatch')
        binding = resources[resource]
        if resource in seen:
            raise RuntimeError('Duplicate actor-partner-resource record')
        seen.add(resource)
        if record not in pointers(export_vectors + binding['native_index'] * 24):
            raise RuntimeError('Trade exporter cross-membership mismatch')
        records.append(dict(binding, importer_native_tag=importer_tag,
                            exporter_native_tag=exporter_tag,
                            required_civilian_factories=unpack('<i', record + 0xe0)[0],
                            lended_civilian_factories=unpack('<i', record + 0xe4)[0],
                            serialized_delivered_raw=unpack('<q', record + 0x98)[0],
                            native_created_date=u32(record + 0xc0)))
    if any(reader.read(p, len(b)) != b for p, b in guards):
        raise RuntimeError('Trade snapshot changed')
    return {'resources': list(resources.values()), 'records': records,
            'boundary': 'Canonical identity and native record ownership only; no affordability, delivery, or execution guarantee'}
