"""Compile the native JSON boundary with simulated readable-memory inputs."""
import json,shutil,subprocess,tempfile,unittest
from pathlib import Path

@unittest.skipUnless(shutil.which('cc'),'C fixture requires the local C compiler')
class NotificationJsonTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup);cls.exe=Path(cls.tmp.name)/'alert-json'
  source=Path(__file__).with_suffix('.c')
  subprocess.run([shutil.which('cc'),'-std=c11','-fsanitize=address,undefined','-Wno-deprecated-declarations','-I',str(source.parent),str(source),'-o',str(cls.exe)],check=True)
 def test_native_controls_quotes_and_newlines_form_valid_json(self):
  result=subprocess.run([str(self.exe)],capture_output=True,text=True,check=True)
  self.assertEqual(json.loads(result.stdout),'a"b\\c\n\x01')
 def test_length_limit_is_rejected(self):subprocess.run([str(self.exe),'1'],check=True)
 def test_invalid_string_capacity_is_rejected(self):subprocess.run([str(self.exe),'2'],check=True)
 def test_output_overflow_is_rejected(self):subprocess.run([str(self.exe),'3'],check=True)
if __name__=='__main__':unittest.main()
