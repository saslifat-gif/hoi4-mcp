"""Research-only read-only binding for the pinned CTextBox/CTextSprite font path.

Call with an already build-verified NativeGuiReader. Scanning the native table
avoids invoking the game or reproducing an unknown hash function. Duplicate names
are rejected rather than choosing a name match that native hashing might not use.
"""
import struct
from runtime_gui import GuiSnapshotChanged

FONT_VTABLES={0x2b41888:'.?AVCBitmapFont@@',0x29e6be8:'.?AVCGameBitmapFont@@'}
# Exact instructions spanning the evidence-bearing stores/calls, not arbitrary
# method prefixes. These constants are independently checked against the PE.
CODE_GUARDS={
    0x22a34ff:'48890748899f80000000',
    0x22a38ad:'e86e51f9ff48898790010000',
    0x22d6e03:'e8181cf6ff4889454f',
    0x237e45d:'0f1143104889432048c743280f000000',
}


def read_font_binding(reader,widget,*,max_buckets=4096,max_nodes=8192):
    """Return engine font identity; never claim GPU assets or displayed freshness."""
    if type(max_buckets)!=int or not 1<=max_buckets<=16384:raise ValueError('Invalid bucket bound')
    if type(max_nodes)!=int or not 1<=max_nodes<=32768:raise ValueError('Invalid node bound')
    reader._guard_root()
    guards={};strings=[]
    def raw(address,size):
        value=reader.read(address,size)
        if value is None or len(value)!=size:raise RuntimeError('Font binding memory unavailable')
        old=guards.get((address,size))
        if old is not None and old!=value:raise GuiSnapshotChanged('Font binding changed during read')
        guards[(address,size)]=value
        return value
    def ptr(address):
        value=struct.unpack('<Q',raw(address,8))[0]
        if not 0x10000<=value<0x7fffffffffff:raise RuntimeError('Invalid font binding pointer')
        return value
    def name(address):
        raw(address,32)
        value=reader._string(address,512)
        if value.get('status')!='read':raise GuiSnapshotChanged('Font binding name unavailable or changed')
        strings.append((address,value['raw_text']))
        return value['raw_text']
    def vt(address,expected):
        value=ptr(address)
        if value-reader.base!=expected:raise RuntimeError(f'Unsupported font binding type at {hex(address)}: expected RVA {hex(expected)}, got {hex(value-reader.base)}')
    for rva,code in CODE_GUARDS.items():
        if raw(reader.base+rva,len(bytes.fromhex(code)))!=bytes.fromhex(code):
            raise RuntimeError('Font binding implementation changed')
    vt(widget,0x2b421d8)
    if ptr(widget+104)!=reader.root:raise RuntimeError('Font widget GUI ownership mismatch')
    graphics=ptr(widget+0x80);sprite=ptr(widget+0x88);cached_font=ptr(widget+0x190)
    graphics_vt=ptr(graphics)-reader.base
    if graphics_vt not in (0x2b3d5f8,0x294a338):
        raise RuntimeError(f'Unsupported graphics type RVA {hex(graphics_vt)}')
    vt(sprite,0x2b47f60)
    if ptr(sprite+0x228)!=graphics:raise RuntimeError('Text drawable graphics ownership mismatch')
    if ptr(reader.base+0x2b47f60+0x188)!=reader.base+0x22d69d0:
        raise RuntimeError('Text drawable font initialization unsupported')
    widget_name=name(widget+0xb8);requested=name(sprite+0x208)
    metadata=raw(graphics+0xd4,12);count,table=struct.unpack('<IQ',metadata)
    if not 1<=count<=max_buckets:raise RuntimeError('Font table extent unsupported')
    if not 0x10000<=table<0x7fffffffffff:raise RuntimeError('Invalid font table pointer')
    buckets=struct.unpack('<'+'Q'*count,raw(table,count*8))
    visited=set();fonts=[];first=None;matches=[]
    for bucket in buckets:
        node=bucket
        while node:
            if not 0x10000<=node<0x7fffffffffff or node in visited or len(visited)>=max_nodes:
                raise RuntimeError('Invalid, cyclic, or oversized font table')
            visited.add(node)
            obj,node=struct.unpack('<2Q',raw(node,16))
            font_vt=ptr(obj)-reader.base
            if font_vt not in FONT_VTABLES:raise RuntimeError('Unsupported loaded font type')
            if ptr(obj+0x48)!=graphics:raise RuntimeError('Font graphics ownership mismatch')
            font_name=name(obj+0x10)
            record={'object_id':hex(obj),'native_type':FONT_VTABLES[font_vt],'name':font_name}
            if first is None:first=record
            fonts.append(record)
            if font_name==requested:matches.append(record)
    if len(matches)>1:raise RuntimeError('Ambiguous loaded font name')
    selected=matches[0] if matches else first
    if selected is None:raise RuntimeError('No loaded font available')
    # Names are read again including heap payloads, alongside all sampled headers,
    # pointers and bucket/node metadata. This still is not an atomic game frame.
    for address,text in strings:
        value=reader._string(address,512)
        if value.get('status')!='read' or value.get('raw_text')!=text:
            raise GuiSnapshotChanged('Font binding name changed during read')
    if any(reader.read(address,size)!=value for (address,size),value in guards.items()):
        raise GuiSnapshotChanged('Font binding changed during read')
    reader._guard_root()
    return {'status':'verified_engine_font_selection','widget_id':hex(widget),
            'text_drawable_id':hex(sprite),'graphics_manager_id':hex(graphics),
            'widget_requested_font':widget_name,'drawable_requested_font':requested,
            'requested_names_match':widget_name==requested,'selected_font':selected,
            'lookup_outcome':'exact_name' if matches else 'native_first_font_fallback',
            'widget_cached_font_id':hex(cached_font),
            'widget_cached_font_matches_selected':hex(cached_font)==selected['object_id'],
            'lookup_implementation':'bounded_native_table_scan_exact_name_then_first_bucket_fallback',
            'font_count':len(fonts),'table_bucket_count':count,
            'process_writes':False,'native_invocation':False,'atomic_game_frame':False,
            'font_texture_identity_verified':False,'render_cache_freshness_verified':False,
            'physical_display_verified':False}
