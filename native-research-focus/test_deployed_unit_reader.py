import struct,unittest
from types import SimpleNamespace
from unittest.mock import patch
from deployed_unit_reader import read_deployed_unit
from runtime_gui import GuiSnapshotChanged
class DeployedUnitTests(unittest.TestCase):
 def setUp(self):
  self.base=0x140000000;self.mem={};self.unit=0x100000;self.template=0x110000
  self.put(self.unit,'<Q',self.base+0x295a2b0);self.put(self.unit+0x10,'<Q',self.base+0x295a490);self.put(self.unit+0x1d8,'<I',1);self.put(self.unit+0x3b8,'<Q',self.template)
  self.put(self.template,'<Q',self.base+0x294f5b0);self.put(self.template+8,'<II',4714,4000);self.put(self.template+0x1ec,'<I',1)
  self.put(self.unit+0x350,'<QII',0x200000,1,1);self.put(0x200000,'<QQq',0x12345,0,91000000)
  self.put(self.unit+0x3e0,'<QII',0x210000,1,1);self.put(0x210000,'<Ii',1,9600)
  self.r=SimpleNamespace(base=self.base,read=self.read,typename=lambda address:'.?AVCReferencedDivisionTemplate@@')
  self.ids={(4713,3966):self.unit+0x10,(4714,4000):self.template}
 def put(self,address,fmt,*v):self.mem.update((address+i,b) for i,b in enumerate(struct.pack(fmt,*v)))
 def read(self,address,size):
  try:return bytes(self.mem[address+i] for i in range(size))
  except KeyError:return None
 def capture(self,unit_id='4713:3966'):
  inventory={'units':[{'unit_id':'4713:3966','current_province_id':6334}],'country_tag_native':1,'native_tick':10}
  with patch('deployed_unit_reader.read_unit_ids',return_value=inventory),patch('deployed_unit_reader.resolve_native_handle',side_effect=lambda base,read,*words:self.ids.get(words,0)):return read_deployed_unit(self.r,0x300000,0x400000,unit_id)
 def test_dynamic_ids_resources_and_correct_manpower_offset(self):
  d=self.capture();self.assertEqual(d['template_id'],'4714:4000');self.assertEqual(d['equipment'][0]['quantity_raw'],91000000);self.assertEqual(d['manpower'],9600);self.assertFalse(d['resource_identity_matches_source_verified'])
 def test_not_country_owned_rejects(self):
  with self.assertRaises(ValueError):self.capture('4713:4000')
 def test_stale_template_rejects(self):
  self.ids[4714,4000]=self.unit
  with self.assertRaises(GuiSnapshotChanged):self.capture()
 def test_wrong_owner_and_bad_extent_reject(self):
  self.put(self.template+0x1ec,'<I',2)
  with self.assertRaises(RuntimeError):self.capture()
  self.put(self.template+0x1ec,'<I',1);self.put(self.unit+0x350,'<QII',0x200000,1,2)
  with self.assertRaises(RuntimeError):self.capture()
if __name__=='__main__':unittest.main()
