"""Pinned native object-ID lookup shared by unit and theater readers; no invocation."""
import struct
HANDLE_SIGNATURES={0x221f310:'4883ec288b013d681200007624488b058c2a23014885c07459488bd1488bc8e8ecdf',
                   0x221d320:'48895c2408488b59084c8bd14c635914448b02448b4a04418bc048c1e0204903c1'}

def resolve_native_handle(base,read,first,second):
 def ptr(address):return struct.unpack('<Q',read(address,8))[0]
 if not (first or second):return 0
 database=ptr(base+(0x3451db0 if first>0x1268 else 0x3451dc0+8*first if first<100 else 0x3451db8))
 if not database:return 0
 array=ptr(database+8);mask=struct.unpack('<i',read(database+20,4))[0];distance=read(database+24,1)[0]
 if mask<0 or mask>=1000000 or mask&(mask+1):raise RuntimeError('Native handle table extent invalid')
 hashed=(((first<<32)+second)*0x49631a45)&0xffffffffffffffff
 position=((hashed>>32)^(hashed&0xffffffff))&mask
 for rank in range(1,256):
  if position>mask+distance:break
  slot=read(array+position*24,24)
  if slot[4]<rank:break
  if struct.unpack_from('<2I',slot,8)==(first,second):return struct.unpack_from('<Q',slot,16)[0]
  position+=1
 else:raise RuntimeError('Native handle probe extent invalid')
 return 0
