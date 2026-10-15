"""Read active region/theater cache contexts before relying on UI entry existence.

Mirrors the normal b076f0/b07820 collectors' active-byte/key tests. Never creates
records, runs a formatter, or treats cached strings as freshly generated.
"""
import struct
from runtime_gui import GuiSnapshotChanged

def read_regional_cache(reader):
 r=reader;guards=[]
 def raw(a,n):
  b=r.read(a,n)
  if b is None:raise RuntimeError('Regional cache binding unreadable')
  guards.append((a,b));return b
 def ptr(a):return struct.unpack('<Q',raw(a,8))[0]
 ui=ptr(r.base+0x332f6a0);manager=ptr(ui+0x798)
 if not manager:raise RuntimeError('Native alert manager unavailable')
 entries=[];unresolved=[]
 for kind in range(82):
  array,capacity,count=struct.unpack('<QII',raw(manager+24*(kind+0xf0e),16))
  if count>capacity or capacity>1000:raise RuntimeError('Regional cache extent invalid')
  for i in range(count):
   entry=array+0x468*i
   if raw(entry,1)[0]:continue
   region,theater,opaque,country=struct.unpack('<4Q',raw(entry+0x438,32))
   if not (region or theater):continue
   if country or (region and theater):
    unresolved.append({'native_alert_kind':kind,'record_id':hex(entry),'reason':'mixed_context_key'});continue
   scope='region' if region else 'theater';context=region or theater
   expected,typename=(0x296d558,'.?AVCStrategicRegion@@') if region else (0x29e5c50,'.?AVCTheaterGroup@@')
   if ptr(context)!=r.base+expected or r.typename(context)!=typename:
    raise RuntimeError('Native regional cache context type mismatch')
   item={'alert_scope':scope,'native_alert_kind':kind,'native_context_id':hex(context),
         'native_context_type':typename,'record_id':hex(entry),'native_cache_record_active':True,
         'native_context_runtime_binding_verified':True,'fresh_message_generated':False}
   if theater:item['native_context_handle']=list(struct.unpack('<2I',raw(context+8,8)))
   entries.append(item)
 for a,b in guards:
  if r.read(a,len(b))!=b:raise GuiSnapshotChanged('Native regional cache changed during read')
 r._guard_root()
 return {'entries':entries,'unresolved':unresolved,'process_writes':False,'native_callback_invoked':False,
         'ui_entry_existence_verified':False,'atomic_game_frame':False,'fresh_message_generated':False}
