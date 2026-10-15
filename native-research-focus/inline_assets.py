"""Pinned read-only named inline sprite and atlas-to-native-texture-record binding.

Does not load files, issue native calls, inspect pixels, or claim GPU rendering.
Requires a verified NativeGuiReader and reads the widget's own current text buffer.
"""
import struct
from runtime_gui import GuiSnapshotChanged,native_markup
from font_binding import read_font_binding

SPRITES={0x2b3dd58:'.?AVCSpriteType@@',0x2b51c60:'.?AVCFrameAnimatedSpriteType@@',0x29e6dc0:'.?AVCMaskedSpriteType@@'}
# Generic inline rendering uses the resolved definition's primary texture index
# directly. It calls only its frame-count virtual, not the derived sprite renderer.
INLINE_GUARDS={
    0x24cc0e0:'488379180f7603488b090fb60133d284c074200f1f4000660f1f8400000000000fbec0488d490103c26bd03d0fb60184c075ed8bc2c3',
    0x2238df0:'4881c100010000e9b43280fe',
    0x22403e0:'8b8190000000c3',
    0x29c820:'b801000000c3',
    0x1640e60+0xa9:'c74424504746585f',
    0x16416b7+0x17:'458b86a0010000',
    0x24071e0+0x29:'4c8d04f64e8d34c500000000488b4108',
}

FLAG_GUARDS={0x71bc80+0x20:'41b9c59d1c81',
    0x71bd10+0x12:'488b41304863d2488d0490',
    0xbb5490+0xae:'488b0d1b9d7702486313488b81400300008b0490',
    0x1641210+0x117:'3b87c4280300',
    0x1641210+0x1a3:'0fb64a11488b87a0280300',
}

def native_token_frame(token):
    """Mirror 1640e60's optional decimal suffix with x86 signed32 wrap semantics."""
    prefix,sep,suffix=token.partition('|')
    frame=0
    if sep:
        value=0
        for ch in suffix:
            if not '0'<=ch<='9':return prefix,0
            value=(value*10+ord(ch)-48)&0xffffffff
        if value&0x80000000:return prefix,0
        frame=(value-1)&0xffffffff
        if frame&0x80000000:frame-=0x100000000
    return prefix,frame

def native_sprite_hash(name):
    """Pinned24cc0e0: signed UTF-8 byte addition, then multiply by61, uint32."""
    value=0
    for byte in name.encode('utf-8'):
        value=((value+(byte if byte<128 else byte-256))*61)&0xffffffff
    return value

def read_inline_assets(reader,widget,*,max_buckets=8192,max_nodes=32768,raw_text=None):
    """Bind ordered current-buffer runs to actual native sprite/texture records."""
    if raw_text is not None and (not isinstance(raw_text,str) or len(raw_text.encode('utf-8'))>65536):raise ValueError('Native result text exceeds supported bound')
    binding=read_font_binding(reader,widget)
    if binding['selected_font']['native_type']!='.?AVCGameBitmapFont@@':
        return {'status':'unsupported_font_inline_implementation','font_binding':binding,'assets':[]}
    if type(max_buckets)!=int or not 1<=max_buckets<=32768:raise ValueError('Invalid sprite bucket bound')
    if type(max_nodes)!=int or not 1<=max_nodes<=131072:raise ValueError('Invalid sprite node bound')
    guards={};strings=[]
    def raw(a,n):
        value=reader.read(a,n)
        if value is None or len(value)!=n:raise RuntimeError('Inline asset memory unavailable')
        if (a,n) in guards and guards[(a,n)]!=value:raise GuiSnapshotChanged('Inline assets changed during read')
        guards[(a,n)]=value;return value
    def ptr(a):
        value=struct.unpack('<Q',raw(a,8))[0]
        if not 0x10000<=value<0x7fffffffffff:raise RuntimeError('Invalid inline asset pointer')
        return value
    def string(a,limit=4096):
        raw(a,32);v=reader._string(a,limit)
        if v.get('status')!='read':raise GuiSnapshotChanged('Inline asset string unavailable or changed')
        strings.append((a,limit,v['raw_text']));return v['raw_text']
    for rva,code in INLINE_GUARDS.items():
        if raw(reader.base+rva,len(bytes.fromhex(code)))!=bytes.fromhex(code):raise RuntimeError('Inline asset implementation changed')
    graphics=int(binding['graphics_manager_id'],16);font=int(binding['selected_font']['object_id'],16)
    if ptr(font+0x3620)!=graphics or ptr(font+0x48)!=graphics:raise RuntimeError('Inline font graphics mismatch')
    buffer=string(widget+0x130,65536);text=buffer if raw_text is None else raw_text;runs=native_markup(text)
    sprite_table=None
    sprite_matches={}
    def sprite(name):
        nonlocal sprite_table
        if name in sprite_matches:return sprite_matches[name]
        if sprite_table is None:
            count,table=struct.unpack('<IQ',raw(graphics+0x104,12))
            if not 1<=count<=max_buckets or not 0x10000<=table<0x7fffffffffff:raise RuntimeError('Sprite table extent unsupported')
            sprite_table=count,table
        count,table=sprite_table
        # Match nativea3c0b0 exactly: one hash bucket, first exact string match.
        # Unrelated buckets and nodes are not part of this lookup's evidence.
        node=struct.unpack('<Q',raw(table+8*(native_sprite_hash(name)%count),8))[0];visited=set()
        while node:
            if not 0x10000<=node<0x7fffffffffff or node in visited or len(visited)>=max_nodes:raise RuntimeError('Invalid/cyclic/oversized sprite lookup chain')
            visited.add(node);obj,node=struct.unpack('<2Q',raw(node,16))
            if not 0x10000<=obj<0x7fffffffffff:raise RuntimeError('Invalid sprite object pointer')
            if string(obj+0x10,512)==name:
                sprite_matches[name]=obj;return obj
        sprite_matches[name]=None;return None
    texture_manager=None
    def texture(index):
        nonlocal texture_manager
        if texture_manager is None:texture_manager=ptr(graphics+0x170)
        array=ptr(texture_manager+8);count=struct.unpack('<i',raw(texture_manager+0x14,4))[0]
        if not 0<=index<count<=1000000:return {'status':'texture_index_out_of_range','native_texture_index':index}
        record=array+index*72;data=raw(record,72);path=string(record+8)
        return {'status':'bound_native_texture_record','native_texture_index':index,
                'native_record_id':hex(record),'texture_reference':path,
                'native_texture_id':hex(struct.unpack_from('<Q',data)[0]),
                'native_load_attempted':bool(data[0x38]),
                'native_texture_nonnull':bool(struct.unpack_from('<Q',data)[0]),
                'file_bytes_verified':False,'gpu_pixels_verified':False}
    def flag(tag):
        # Country-tag strings use native byte-oriented FNV-1a. Non-ASCII markup
        # cannot be treated as a three-byte native tag merely by slicing Python.
        if len(tag)!=3 or not tag.isascii():return {'status':'unsupported_flag_tag_encoding'}
        manager=ptr(reader.base+0x3330d98)
        mask=struct.unpack('<Q',raw(manager+0x78,8))[0]
        if mask>1048575 or mask&(mask+1):raise RuntimeError('Country tag map mask unsupported')
        head=ptr(manager+0x50);buckets=ptr(manager+0x60)
        h=0x811c9dc5
        for byte in tag.encode('ascii'):h=((h^byte)*0x1000193)&0xffffffff
        first,last=struct.unpack('<2Q',raw(buckets+16*(h&mask),16))
        node=last;seen=set();index=-1
        if last!=head:
            while True:
                if not 0x10000<=node<0x7fffffffffff or node in seen or len(seen)>=10000:raise RuntimeError('Invalid country tag bucket chain')
                seen.add(node)
                if string(node+0x10,512)==tag:
                    index=struct.unpack('<i',raw(node+0x30,4))[0];break
                if node==first:break
                node=ptr(node+8)
        tags=ptr(manager+0x30);tag_count=struct.unpack('<i',raw(manager+0x3c,4))[0]
        if not 1<=tag_count<=1000000:raise RuntimeError('Country tag vector extent unsupported')
        selected=index if 0<=index<tag_count else 0
        native_tag=struct.unpack('<i',raw(tags+4*selected,4))[0]
        world_raw=raw(reader.base+0x332f260,8);world=struct.unpack('<Q',world_raw)[0]
        native_index=0
        if native_tag:
            if native_tag<0:raise RuntimeError('Invalid native country tag')
            if world:
                if not 0x10000<=world<0x7fffffffffff:raise RuntimeError('Invalid flag world pointer')
                native_index=struct.unpack('<i',raw(ptr(world+0x340)+4*native_tag,4))[0]
            else:native_index=native_tag
        records=ptr(graphics+0x328b8);count=struct.unpack('<i',raw(graphics+0x328c4,4))[0]
        if not 1<=count<=1000000 or native_index<0:return {'status':'flag_record_extent_unavailable','native_country_tag':native_tag}
        record_index=native_index if native_index<count else 0
        record=raw(records+24*record_index,24)
        item={'status':'verified_native_flag_atlas_identity','country_tag_lookup':'exact_name' if 0<=index<tag_count else 'native_first_tag_fallback',
              'native_country_tag':native_tag,'native_flag_index':native_index,'record_index':record_index,
              'native_uv_rectangle':list(struct.unpack_from('<4f',record)),
              'file_reference_verified':False,'gpu_pixels_verified':False}
        if not record[0x10]:item['status']='native_flag_record_disabled';return item
        atlas_index=record[0x11];atlas=ptr(graphics+0x328a0)
        texture_id=struct.unpack('<Q',raw(atlas+8*atlas_index,8))[0]
        item.update(native_atlas_index=atlas_index,native_texture_id=hex(texture_id),native_texture_nonnull=bool(texture_id))
        return item
    assets=[]
    for i,run in enumerate(runs):
        kind=run['kind']
        if kind=='icon':
            prefix,frame=native_token_frame(run['name']);key='GFX_'+prefix
            obj=sprite(key)
            if obj is None:key=prefix;obj=sprite(key)
            item={'run_index':i,'kind':'icon','token':run['name'],'native_frame':frame}
            if obj is None:item.update(status='native_sprite_not_found',lookup_candidates=['GFX_'+prefix,prefix])
            else:
                vt=ptr(obj)-reader.base
                item.update(definition_id=hex(obj),resolved_name=key)
                if vt not in SPRITES:item.update(status='unsupported_inline_sprite_type',vtable_rva=hex(vt))
                else:
                    frame_getter=0x29c820 if vt==0x29e6dc0 else 0x22403e0
                    if ptr(reader.base+vt+0x78)!=reader.base+frame_getter:raise RuntimeError('Inline sprite frame implementation mismatch')
                    frames=1 if vt==0x29e6dc0 else struct.unpack('<i',raw(obj+0x90,4))[0]
                    index=struct.unpack('<i',raw(obj+0x1a0,4))[0]
                    bound_texture=texture(index)
                    item.update(status='verified_native_inline_texture_binding' if bound_texture['status']=='bound_native_texture_record' else 'definition_resolved_texture_unavailable',native_type=SPRITES[vt],
                                frame_count=frames,frame_in_range=0<=frame<frames,inline_renderer_uses_primary_texture_only=True,
                                definition_texture_reference=string(obj+0x70),texture=bound_texture)
            assets.append(item)
        elif kind=='atlas_icon':
            index=run['atlas_index'];item={'run_index':i,'kind':kind,'atlas_index':index,'native_frame':run['frame']}
            initialized=raw(font+0x3630,1)[0];atlas_raw=raw(font+0x3628,8);atlas=struct.unpack('<Q',atlas_raw)[0]
            if not initialized or not atlas:item.update(status='atlas_not_initialized')
            elif index not in (0,3):item.update(status='unsupported_atlas_index')
            elif not 0x10000<=atlas<0x7fffffffffff:raise RuntimeError('Invalid font atlas pointer')
            else:
                entry=raw(atlas+24*index,24);texture_index,frames,width,height,display_w,display_h=struct.unpack('<iiffii',entry)
                bound_texture=texture(texture_index)
                item.update(status='verified_native_atlas_texture_binding' if bound_texture['status']=='bound_native_texture_record' else 'atlas_resolved_texture_unavailable',frame_count=frames,
                            frame_in_range=0<=run['frame']<frames,
                            native_uv_extent=[width,height],native_display_size=[display_w,display_h],texture=bound_texture)
            assets.append(item)
        elif kind=='flag':
            for rva,code in FLAG_GUARDS.items():
                if raw(reader.base+rva,len(bytes.fromhex(code)))!=bytes.fromhex(code):raise RuntimeError('Flag binding implementation changed')
            assets.append({'run_index':i,'kind':'flag','tag':run['tag'],**flag(run['tag'])})
    for a,limit,value in strings:
        v=reader._string(a,limit)
        if v.get('status')!='read' or v.get('raw_text')!=value:raise GuiSnapshotChanged('Inline asset payload changed during read')
    if any(reader.read(a,n)!=v for (a,n),v in guards.items()):raise GuiSnapshotChanged('Inline assets changed during read')
    if read_font_binding(reader,widget)!=binding:raise GuiSnapshotChanged('Font selection changed during inline asset read')
    return {'status':'verified_native_inline_asset_snapshot','font_binding':binding,'raw_text':text,'assets':assets,'text_source':'current_widget_buffer' if raw_text is None else 'provided_native_result',
            'process_writes':False,'native_invocation':False,'atomic_game_frame':False,
            'render_cache_freshness_verified':False,'physical_display_verified':False,
            'complete_inline_control_coverage':False}
