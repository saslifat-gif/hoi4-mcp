"""Read the country idea pointer set used by native AddIdea validation.
Native definition names are read through the CIdea name layout; source overlays,
normal costs and advisor/decision/trade outcomes remain unresolved.
"""
import struct
from runtime_gui import GuiSnapshotChanged,decode_std_string
IDEA_SIGNATURES={0x6cf890:'488b81900f0000c3',0x1161b14:'4533c04863405c85c0',0x1161b1f:'488b4d50',0x647e90:'488379200f488d41087603488b00c3',
 0xfcf630:'488b81a00a0000488b4060c3',0xfd5f66:'488d5738',
 0xfcdd56:'488b53284883fa0f',0xfce258:'48399de0000000'}

def read_country_ideas(reader,country,world,identifier=None):
 if identifier is not None and (not isinstance(identifier,str) or not identifier or len(identifier)>159):raise ValueError('Exact idea identifier required')
 r=reader;guards=[]
 def read(address,size):
  data=r.read(address,size)
  if data is None or len(data)!=size:raise RuntimeError('Native idea field unreadable')
  guards.append((address,data));return data
 def ptr(address):return struct.unpack('<Q',read(address,8))[0]
 for rva,code in IDEA_SIGNATURES.items():
  expected=bytes.fromhex(code)
  if read(r.base+rva,len(expected))!=expected:raise RuntimeError('Native idea implementation changed')
 if ptr(r.base+0x332f260)!=world:raise GuiSnapshotChanged('Idea world changed')
 read(country,8)
 if r.typename(country)!='.?AVCCountry@@':raise RuntimeError('Native idea country type mismatch')
 tick=read(world+0x468,4);manager=ptr(country+0xf90)
 array,capacity,count=struct.unpack('<QII',read(manager+0x50,16))
 if not 0<=count<=capacity<=100000:raise RuntimeError('Native idea list extent invalid')
 selected=list(struct.unpack('<'+'Q'*count,read(array,count*8))) if count else []
 pointers=selected
 if identifier is not None:
  # 18d054 constructs CIdeaDatabase; 18d05e stores it in global 332ef30.
  code=bytes.fromhex('488905cb1e1a03')
  if read(r.base+0x18d05e,len(code))!=code:raise RuntimeError('Native idea database binding changed')
  database=ptr(r.base+0x332ef30)
  if ptr(database)!=r.base+0x293c2b0 or r.typename(database)!='.?AVCIdeaDatabase@@':raise RuntimeError('Native idea database type mismatch')
  array,capacity,count=struct.unpack('<QII',read(database+0x68,16))
  if not 1<=count<=capacity<=100000:raise RuntimeError('Native idea database extent invalid')
  pointers=list(struct.unpack('<'+'Q'*count,read(array,count*8)))
 political_power_raw=struct.unpack('<q',read(manager+0xe0,8))[0]
 names=[];ideas=[];seen=set()
 for index,idea in enumerate(pointers):
  header=read(idea,24)
  if identifier is not None and index==0:
   if struct.unpack_from('<Q',header)[0]!=r.base+0x293c510 or struct.unpack_from('<Q',header,16)[0]!=r.base+0x293c560 or r.typename(idea)!='.?AV?$TNullObject@VCIdea@@V1@@@':raise RuntimeError('Native idea database sentinel mismatch')
   continue
  if struct.unpack_from('<Q',header)[0]!=r.base+0x29815e0 or struct.unpack_from('<Q',header,16)[0]!=r.base+0x2981630 or r.typename(idea)!='.?AVCIdea@@':raise RuntimeError('Native idea type mismatch')
  # Secondary vtable slot1 is 647e90: CIdea+16 -> string at subobject+8.
  name=decode_std_string(read,idea+24,159)
  if name['status']!='read' or not name['raw_text']:raise RuntimeError('Native idea name unreadable or invalid')
  key=name['raw_text']
  if identifier is not None and key!=identifier:continue
  if key in seen:raise RuntimeError('Duplicate native idea name')
  # ReplaceIdea compares this exact group; fcf630 follows group+60 for payment.
  group=ptr(idea+0xaa0);category=ptr(group+0x60)
  for address,vtable,kind in ((group,0x2946650,'.?AVCIdeaGroupType@@'),(category,0x2981648,'.?AVCIdeaCategory@@')):
   if ptr(address)!=r.base+vtable or r.typename(address)!=kind:raise RuntimeError('Native idea group/category type mismatch')
  group_name=decode_std_string(read,group+0x38,159);category_name=decode_std_string(read,category+0x10,159)
  if any(x['status']!='read' or not x['raw_text'] for x in (group_name,category_name)):raise RuntimeError('Native idea group/category name invalid')
  resource=struct.unpack('<i',read(category+0x78,4))[0]
  seen.add(key);ideas.append(idea);names.append({'idea_id':key,'native_definition_id':struct.unpack_from('<I',header,8)[0],'selected_for_country':idea in selected,
   'group_id':group_name['raw_text'],'category_id':category_name['raw_text'],'native_cost_resource_type':resource})
 if any(r.read(address,len(data))!=data for address,data in guards):raise GuiSnapshotChanged('Native idea state changed during read')
 return {('idea_pointers' if identifier is None else 'definition_pointers'):ideas,'ideas':names,'native_name_binding_verified':True,'native_tick':struct.unpack('<i',tick)[0],
         'scope':'native_AddIdea_membership' if identifier is None else 'native_idea_database_definition','script_id_binding_verified':False,
         'political_power_raw':political_power_raw,'political_power_scale':100000,
         'cost_verified':False,'process_writes':False,'uses_keyboard_or_mouse':False}

def idea_selection_postcondition(snapshot,requested_pointer,previous_pointer=None):
 if not requested_pointer or previous_pointer==requested_pointer:raise ValueError('Distinct resolved idea pointers required')
 present=requested_pointer in snapshot['idea_pointers']
 previous_absent=None if previous_pointer is None else previous_pointer not in snapshot['idea_pointers']
 return {'requested_idea_present':present,'previous_idea_absent':previous_absent,
         'pointer_membership_verified':present and previous_absent is not False,
         'native_tick':snapshot['native_tick'],'script_id_binding_verified':False,'cost_verified':False}
