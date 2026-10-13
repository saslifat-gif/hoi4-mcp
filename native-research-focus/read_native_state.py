"""Independent, read-only state verification for the pinned temporary campaign."""
import ctypes,json,struct,sys
from pathlib import Path
from ctypes import wintypes as W
from direct_process import process_identity
from attach_native_probe import MODULEENTRY32W
from research_reader import read_research

def read_state(session_file):
 c=json.loads(Path(session_file).read_text())
 if process_identity(c['process_identity']['pid'])!=c['process_identity']:raise RuntimeError('Bound game process changed before snapshot')
 k=ctypes.WinDLL('kernel32',use_last_error=True)
 k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
 k.ReadProcessMemory.argtypes=[W.HANDLE,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t)]
 k.CloseHandle.argtypes=[W.HANDLE]
 k.CreateToolhelp32Snapshot.argtypes=[W.DWORD,W.DWORD];k.CreateToolhelp32Snapshot.restype=W.HANDLE
 k.Module32FirstW.argtypes=[W.HANDLE,ctypes.POINTER(MODULEENTRY32W)]
 s=k.CreateToolhelp32Snapshot(0x18,c['process_identity']['pid']);m=MODULEENTRY32W();m.dwSize=ctypes.sizeof(m)
 try:
  if not k.Module32FirstW(s,ctypes.byref(m)):raise RuntimeError('Cannot read game module')
  base=m.modBaseAddr
 finally:k.CloseHandle(s)
 h=k.OpenProcess(0x410,False,c['process_identity']['pid'])
 if not h:raise RuntimeError('Cannot open game for read-only snapshot')
 def raw(a,n):
  b=ctypes.create_string_buffer(n);got=ctypes.c_size_t()
  if not k.ReadProcessMemory(h,a,b,n,ctypes.byref(got)) or got.value!=n:raise RuntimeError('Native snapshot memory is unreadable')
  return b.raw
 def u(a):return struct.unpack('<Q',raw(a,8))[0]
 def i(a):return struct.unpack('<i',raw(a,4))[0]
 def name(a):
  n=u(a+16);cap=u(a+24)
  if not 0<n<160 or not n<=cap<65536:raise RuntimeError('Invalid native focus identifier')
  return raw(u(a) if cap>15 else a,n).decode('ascii')
 try:
  o=json.loads((Path(session_file).parent/'native'/'native-observation.json').read_text())
  if o['session_id']!=c['session_id']:raise RuntimeError('Native observation session mismatch')
  tree=int(o['focus_tree'],16);p=int(o['focus_progress'],16)
  world=int(o['world'],16);country=int(o['country'],16)
  if o['pid']!=c['process_identity']['pid'] or i(country+8)!=o['country_tag']:raise RuntimeError('Native observation process/country mismatch')
  research=read_research(raw,base,country,world)
  if u(tree)!=base+0x2739bb8:raise RuntimeError('Native focus tree type mismatch')
  count=i(tree+0x3c)
  if not 0<count<1000:raise RuntimeError('Invalid native focus count')
  focuses=[];focus_list=u(tree+0x30)
  for j in range(count):
   f=u(focus_list+8*j)
   if u(f)!=base+0x2739c08 or u(f+0x160)!=tree:raise RuntimeError('Native focus ownership/type mismatch')
   focuses.append({'id':name(f+0x18),'address':hex(f)})
  by_address={int(x['address'],16):x['id'] for x in focuses};completed=[]
  completed_count=i(p+0x4c)
  if not 0<=completed_count<1000:raise RuntimeError('Invalid completed focus count')
  completed_list=u(p+0x40) if completed_count else 0
  for j in range(completed_count):
   f=u(completed_list+8*j)
   match=by_address.get(f)
   if match is None:raise RuntimeError('Completed focus is absent from native tree')
   completed.append(match)
  result={'completed_focuses':completed,'pid':c['process_identity']['pid'],**research,'focuses':focuses,'active_focus':by_address.get(u(p+0x10)),'focus_elapsed_raw':struct.unpack('<q',raw(p+0x18,8))[0]}
  if process_identity(c['process_identity']['pid'])!=c['process_identity']:raise RuntimeError('Game process changed during snapshot')
  return result
 finally:k.CloseHandle(h)
if __name__=='__main__':
 r=read_state(sys.argv[1]);Path(sys.argv[2]).write_text(json.dumps(r,indent=2));print(json.dumps({'slots':r['research_slots'],'active_focus':r['active_focus'],'focuses':[f['id'] for f in r['focuses'] if any(s in f['id'] for s in ('year','industrial','econom','autark','plan'))]}))
