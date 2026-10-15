import tempfile,unittest
from pathlib import Path
from save_paths import owned_save_path
class SavePathTests(unittest.TestCase):
 def test_native_relative_path_uses_user_write_root(self):
  with tempfile.TemporaryDirectory() as d:
   self.assertEqual(owned_save_path(d,'save games/mcp_test_123.hoi4','mcp_test_123'),(Path(d)/'save games/mcp_test_123.hoi4').resolve())
 def test_exact_absolute_owned_path(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'save games/folder/mcp_test_123.hoi4';self.assertEqual(owned_save_path(d,str(p),'mcp_test_123'),p.resolve())
 def test_traversal_other_root_and_wrong_name_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   for p in ['save games/../mcp_test_123.hoi4','other/mcp_test_123.hoi4',str(Path(d)/'mcp_test_123.hoi4'),'save games/other.hoi4']:
    with self.assertRaises(ValueError):owned_save_path(d,p,'mcp_test_123')
if __name__=='__main__':unittest.main()
