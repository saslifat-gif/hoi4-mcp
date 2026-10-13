import struct,unittest
from research_reader import decode_technology,read_research,ResearchReadError
class Memory:
 def __init__(self):self.regions={};self.hook=None
 def region(self,a,n):self.regions[a]=bytearray(n)
 def write(self,a,data):
  for start,b in self.regions.items():
   if start<=a and a+len(data)<=start+len(b):b[a-start:a-start+len(data)]=data;return
  raise AssertionError(hex(a))
 def pack(self,a,fmt,value):self.write(a,struct.pack(fmt,value))
 def raw(self,a,n):
  if self.hook:self.hook(a,n)
  for start,b in self.regions.items():
   if start<=a and a+n<=start+len(b):return bytes(b[a-start:a-start+n])
  raise ResearchReadError('Unreadable memory')
class ResearchTests(unittest.TestCase):
 def row(self,**kw):
  args=dict(identifier='test',level=0,max_level=1,points=0,base_cost=100000,cost_factor=11000000,slots=[])
  args.update(kw);return decode_technology(**args)
 def test_completed_reset_is_100_percent(self):
  r=self.row(level=1,points=0);self.assertTrue(r['completed']);self.assertEqual(r['progress_percent'],100)
 def test_native_cost_scale(self):
  r=self.row(points=5500000,slots=[1]);self.assertEqual(r['completion_threshold_raw'],11000000);self.assertEqual(r['progress_percent'],50)
 def test_repeatable_level(self):
  r=self.row(level=2,max_level=5,points=5500000,slots=[2]);self.assertTrue(r['unlocked']);self.assertFalse(r['completed']);self.assertEqual(r['research_target_level'],3)
 def test_repeatable_next_level_available(self):self.assertEqual(self.row(level=2,max_level=5)['state'],'available_next_level')
 def test_unassigned_partial_progress(self):self.assertEqual(self.row(points=1)['state'],'partially_researched')
 def test_engine_override(self):self.assertEqual(self.row(points=50000,slots=[1],override=True)['progress_percent'],50)
 def test_negative_cost_sentinel(self):self.assertIsNone(self.row(base_cost=-100000)['progress_fraction'])
 def test_assigned_negative_cost_rejected(self):
  with self.assertRaises(ResearchReadError):self.row(base_cost=-100000,slots=[1])
 def test_bad_values(self):
  for kw in ({'level':-1},{'max_level':-1},{'points':-1},{'cost_factor':0}):
   with self.assertRaises(ResearchReadError):self.row(**kw)
 def test_completed_active_slot_rejected(self):
  with self.assertRaises(ResearchReadError):self.row(level=1,slots=[1])
 def setUp(self):
  self.mem=Memory();self.base=0x10000000;self.world=0x200000;self.country=0x300000;self.tech=0x400000
  m=self.mem
  for a,n in [(self.base+0x332f260,8),(self.base+0x3332ba0,8),(self.base+0x332f661,1),(self.world,0x500),(self.country,0x1000),(self.tech,0xb0),(0x500000,16),(0x510000,8),(0x520000,16),(0x530000,0x40),(0x600000,0x1f8),(0x610000,0x1f8),(0x700000,0x3e8),(0x710000,0x3e8)]:m.region(a,n)
  for a,v in [(self.base+0x332f260,self.world),(self.country+0xf60,self.tech),(self.tech+0x88,0x500000),(self.tech+0xa0,0x510000),(self.tech+0x40,0x520000),(0x500000,0x600000),(0x500008,0x610000),(0x510000,0x530000),(0x520000,0x610000),(0x530018,0x600000)]:m.pack(a,'<Q',v)
  m.pack(self.base+0x3332ba0,'<q',11000000)
  for a,v in [(self.tech+0x94,2),(self.tech+0xac,1),(self.tech+0x4c,1)]:m.pack(a,'<i',v)
  for j,(model,d,name,level,progress) in enumerate([(0x600000,0x700000,b'new_tech',0,5500000),(0x610000,0x710000,b'old_tech',1,0)]):
   for a,v in [(model,self.base+0x2974ee0),(model+0x158,self.tech),(model+0x160,d),(d,self.base+0x293c2e0)]:m.pack(a,'<Q',v)
   m.pack(model+0x174,'<i',level);m.pack(model+0x198,'<q',progress);m.pack(d+0x38,'<i',j+1);m.pack(d+0x3dc,'<i',1);m.pack(d+0x3e0,'<q',100000);m.write(d+0x40,b'\x01')
   m.write(d+0x10,name+b'\0');m.pack(d+0x20,'<Q',len(name));m.pack(d+0x28,'<Q',15)
 def read(self,**kw):return read_research(self.mem.raw,self.base,self.country,self.world,**kw)
 def test_native_list_and_slot(self):
  r=self.read();self.assertTrue(r['research_read_consistent']);self.assertTrue(r['technologies'][1]['completed']);self.assertEqual(r['research_slots'][0]['progress_percent'],50)
 def test_completion_tick_retries_without_mixed_result(self):
  done=False
  def hook(a,n):
   nonlocal done
   if a==0x600170 and n==8 and not done:
    done=True;self.mem.pack(0x600174,'<i',1);self.mem.pack(0x600198,'<q',0);self.mem.pack(0x530018,'<Q',0);self.mem.pack(0x520008,'<Q',0x600000);self.mem.pack(self.tech+0x4c,'<i',2)
  self.mem.hook=hook;r=self.read();self.assertTrue(r['technologies'][0]['completed']);self.assertEqual(r['technologies'][0]['progress_percent'],100);self.assertIsNone(r['research_slots'][0]['technology'])
 def test_persistent_tick_churn_fails_closed(self):
  tick=0
  def hook(a,n):
   nonlocal tick
   if a==self.world+0x468:tick+=1;self.mem.pack(a,'<i',tick)
  self.mem.hook=hook
  with self.assertRaisesRegex(ResearchReadError,'consistent'):self.read(attempts=2)
 def test_completion_list_disagreement_fails_closed(self):
  self.mem.pack(self.tech+0x4c,'<i',0)
  with self.assertRaisesRegex(ResearchReadError,'consistent'):self.read(attempts=2)
 def test_definition_cost_change_retries(self):
  done=False
  def hook(a,n):
   nonlocal done
   if a==0x7003dc and n==12 and not done:
    done=True;self.mem.pack(0x7003e0,'<q',200000)
  self.mem.hook=hook;r=self.read();self.assertEqual(r['research_slots'][0]['progress_percent'],25)
 def test_changed_world_rejected(self):
  self.mem.pack(self.base+0x332f260,'<Q',1)
  with self.assertRaisesRegex(ResearchReadError,'world changed'):self.read()
 def test_wrong_owner_rejected(self):
  self.mem.pack(0x600158,'<Q',1)
  with self.assertRaisesRegex(ResearchReadError,'ownership'):self.read()
 def test_empty_research_slot(self):
  self.mem.pack(0x530018,'<Q',0);r=self.read();self.assertIsNone(r['research_slots'][0]['progress_percent'])
 def test_unknown_slot_model_rejected(self):
  self.mem.pack(0x530018,'<Q',123)
  with self.assertRaisesRegex(ResearchReadError,'consistent'):self.read(attempts=2)
if __name__=='__main__':unittest.main()
