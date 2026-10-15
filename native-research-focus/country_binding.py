"""Exact native country-tag lookup using the engine's existing tag map."""
import re,struct
from runtime_gui import GuiSnapshotChanged

def read_country_binding(reader,world,tag):
 if not isinstance(tag,str) or not re.fullmatch('[A-Z0-9]{3}',tag):raise ValueError('Exact three-character native country tag required')
 guards=[]
 def read(a,n):
  b=reader.read(a,n)
  if b is None or len(b)!=n:raise RuntimeError('Country binding unreadable')
  guards.append((a,b));return b
 def ptr(a):return struct.unpack('<Q',read(a,8))[0]
 if ptr(reader.base+0x332f260)!=world:raise RuntimeError('Bound country world changed')
 manager=ptr(reader.base+0x3330d98);mask=ptr(manager+0x78)
 if mask>1048575 or mask&(mask+1):raise RuntimeError('Country tag-map mask invalid')
 head=ptr(manager+0x50);buckets=ptr(manager+0x60);h=0x811c9dc5
 for byte in tag.encode('ascii'):h=((h^byte)*0x1000193)&0xffffffff
 first,last=struct.unpack('<QQ',read(buckets+16*(h&mask),16));node=last;seen=set();index=None
 if last!=head:
  while True:
   if not node or node in seen or len(seen)>=10000:raise RuntimeError('Country tag chain invalid')
   seen.add(node);s=node+0x10;header=read(s,32);length,capacity=struct.unpack_from('<QQ',header,16)
   if length>512 or length>capacity or capacity>65536:raise RuntimeError('Country tag string extent invalid')
   data=ptr(s) if capacity>15 else s;raw=read(data,length+1)
   if raw[-1]!=0:raise RuntimeError('Country tag string terminator invalid')
   if raw[:-1]==tag.encode('ascii'):
    index=struct.unpack('<i',read(node+0x30,4))[0];break
   if node==first:break
   node=ptr(node+8)
 if index is None:raise ValueError('Country tag is not registered')
 tags=ptr(manager+0x30);count=struct.unpack('<i',read(manager+0x3c,4))[0]
 if not 0<=index<count<=1000000:raise RuntimeError('Country tag inventory extent invalid')
 native_tag=struct.unpack('<i',read(tags+4*index,4))[0]
 if not 0<native_tag<1000000:raise ValueError('Country tag is inactive')
 native_index=struct.unpack('<i',read(ptr(world+0x340)+4*native_tag,4))[0]
 if not 0<native_index<1000000:raise ValueError('Country tag has no active country')
 country=ptr(ptr(world+0x310)+8*native_index)
 if ptr(country)!=reader.base+0x27e7360 or reader.typename(country)!='.?AVCCountry@@' or struct.unpack('<i',read(country+8,4))[0]!=native_tag:raise RuntimeError('Country native identity mismatch')
 if any(reader.read(a,len(b))!=b for a,b in guards):raise GuiSnapshotChanged('Country binding changed during read')
 return {'country_id':country,'country_tag':tag,'native_tag':native_tag,'native_index':native_index}
