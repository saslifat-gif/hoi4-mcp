import struct,unittest
from military_reader import read_unit_ids,ARMY_VTABLE,ARMY_OBJECT_VTABLE
from native_handle import HANDLE_SIGNATURES
from runtime_gui import NativeGuiReader,SUPPORTED_HASH,GuiSnapshotChanged
from test_runtime_gui import FakeProcess

class MilitaryReaderTests(unittest.TestCase):
 def setUp(self):
  self.p=FakeProcess();self.r=NativeGuiReader(self.p,SUPPORTED_HASH)
  self.country=0x25000000;self.world=0x26000000;self.array=0x27000000;self.unit=0x28000000
  self.p.put(self.p.base+0x332f260,struct.pack('<Q',self.world))
  self.p.put(self.country,struct.pack('<QI',self.p.base+0x1000,67));self.r.types[self.p.base+0x1000]='.?AVCCountry@@'
  self.p.put(self.world+0x468,struct.pack('<i',123))
  self.p.put(self.country+0x290,struct.pack('<QII',self.array,1,1));self.p.put(self.array,struct.pack('<Q',self.unit))
  self.r.types[self.p.base+ARMY_VTABLE]='.?AVCArmy@@'
  self.header=struct.pack('<QQQII',self.p.base+ARMY_VTABLE,0,self.p.base+ARMY_OBJECT_VTABLE,51,1)
  self.p.put(self.unit,self.header)
  for address,code in HANDLE_SIGNATURES.items():self.p.put(self.p.base+address,bytes.fromhex(code))
  self.database=0x29000000;self.buckets=0x30000000
  self.p.put(self.p.base+0x3451dc0+51*8,struct.pack('<Q',self.database))
  self.p.put(self.database+8,struct.pack('<Q',self.buckets));self.p.put(self.database+20,struct.pack('<iB',3,1))
  hashed=(((51<<32)+1)*0x49631a45)&0xffffffffffffffff;self.bucket=((hashed>>32)^hashed)&3
  slots=bytearray(5*24);slots[self.bucket*24+4]=1;struct.pack_into('<IIQ',slots,self.bucket*24+8,51,1,self.unit+16);self.p.put(self.buckets,slots)
  self.provinces=0x31000000;self.province=0x32000000
  self.p.put(self.world+0x2b0,struct.pack('<Q',self.provinces));self.p.put(self.world+0x2bc,struct.pack('<i',100))
  self.p.put(self.province+0xa4,struct.pack('<i',10));self.p.put(self.provinces+10*8,struct.pack('<Q',self.province))
  self.p.put(self.unit+0x1e8,struct.pack('<Q',0));self.p.put(self.unit+0x1f0,struct.pack('<Q',self.province));self.p.put(self.unit+0x200,struct.pack('<QII',0,0,0))
 def capture(self):return read_unit_ids(self.r,self.country,self.world)
 def test_id_uses_game_object_subobject_not_zero_primary_padding(self):
  d=self.capture();self.assertEqual(d['units'][0]['unit_id'],'51:1');self.assertEqual(d['count'],1)
  self.assertFalse(d['command_eligibility_verified']);self.assertTrue(d['database_resolution_verified'])
 def test_stale_id_cannot_resolve_to_another_unit(self):
  slots=bytearray(self.p.blocks[self.buckets]);struct.pack_into('<Q',slots,self.bucket*24+16,self.unit+0x100+16);self.p.put(self.buckets,slots)
  with self.assertRaisesRegex(GuiSnapshotChanged,'resolves'):self.capture()
 def test_missing_database_object_is_rejected(self):
  self.p.put(self.p.base+0x3451dc0+51*8,struct.pack('<Q',0))
  with self.assertRaises(GuiSnapshotChanged):self.capture()
 def test_movement_readback_uses_native_province_objects(self):
  self.p.put(self.unit+0x1e8,struct.pack('<Q',self.province));self.p.put(self.unit+0x200,struct.pack('<QII',0x33000000,2,2));self.p.put(0x33000000,struct.pack('<ii',10,10))
  unit=self.capture()['units'][0]
  self.assertEqual((unit['current_province_id'],unit['destination_province_id'],unit['movement_path_count']),(10,10,2))
 def test_order_path_survives_cleared_immediate_destination(self):
  target=0x34000000;path=0x33000000
  self.p.put(target+0xa4,struct.pack('<i',20));self.p.put(self.provinces+20*8,struct.pack('<Q',target))
  self.p.put(self.unit+0x200,struct.pack('<QII',path,4,2));self.p.put(path,struct.pack('<iiii',10,20,99,99))
  unit=self.capture()['units'][0]
  self.assertIsNone(unit['destination_province_id'])
  self.assertEqual(unit['movement_path_province_ids'],[10,20]);self.assertEqual(unit['movement_path_target_province_id'],20)
 def test_invalid_path_extent_is_rejected(self):
  self.p.put(self.unit+0x200,struct.pack('<QII',0x33000000,1,2))
  with self.assertRaisesRegex(RuntimeError,'path extent'):self.capture()
 def test_invalid_path_province_is_rejected(self):
  self.p.put(self.unit+0x200,struct.pack('<QII',0x33000000,1,1));self.p.put(0x33000000,struct.pack('<i',100))
  with self.assertRaisesRegex(RuntimeError,'path province'):self.capture()
 def test_path_mutation_invalidates_snapshot(self):
  path=0x33000000;self.p.put(self.unit+0x200,struct.pack('<QII',path,1,1));self.p.put(path,struct.pack('<i',10))
  original=self.r.read;seen=0
  def read(address,size):
   nonlocal seen
   if address==path:
    seen+=1
    if seen>1:return struct.pack('<i',20)
   return original(address,size)
  self.r.read=read
  with self.assertRaises(GuiSnapshotChanged):self.capture()
 def test_stale_province_pointer_is_rejected(self):
  self.p.put(self.provinces+10*8,struct.pack('<Q',self.province+8))
  with self.assertRaisesRegex(GuiSnapshotChanged,'province'):self.capture()
 def test_empty_list_is_valid(self):
  self.p.put(self.country+0x290,struct.pack('<QII',0,0,0));self.assertEqual(self.capture()['units'],[])
 def test_duplicate_ids_are_rejected(self):
  self.p.put(self.country+0x290,struct.pack('<QII',self.array,2,2));self.p.put(self.array,struct.pack('<QQ',self.unit,self.unit))
  with self.assertRaisesRegex(RuntimeError,'duplicate'):self.capture()
 def test_invalid_extent_is_rejected(self):
  self.p.put(self.country+0x290,struct.pack('<QII',self.array,1,2))
  with self.assertRaisesRegex(RuntimeError,'extent'):self.capture()
 def test_wrong_inherited_vtable_is_rejected(self):
  h=bytearray(self.header);struct.pack_into('<Q',h,16,self.p.base+0x1000);self.p.put(self.unit,h)
  with self.assertRaisesRegex(RuntimeError,'type'):self.capture()
 def test_changed_handle_is_rejected(self):
  original=self.r.read;seen=0
  def read(address,size):
   nonlocal seen
   if address==self.unit and size==32:
    seen+=1
    if seen>1:return self.header[:-4]+struct.pack('<I',2)
   return original(address,size)
  self.r.read=read
  with self.assertRaises(GuiSnapshotChanged):self.capture()
 def test_world_replacement_is_rejected(self):
  self.p.put(self.p.base+0x332f260,struct.pack('<Q',self.world+8))
  with self.assertRaisesRegex(RuntimeError,'world'):self.capture()
 def test_wrong_country_type_is_rejected(self):
  self.r.types[self.p.base+0x1000]='.?AVCTheatre@@'
  with self.assertRaisesRegex(RuntimeError,'country'):self.capture()

if __name__=='__main__':unittest.main()
