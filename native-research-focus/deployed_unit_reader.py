"""Independent typed identity and raw resources of an owned deployed unit."""
import struct
from military_reader import read_unit_ids
from native_handle import resolve_native_handle
from runtime_gui import GuiSnapshotChanged

def read_deployed_unit(reader,country,world,unit_id):
 r=reader;units=read_unit_ids(r,country,world)
 found=[u for u in units['units'] if u['unit_id']==unit_id]
 if len(found)!=1:raise ValueError('Exactly one country-owned unit required')
 guards=[]
 def read(address,size):
  b=r.read(address,size)
  if b is None or len(b)!=size:raise RuntimeError('Deployed-unit field unreadable')
  guards.append((address,b));return b
 def ptr(address):return struct.unpack('<Q',read(address,8))[0]
 words=tuple(map(int,unit_id.split(':')));unit=resolve_native_handle(r.base,read,*words)-0x10
 if unit<=0 or ptr(unit)!=r.base+0x295a2b0 or ptr(unit+0x10)!=r.base+0x295a490:raise RuntimeError('Deployed-unit type mismatch')
 if struct.unpack('<I',read(unit+0x1d8,4))[0]!=units['country_tag_native']:raise RuntimeError('Deployed-unit owner mismatch')
 template=ptr(unit+0x3b8)
 if ptr(template)!=r.base+0x294f5b0 or r.typename(template)!='.?AVCReferencedDivisionTemplate@@':raise RuntimeError('Deployed-unit template type mismatch')
 template_id=struct.unpack('<II',read(template+8,8))
 if not all(template_id) or resolve_native_handle(r.base,read,*template_id)!=template:raise GuiSnapshotChanged('Deployed-unit template ID changed')
 if struct.unpack('<I',read(template+0x1ec,4))[0]!=units['country_tag_native']:raise RuntimeError('Deployed-unit template owner mismatch')
 def vector(field,width):
  data,capacity,count=struct.unpack('<QII',read(field,16))
  if not 0<=count<=capacity<=100000:raise RuntimeError('Deployed-unit resource extent invalid')
  return read(data,count*width) if count else b''
 eq=vector(unit+0x350,24);manpower=vector(unit+0x3e0,8)
 equipment=[{'native_key':hex(struct.unpack_from('<Q',eq,i)[0]),'quantity_raw':struct.unpack_from('<q',eq,i+16)[0]} for i in range(0,len(eq),24)]
 men=[{'country_tag_native':struct.unpack_from('<I',manpower,i)[0],'amount':struct.unpack_from('<i',manpower,i+4)[0]} for i in range(0,len(manpower),8)]
 if any(r.read(address,len(b))!=b for address,b in guards):raise GuiSnapshotChanged('Deployed-unit fields changed during read')
 return {**found[0],'template_id':f'{template_id[0]}:{template_id[1]}','equipment':equipment,'manpower_rows':men,'manpower':sum(m['amount'] for m in men),'country_tag_native':units['country_tag_native'],'native_tick':units['native_tick'],'process_writes':False,'uses_keyboard_or_mouse':False,'atomic_game_frame':False,'resource_identity_matches_source_verified':False}
