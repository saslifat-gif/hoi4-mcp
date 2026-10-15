"""Simulated native-memory regressions, not live appointment tests."""
import struct,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from runtime_gui import NativeGuiReader,SUPPORTED_HASH,GuiSnapshotChanged
from test_runtime_gui import FakeProcess
from advisor_reader import read_country_advisors,ADVISOR_SIGNATURES
from native_controller import NativeController

class AdvisorReaderTests(unittest.TestCase):
 def setUp(self):
  self.p=FakeProcess();self.r=NativeGuiReader(self.p,SUPPORTED_HASH)
  self.country=0x30000000;self.world=0x31000000;self.manager=0x32000000
  for address,code in ADVISOR_SIGNATURES.items():self.p.put(self.p.base+address,bytes.fromhex(code))
  self.putq(self.p.base+0x332f260,self.world);self.p.put(self.world+0x468,struct.pack('<i',123))
  self.typed(self.country,0x1000,'.?AVCCountry@@');self.p.put(self.country+8,struct.pack('<I',1))
  self.putq(self.country+0xff0,self.manager);self.typed(self.manager,0x298ae18,'.?AVCCountryCharacters@@');self.putq(self.manager+8,self.country)
  self.politics=0x37000000;self.putq(self.country+0xf90,self.politics)
  self.p.put(self.politics+0xe0,struct.pack('<q',17500000));self.p.put(self.country+0x1f0,struct.pack('<q',5000000))
  self.role=0x33000000;self.character=0x34000000
  self.make_role(self.role,self.character,'GER_ernst_udet','ernst_udet',16)
  self.array(0x40,[self.role]);self.array(0x58,[])
 def putq(self,address,value):self.p.put(address,struct.pack('<Q',value))
 def typed(self,address,vtable,kind):
  self.putq(address,self.p.base+vtable);self.r.types[self.p.base+vtable]=kind
 def array(self,field,values):
  address=0x35000000+field*0x100
  self.p.put(self.manager+field,struct.pack('<QII',address,len(values),len(values)))
  self.p.put(address,struct.pack('<'+'Q'*len(values),*values))
 def make_role(self,role,character,character_id,role_id,slot):
  self.typed(role,0x29a7d60,'.?AVCAdvisor@@');self.putq(role+0x10,character)
  self.typed(character,0x297ea60,'.?AVCCharacter@@');self.p.put(character+0x68,struct.pack('<I',1))
  self.p.put_string(character+0x48,character_id,character+0x1000)
  self.p.put_string(role+0x30,role_id,role+0x1000);self.p.put(role+0x28,struct.pack('<I',slot))
 def read(self):return read_country_advisors(self.r,self.country,self.world)
 def test_separate_character_and_role_ids_without_eligibility_claim(self):
  d=self.read();self.assertEqual(d['advisors'],[{'character_id':'GER_ernst_udet','role_id':'ernst_udet','native_slot_code':16,'listed_for_country':True,'active':False}])
  self.assertTrue(d['native_identity_verified']);self.assertFalse(d['runtime_availability_verified']);self.assertFalse(d['cost_verified'])
  self.assertFalse(d['slot_names_verified']);self.assertFalse(d['process_writes']);self.assertEqual(d['native_tick'],123)
  self.assertEqual(d['political_power_raw'],17500000);self.assertEqual(d['command_power_raw'],5000000)
 def test_active_membership_is_separate_and_accepts_empty_lists(self):
  self.array(0x58,[self.role]);d=self.read();self.assertEqual(d['active_count'],1);self.assertTrue(d['advisors'][0]['active'])
  self.array(0x40,[]);self.assertFalse(self.read()['advisors'][0]['listed_for_country'])
  self.array(0x58,[]);self.assertEqual(self.read()['advisors'],[])
 def test_heap_ids_multiple_roles_and_unknown_slots_are_preserved(self):
  self.make_role(0x36000000,self.character,'GER_ernst_udet','another_long_advisor_role',42)
  self.array(0x40,[self.role,0x36000000]);d=self.read()['advisors']
  self.assertEqual(d[1]['role_id'],'another_long_advisor_role');self.assertEqual(d[1]['native_slot_code'],42)
 def test_foreign_owner_and_wrong_manager_are_rejected(self):
  self.p.put(self.character+0x68,struct.pack('<I',2))
  with self.assertRaisesRegex(RuntimeError,'owner'):self.read()
  self.putq(self.manager+8,self.country+8)
  with self.assertRaisesRegex(RuntimeError,'binding'):self.read()
 def test_duplicate_pointer_and_identity_are_rejected(self):
  self.array(0x40,[self.role,self.role])
  with self.assertRaisesRegex(RuntimeError,'Duplicate'):self.read()
  self.make_role(0x36000000,self.character,'GER_ernst_udet','ernst_udet',16);self.array(0x40,[self.role,0x36000000])
  with self.assertRaisesRegex(RuntimeError,'identity'):self.read()
 def test_layout_extent_type_and_missing_name_fail_closed(self):
  for address,value,pattern in ((self.p.base+0x6c00e0,b'\0'*5,'implementation'),(self.manager+0x40,struct.pack('<QII',0,1,2),'extent'),(self.role,struct.pack('<Q',0),'type'),(self.role+0x30,b'\0'*32,'identity')):
   old=self.p.blocks[address];self.p.put(address,value)
   with self.assertRaisesRegex(RuntimeError,pattern):self.read()
   self.p.put(address,old)
 def test_snapshot_mutations_are_rejected(self):
  original=self.r.read
  for address in (self.p.base+0x332f260,self.world+0x468,self.country+0xff0,self.manager+0x58,self.character+0x68,self.role+0x30,self.country+0xf90,self.politics+0xe0,self.country+0x1f0):
   seen=0
   def read(where,size):
    nonlocal seen
    data=original(where,size)
    if where==address:
     seen+=1
     if seen>1:return bytes([data[0]^1])+data[1:]
    return data
   self.r.read=read
   with self.assertRaises((GuiSnapshotChanged,RuntimeError)):self.read()
  self.r.read=original

class AdvisorControllerTests(unittest.TestCase):
 def test_adapter_guards_process_and_closes_on_success_or_read_failure(self):
  with tempfile.TemporaryDirectory() as directory:
   Path(directory,'hoi4.exe').write_bytes(b'fixture')
   c=NativeController.__new__(NativeController)
   c.config={'game_root':directory,'process_identity':{},'session_id':'test-session'}
   c.check=Mock(return_value={'country':'0x30000000','world':'0x31000000'})
   with patch('runtime_gui.WindowsProcess') as process,patch('runtime_gui.NativeGuiReader') as reader,patch('advisor_reader.read_country_advisors') as snapshot:
    snapshot.return_value={'advisors':[]};result=c.advisor_snapshot()
    self.assertEqual(result,{'advisors':[],'session_id':'test-session'})
    snapshot.assert_called_once_with(reader.return_value,0x30000000,0x31000000)
    process.return_value.guard.assert_called_once();process.return_value.close.assert_called_once()
    process.reset_mock();snapshot.side_effect=GuiSnapshotChanged('fixture changed')
    with self.assertRaises(GuiSnapshotChanged):c.advisor_snapshot()
    process.return_value.close.assert_called_once();process.return_value.guard.assert_not_called()

if __name__=='__main__':unittest.main()
