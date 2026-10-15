"""Build-pinned, read-only country advisor identities and appointment membership."""
import struct
from runtime_gui import GuiSnapshotChanged,decode_std_string

# Country getter, role key getter, role serializer and active-list insertion.
ADVISOR_SIGNATURES={0x6cf2c7:'488b81f00f0000',0x6c00e0:'488d4130c3',
 0x12a5411:'448b4328ba72280000',0x10e9cca:'498d4d58e80dcbffff',
 0xa6af60:'488d4168c3',0xfa658c:'4c8d4648',
 0x6cf890:'488b81900f0000c3',0x10ea13e:'483981f0010000'}

def read_country_advisors(reader,country,world):
 r=reader;guards=[]
 def read(address,size):
  data=r.read(address,size)
  if data is None or len(data)!=size:raise RuntimeError('Native advisor field unreadable')
  guards.append((address,data));return data
 def ptr(address):return struct.unpack('<Q',read(address,8))[0]
 def typed(address,vtable,kind):
  value=ptr(address)
  if (vtable is not None and value!=r.base+vtable) or r.typename(address)!=kind:raise RuntimeError('Native advisor object type mismatch')
 def name(address):
  value=decode_std_string(read,address,159)
  if value['status']!='read' or not value['raw_text']:raise RuntimeError('Native advisor identity unreadable or empty')
  return value['raw_text']
 def array(address):
  data,capacity,count=struct.unpack('<QII',read(address,16))
  if not 0<=count<=capacity<=10000:raise RuntimeError('Native advisor list extent invalid')
  values=list(struct.unpack('<'+'Q'*count,read(data,8*count))) if count else []
  if len(set(values))!=count:raise RuntimeError('Duplicate native advisor pointer')
  return values
 for rva,code in ADVISOR_SIGNATURES.items():
  expected=bytes.fromhex(code)
  if read(r.base+rva,len(expected))!=expected:raise RuntimeError('Native advisor implementation changed')
 if ptr(r.base+0x332f260)!=world:raise GuiSnapshotChanged('Advisor world changed')
 typed(country,None,'.?AVCCountry@@');tag=read(country+8,4);tick=read(world+0x468,4)
 manager=ptr(country+0xff0);typed(manager,0x298ae18,'.?AVCCountryCharacters@@')
 if ptr(manager+8)!=country:raise RuntimeError('Native advisor country binding mismatch')
 listed=array(manager+0x40);active=array(manager+0x58);rows=[];seen=set()
 politics=ptr(country+0xf90)
 pp=struct.unpack('<q',read(politics+0xe0,8))[0]
 cp=struct.unpack('<q',read(country+0x1f0,8))[0]
 for role in dict.fromkeys(listed+active):
  typed(role,0x29a7d60,'.?AVCAdvisor@@');character=ptr(role+0x10)
  typed(character,0x297ea60,'.?AVCCharacter@@')
  if read(character+0x68,4)!=tag:raise RuntimeError('Native advisor character owner mismatch')
  character_id=name(character+0x48);role_id=name(role+0x30);key=(character_id,role_id)
  if key in seen:raise RuntimeError('Duplicate native advisor identity')
  seen.add(key)
  rows.append({'character_id':character_id,'role_id':role_id,
   'native_slot_code':struct.unpack('<I',read(role+0x28,4))[0],
   'listed_for_country':role in listed,'active':role in active})
 if any(r.read(address,len(data))!=data for address,data in guards):raise GuiSnapshotChanged('Native advisor state changed during read')
 return {'advisors':rows,'native_tick':struct.unpack('<i',tick)[0],
  'political_power_raw':pp,'command_power_raw':cp,
  'listed_count':len(listed),'active_count':len(active),'native_identity_verified':True,
  'scope':'native_country_advisor_membership','slot_names_verified':False,
  'runtime_availability_verified':False,'cost_verified':False,
  'process_writes':False,'uses_keyboard_or_mouse':False}
