"""Read-only, build-pinned native GUI data. No desktop capture, input or process writes."""
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import time

class GuiSnapshotChanged(RuntimeError):pass

SUPPORTED_HASH='7dc947be34970da1e1c787bcddbe7f62b610ff258aebf8f06aa8b348f3a031d5'
GUI_ROOT_RVA=0x34531e0
GUI_ROOT_VTABLE_RVA=43296392
REGISTRIES=(('registered',264,276,272),)

CONTAINER_CHILD_VECTORS=(('background',0x10d8,0),('standard_buttons',0x1120,0),
                         ('icons',0x1150,0),('child_vector_0x1180',0x1180,0),
                         ('child_vector_0x11b0',0x11b0,0),('instant_text',0x11e0,0),
                         ('child_vector_0x1210',0x1210,0),('child_vector_0x1240',0x1240,0),
                         ('child_vector_0x1270',0x1270,0),('child_vector_0x12a0',0x12a0,8),
                         ('child_vector_0x12d0',0x12d0,8),('child_vector_0x1300',0x1300,0),
                         ('nested_containers',0x1330,48),('grid_panels',0x1360,0),
                         ('child_vector_0x1390',0x1390,0),('child_vector_0x13c0',0x13c0,0),
                         ('child_vector_0x13f0',0x13f0,0))

ICON_DEFINITION_PARSERS={
    '.?AVCSpriteType@@':(0x2241240,None,80),
    '.?AVCFrameAnimatedSpriteType@@':(0x2357650,'4883ec28458bc84c8bd24181e9c4010000746d4183e90174544183e901743b4183e90174224183f90274094883c428e9bc9beeff',80),
    '.?AVCMaskedSpriteType@@':(0x16422f0,'458bc84c8bd24183e926744c4183e90174344183e933741c4181f97d3000000f852befbf00488d91b0020000498bcae9dce8e700488d91500200004533c0498bcae97ae7e700488d91f80100004533c0498bcae968e7e700488d91180200004533c0498bcae956e7e700',592),
}

CHECKBOX_LABEL_UPDATE_SIGNATURE=bytes.fromhex('48895c24084889742410574883ec50488bf9488d542430488b89b8000000e8bd530a00488bd8488bb798010000488d8f78010000483bc87416488bd0488378180f7603488b104c8b4010e88100e6fd')

PAIRED_NATIVE_ICON=re.compile('\x13([^\\s\\x00-\\x1f]+)\x13')

def plain_native(text):
    text=PAIRED_NATIVE_ICON.sub(lambda m:'[icon:'+m.group(1)+']',text)
    text=re.sub('\x11.', '', text)
    return text

def native_markup(text):
    """Preserve ordered native formatting without inferring gameplay conditions."""
    runs=[];color=None;start=0;i=0
    def emit(end):
        if end>start:runs.append({'kind':'text','text':text[start:end],'color_code':color})
    while i<len(text):
        if text[i]=='\x11':
            emit(i)
            if i+1==len(text):
                runs.append({'kind':'incomplete_control','raw':text[i:]});i=len(text);start=i
                break
            code=text[i+1]
            runs.append({'kind':'color_reset' if code=='!' else 'color','code':code})
            color=None if code=='!' else code;i+=2;start=i
        elif text[i]=='\x13':
            emit(i);match=PAIRED_NATIVE_ICON.match(text,i)
            if match:
                runs.append({'kind':'icon','name':match.group(1),'color_code':color})
                i=match.end();start=i
            elif re.fullmatch('[^\\s\\x00-\\x1f]*',text[i+1:]):
                runs.append({'kind':'incomplete_icon','raw':text[i:]});i=len(text);start=i
            else:
                # Some live engine strings have an unpaired icon marker. Its
                # termination rules are unresolved: preserve it separately and
                # keep parsing following text/colors instead of swallowing them.
                runs.append({'kind':'unknown_control','raw':text[i],
                             'codepoint':'U+0013','meaning_verified':False,
                             'reason':'unpaired_icon_marker','color_code':color})
                i+=1;start=i
        elif ord(text[i])<32 and text[i] not in '\t\r\n':
            emit(i)
            runs.append({'kind':'unknown_control','raw':text[i],
                         'codepoint':f'U+{ord(text[i]):04X}',
                         'meaning_verified':False,'color_code':color})
            i+=1;start=i
        else:i+=1
    emit(len(text))
    return runs

def decode_std_string(read,address,max_length=65536):
    """Validate MSVC x64 string length/capacity before following its data pointer."""
    data=read(address,32)
    if data is None or len(data)!=32:return {'status':'unreadable'}
    length,capacity=struct.unpack_from('<QQ',data,16)
    if capacity<length or capacity>16*1024*1024:return {'status':'invalid_layout'}
    if length>max_length:return {'status':'too_long','length':length}
    if capacity==15 and length<=15:
        raw=data[:length]
    elif capacity>=16:
        pointer=struct.unpack_from('<Q',data)[0]
        if not 0x10000<=pointer<0x7fffffffffff:return {'status':'invalid_pointer'}
        raw=read(pointer,length) if length else b''
    else:return {'status':'invalid_layout'}
    if raw is None or len(raw)!=length:return {'status':'unreadable'}
    if capacity>=16 and length and read(pointer,length)!=raw:return {'status':'changed_during_read'}
    if read(address,32)!=data:return {'status':'changed_during_read'}
    try:text=raw.decode('utf-8',errors='strict')
    except UnicodeDecodeError:return {'status':'invalid_utf8','length':length}
    return {'status':'read','raw_text':text,'text':plain_native(text),'length':length}

def decode_u32_string(read,address,max_length=16384):
    """Decode MSVC UTF-32 strings: three inline codepoints, otherwise heap storage."""
    data=read(address,32)
    if data is None or len(data)!=32:return {'status':'unreadable'}
    length,capacity=struct.unpack_from('<QQ',data,16)
    if capacity<length or capacity>4*1024*1024:return {'status':'invalid_layout'}
    if length>max_length:return {'status':'too_long','length':length}
    if capacity==3 and length<=3:raw=data[:length*4]
    elif capacity>=4:
        pointer=struct.unpack_from('<Q',data)[0]
        if not 0x10000<=pointer<0x7fffffffffff:return {'status':'invalid_pointer'}
        raw=read(pointer,length*4) if length else b''
    else:return {'status':'invalid_layout'}
    if raw is None or len(raw)!=length*4:return {'status':'unreadable'}
    if read(address,32)!=data:return {'status':'changed_during_read'}
    try:text=raw.decode('utf-32-le',errors='strict')
    except UnicodeDecodeError:return {'status':'invalid_utf32','length':length}
    return {'status':'read','raw_text':text,'text':text,'length':length,'encoding':'utf-32-le'}

def registry_header(data,pointer_offset,count_offset,capacity_offset):
    if len(data)<max(pointer_offset+8,count_offset+4,capacity_offset+4):
        raise RuntimeError('GUI registry header incomplete')
    pointer=struct.unpack_from('<Q',data,pointer_offset)[0]
    count=struct.unpack_from('<I',data,count_offset)[0]
    capacity=struct.unpack_from('<I',data,capacity_offset)[0]
    if not 0<=count<=capacity<=500000:
        raise RuntimeError('GUI registry counts invalid')
    if count and not 0x10000<=pointer<0x7fffffffffff:
        raise RuntimeError('GUI registry pointer invalid')
    return pointer,count,capacity

def dynamic_slots_header(data):
    """Build-pinned sparse GUI slots; field 300 is opaque, not vector capacity."""
    if len(data)<304:raise RuntimeError('Dynamic GUI slot header incomplete')
    pointer,slots,opaque=struct.unpack_from('<QII',data,288)
    if not 0<=slots<=500000:raise RuntimeError('Dynamic GUI slot extent invalid')
    if slots and not 0x10000<=pointer<0x7fffffffffff:
        raise RuntimeError('Dynamic GUI slot pointer invalid')
    return pointer,slots,opaque

def registry_tables(data):
    return [(name,*registry_header(data,p,c,cap)) for name,p,c,cap in REGISTRIES]+[
        ('dynamic_slots',*dynamic_slots_header(data))]

def registry_identity(tables):
    # Sparse field 300 changes independently of its pointer/extent. It is opaque
    # bookkeeping, not registry identity; pointer contents are checked separately.
    return [(n,a,c,None if n=='dynamic_slots' else cap) for n,a,c,cap in tables]

class WindowsProcess:
    """Narrow Windows capability: QUERY_INFORMATION + VM_READ only."""
    def __init__(self,expected,expected_executable):
        if os.name!='nt':raise RuntimeError('Native GUI reads require the Windows game host')
        import ctypes as c
        from ctypes import wintypes as w
        self.c,self.w=c,w
        self.expected=expected
        self.expected_executable=Path(expected_executable)
        self.k=c.WinDLL('kernel32',use_last_error=True)
        k=self.k
        k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenProcess.restype=w.HANDLE
        k.CloseHandle.argtypes=[w.HANDLE]
        k.ReadProcessMemory.argtypes=[w.HANDLE,c.c_void_p,c.c_void_p,c.c_size_t,c.POINTER(c.c_size_t)];k.ReadProcessMemory.restype=w.BOOL
        k.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,c.POINTER(w.DWORD)]
        k.GetProcessTimes.argtypes=[w.HANDLE,c.POINTER(w.FILETIME),c.POINTER(w.FILETIME),c.POINTER(w.FILETIME),c.POINTER(w.FILETIME)]
        k.CreateToolhelp32Snapshot.argtypes=[w.DWORD,w.DWORD];k.CreateToolhelp32Snapshot.restype=w.HANDLE
        self.handle=k.OpenProcess(0x0410,False,expected['pid'])
        if not self.handle:raise RuntimeError('Read-only game process open failed')
        try:self.guard();self.base=self._module_base()
        except Exception:self.close();raise

    def guard(self):
        c,w,k=self.c,self.w,self.k
        path=c.create_unicode_buffer(32768);length=w.DWORD(len(path))
        if not k.QueryFullProcessImageNameW(self.handle,0,path,c.byref(length)):
            raise RuntimeError('Game process identity unreadable')
        if Path(path.value)!=self.expected_executable or str(Path(path.value))!=self.expected['executable']:
            raise RuntimeError('Bound game executable changed')
        created,exit_time,kernel,user=(w.FILETIME() for _ in range(4))
        if not k.GetProcessTimes(self.handle,c.byref(created),c.byref(exit_time),c.byref(kernel),c.byref(user)):
            raise RuntimeError('Game process creation time unreadable')
        stamp=created.dwLowDateTime|(created.dwHighDateTime<<32)
        if stamp!=self.expected['created']:raise RuntimeError('Bound game process changed')
        if exit_time.dwLowDateTime or exit_time.dwHighDateTime:raise RuntimeError('Bound game process stopped')

    def _module_base(self):
        c,w,k=self.c,self.w,self.k
        class Module(c.Structure):
            _fields_=[('dwSize',w.DWORD),('th32ModuleID',w.DWORD),('th32ProcessID',w.DWORD),
                      ('GlblcntUsage',w.DWORD),('ProccntUsage',w.DWORD),('modBaseAddr',c.c_void_p),
                      ('modBaseSize',w.DWORD),('hModule',w.HMODULE),('szModule',w.WCHAR*256),('szExePath',w.WCHAR*260)]
        k.Module32FirstW.argtypes=[w.HANDLE,c.POINTER(Module)];k.Module32NextW.argtypes=[w.HANDLE,c.POINTER(Module)]
        snap=k.CreateToolhelp32Snapshot(0x18,self.expected['pid'])
        if snap==c.c_void_p(-1).value:raise RuntimeError('Game module list unavailable')
        try:
            module=Module();module.dwSize=c.sizeof(Module)
            ok=k.Module32FirstW(snap,c.byref(module))
            while ok:
                if Path(module.szExePath)==self.expected_executable:
                    self.image_size=module.modBaseSize
                    return module.modBaseAddr
                ok=k.Module32NextW(snap,c.byref(module))
        finally:k.CloseHandle(snap)
        raise RuntimeError('Game module unavailable')

    def read(self,address,size):
        if not isinstance(address,int) or not 0x10000<=address<0x7fffffffffff or not 0<=size<=4*1024*1024:return None
        if size==0:return b''
        c=self.c;buffer=c.create_string_buffer(size);count=c.c_size_t()
        if not self.k.ReadProcessMemory(self.handle,address,buffer,size,c.byref(count)) or count.value!=size:return None
        return buffer.raw

    def foreground_metadata(self):
        """Read focus identity on the interactive bridge's desktop; no screen/input."""
        c,w=self.c,self.w
        u=c.WinDLL('user32',use_last_error=True)
        u.GetForegroundWindow.restype=w.HWND
        u.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)]
        hwnd=u.GetForegroundWindow()
        if not hwnd:return {'available':False,'pid':None,'is_bound_game':None}
        pid=w.DWORD()
        thread=u.GetWindowThreadProcessId(hwnd,c.byref(pid))
        if not thread or not pid.value:return {'available':False,'pid':None,'is_bound_game':None}
        return {'available':True,'pid':pid.value,'is_bound_game':pid.value==self.expected['pid']}

    def close(self):
        if getattr(self,'handle',None):self.k.CloseHandle(self.handle);self.handle=None

def annotate_traversal_ancestors(records):
    """Expose sampled ancestor flags along returned edges, never screen visibility.

    A selected top-level record can have ancestors outside this traversal. Flags
    are non-atomic observations and no parent show/hide propagation is inferred.
    """
    edges=('container_children','fixed_window_children','grid_children',
           'listbox_children','dropdown_components')
    def visit(record,ancestors):
        states=[a['engine_local_shown'] for a in ancestors]
        record['traversal_ancestor_state']={
            'ancestors':[dict(a) for a in ancestors],
            'has_sampled_hidden_ancestor':False in states,
            'all_sampled_ancestors_shown':bool(states) and all(s is True for s in states),
            'complete_ancestry_verified':False,
            'effective_visibility':None,
            'atomic_game_frame':False}
        state=record.get('engine_show_state',{})
        shown=state.get('engine_local_shown') if state.get('engine_show_state_verified') else None
        chain=(*ancestors,{'widget_id':record['widget_id'],'name':record.get('name'),
                          'engine_local_shown':shown})
        for edge in edges:
            details=record.get(edge,{})
            for collection in ('children','rows'):
                for child in details.get(collection,[]):
                    if 'widget_id' in child:visit(child,chain)
    for record in records:visit(record,())

class NativeGuiReader:
    def __init__(self,process,executable_hash,*,decode_edit_inputs=False):
        if executable_hash!=SUPPORTED_HASH:raise RuntimeError('Unsupported game build; no native offsets applied')
        if type(decode_edit_inputs)!=bool:raise ValueError('decode_edit_inputs must be boolean')
        self.decode_edit_inputs=decode_edit_inputs
        self.process=process;self.read=process.read;self.base=process.base;self.image_size=process.image_size
        self.types={}
        raw=self.read(self.base+GUI_ROOT_RVA,8)
        if raw is None:raise RuntimeError('Native GUI root pointer unavailable')
        self.root=struct.unpack('<Q',raw)[0]
        self._guard_root()

    def _guard_root(self):
        self.process.guard()
        pointer=self.read(self.base+GUI_ROOT_RVA,8)
        if pointer is None or struct.unpack('<Q',pointer)[0]!=self.root:raise RuntimeError('Native GUI root changed')
        raw=self.read(self.root,8)
        if raw is None or struct.unpack('<Q',raw)[0]!=self.base+GUI_ROOT_VTABLE_RVA:
            raise RuntimeError('Native GUI root type validation failed')

    def typename(self,pointer):
        raw=self.read(pointer,8)
        if raw is None:return None
        vt=struct.unpack('<Q',raw)[0]
        if vt in self.types:return self.types[vt]
        result=None
        if self.base<vt<self.base+self.image_size:
            raw=self.read(vt-8,8)
            if raw:
                col=struct.unpack('<Q',raw)[0]
                if self.base<col<self.base+self.image_size:
                    raw=self.read(col,24)
                    if raw:
                        sig,offset,ctor,typed,cls,selfrva=struct.unpack('<IIIIII',raw)
                        if sig==1 and col==self.base+selfrva and typed+16<self.image_size:
                            name=self.read(self.base+typed+16,240)
                            if name:
                                try:result=name.split(b'\0',1)[0].decode('ascii')
                                except UnicodeDecodeError:pass
        self.types[vt]=result
        return result

    def _string(self,address,max_length=65536):
        return decode_std_string(self.read,address,max_length)

    def widget_show_state(self,gui):
        """Local engine state only: parents, clipping and occlusion are unresolved."""
        header=self.read(gui,160)
        if header is None or struct.unpack_from('<Q',header,104)[0]!=self.root:
            raise RuntimeError('Widget shown-state ownership unavailable')
        vt=struct.unpack_from('<Q',header)[0];methods=self.read(vt+120,16)
        pairs={
            (0x22a4440,0x22a4080):((0x22a4440,'40534883ec20f6417510488bd97519b201e89a9c0000'),
                                  (0x22a4080,'40534883ec2033d2488bd9e860a00000')),
            (0x22c4510,0x22be1a0):((0x22c4510,'40574883ec2080797400488bf90f8cbb000000f64175100f85b10000004883c1d0'),
                                   (0x22b94b0+0x94,'b201488d4b30e8a14bffff'),
                                   (0x22b93e0,'40574883ec20488bf948897424384883c13033d2e8f74cffff')),
            (0x232a810,0x2327840):((0x232a810+0x6d,'b201488bcbe86938f8ff'),
                                   (0x2327840+0x1a,'33d2488bcbe88c68f8ff')),
        }
        pair=tuple(value-self.base for value in struct.unpack('<2Q',methods)) if methods else None
        if pair not in pairs:
            if self.read(gui,160)!=header:raise GuiSnapshotChanged('Widget shown-state changed during read')
            return {'status':'unsupported_show_hide_methods','engine_show_state_verified':False,
                    'engine_local_shown':None,'effective_visibility':None}
        checks=(*pairs[pair],(0x22ae0f0,'440fb641750fb6c24180e0f7c0e003440ac044884175'))
        for rva,encoded in checks:
            expected=bytes.fromhex(encoded)
            if self.read(self.base+rva,len(expected))!=expected:
                raise RuntimeError('Widget shown-state implementation changed')
        if self.read(gui,160)!=header or self.read(vt+120,16)!=methods:
            raise GuiSnapshotChanged('Widget shown-state changed during read')
        shown=bool(header[117]&8)
        return {'status':'verified_engine_local_state','engine_show_state_verified':True,
                'engine_local_shown':shown,'state':'engine_shown' if shown else 'engine_hidden',
                'effective_visibility':None,'parent_visibility_verified':False,
                'buffer_last_update_unix':None}

    def icon_frame(self,gui):
        """Read native sprite frame state; frame meaning and visibility remain unknown."""
        header=self.read(gui,160)
        if header is None or self.typename(gui)!='.?AVCIcon@@' or struct.unpack_from('<Q',header,104)[0]!=self.root:
            raise RuntimeError('Icon type/ownership unavailable')
        vt=struct.unpack_from('<Q',header)[0]
        if self.read(vt+78*8,8)!=struct.pack('<Q',self.base+0x22fb5e0):
            raise RuntimeError('Icon sprite implementation unsupported')
        for rva,code in ((0x22fb5e0,'488b89e8000000488b0148ff6060'),
                         (0x22fe4f0,'8b81a0010000c3'),
                         (0x22fe900,'3b91a00100008991a00100007407c681a401000001c3')):
            expected=bytes.fromhex(code)
            if self.read(self.base+rva,len(expected))!=expected:raise RuntimeError('Icon frame implementation changed')
        binding=self.read(gui+232,8)
        if binding is None:raise RuntimeError('Icon sprite binding unavailable')
        sprite=struct.unpack('<Q',binding)[0]
        # These verified RTTI types are live non-frame icon components. Preserve
        # the rest of a popup without interpreting their fields as CSprite.
        component_type=self.typename(sprite) if 0x10000<=sprite<0x7fffffffffff else None
        if component_type in ('.?AVCCorneredTileSprite@@','.?AV?$C2dPieChartTemplate@USPieVertex@@@@','.?AVCProgressbarSprite@@'):
            component_header=self.read(sprite,8)
            if component_header is None:raise RuntimeError('Icon component header unavailable')
            if self.read(gui,160)!=header or self.read(gui+232,8)!=binding or self.read(sprite,8)!=component_header or self.typename(sprite)!=component_type:
                raise GuiSnapshotChanged('Icon component changed during read')
            return {'status':'unsupported_non_frame_component','component_native_type':component_type,
                    'native_frame_value':None,'frame_meaning_verified':False,
                    'asset_identity_verified':False,'effective_visibility':None,
                    'buffer_last_update_unix':None}
        if not 0x10000<=sprite<0x7fffffffffff or self.typename(sprite) not in ('.?AVCSprite@@','.?AVCFrameAnimatedSprite@@','.?AVCShieldObject@@'):
            raise RuntimeError('Icon sprite type unavailable')
        sprite_header=self.read(sprite,8)
        if sprite_header is None:raise RuntimeError('Icon sprite header unavailable')
        svt=struct.unpack('<Q',sprite_header)[0]
        if self.read(svt+19*8,8)!=struct.pack('<Q',self.base+0x22fe900) or self.read(svt+22*8,8)!=struct.pack('<Q',self.base+0x22fe4f0):
            raise RuntimeError('Icon sprite frame methods unsupported')
        assets=self.icon_asset_references(sprite)
        frame=self.read(sprite+416,4)
        if frame is None:raise RuntimeError('Icon frame unavailable')
        if self.read(gui,160)!=header or self.read(gui+232,8)!=binding or self.read(sprite,8)!=sprite_header or self.read(sprite+416,4)!=frame:
            raise GuiSnapshotChanged('Icon frame changed during read')
        return {'status':'verified_sprite_frame','native_frame_value':struct.unpack('<I',frame)[0],
                'component_native_type':self.typename(sprite),
                'frame_meaning_verified':False,'asset_identity_verified':assets['status']=='verified_definition_references' and assets['identifier']['status']=='read' and bool(assets['identifier']['value']),
                'asset_references':assets,'effective_visibility':None,
                'buffer_last_update_unix':None}

    def icon_asset_references(self,sprite):
        """Verified sprite definition fields; no texture loading or gameplay inference."""
        header=self.read(sprite,8);binding=self.read(sprite+16,8)
        if header is None or binding is None:raise RuntimeError('Icon definition binding unavailable')
        definition=struct.unpack('<Q',binding)[0]
        kind=self.typename(definition) if definition else None
        if kind not in ICON_DEFINITION_PARSERS:
            if self.read(sprite,8)!=header or self.read(sprite+16,8)!=binding:
                raise GuiSnapshotChanged('Icon definition changed during read')
            return {'status':'unsupported_definition_type','native_type':kind}
        dh=self.read(definition,8)
        if dh is None:raise RuntimeError('Icon definition header unavailable')
        vt=struct.unpack('<Q',dh)[0]
        parser_rva,derived_code,shader_offset=ICON_DEFINITION_PARSERS[kind]
        if derived_code:
            expected=bytes.fromhex(derived_code)
            if self.read(self.base+parser_rva,len(expected))!=expected:raise RuntimeError('Derived icon definition parser changed')
        if self.read(vt+4*8,8)!=struct.pack('<Q',self.base+parser_rva):
            raise RuntimeError('Icon definition parser unsupported')
        for rva,code in ((0x22fe930+0x27,'4889bb8001000048897b10'),
                         (0x2355fd0+0x164,'488d51104533c0498bca'),
                         (0x2241240+0x208,'488d51704533c0498bc9'),
                         (0x2241240+0x230,'488d51504533c0498bc9')):
            expected=bytes.fromhex(code)
            if self.read(self.base+rva,len(expected))!=expected:
                raise RuntimeError('Icon definition fields implementation changed')
        fields={};guards=[]
        field_offsets=[('identifier',16),('shader_reference',shader_offset),('texture_reference',112)]
        if kind=='.?AVCMaskedSpriteType@@':field_offsets.extend((('texture_file_1_reference',536),('texture_file_2_reference',504)))
        for key,off in field_offsets:
            raw=self.read(definition+off,32)
            value=self._string(definition+off,1024)
            fields[key]={'status':value['status'],'value':value.get('raw_text')}
            if raw is not None:guards.append((definition+off,raw))
        if self.read(sprite,8)!=header or self.read(sprite+16,8)!=binding or self.read(definition,8)!=dh or any(self.read(a,len(raw))!=raw for a,raw in guards):
            raise GuiSnapshotChanged('Icon definition changed during read')
        return {'status':'verified_definition_references','native_type':kind,**fields,
                'texture_loaded_verified':False,'gameplay_meaning_verified':False}

    def dropdown_components(self,gui,expand_depth=0,_ancestors=(),_budget=None):
        """Follow native-verified dropdown button and panel bindings without calls."""
        if type(expand_depth)!=int or not 0<=expand_depth<=8:raise ValueError('expand_depth must be 0..8')
        if gui in _ancestors:raise RuntimeError('Dropdown hierarchy cycle detected')
        if _budget is None:_budget=[2000,time.monotonic()+8]
        header=self.read(gui,160)
        if header is None or self.typename(gui)!='.?AVCDropDownBox@@' or struct.unpack_from('<Q',header,104)[0]!=self.root:
            raise RuntimeError('Dropdown type/ownership unavailable')
        vt=struct.unpack_from('<Q',header)[0]
        if self.read(vt+0x268,16)!=struct.pack('<QQ',self.base+0x2303090,self.base+0x2303030):
            raise RuntimeError('Dropdown components implementation unsupported')
        expected=bytes.fromhex('40534883ec20488bd9488b89000b00004885c97406488b01ff5078488b8b080b00004885c9741480bb180b000000740b488b41304883c130ff5078')
        if self.read(self.base+0x2303090,len(expected))!=expected:raise RuntimeError('Dropdown component layout changed')
        binding=self.read(gui+2816,24)
        if binding is None:raise RuntimeError('Dropdown component bindings unavailable')
        children=[];guards=[]
        for (role,adjust),ptr in zip((('button',0),('option_panel',48),('background_panel',48)),struct.unpack('<3Q',binding)):
            if not ptr:continue
            _budget[0]-=1
            if _budget[0]<0 or time.monotonic()>_budget[1]:raise RuntimeError('Dropdown hierarchy read limit exceeded')
            child=ptr+adjust;data=self.read(child,160);kind=self.typename(child)
            expected_kind='.?AVCButtonStandard@@' if role=='button' else '.?AVCContainerWindow@@'
            if data is None or kind!=expected_kind or struct.unpack_from('<Q',data,104)[0]!=self.root:
                raise RuntimeError('Dropdown child type/ownership unavailable')
            definition=struct.unpack_from('<Q',data,96)[0];name=self._string(definition+40,512);source=self._string(definition+72,1024)
            if name['status']!='read' or source['status']!='read':raise RuntimeError('Dropdown child definition unavailable')
            item={'widget_id':hex(child),'role':role,'native_type':kind,'name':name['text'],'source':source['text'],'effective_visibility':None}
            item['engine_show_state']=self.widget_show_state(child)
            if role=='button':
                # This is the verified standard-button component, not an edit input.
                caption_header=self.read(child+392,32)
                text=self._string(child+392)
                item.update({'text_status':text['status'],'text':text.get('text'),
                             'raw_text':text.get('raw_text'),'text_length':text.get('length'),
                             'formatted_runs':native_markup(text['raw_text']) if text['status']=='read' else None,
                             'buffer_last_update_unix':None,'selection_state_verified':False})
                if caption_header is not None:guards.append((child+392,caption_header))
            else:
                item['descendants_expanded']=expand_depth>0
                if expand_depth:item['container_children']=self.container_children(child,expand_depth-1,(*_ancestors,gui),_budget)
            children.append(item);guards.append((child,data))
        if self.read(gui,160)!=header or self.read(gui+2816,24)!=binding or any(self.read(a,len(raw))!=raw for a,raw in guards):
            raise GuiSnapshotChanged('Dropdown bindings changed during read')
        return {'status':'verified_component_bindings','children':children,'expand_depth':expand_depth,
                'complete_child_coverage':False,'effective_visibility':None}

    def checkbox_selection(self,gui):
        """Expose the native CCheckBox local-state == 1 predicate; no gameplay inference."""
        header=self.read(gui,160)
        if header is None or self.typename(gui)!='.?AVCCheckBox@@' or struct.unpack_from('<Q',header,104)[0]!=self.root:
            raise RuntimeError('Checkbox selection type/ownership unavailable')
        if struct.unpack_from('<Q',header)[0]!=self.base+0x2b465d8:
            raise RuntimeError('Checkbox selection layout unsupported')
        code=bytes.fromhex('83b9b0000000010f94c0c3')
        if self.read(self.base+0x22c96a0,len(code))!=code:
            raise RuntimeError('Checkbox selection predicate changed')
        value=self.read(gui+176,4)
        if value is None:raise RuntimeError('Checkbox selection state unavailable')
        raw_state=struct.unpack('<I',value)[0]
        if self.read(gui,160)!=header or self.read(gui+176,4)!=value:
            raise GuiSnapshotChanged('Checkbox selection changed during read')
        return {'status':'verified_native_local_selection_predicate','raw_local_state':raw_state,
                'engine_selected':raw_state==1,'selection_predicate':'local_state_equals_1',
                'gameplay_value_verified':False,'effective_visibility':None}

    def checkbox_text(self,gui):
        """CCheckBox's label update assigns the MSVC string at +0x178."""
        header=self.read(gui,160)
        if header is None or self.typename(gui)!='.?AVCCheckBox@@' or struct.unpack_from('<Q',header,104)[0]!=self.root:
            raise RuntimeError('Checkbox type/ownership unavailable')
        vt=struct.unpack_from('<Q',header)[0]
        method_address=vt+75*8;method=struct.pack('<Q',self.base+0x22c9bd0)
        if vt!=self.base+0x2b465d8 or self.read(method_address,8)!=method:
            raise RuntimeError('Checkbox label implementation unsupported')
        if self.read(self.base+0x22c9bd0,len(CHECKBOX_LABEL_UPDATE_SIGNATURE))!=CHECKBOX_LABEL_UPDATE_SIGNATURE:
            raise RuntimeError('Checkbox label implementation changed')
        result=self._string(gui+376)
        if self.read(gui,160)!=header or self.read(method_address,8)!=method:
            raise GuiSnapshotChanged('Checkbox changed during read')
        return result

    def _snapshot_edit_text(self,gui):
        # Public capture functions use the default false policy for the whole traversal.
        if not self.decode_edit_inputs:return {'status':'editable_input_text_omitted'}
        return self.edit_text(gui)

    def edit_text(self,gui):
        """Read the verified input interface buffer, not font/background asset strings."""
        header=self.read(gui,160)
        if header is None or self.typename(gui)!='.?AVCEditBox@@' or struct.unpack_from('<Q',header,104)[0]!=self.root:
            raise RuntimeError('Edit box type/ownership unavailable')
        vt=struct.unpack_from('<Q',header)[0]
        if self.read(vt+0x268,8)!=struct.pack('<Q',self.base+36651696):
            raise RuntimeError('Edit box layout implementation unsupported')
        for rva,code in ((0x22f30a0,'40534883ec40488bd90f57c00f11442420'),
                         (0x22f2e30+0xe0,'488b4f404c8d4f30'),
                         (0x22f2e30+0xed,'48837f4803'),
                         (0x22f2e30+0x10d,'4883c004')):
            expected=bytes.fromhex(code)
            if self.read(self.base+rva,len(expected))!=expected:raise RuntimeError('Edit input buffer implementation changed')
        result=decode_u32_string(self.read,gui+176)
        if self.read(gui,160)!=header:raise GuiSnapshotChanged('Edit box changed during read')
        return result

    def container_children(self,gui,expand_depth=0,_ancestors=(),_budget=None):
        """Read verified container child vectors; this does not assert visibility."""
        if type(expand_depth)!=int or not 0<=expand_depth<=8:raise ValueError('expand_depth must be 0..8')
        if gui in _ancestors:raise RuntimeError('Container hierarchy cycle detected')
        if _budget is None:_budget=[2000,time.monotonic()+8]
        if time.monotonic()>_budget[1]:raise RuntimeError('Container hierarchy read deadline exceeded')
        _ancestors=(*_ancestors,gui)
        header=self.read(gui,160)
        if header is None or self.typename(gui)!='.?AVCContainerWindow@@':
            raise RuntimeError('Container type unavailable')
        if struct.unpack_from('<Q',header,104)[0]!=self.root:raise RuntimeError('Container ownership unavailable')
        vt=struct.unpack_from('<Q',header)[0]
        if self.read(vt+15*8,16)!=struct.pack('<QQ',self.base+0x22c4510,self.base+0x22be1a0):
            raise RuntimeError('Container show/hide implementation not verified')
        signature=bytes.fromhex('40574883ec2080797400488bf90f8cbb000000f64175100f85b10000004883c1d0')
        if self.read(self.base+0x22c4510,len(signature))!=signature:
            raise RuntimeError('Container layout implementation changed')
        state_signatures=((0x22b94b0+0x94,'b201488d4b30e8a14bffff'),
                          (0x22b93e0,'40574883ec20488bf948897424384883c13033d2e8f74cffff'),
                          (0x22ae0f0,'440fb641750fb6c24180e0f7c0e003440ac044884175'))
        for rva,encoded in state_signatures:
            expected=bytes.fromhex(encoded)
            if self.read(self.base+rva,len(expected))!=expected:
                raise RuntimeError('Container shown-state implementation changed')
        full=gui-48;children=[];guards=[]
        # Vectors confirmed by show routines and real native pointer/name reads.
        for label,off,adjust in CONTAINER_CHILD_VECTORS:
            h=self.read(full+off,16)
            if h is None:raise RuntimeError('Container child vector unavailable')
            array,capacity,count=struct.unpack('<QII',h)
            if count>capacity or capacity>10000:
                raise RuntimeError('Container child vector counts invalid')
            raw=self.read(array,count*8) if count else b''
            if raw is None:raise RuntimeError('Container children unreadable')
            guards.append((full+off,h,array,raw))
            for ptr in struct.unpack('<'+'Q'*count,raw):
                _budget[0]-=1
                if _budget[0]<0:raise RuntimeError('Container hierarchy exceeds node budget; use less expansion')
                if time.monotonic()>_budget[1]:raise RuntimeError('Container hierarchy read deadline exceeded')
                child=ptr+adjust;data=self.read(child,160)
                if data is None or struct.unpack_from('<Q',data,104)[0]!=self.root:
                    raise RuntimeError('Container child ownership unavailable')
                definition=struct.unpack_from('<Q',data,96)[0]
                name=self._string(definition+40,512);source=self._string(definition+72,1024)
                if name['status']!='read' or source['status']!='read':
                    raise RuntimeError('Container child definition unavailable')
                kind=self.typename(child);text={'status':'not_decoded_for_this_widget_type'}
                if kind=='.?AVCInstantTextBox@@':text=self._string(child+272)
                elif kind in ('.?AVCButtonStandard@@','.?AVCCallbackButtonStandard@@'):text=self._string(child+392)
                elif kind=='.?AVCTextBox@@':text=self._string(child+304)
                elif kind=='.?AVCCheckBox@@':text=self.checkbox_text(child)
                elif kind=='.?AVCEditBox@@':text=self._snapshot_edit_text(child)
                children.append({'widget_id':hex(child),'group':label,'name':name['text'],
                                 'source':source['text'],'native_type':kind,'text_status':text['status'],
                                 'text':text.get('text'),'raw_text':text.get('raw_text'),
                                 'formatted_runs':native_markup(text['raw_text']) if text['status']=='read' else None,
                                 'effective_visibility':None})
                children[-1]['engine_show_state']=self.widget_show_state(child)
                if kind=='.?AVCIcon@@':children[-1]['icon_frame']=self.icon_frame(child)
                if kind=='.?AVCCheckBox@@':children[-1]['checkbox_selection']=self.checkbox_selection(child)
                if kind=='.?AVCContainerWindow@@':
                    children[-1]['descendants_expanded']=expand_depth>0
                    if expand_depth:
                        children[-1]['container_children']=self.container_children(child,expand_depth-1,_ancestors,_budget)
                elif kind=='.?AVCFixedWindow@@':
                    children[-1]['descendants_expanded']=expand_depth>0
                    if expand_depth:children[-1]['fixed_window_children']=self.fixed_window_children(child,expand_depth-1,_ancestors,_budget)
                elif kind=='.?AVCStandardGridBox@@':
                    children[-1]['descendants_expanded']=expand_depth>0
                    if expand_depth:
                        children[-1]['grid_children']=self.grid_children(child,expand_depth-1,_ancestors,_budget)
                elif kind in ('.?AVCStandardlistbox@@','.?AVCSmoothListbox@@','.?AVCOverlappingElementsBox@@'):
                    children[-1]['descendants_expanded']=expand_depth>0
                    if expand_depth:
                        children[-1]['listbox_children']=self.listbox_children(child,expand_depth-1,_ancestors,_budget)
                elif kind=='.?AVCDropDownBox@@':
                    children[-1]['descendants_expanded']=expand_depth>0
                    if expand_depth:children[-1]['dropdown_components']=self.dropdown_components(child,expand_depth-1,_ancestors,_budget)
                if self.read(child,160)!=data:raise GuiSnapshotChanged('Container child changed during read')
        for address,h,array,raw in guards:
            if self.read(address,16)!=h or (raw and self.read(array,len(raw))!=raw):
                raise GuiSnapshotChanged('Container children changed during read')
        if self.read(gui,160)!=header:raise GuiSnapshotChanged('Container changed during read')
        return {'status':'verified_child_vectors','children':children,
                'child_vectors_checked':len(CONTAINER_CHILD_VECTORS),'expand_depth':expand_depth,
                'complete_child_coverage':False,'effective_visibility':None,
                'engine_show_state_verified':True,'engine_local_shown':bool(header[117]&8),
                'state':'engine_shown' if header[117]&8 else 'engine_hidden'}

    def grid_children(self,gui,expand_depth=0,_ancestors=(),_budget=None):
        """Follow build-verified row controllers to their container windows."""
        if type(expand_depth)!=int or not 0<=expand_depth<=8:raise ValueError('expand_depth must be 0..8')
        if gui in _ancestors:raise RuntimeError('Grid hierarchy cycle detected')
        if _budget is None:_budget=[2000,time.monotonic()+8]
        header=self.read(gui,160)
        if header is None or self.typename(gui)!='.?AVCStandardGridBox@@' or struct.unpack_from('<Q',header,104)[0]!=self.root:
            raise RuntimeError('Grid type/ownership unavailable')
        vt=struct.unpack_from('<Q',header)[0]
        if self.read(vt+0x268,8)!=struct.pack('<Q',self.base+0x22c6bd0):
            raise RuntimeError('Grid row implementation unsupported')
        loop=bytes.fromhex('488b83a0010000488b0c06488b01ff5010')
        if self.read(self.base+0x22c6bd0+0x30,len(loop))!=loop:
            raise RuntimeError('Grid row vector implementation changed')
        h=self.read(gui+416,16)
        if h is None:raise RuntimeError('Grid row vector unavailable')
        array,capacity,count=struct.unpack('<QII',h)
        if count>capacity or capacity>10000:raise RuntimeError('Grid row counts invalid')
        raw=self.read(array,count*8) if count else b''
        if raw is None:raise RuntimeError('Grid rows unreadable')
        rows=[];binding_code=bytes.fromhex('488b49104885c9740c488b41304883c13048ff6078c3')
        for index,controller in enumerate(struct.unpack('<'+'Q'*count,raw)):
            _budget[0]-=1
            if _budget[0]<0:raise RuntimeError('Grid hierarchy exceeds node budget')
            if time.monotonic()>_budget[1]:raise RuntimeError('Grid hierarchy read deadline exceeded')
            binding=self.read(controller,24);row={'index':index,'controller_type':self.typename(controller)}
            if binding is None:raise RuntimeError('Grid row controller unavailable')
            cvt=struct.unpack_from('<Q',binding)[0]
            if self.read(cvt+16,8)!=struct.pack('<Q',self.base+0x1d641c0) or self.read(self.base+0x1d641c0,len(binding_code))!=binding_code:
                row['status']='unsupported_row_binding';rows.append(row);continue
            full=struct.unpack_from('<Q',binding,16)[0];child=full+48;data=self.read(child,160);kind=self.typename(child)
            if not full or data is None or kind not in ('.?AVCContainerWindow@@','.?AVCFixedWindow@@') or struct.unpack_from('<Q',data,104)[0]!=self.root:
                raise RuntimeError('Grid row container unavailable')
            fixed=kind=='.?AVCFixedWindow@@'
            row.update(status='verified_fixed_window_binding' if fixed else 'verified_container_binding',widget_id=hex(child),descendants_expanded=expand_depth>0)
            if expand_depth:
                if fixed:row['fixed_window_children']=self.fixed_window_children(child,expand_depth-1,(*_ancestors,gui),_budget)
                else:row['container_children']=self.container_children(child,expand_depth-1,(*_ancestors,gui),_budget)
            if self.read(child,160)!=data:raise GuiSnapshotChanged('Grid row window changed during read')
            if self.read(controller,24)!=binding:raise GuiSnapshotChanged('Grid row binding changed during read')
            rows.append(row)
        if self.read(gui+416,16)!=h or (raw and self.read(array,len(raw))!=raw) or self.read(gui,160)!=header:
            raise GuiSnapshotChanged('Grid rows changed during read')
        return {'status':'verified_row_vector','rows':rows,'row_count':count,'expand_depth':expand_depth,
                'complete_child_coverage':False,'effective_visibility':None}

    def listbox_children(self,gui,expand_depth=0,_ancestors=(),_budget=None):
        """Read build-verified standard/smooth/overlapping linked rows without invoking callbacks."""
        if type(expand_depth)!=int or not 0<=expand_depth<=8:raise ValueError('expand_depth must be 0..8')
        if gui in _ancestors:raise RuntimeError('Listbox hierarchy cycle detected')
        if _budget is None:_budget=[2000,time.monotonic()+8]
        header=self.read(gui,160)
        kind=self.typename(gui);smooth=kind=='.?AVCSmoothListbox@@';overlap=kind=='.?AVCOverlappingElementsBox@@'
        if header is None or kind not in ('.?AVCStandardlistbox@@','.?AVCSmoothListbox@@','.?AVCOverlappingElementsBox@@') or struct.unpack_from('<Q',header,104)[0]!=self.root:
            raise RuntimeError('Listbox type/ownership unavailable')
        primary_address=gui+168 if overlap else gui-8
        primary=self.read(primary_address,8)
        if primary is None:raise RuntimeError('Listbox primary vtable unavailable')
        vt=struct.unpack('<Q',primary)[0];implementation_guards=[]
        if overlap:
            getter=self.read(vt+88,8)
            if getter!=struct.pack('<Q',self.base+2238528) or self.read(self.base+2238528,5)!=bytes.fromhex('488d4110c3'):
                raise RuntimeError('Overlapping list header getter unsupported')
            gui_vt=struct.unpack_from('<Q',header)[0]
            show=self.read(gui_vt+0x268,8)
            if show!=struct.pack('<Q',self.base+0x2386e00):raise RuntimeError('Overlapping row implementation unsupported')
            expected=bytes.fromhex('48895c2408574883ec20488bf94881c1a8000000488b01ff5058488b184885db7416488b0b4883c138488b01ff5050488b5b104885db75ea')
            if self.read(self.base+0x2386e00,len(expected))!=expected:raise RuntimeError('Overlapping row implementation changed')
            implementation_guards=[(vt+88,getter),(gui_vt+0x268,show)]
        else:
            row_rva=0x23018c0 if smooth else 0x22ad160
            if self.read(vt+0xc8,8)!=struct.pack('<Q',self.base+row_rva):
                raise RuntimeError('Listbox row implementation unsupported')
            signatures=((0x15e,'488bbe90000000'),(0x203,'498b06498bceff5050'),(0x20c,'488b7f10')) if smooth else ((0x120,'488b9e90000000'),(0x15c,'488b01ff5060'),(0x162,'488b5b10'))
            for off,code in signatures:
                expected=bytes.fromhex(code)
                if self.read(self.base+row_rva+off,len(expected))!=expected:
                    raise RuntimeError('Listbox linked row implementation changed')
        row_header_address=gui+(184 if overlap else 136)
        h=self.read(row_header_address,20)
        if h is None:raise RuntimeError('Listbox row header unavailable')
        head,tail,count=struct.unpack('<QQI',h)
        if count>10000 or bool(head)!=bool(count) or bool(tail)!=bool(count):
            raise RuntimeError('Listbox row counts invalid')
        rows=[];guards=implementation_guards;seen=set();node=head;previous=0
        binding_code=bytes.fromhex('c6410800488b49284885c9740f488b41304883c13048ffa080000000c3' if smooth else '488b49084885c9740f488b41304883c13048ffa080000000c3')
        binding_size=48 if smooth else 16
        while node:
            if node in seen:raise RuntimeError('Listbox linked row cycle detected')
            seen.add(node);_budget[0]-=1
            if _budget[0]<0:raise RuntimeError('Listbox hierarchy exceeds node budget')
            if time.monotonic()>_budget[1]:raise RuntimeError('Listbox hierarchy read deadline exceeded')
            if len(rows)>=count:raise RuntimeError('Listbox linked row count mismatch')
            raw=self.read(node,24)
            if raw is None:raise RuntimeError('Listbox row node unavailable')
            controller,prev,next_node=struct.unpack('<QQQ',raw)
            if prev!=previous:raise RuntimeError('Listbox linked row previous pointer mismatch')
            binding_address=controller+(56 if overlap else 0)
            binding=self.read(binding_address,binding_size)
            if binding is None:raise RuntimeError('Listbox row controller unavailable')
            cvt=struct.unpack_from('<Q',binding)[0]
            full=struct.unpack_from('<Q',binding,40 if smooth else 8)[0]
            cb=self.read(cvt+0x60,8)
            if cb is None:raise RuntimeError('Listbox row callback unavailable')
            callback=struct.unpack('<Q',cb)[0]
            row={'index':len(rows),'controller_type':self.typename(controller)}
            if not self.base<=callback<self.base+self.process.image_size or self.read(callback,len(binding_code))!=binding_code:
                row['status']='unsupported_row_binding'
            else:
                child=full+48;data=self.read(child,160);child_kind=self.typename(child)
                if not full or data is None or child_kind not in ('.?AVCContainerWindow@@','.?AVCFixedWindow@@') or struct.unpack_from('<Q',data,104)[0]!=self.root:
                    raise RuntimeError('Listbox row container unavailable')
                fixed=child_kind=='.?AVCFixedWindow@@'
                row.update(status='verified_fixed_window_binding' if fixed else 'verified_container_binding',widget_id=hex(child),descendants_expanded=expand_depth>0)
                if expand_depth:
                    if fixed:row['fixed_window_children']=self.fixed_window_children(child,expand_depth-1,(*_ancestors,gui),_budget)
                    else:row['container_children']=self.container_children(child,expand_depth-1,(*_ancestors,gui),_budget)
                guards.append((child,data))
            guards.extend(((node,raw),(binding_address,binding),(cvt+0x60,cb)))
            rows.append(row);previous=node;node=next_node
        if len(rows)!=count or previous!=tail:raise RuntimeError('Listbox linked row count/tail mismatch')
        for address,raw in guards:
            if self.read(address,len(raw))!=raw:raise GuiSnapshotChanged('Listbox row binding or node changed during read')
        if self.read(row_header_address,20)!=h or self.read(gui,160)!=header or self.read(primary_address,8)!=primary:
            raise GuiSnapshotChanged('Listbox rows changed during read')
        return {'status':'verified_linked_rows','rows':rows,'row_count':count,'expand_depth':expand_depth,
                'complete_child_coverage':False,'effective_visibility':None}

    def fixed_window_children(self,gui,expand_depth=0,_ancestors=(),_budget=None):
        """Decode build-verified maps, vectors and named containers without native calls."""
        if type(expand_depth)!=int or not 0<=expand_depth<=8:raise ValueError('expand_depth must be 0..8')
        if gui in _ancestors:raise RuntimeError('Fixed window hierarchy cycle detected')
        if _budget is None:_budget=[2000,time.monotonic()+8]
        _ancestors=(*_ancestors,gui)
        header=self.read(gui,160)
        if header is None or self.typename(gui)!='.?AVCFixedWindow@@' or struct.unpack_from('<Q',header,104)[0]!=self.root:
            raise RuntimeError('Fixed window type/ownership unavailable')
        vt=struct.unpack_from('<Q',header)[0]
        if self.read(vt+120,16)!=struct.pack('<QQ',self.base+0x232a810,self.base+0x2327840):
            raise RuntimeError('Fixed window implementation unsupported')
        checks=((0x232a810+0x6d,'b201488bcbe86938f8ff'),
                (0x2327840+0x1a,'33d2488bcbe88c68f8ff'),
                (0x22ae0f0,'440fb641750fb6c24180e0f7c0e003440ac044884175'),
                (36029680+0x46,'488b03488b5c2430488b7424384883c4205fc3'))
        for rva,encoded in checks:
            raw=bytes.fromhex(encoded)
            if self.read(self.base+rva,len(raw))!=raw:raise RuntimeError('Fixed window native implementation changed')
        vector_offsets=(0x1ab0,0x1ae0,0x1bd0,0x1c00,0x1b10,0x1b40,0x1b70,0x1c30)
        # Exact load/index sites from this build's fixed-window child visitor.
        for off,position in zip(vector_offsets,(128,192,256,784,848,912,976,1040)):
            expected=bytes.fromhex('488b87')+struct.pack('<I',off)+bytes.fromhex('488b0cd8')
            if self.read(self.base+0x2325730+position,len(expected))!=expected:
                raise RuntimeError('Fixed window vector visitor changed')
        for position,code in ((376,'488b9fe01d0000486387ec1d0000488d0c804c8d34cb'),
                              (415,'488b4b2048894df0488d4130'),
                              (1094,'488b87e01c0000488bd348')):
            expected=bytes.fromhex(code)
            if self.read(self.base+0x2325730+position,len(expected))!=expected:
                raise RuntimeError('Fixed window child visitor changed')
        full=gui-48;children=[];guards=[];seen_children={}
        def collect(child,group):
            if expand_depth and child in _ancestors:raise RuntimeError('Fixed window hierarchy cycle detected')
            _budget[0]-=1
            if _budget[0]<0 or time.monotonic()>_budget[1]:raise RuntimeError('Fixed window hierarchy read limit exceeded')
            if child in seen_children:
                seen_children[child]['groups'].append(group);return
            h=self.read(child,160)
            if h is None or struct.unpack_from('<Q',h,104)[0]!=self.root:raise RuntimeError('Fixed window child ownership unavailable')
            definition=struct.unpack_from('<Q',h,96)[0];name=self._string(definition+40,512);source=self._string(definition+72,1024)
            if name['status']!='read' or source['status']!='read':raise RuntimeError('Fixed window child definition unavailable')
            kind=self.typename(child);text={'status':'not_decoded_for_this_widget_type'}
            if kind=='.?AVCInstantTextBox@@':text=self._string(child+272)
            elif kind in ('.?AVCButtonStandard@@','.?AVCCallbackButtonStandard@@'):text=self._string(child+392)
            elif kind=='.?AVCTextBox@@':text=self._string(child+304)
            elif kind=='.?AVCCheckBox@@':text=self.checkbox_text(child)
            elif kind=='.?AVCEditBox@@':text=self._snapshot_edit_text(child)
            item={'widget_id':hex(child),'name':name['text'],'source':source['text'],'native_type':kind,'groups':[group],
                  'text_status':text['status'],'text':text.get('text'),'raw_text':text.get('raw_text'),
                  'formatted_runs':native_markup(text['raw_text']) if text['status']=='read' else None,'effective_visibility':None}
            item['engine_show_state']=self.widget_show_state(child)
            if kind=='.?AVCIcon@@':item['icon_frame']=self.icon_frame(child)
            if kind=='.?AVCCheckBox@@':item['checkbox_selection']=self.checkbox_selection(child)
            seen_children[child]=item;children.append(item);guards.append((child,h))
            if kind in ('.?AVCContainerWindow@@','.?AVCFixedWindow@@','.?AVCStandardGridBox@@','.?AVCStandardlistbox@@','.?AVCSmoothListbox@@','.?AVCOverlappingElementsBox@@','.?AVCDropDownBox@@'):
                item['descendants_expanded']=expand_depth>0
                if expand_depth:
                    if kind=='.?AVCContainerWindow@@':item['container_children']=self.container_children(child,expand_depth-1,_ancestors,_budget)
                    elif kind=='.?AVCFixedWindow@@':item['fixed_window_children']=self.fixed_window_children(child,expand_depth-1,_ancestors,_budget)
                    elif kind=='.?AVCStandardGridBox@@':item['grid_children']=self.grid_children(child,expand_depth-1,_ancestors,_budget)
                    elif kind=='.?AVCDropDownBox@@':item['dropdown_components']=self.dropdown_components(child,expand_depth-1,_ancestors,_budget)
                    else:item['listbox_children']=self.listbox_children(child,expand_depth-1,_ancestors,_budget)
        for off,adjust in [(0x1da0,0),(0x1c60,0),(0x1ca0,0),(0x1ce0,0),(0x1d20,8),(0x1d60,8)]:
            mh=self.read(full+off,16)
            if mh is None:raise RuntimeError('Fixed window map unavailable')
            mapvt,root=struct.unpack('<QQ',mh)
            if self.read(mapvt+16,8)!=struct.pack('<Q',self.base+36029680):
                raise RuntimeError('Fixed window map getter unsupported')
            guards.append((full+off,mh));pending=[root] if root else [];seen=set()
            while pending:
                node=pending.pop()
                if node in seen:raise RuntimeError('Fixed window map cycle detected')
                seen.add(node);_budget[0]-=1
                if _budget[0]<0 or time.monotonic()>_budget[1]:raise RuntimeError('Fixed window map read limit exceeded')
                data=self.read(node,40)
                if data is None:raise RuntimeError('Fixed window map node unreadable')
                guards.append((node,data));value=struct.unpack_from('<Q',data)[0]
                pending.extend(p for p in struct.unpack_from('<3Q',data,16) if p)
                if value:collect(value+adjust,'named_map_'+hex(off))
        for off,stride,adjust in [(off,8,0) for off in vector_offsets]+[(0x1de0,40,48)]:
            h=self.read(full+off,16)
            if h is None:raise RuntimeError('Fixed window vector unavailable')
            array,capacity,count=struct.unpack('<QII',h)
            if count>capacity or capacity>10000:raise RuntimeError('Fixed window vector counts invalid')
            raw=self.read(array,count*stride) if count else b''
            if raw is None:raise RuntimeError('Fixed window vector unreadable')
            guards.append((full+off,h))
            if raw:guards.append((array,raw))
            for index in range(count):
                value=struct.unpack_from('<Q',raw,index*stride+(32 if stride==40 else 0))[0]
                if not value:raise RuntimeError('Fixed window null child pointer')
                collect(value+adjust,'named_containers' if stride==40 else 'child_vector_'+hex(off))
        if self.read(gui,160)!=header or any(self.read(addr,len(raw))!=raw for addr,raw in guards):
            raise GuiSnapshotChanged('Fixed window children changed during read')
        return {'status':'verified_maps_and_vectors','children':children,'complete_child_coverage':False,
                'child_vectors_checked':len(vector_offsets)+1,'named_maps_checked':6,'expand_depth':expand_depth,
                'engine_show_state_verified':True,'engine_local_shown':bool(header[117]&8),
                'state':'engine_shown' if header[117]&8 else 'engine_hidden','effective_visibility':None}

    def current_tooltip(self):
        """Read the engine-owned tooltip and verified local show/hide state."""
        self._guard_root();started=time.time()
        owner_raw=self.read(self.base+0x332f698,8)
        if owner_raw is None:raise RuntimeError('Tooltip owner unavailable')
        owner=struct.unpack('<Q',owner_raw)[0]
        owner_type=self.typename(owner)
        owner_vtables={'.?AVCInGameIdler@@':0x2968ff0,'.?AVCFrontEndIdler@@':0x2949d50}
        if owner_type not in owner_vtables:raise RuntimeError('Tooltip owner type mismatch')
        owner_header=self.read(owner,8)
        expected_owner_vt=self.base+owner_vtables[owner_type]
        if owner_header!=struct.pack('<Q',expected_owner_vt):
            raise RuntimeError('Tooltip owner vtable mismatch')
        # Both types inherit CGameIdler at offset zero in this build's RTTI.
        owner_methods={12:0x29eed0,15:0x29ece0,16:0x29ece0}
        owner_method_guards=[]
        for slot,rva in owner_methods.items():
            address=expected_owner_vt+slot*8;value=struct.pack('<Q',self.base+rva)
            if self.read(address,8)!=value:raise RuntimeError('Tooltip owner methods unsupported')
            owner_method_guards.append((address,value))
        binding=self.read(owner+1256,24)
        if binding is None:raise RuntimeError('Tooltip binding unavailable')
        tooltip,graphics,gui=struct.unpack('<3Q',binding)
        if gui!=self.root or self.typename(tooltip)!='.?AVCTextBox@@':
            raise RuntimeError('Tooltip binding/type mismatch')
        header=self.read(tooltip,160)
        if header is None or struct.unpack_from('<Q',header,104)[0]!=self.root:
            raise RuntimeError('Tooltip GUI ownership mismatch')
        vt=struct.unpack_from('<Q',header)[0]
        methods=self.read(vt+15*8,16)
        if methods!=struct.pack('<2Q',self.base+0x22a4440,self.base+0x22a4080):
            raise RuntimeError('Tooltip show/hide methods unsupported')
        setter=bytes.fromhex('440fb641750fb6c24180e0f7c0e003440ac044884175')
        if self.read(self.base+0x22ae0f0,len(setter))!=setter:
            raise RuntimeError('Tooltip show/hide state setter changed')
        definition=struct.unpack_from('<Q',header,96)[0]
        name=self._string(definition+40,512);source=self._string(definition+72,1024)
        if name.get('text')!='ToolTip' or source.get('text')!='interface/core.gui':
            raise RuntimeError('Core tooltip definition mismatch')
        fields=(('rendered_buffer',tooltip+304),('owner_combined_buffer',owner+88),
                ('title_buffer',owner+1152),('body_buffer',owner+1184))
        before={label:self.read(addr,32) for label,addr in fields}
        values={label:self._string(addr) for label,addr in fields}
        if any(v['status']!='read' for v in values.values()):
            raise GuiSnapshotChanged('Tooltip text unavailable or changed during read')
        if any(self.read(addr,32)!=before[label] for label,addr in fields):
            raise GuiSnapshotChanged('Tooltip text headers changed during read')
        for label,addr in fields:
            check=self._string(addr)
            if check.get('status')!='read' or check['raw_text']!=values[label]['raw_text']:
                raise GuiSnapshotChanged('Tooltip text payloads changed during read')
        final=self.read(tooltip,160)
        if final is None or final[:8]!=header[:8] or final[96:118]!=header[96:118]:
            raise GuiSnapshotChanged('Tooltip state changed during read')
        if (self.read(self.base+0x332f698,8)!=owner_raw or self.read(owner+1256,24)!=binding
                or self.read(owner,8)!=owner_header
                or any(self.read(address,8)!=value for address,value in owner_method_guards)):
            raise GuiSnapshotChanged('Tooltip owner binding changed during read')
        self._guard_root()
        shown=bool(header[117]&8)
        rendered=values['rendered_buffer']['raw_text'];combined=values['owner_combined_buffer']['raw_text']
        if rendered==combined:agreement='rendered_equals_combined'
        elif rendered and not combined:agreement='rendered_nonempty_combined_empty'
        elif combined and not rendered:agreement='combined_nonempty_rendered_empty'
        else:agreement='rendered_differs_from_combined'
        for val in values.values():val['formatted_runs']=native_markup(val['raw_text'])
        return {'mode':'native_current_tooltip','owner_native_type':owner_type,'screen_capture':False,'input_events':False,
                'process_writes':False,'process_identity':self.process.expected,
                'captured_start_unix':started,'captured_end_unix':time.time(),'atomic_game_frame':False,
                'engine_show_state_verified':True,'engine_local_shown':shown,
                'state':'engine_shown' if shown else 'hidden_buffer',
                'effective_visibility':None,'buffer_last_update_unix':None,
                'rendered_matches_owner_combined':rendered==combined,
                'buffer_agreement':agreement,'buffer_freshness_verified':False,
                'text_consistency':'sampled_headers_and_payloads','active_tooltip_verified':False,
                'widget_id':hex(tooltip),'source':source['text'],'name':name['text'],'buffers':values,
                'limitations':['Engine local show state does not prove physical screen visibility.',
                               'Hidden text buffers can retain prior tooltip text.',
                               'Buffer last-update time is unknown; read is non-atomic.']}

    def snapshot(self,query='',source='',offset=0,limit=100,expand_depth=0,native_type='',engine_state='any'):
        if not isinstance(query,str) or len(query)>160 or not isinstance(source,str) or len(source)>240:
            raise ValueError('query/source filter too long or invalid')
        if type(offset)!=int or offset<0 or type(limit)!=int or not 1<=limit<=200:
            raise ValueError('Use nonnegative offset and 1..200 limit')
        if type(expand_depth)!=int or not 0<=expand_depth<=8:raise ValueError('expand_depth must be 0..8')
        if not isinstance(native_type,str) or (native_type and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,79}',native_type)):
            raise ValueError('native_type must be an exact native class name, e.g. CStandardGridBox')
        if not isinstance(engine_state,str) or engine_state not in ('any','shown','hidden'):
            raise ValueError('engine_state must be any, shown or hidden')
        expected_type='.?AV'+native_type+'@@' if native_type else None
        self._guard_root()
        started=time.time();start_monotonic=time.monotonic()
        foreground_read=getattr(self.process,'foreground_metadata',lambda:{'available':False,'pid':None,'is_bound_game':None})
        foreground_start=foreground_read()
        header=self.read(self.root,312)
        if header is None:raise RuntimeError('Native GUI registry unavailable')
        tables=registry_tables(header)
        definitions={};seen=set();matches=[];records={};table_bytes={};readable=0;unknown_text=0
        query=query.casefold();source_filter=source.casefold()
        for registry,array,count,capacity in tables:
            raw=self.read(array,count*8) if count else b''
            if raw is None:raise RuntimeError('Native GUI registry unreadable')
            table_bytes[registry]=raw
            for gui in struct.unpack('<'+'Q'*count,raw):
                if time.monotonic()-start_monotonic>8:raise RuntimeError('Native GUI read deadline exceeded; no partial snapshot returned')
                if gui in seen:
                    if gui in records and registry not in records[gui]['registry_memberships']:
                        records[gui]['registry_memberships'].append(registry)
                    continue
                seen.add(gui)
                data=self.read(gui,160)
                if data is None or struct.unpack_from('<Q',data,104)[0]!=self.root:continue
                definition=struct.unpack_from('<Q',data,96)[0]
                if definition not in definitions:
                    definitions[definition]=(self._string(definition+40,512),self._string(definition+72,1024))
                name,filename=definitions[definition]
                if name['status']!='read' or filename['status']!='read':continue
                readable+=1
                if source_filter and source_filter not in filename['text'].casefold():continue
                kind=self.typename(gui)
                if expected_type and kind!=expected_type:continue
                shown_state=None
                if engine_state!='any':
                    shown_state=self.widget_show_state(gui)
                    if not shown_state['engine_show_state_verified'] or shown_state['engine_local_shown']!=(engine_state=='shown'):continue
                text={'status':'not_decoded_for_this_widget_type'}
                if kind=='.?AVCInstantTextBox@@':text=self._string(gui+272)
                elif kind in ('.?AVCButtonStandard@@','.?AVCCallbackButtonStandard@@'):text=self._string(gui+392)
                elif kind=='.?AVCTextBox@@':text=self._string(gui+304)
                elif kind=='.?AVCCheckBox@@':text=self.checkbox_text(gui)
                elif kind=='.?AVCEditBox@@':text=self._snapshot_edit_text(gui)
                if text['status']!='read':unknown_text+=1
                if query and query not in (name['text']+' '+text.get('text','')).casefold():continue
                parent=struct.unpack_from('<Q',data,80)[0]
                matches.append({'widget_id':hex(gui),'registry':registry,'registry_memberships':[registry],'name':name['text'],
                                'source':filename['text'],'native_type':kind,
                                'text_status':text['status'],'raw_text':text.get('raw_text'),
                                'text':text.get('text'),'text_length':text.get('length'),
                                'formatted_runs':native_markup(text['raw_text']) if text['status']=='read' else None,
                                'buffer_last_update_unix':None,
                                'text_freshness':'buffer_update_time_unknown',
                                'native_flag_bytes':data[116:118].hex(),
                                'flag_0x04_set':bool(data[116]&4),
                                'effective_visibility':None,
                                'owner_native_type':self.typename(parent) if parent else None})
                records[gui]=matches[-1]
                records[gui]['engine_show_state']=shown_state if shown_state is not None else self.widget_show_state(gui)
                # Detailed traversal belongs only to the requested page.
                if not offset<=len(matches)-1<offset+limit:continue
                if kind=='.?AVCContainerWindow@@' and filename['text'] in ('interface/eventwindow.gui','interface/alerts.gui','interface/worldtensionwindowpopup.gui'):
                    from native_popup import read_native_popup
                    records[gui]['native_popup']=read_native_popup(self,gui)
                if kind=='.?AVCIcon@@':records[gui]['icon_frame']=self.icon_frame(gui)
                if kind=='.?AVCCheckBox@@':records[gui]['checkbox_selection']=self.checkbox_selection(gui)
                if kind=='.?AVCContainerWindow@@':
                    records[gui]['container_children']=self.container_children(gui,expand_depth)
                elif kind in ('.?AVCStandardlistbox@@','.?AVCSmoothListbox@@','.?AVCOverlappingElementsBox@@'):
                    records[gui]['listbox_children']=self.listbox_children(gui,expand_depth)
                elif kind=='.?AVCStandardGridBox@@':
                    records[gui]['grid_children']=self.grid_children(gui,expand_depth)
                elif kind=='.?AVCDropDownBox@@':
                    records[gui]['dropdown_components']=self.dropdown_components(gui,expand_depth)
                elif kind=='.?AVCFixedWindow@@':
                    records[gui]['fixed_window_children']=self.fixed_window_children(gui,expand_depth)
        final=self.read(self.root,312)
        if final is None or registry_identity(registry_tables(final))!=registry_identity(tables):
            raise GuiSnapshotChanged('GUI registry changed during read; request a new snapshot')
        for registry,array,count,capacity in tables:
            final_raw=self.read(array,count*8) if count else b''
            if final_raw!=table_bytes[registry]:
                raise GuiSnapshotChanged('GUI registry contents changed during read; request a new snapshot')
        self._guard_root()
        annotate_traversal_ancestors(matches[offset:offset+limit])
        return {'mode':'native_gui_memory','screen_capture':False,'input_events':False,
                'process_writes':False,'live_ui_text_available':True,'editable_input_text_decoded':self.decode_edit_inputs,'exe_sha256':SUPPORTED_HASH,
                'process_identity':self.process.expected,'captured_start_unix':started,'captured_end_unix':time.time(),
                'atomic_game_frame':False,'foreground_start':foreground_start,'foreground_end':foreground_read(),'foreground_required':False,'registries':[{'name':n,'slots_scanned':c,**({'opaque_header_field':cap,'sparse':True} if n=='dynamic_slots' else {'capacity':cap,'sparse':False})} for n,a,c,cap in tables],
                'readable_widgets':readable,'matches':matches[offset:offset+limit],
                'engine_state_filter':engine_state,'engine_state_filter_scope':'top_level_widgets_only',
                'native_type_filter':native_type,'native_type_filter_scope':'top_level_widgets_only',
                'match_count':len(matches),'offset':offset,'truncated':offset+limit<len(matches),
                'visibility_verified':False,'unsupported_or_unreadable_text_widgets_in_filter':unknown_text,
                'limitations':['Registered widgets include hidden panels; effective visibility is not yet decoded.',
                               'Formatted core tooltip text is buffered; its current visibility and freshness are not verified.',
                               'Only verified instant/formatted text-box and standard/callback button layouts are decoded.',
                               'Build-pinned offsets reject other executable hashes.']}

def capture_live_ui(session_file,game_root,**filters):
    config=json.loads(Path(session_file).read_text(encoding='utf-8-sig'))
    executable=Path(game_root)/'hoi4.exe'
    digest=hashlib.sha256(executable.read_bytes()).hexdigest()
    if digest!=SUPPORTED_HASH:raise RuntimeError('Unsupported game build; native information unavailable')
    process=WindowsProcess(config['process_identity'],executable)
    try:return NativeGuiReader(process,digest).snapshot(**filters)
    finally:process.close()

def capture_current_tooltip(session_file,game_root):
    config=json.loads(Path(session_file).read_text(encoding='utf-8-sig'))
    executable=Path(game_root)/'hoi4.exe'
    digest=hashlib.sha256(executable.read_bytes()).hexdigest()
    if digest!=SUPPORTED_HASH:raise RuntimeError('Unsupported game build; native information unavailable')
    process=WindowsProcess(config['process_identity'],executable)
    try:return NativeGuiReader(process,digest).current_tooltip()
    finally:process.close()
