"""Attach only the source-built observation probe to a freshly bound test game.
Never launches the game, sends input, or writes gameplay fields.
"""
import argparse,ctypes,hashlib,json,os,struct
from ctypes import wintypes as W
from pathlib import Path
from direct_process import process_identity
from bind_session import verify_sources

def export_rva(path,name):
 b=Path(path).read_bytes();pe=struct.unpack_from('<I',b,0x3c)[0];o=pe+24
 if b[pe:pe+4]!=b'PE\0\0' or struct.unpack_from('<H',b,o)[0]!=0x20b:raise ValueError('Native module must be a PE32+ image')
 n=struct.unpack_from('<H',b,pe+6)[0];sz=struct.unpack_from('<H',b,pe+20)[0];secs=[]
 for i in range(n):
  a=o+sz+40*i;vs,va,rs,raw=struct.unpack_from('<IIII',b,a+8);secs.append((va,rs,raw))
 def offset(rva):
  for va,size,raw in secs:
   if va<=rva<va+size:return raw+rva-va
  raise ValueError('Unmapped export RVA')
 addr,size=struct.unpack_from('<II',b,o+112);e=offset(addr)
 funcs,names,ft,nt,ot=struct.unpack_from('<IIIII',b,e+20)
 for i in range(names):
  p=offset(struct.unpack_from('<I',b,offset(nt)+4*i)[0]);end=b.index(b'\0',p)
  if b[p:end].decode()==name:
   ordinal=struct.unpack_from('<H',b,offset(ot)+2*i)[0];rva=struct.unpack_from('<I',b,offset(ft)+4*ordinal)[0]
   if addr<=rva<addr+size:raise ValueError('Forwarded bridge export rejected')
   return rva
 raise ValueError('Required probe export missing')

class MODULEENTRY32W(ctypes.Structure):
 _fields_=[('dwSize',W.DWORD),('th32ModuleID',W.DWORD),('th32ProcessID',W.DWORD),('GlblcntUsage',W.DWORD),('ProccntUsage',W.DWORD),('modBaseAddr',ctypes.c_void_p),('modBaseSize',W.DWORD),('hModule',W.HMODULE),('szModule',W.WCHAR*256),('szExePath',W.WCHAR*260)]
class MEMORY_BASIC_INFORMATION(ctypes.Structure):
 _fields_=[('BaseAddress',ctypes.c_void_p),('AllocationBase',ctypes.c_void_p),('AllocationProtect',W.DWORD),('PartitionId',W.WORD),('RegionSize',ctypes.c_size_t),('State',W.DWORD),('Protect',W.DWORD),('Type',W.DWORD)]

def bind_native_files(directory,sid,country):
 bindings={'session-id.txt':sid,'country-code.txt':country}
 for name,value in bindings.items():
  path=directory/name
  if path.exists() and path.read_text()!=value:raise RuntimeError('Different native binding was not overwritten')
 for name,value in bindings.items():
  path=directory/name
  if not path.exists():path.write_text(value,encoding='ascii')

def attach(session_file,dll_file,expected_sha):
 if os.name!='nt':raise RuntimeError('Native attachment requires Windows')
 c=json.loads(Path(session_file).read_text());verify_sources(c)
 if c['country'] not in ('GER','ITA') or c['mode']!='singleplayer_test' or not c.get('process_identity'):raise ValueError('Freshly bound supported-country test session required')
 pid=c['process_identity']['pid']
 if process_identity(pid)!=c['process_identity']:raise RuntimeError('Bound game process changed before attachment')
 dll=Path(dll_file).resolve()
 if hashlib.sha256(dll.read_bytes()).hexdigest()!=expected_sha:raise RuntimeError('Pinned native module changed; no attachment attempted')
 bind_native_files(dll.parent,c['session_id'],c['country'])
 k=ctypes.WinDLL('kernel32',use_last_error=True)
 def fn(name,args,result):
  f=getattr(k,name);f.argtypes=args;f.restype=result;return f
 close=fn('CloseHandle',[W.HANDLE],W.BOOL)
 snapshot=fn('CreateToolhelp32Snapshot',[W.DWORD,W.DWORD],W.HANDLE)
 first=fn('Module32FirstW',[W.HANDLE,ctypes.POINTER(MODULEENTRY32W)],W.BOOL)
 nextmod=fn('Module32NextW',[W.HANDLE,ctypes.POINTER(MODULEENTRY32W)],W.BOOL)
 def modules():
  h=snapshot(0x18,pid)
  if h in (None,ctypes.c_void_p(-1).value):raise ctypes.WinError(ctypes.get_last_error())
  out={};entry=MODULEENTRY32W();entry.dwSize=ctypes.sizeof(entry)
  try:
   ok=first(h,ctypes.byref(entry))
   while ok:
    out[entry.szModule.lower()]={'base':entry.modBaseAddr,'path':entry.szExePath,'size':entry.modBaseSize};ok=nextmod(h,ctypes.byref(entry))
  finally:close(h)
  return out
 mods=modules()
 if dll.name.lower()=='hoi4-native-selection.dll':
  predecessor=mods.get('hoi4-native-probe.dll')
  if not predecessor or Path(predecessor['path']).resolve()!=dll.parent/'hoi4-native-probe.dll' or hashlib.sha256(Path(predecessor['path']).read_bytes()).hexdigest()!='dad934b71750c9e4562e77b17dfaf82dfeb3947544193b72c76573f3dd6a9b21':
   raise RuntimeError('Verified session observation predecessor required')
 if dll.name.lower()=='hoi4-native-choices.dll':
  predecessor=mods.get('hoi4-native-selection.dll')
  if not predecessor or Path(predecessor['path']).resolve()!=dll.parent/'hoi4-native-selection.dll' or hashlib.sha256(Path(predecessor['path']).read_bytes()).hexdigest()!='ea4c632ab61bfe03315b952a9d5ee28b9c7c45b1d48b2428e0c9a0646a096cc0':
   raise RuntimeError('Verified session selection predecessor required')
 if dll.name.lower() in mods:raise RuntimeError('Probe already loaded; binding was not reset')
 gm=fn('GetModuleHandleW',[W.LPCWSTR],W.HMODULE)
 gp=fn('GetProcAddress',[W.HMODULE,ctypes.c_char_p],ctypes.c_void_p)
 q=fn('VirtualQuery',[ctypes.c_void_p,ctypes.POINTER(MEMORY_BASIC_INFORMATION),ctypes.c_size_t],ctypes.c_size_t)
 filename=fn('GetModuleFileNameW',[W.HMODULE,W.LPWSTR,W.DWORD],W.DWORD)
 local=gp(gm('kernel32.dll'),b'LoadLibraryW');m=MEMORY_BASIC_INFORMATION()
 if not q(local,ctypes.byref(m),ctypes.sizeof(m)):raise ctypes.WinError(ctypes.get_last_error())
 buf=ctypes.create_unicode_buffer(32768);filename(m.AllocationBase,buf,len(buf));key=Path(buf.value).name.lower()
 if key not in mods or Path(mods[key]['path']).resolve()!=Path(buf.value).resolve():raise RuntimeError('Remote loader module identity differs')
 loader=mods[key]['base']+local-m.AllocationBase
 openproc=fn('OpenProcess',[W.DWORD,W.BOOL,W.DWORD],W.HANDLE)
 read=fn('ReadProcessMemory',[W.HANDLE,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t)],W.BOOL)
 write=fn('WriteProcessMemory',[W.HANDLE,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t)],W.BOOL)
 alloc=fn('VirtualAllocEx',[W.HANDLE,ctypes.c_void_p,ctypes.c_size_t,W.DWORD,W.DWORD],ctypes.c_void_p)
 free=fn('VirtualFreeEx',[W.HANDLE,ctypes.c_void_p,ctypes.c_size_t,W.DWORD],W.BOOL)
 create=fn('CreateRemoteThread',[W.HANDLE,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_void_p,W.DWORD,ctypes.POINTER(W.DWORD)],W.HANDLE)
 wait=fn('WaitForSingleObject',[W.HANDLE,W.DWORD],W.DWORD)
 result=fn('GetExitCodeThread',[W.HANDLE,ctypes.POINTER(W.DWORD)],W.BOOL)
 h=openproc(0x43a,False,pid)
 if not h:raise ctypes.WinError(ctypes.get_last_error())
 def run(address,argument):
  if process_identity(pid)!=c['process_identity']:raise RuntimeError('Bound game process changed before native execution')
  t=create(h,None,0,address,argument,0,None)
  if not t:raise ctypes.WinError(ctypes.get_last_error())
  try:
   if wait(t,30000)!=0:raise RuntimeError('Native attachment completion uncertain; do not retry')
   code=W.DWORD()
   if not result(t,ctypes.byref(code)):raise ctypes.WinError(ctypes.get_last_error())
   return code.value
  finally:close(t)
 remote=None
 try:
  sample=ctypes.create_string_buffer(32);count=ctypes.c_size_t()
  if not read(h,loader,sample,32,ctypes.byref(count)) or count.value!=32:raise RuntimeError('Remote loader bytes unreadable')
  # A game's overlay can detour the normal loader export. Validate its exact
  # module/export RVA, and call the existing entry without replacing the hook.
  if export_rva(mods[key]['path'],'LoadLibraryW')!=local-m.AllocationBase:
   raise RuntimeError('Remote loader export identity differs')
  loader_detoured=sample.raw!=ctypes.string_at(local,32)
  payload=(str(dll)+'\0').encode('utf-16-le');remote=alloc(h,None,len(payload),0x3000,4)
  if not remote:raise ctypes.WinError(ctypes.get_last_error())
  memory=ctypes.create_string_buffer(payload)
  if not write(h,remote,memory,len(payload),ctypes.byref(count)) or count.value!=len(payload):raise ctypes.WinError(ctypes.get_last_error())
  run(loader,remote)
  free(h,remote,0,0x8000);remote=None
  now=modules();item=now.get(dll.name.lower())
  if not item or Path(item['path']).resolve()!=dll:raise RuntimeError('Expected probe module was not loaded')
  code=run(item['base']+export_rva(dll,'Initialize'),None)
  report={'pid':pid,'session_id':c['session_id'],'dll_sha256':expected_sha,'initialize_result':code,'module_base':hex(item['base']),'process_memory_writes':True,'uses_keyboard_or_mouse':False,'selection_commands_enabled':json.loads((dll.parent/'native-initialized.json').read_text()).get('selection_commands_enabled',False) if code==0 else False,'existing_loader_hook_preserved':loader_detoured}
  (dll.parent/'attachment-result.json').write_text(json.dumps(report,indent=2))
  print(json.dumps(report))
  if code!=0:raise RuntimeError('Native initialization rejected attachment')
 finally:
  # Retain an allocation after any uncertain loader result: its thread might
  # still be using the path. The temporary game's exit reclaims it.
  close(h)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--session-file',required=True);p.add_argument('--dll',required=True);p.add_argument('--sha256',required=True)
 a=p.parse_args();attach(a.session_file,a.dll,a.sha256)
