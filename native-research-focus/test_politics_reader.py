import struct,unittest
from runtime_gui import NativeGuiReader,SUPPORTED_HASH,GuiSnapshotChanged
from test_runtime_gui import FakeProcess
from politics_reader import read_country_ideas,idea_selection_postcondition,IDEA_SIGNATURES

class PoliticsReaderTests(unittest.TestCase):
 def setUp(self):
  self.p=FakeProcess();self.r=NativeGuiReader(self.p,SUPPORTED_HASH)
  self.country=0x25000000;self.world=0x26000000;self.manager=0x27000000;self.array=0x28000000
  self.p.put(self.p.base+0x332f260,struct.pack('<Q',self.world));self.p.put(self.world+0x468,struct.pack('<i',123))
  self.p.put(self.country,struct.pack('<Q',self.p.base+0x1000));self.r.types[self.p.base+0x1000]='.?AVCCountry@@'
  self.p.put(self.country+0xf90,struct.pack('<Q',self.manager))
  self.p.put(self.manager+0xe0,struct.pack('<q',12345678))
  self.p.put(self.manager+0x50,struct.pack('<QII',self.array,2,2));self.p.put(self.array,struct.pack('<QQ',0x30000000,0x31000000))
  for address,code in IDEA_SIGNATURES.items():self.p.put(self.p.base+address,bytes.fromhex(code))
  self.r.types[self.p.base+0x29815e0]='.?AVCIdea@@'
  self.r.types[self.p.base+0x2946650]='.?AVCIdeaGroupType@@';self.r.types[self.p.base+0x2981648]='.?AVCIdeaCategory@@'
  self.group=0x39000000;self.category=0x3a000000
  self.p.put(self.group,struct.pack('<Q',self.p.base+0x2946650));self.p.put(self.group+0x60,struct.pack('<Q',self.category))
  self.p.put(self.category,struct.pack('<Q',self.p.base+0x2981648));self.p.put(self.category+0x78,struct.pack('<i',0))
  self.name(self.group+0x20,'trade_laws');self.name(self.category-8,'government')
  for i,address in enumerate((0x30000000,0x31000000)):
   self.p.put(address+0xaa0,struct.pack('<Q',self.group))
   self.p.put(address,struct.pack('<QIIQ',self.p.base+0x29815e0,i+1,0,self.p.base+0x2981630))
   self.name(address,('limited_exports','sour_loser')[i])
 def name(self,address,text):
  raw=text.encode();self.p.put(address+24,raw.ljust(16,b'\0')+struct.pack('<QQ',len(raw),15))
 def read(self):return read_country_ideas(self.r,self.country,self.world)
 def test_native_membership_checks_requested_and_previous_pointers(self):
  result=self.read();self.assertEqual(result['idea_pointers'],[0x30000000,0x31000000])
  self.assertTrue(idea_selection_postcondition(result,0x30000000,0x32000000)['pointer_membership_verified'])
  self.assertFalse(idea_selection_postcondition(result,0x30000000,0x31000000)['pointer_membership_verified'])
  self.assertFalse(idea_selection_postcondition(result,0x32000000)['pointer_membership_verified'])
  self.assertFalse(result['script_id_binding_verified']);self.assertFalse(result['cost_verified'])
  self.assertEqual([x['idea_id'] for x in result['ideas']],['limited_exports','sour_loser']);self.assertTrue(result['native_name_binding_verified'])
 def database(self):
  database=0x35000000;array=0x36000000;null=0x37000000;extra=0x38000000
  self.p.put(self.p.base+0x18d05e,bytes.fromhex('488905cb1e1a03'))
  self.p.put(self.p.base+0x332ef30,struct.pack('<Q',database));self.p.put(database,struct.pack('<Q',self.p.base+0x293c2b0));self.r.types[self.p.base+0x293c2b0]='.?AVCIdeaDatabase@@'
  self.p.put(null,struct.pack('<QQQ',self.p.base+0x293c510,357,self.p.base+0x293c560));self.r.types[self.p.base+0x293c510]='.?AV?$TNullObject@VCIdea@@V1@@@'
  self.p.put(extra,struct.pack('<QIIQ',self.p.base+0x29815e0,777,0,self.p.base+0x2981630));self.name(extra,'war_economy')
  self.p.put(extra+0xaa0,struct.pack('<Q',self.group))
  self.p.put(database+0x68,struct.pack('<QII',array,4,4));self.p.put(array,struct.pack('<QQQQ',null,0x30000000,0x31000000,extra))
  return database,array,extra
 def test_exact_database_lookup_distinguishes_unselected_idea(self):
  self.database();d=read_country_ideas(self.r,self.country,self.world,'war_economy')
  self.assertEqual(d['scope'],'native_idea_database_definition');self.assertNotIn('idea_pointers',d)
  self.assertEqual(d['definition_pointers'],[0x38000000]);self.assertFalse(d['ideas'][0]['selected_for_country'])
  self.assertEqual(read_country_ideas(self.r,self.country,self.world,'missing')['ideas'],[])
  self.assertTrue(read_country_ideas(self.r,self.country,self.world,'limited_exports')['ideas'][0]['selected_for_country'])
 def test_database_duplicate_name_and_sentinel_are_rejected(self):
  database,array,extra=self.database();self.name(extra,'limited_exports')
  with self.assertRaisesRegex(RuntimeError,'Duplicate'):read_country_ideas(self.r,self.country,self.world,'limited_exports')
  self.p.put(array,struct.pack('<QQQQ',0x30000000,0x30000000,0x31000000,extra))
  with self.assertRaisesRegex(RuntimeError,'sentinel'):read_country_ideas(self.r,self.country,self.world,'war_economy')
 def test_database_binding_change_invalidates_snapshot(self):
  self.database();original=self.r.read;seen=0
  def read(address,size):
   nonlocal seen
   if address==self.p.base+0x332ef30:
    seen+=1
    if seen>1:return struct.pack('<Q',0)
   return original(address,size)
  self.r.read=read
  with self.assertRaises(GuiSnapshotChanged):read_country_ideas(self.r,self.country,self.world,'war_economy')
 def test_native_groups_and_political_power_do_not_claim_computed_cost(self):
  d=self.read();idea=d['ideas'][0]
  self.assertEqual((idea['group_id'],idea['category_id'],idea['native_cost_resource_type']),('trade_laws','government',0))
  self.assertEqual(d['political_power_raw'],12345678);self.assertEqual(d['political_power_scale'],100000);self.assertFalse(d['cost_verified'])
 def test_heap_group_name_and_unknown_resource_type_are_preserved(self):
  raw=b'mobilization_laws';heap=0x3b000000
  self.p.put(self.group+0x38,struct.pack('<QQQQ',heap,0,len(raw),31));self.p.put(heap,raw)
  self.p.put(self.category+0x78,struct.pack('<i',42))
  d=self.read()['ideas'][0];self.assertEqual(d['group_id'],raw.decode());self.assertEqual(d['native_cost_resource_type'],42)
 def test_group_and_category_types_and_names_are_not_guessed(self):
  for address in (self.group,self.category):
   original=self.p.blocks[address];self.p.put(address,struct.pack('<Q',0))
   with self.assertRaisesRegex(RuntimeError,'type'):self.read()
   self.p.put(address,original)
  self.name(self.group+0x20,'')
  with self.assertRaisesRegex(RuntimeError,'name'):self.read()
 def test_group_binding_or_balance_change_invalidates_snapshot(self):
  original=self.r.read
  for address,size in ((0x30000000+0xaa0,8),(self.group+0x60,8),(self.category+0x78,4),(self.manager+0xe0,8)):
   seen=0
   def read(where,count):
    nonlocal seen
    data=original(where,count)
    if where==address and count==size:
     seen+=1
     if seen>1:return bytes([data[0]^1])+data[1:]
    return data
   self.r.read=read
   with self.assertRaises((GuiSnapshotChanged,RuntimeError)):self.read()
  self.r.read=original
 def test_heap_native_name_is_read_exactly(self):
  raw=b'GER_test_long_native_idea';heap=0x33000000
  self.p.put(0x30000000+24,struct.pack('<QQQQ',heap,0,len(raw),31));self.p.put(heap,raw)
  self.assertEqual(self.read()['ideas'][0]['idea_id'],raw.decode())
 def test_duplicate_and_empty_names_are_rejected(self):
  self.name(0x31000000,'limited_exports')
  with self.assertRaisesRegex(RuntimeError,'Duplicate'):self.read()
  self.name(0x31000000,'')
  with self.assertRaisesRegex(RuntimeError,'name'):self.read()
 def test_wrong_idea_subobject_is_rejected(self):
  header=bytearray(self.p.blocks[0x30000000]);struct.pack_into('<Q',header,16,self.p.base+0x2981638);self.p.put(0x30000000,header)
  with self.assertRaisesRegex(RuntimeError,'type'):self.read()
 def test_name_change_invalidates_snapshot(self):
  original=self.r.read;seen=0
  def read(address,size):
   nonlocal seen
   data=original(address,size)
   if address==0x30000000+24:
    seen+=1
    if seen>1:return b'X'+data[1:]
   return data
  self.r.read=read
  with self.assertRaisesRegex(RuntimeError,'name'):self.read()
 def test_empty_native_list_is_not_a_success(self):
  self.p.put(self.manager+0x50,struct.pack('<QII',0,0,0))
  self.assertFalse(idea_selection_postcondition(self.read(),0x30000000)['pointer_membership_verified'])
 def test_world_replacement_and_changed_layout_are_rejected(self):
  self.p.put(self.p.base+0x332f260,struct.pack('<Q',0))
  with self.assertRaises(GuiSnapshotChanged):self.read()
  self.p.put(self.p.base+0x332f260,struct.pack('<Q',self.world));self.p.put(self.p.base+0x6cf890,b'\0'*8)
  with self.assertRaisesRegex(RuntimeError,'implementation'):self.read()
 def test_invalid_count_is_rejected(self):
  self.p.put(self.manager+0x50,struct.pack('<QII',self.array,1,2))
  with self.assertRaisesRegex(RuntimeError,'extent'):self.read()
 def test_changing_manager_binding_is_rejected(self):
  original=self.r.read;seen=0
  def read(address,size):
   nonlocal seen
   if address==self.country+0xf90:
    seen+=1
    if seen>1:return struct.pack('<Q',self.manager+8)
   return original(address,size)
  self.r.read=read
  with self.assertRaises(GuiSnapshotChanged):self.read()

if __name__=='__main__':unittest.main()
