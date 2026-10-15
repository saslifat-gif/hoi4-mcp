"""Pinned country-list unit IDs. No input, native invocation or process writes."""
import struct
from runtime_gui import GuiSnapshotChanged
from native_handle import HANDLE_SIGNATURES,resolve_native_handle

ARMY_VTABLE=0x295a2b0
ARMY_OBJECT_VTABLE=0x295a490

def read_unit_ids(reader,country,world):
 r=reader;guards=[]
 def read(address,size):
  data=r.read(address,size)
  if data is None or len(data)!=size:raise RuntimeError('Native military field unreadable')
  guards.append((address,data));return data
 def ptr(address):return struct.unpack('<Q',read(address,8))[0]
 for address,code in HANDLE_SIGNATURES.items():
  expected=bytes.fromhex(code)
  if read(r.base+address,len(expected))!=expected:raise RuntimeError('Native handle implementation changed')
 if ptr(r.base+0x332f260)!=world:raise RuntimeError('Bound military world changed')
 read(country,8)
 if r.typename(country)!='.?AVCCountry@@':raise RuntimeError('Native military country type mismatch')
 tag=struct.unpack('<I',read(country+8,4))[0]
 if not tag:raise RuntimeError('Missing native country tag')
 tick=read(world+0x468,4)
 array,capacity,count=struct.unpack('<QII',read(country+0x290,16))
 if not 0<=count<=capacity<=100000:raise RuntimeError('Native unit list extent invalid')
 pointers=struct.unpack('<'+'Q'*count,read(array,count*8)) if count else ()
 province_array=ptr(world+0x2b0)
 province_count=struct.unpack('<i',read(world+0x2bc,4))[0]
 if not 1<=province_count<=100000:raise RuntimeError('Native province list extent invalid')
 def province_id(address):
  if not address:return None
  identifier=struct.unpack('<i',read(address+0xa4,4))[0]
  if not 1<=identifier<province_count or ptr(province_array+identifier*8)!=address:
   raise GuiSnapshotChanged('Unit province no longer resolves to its world object')
  return identifier
 units=[];ids=set()
 for unit in pointers:
  header=read(unit,32)
  if struct.unpack_from('<Q',header)[0]!=r.base+ARMY_VTABLE or struct.unpack_from('<Q',header,16)[0]!=r.base+ARMY_OBJECT_VTABLE or r.typename(unit)!='.?AVCArmy@@':
   raise RuntimeError('Native unit type mismatch')
  handle=struct.unpack_from('<II',header,24)
  if not all(handle) or handle in ids:raise RuntimeError('Missing or duplicate native unit ID')
  if resolve_native_handle(r.base,read,*handle)!=unit+16:raise GuiSnapshotChanged('Unit ID no longer resolves to its listed object')
  ids.add(handle)
  # c01dc0+300..37e consumes the first DWORD province and shifts the remaining path.
  path,capacity,path_count=struct.unpack('<QII',read(unit+0x200,16))
  if not 0<=path_count<=capacity<=100000:raise RuntimeError('Native movement path extent invalid')
  path_ids=list(struct.unpack('<'+'i'*path_count,read(path,path_count*4))) if path_count else []
  for identifier in path_ids:
   if not 1<=identifier<province_count:raise RuntimeError('Native movement path province invalid')
   if province_id(ptr(province_array+identifier*8))!=identifier:raise GuiSnapshotChanged('Movement path province no longer resolves')
  units.append({'unit_id':f'{handle[0]}:{handle[1]}','native_id_words':list(handle),
                'identity_source':'CArmy.game_object.id','country_list_membership_verified':True,
                'current_province_id':province_id(ptr(unit+0x1f0)),
                'destination_province_id':province_id(ptr(unit+0x1e8)),
                'movement_path_count':path_count,'movement_path_province_ids':path_ids,
                'movement_path_target_province_id':path_ids[-1] if path_ids else None})
 if any(r.read(address,len(data))!=data for address,data in guards):
  raise GuiSnapshotChanged('Native military identity changed during read')
 return {'country_tag_native':tag,'units':units,'count':count,'native_tick':struct.unpack('<i',tick)[0],
         'uses_keyboard_or_mouse':False,'process_writes':False,'atomic_game_frame':False,
         'command_eligibility_verified':False,'database_resolution_verified':True}
