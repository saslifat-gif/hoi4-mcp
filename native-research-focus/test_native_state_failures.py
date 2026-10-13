"""Simulated Windows API failures; not live native-reading verification."""
import ctypes,json,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import read_native_state as reader
import test_research_reader as fixtures

class StateFailureTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);self.session=self.root/'session.json'
  self.ident={'pid':123,'created':456,'executable':'hoi4.exe'}
  self.session.write_text(json.dumps({'session_id':'a'*32,'process_identity':self.ident}))
  native=self.root/'native';native.mkdir()
  (native/'native-observation.json').write_text(json.dumps({'session_id':'a'*32,'pid':123,'country_tag':1,'focus_tree':'0x100','focus_progress':'0x200','country':'0x300','world':'0x400'}))
  self.kernel=Mock();self.kernel.CreateToolhelp32Snapshot.return_value=10
  self.kernel.Module32FirstW.return_value=1;self.kernel.OpenProcess.return_value=20
 def read(self,identity=None):
  with patch.object(reader,'process_identity',return_value=self.ident if identity is None else identity),patch.object(ctypes,'WinDLL',return_value=self.kernel,create=True):
   return reader.read_state(self.session)
 def test_changed_process_never_opens_memory(self):
  with self.assertRaisesRegex(RuntimeError,'before snapshot'):self.read({'pid':123,'created':999})
  self.kernel.OpenProcess.assert_not_called()
 def test_module_lookup_failure_closes_snapshot(self):
  self.kernel.Module32FirstW.return_value=0
  with self.assertRaisesRegex(RuntimeError,'module'):self.read()
  self.kernel.CloseHandle.assert_called_once_with(10)
  self.kernel.OpenProcess.assert_not_called()
 def test_failed_memory_read_closes_process(self):
  self.kernel.ReadProcessMemory.return_value=0
  with self.assertRaisesRegex(RuntimeError,'unreadable'):self.read()
  self.assertEqual(self.kernel.CloseHandle.call_args_list[-1].args,(20,))
 def test_active_focus_uses_one_observation_during_change(self):
  memory=fixtures.Memory();base=0x10000000
  for address,size in [(0x100,0x80),(0x200,0x80),(0x300,0x20),(0x500,16),(0x600,8),(0x1000,0x200),(0x2000,0x200)]:memory.region(address,size)
  for address,value in [(0x100,base+0x2739bb8),(0x130,0x500),(0x240,0x600),(0x500,0x1000),(0x508,0x2000),(0x600,0x1000)]:memory.pack(address,'<Q',value)
  memory.pack(0x13c,'<i',2);memory.pack(0x24c,'<i',1);memory.pack(0x308,'<i',1)
  for address,name in [(0x1000,b'first'),(0x2000,b'second')]:
   memory.pack(address,'<Q',base+0x2739c08);memory.pack(address+0x160,'<Q',0x100)
   memory.write(address+0x18,name);memory.pack(address+0x28,'<Q',len(name));memory.pack(address+0x30,'<Q',15)
  reads=[]
  def read_memory(handle,address,buffer,size,got):
   if address==0x210:
    reads.append(address);data=struct.pack('<Q',0x2000 if len(reads)==1 else 0)
   else:data=memory.raw(address,size)
   ctypes.memmove(buffer,data,size);got._obj.value=size;return 1
  def module(handle,pointer):pointer._obj.modBaseAddr=base;return 1
  self.kernel.Module32FirstW.side_effect=module;self.kernel.ReadProcessMemory.side_effect=read_memory
  with patch.object(reader,'read_research',return_value={}):result=self.read()
  self.assertEqual(result['active_focus'],'second')
  self.assertEqual(result['completed_focuses'],['first'])
  self.assertEqual(len(reads),1)

if __name__=='__main__':unittest.main()
