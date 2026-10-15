import struct,unittest
from types import SimpleNamespace
from country_binding import read_country_binding
class CountryBindingTests(unittest.TestCase):
 def setUp(self):
  self.base=0x140000000;self.mem={};self.world=0x100000;self.manager=0x200000;self.node=0x300000;self.country=0x400000
  self.r=SimpleNamespace(base=self.base,read=lambda a,n:bytes(self.mem.get(a+i,0) for i in range(n)),typename=lambda a:'.?AVCCountry@@' if a==self.country else None)
  self.put(self.base+0x332f260,'<Q',self.world);self.put(self.base+0x3330d98,'<Q',self.manager)
  self.put(self.manager+0x78,'<Q',0);self.put(self.manager+0x50,'<Q',0x9999);self.put(self.manager+0x60,'<Q',0x210000)
  self.put(0x210000,'<QQ',self.node,self.node);self.put(self.node+0x10,'<4s',b'SOV\0');self.put(self.node+0x20,'<QQ',3,15);self.put(self.node+0x30,'<i',1)
  self.put(self.manager+0x30,'<Q',0x220000);self.put(self.manager+0x3c,'<i',2);self.put(0x220004,'<i',42)
  self.put(self.world+0x340,'<Q',0x110000);self.put(0x110000+42*4,'<i',5);self.put(self.world+0x310,'<Q',0x120000);self.put(0x120000+5*8,'<Q',self.country)
  self.put(self.country,'<Q',self.base+0x27e7360);self.put(self.country+8,'<i',42)
 def put(self,a,f,*v):self.mem.update((a+i,b) for i,b in enumerate(struct.pack(f,*v)))
 def test_exact_name_native_handle_and_index(self):
  self.assertEqual(read_country_binding(self.r,self.world,'SOV'),{'country_id':self.country,'country_tag':'SOV','native_tag':42,'native_index':5})
 def test_missing_tag_never_uses_first_tag_fallback(self):
  with self.assertRaisesRegex(ValueError,'registered'):read_country_binding(self.r,self.world,'ENG')
 def test_no_inactive_handle(self):
  self.put(0x220004,'<i',0)
  with self.assertRaisesRegex(ValueError,'inactive'):read_country_binding(self.r,self.world,'SOV')
 def test_wrong_country_owner(self):
  self.put(self.country+8,'<i',43)
  with self.assertRaisesRegex(RuntimeError,'identity'):read_country_binding(self.r,self.world,'SOV')
 def test_foreign_world(self):
  with self.assertRaisesRegex(RuntimeError,'world'):read_country_binding(self.r,0x777,'SOV')
 def test_cycle_rejected(self):
  self.put(0x210000,'<QQ',0x666,self.node);self.put(self.node+8,'<Q',self.node)
  with self.assertRaisesRegex(RuntimeError,'chain'):read_country_binding(self.r,self.world,'ENG')
if __name__=='__main__':unittest.main()
