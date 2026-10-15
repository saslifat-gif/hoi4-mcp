"""PE fixtures and pre-attachment failures; never loads a module into a game."""
import hashlib,json,struct,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import attach_native_probe as loader

class LoaderTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);self.session=self.root/'session.json'
  self.ident={'pid':123,'created':456,'executable':'hoi4.exe'}
  self.session.write_text(json.dumps({'country':'GER','mode':'singleplayer_test','session_id':'a'*32,'process_identity':self.ident}))
  self.dll=self.root/'probe.dll';self.dll.write_bytes(b'fixture')
 def attach(self,identity,digest):
  with patch.object(loader,'os',SimpleNamespace(name='nt')),patch.object(loader,'verify_sources'),patch.object(loader,'process_identity',return_value=identity):
   loader.attach(self.session,self.dll,digest)
 def test_changed_process_does_not_publish_binding(self):
  with self.assertRaisesRegex(RuntimeError,'process changed'):self.attach({'pid':123,'created':999},hashlib.sha256(b'fixture').hexdigest())
  self.assertFalse((self.root/'session-id.txt').exists())
 def test_native_country_binding_is_immutable(self):
  loader.bind_native_files(self.root,'a'*32,'ITA')
  self.assertEqual((self.root/'country-code.txt').read_bytes(),b'ITA')
  loader.bind_native_files(self.root,'a'*32,'ITA')
  with self.assertRaisesRegex(RuntimeError,'not overwritten'):loader.bind_native_files(self.root,'a'*32,'GER')
  self.assertEqual((self.root/'country-code.txt').read_bytes(),b'ITA')
 def test_changed_module_does_not_publish_binding(self):
  with self.assertRaisesRegex(RuntimeError,'Pinned native module changed'):self.attach(self.ident,'0'*64)
  self.assertFalse((self.root/'session-id.txt').exists())
 def test_invalid_pe_signature_rejected(self):
  raw=bytearray((Path(loader.__file__).parent/'hoi4-native-probe.dll').read_bytes())
  pe=struct.unpack_from('<I',raw,0x3c)[0];raw[pe:pe+4]=b'BAD!';self.dll.write_bytes(raw)
  with self.assertRaisesRegex(ValueError,'PE32'):loader.export_rva(self.dll,'Initialize')
 def test_bundled_module_exports_are_readable(self):
  for name in ('probe','selection','choices','time'):
   path=Path(loader.__file__).parent/('hoi4-native-'+name+'.dll')
   with self.subTest(module=name):self.assertGreater(loader.export_rva(path,'Initialize'),0)

if __name__=='__main__':unittest.main()
