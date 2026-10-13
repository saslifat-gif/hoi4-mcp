import json,unittest
from unittest.mock import Mock,patch
from time_controller import read_native_json

class NativeStatusReadTests(unittest.TestCase):
 def test_transient_replace_conflict_reads_latest_json(self):
  p=Mock();p.read_text.side_effect=[PermissionError(13,'sharing conflict'),'{"paused":true}']
  with patch('time_controller.time.sleep') as sleep:
   self.assertEqual(read_native_json(p),{'paused':True});sleep.assert_called_once_with(.02)
 def test_permanent_denial_remains_visible_and_bounded(self):
  p=Mock();p.read_text.side_effect=PermissionError(13,'denied')
  with patch('time_controller.time.sleep') as sleep:
   with self.assertRaises(PermissionError):read_native_json(p)
   self.assertEqual(p.read_text.call_count,6);self.assertEqual(sleep.call_count,5)
 def test_malformed_json_is_not_silently_retried(self):
  p=Mock();p.read_text.return_value='{'
  with patch('time_controller.time.sleep') as sleep:
   with self.assertRaises(json.JSONDecodeError):read_native_json(p)
   sleep.assert_not_called()
if __name__=='__main__':unittest.main()
