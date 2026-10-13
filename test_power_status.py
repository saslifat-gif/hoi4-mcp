import ctypes,unittest
from unittest.mock import Mock,patch
from direct_process import require_ac_power

class PowerTests(unittest.TestCase):
 def check(self,ac,success=1):
  def read(pointer):
   value=pointer._obj
   self.assertEqual(ctypes.sizeof(value),12)
   value.ac=ac;value.percent=88
   return success
  kernel=Mock();kernel.GetSystemPowerStatus.side_effect=read
  with patch.object(ctypes,'WinDLL',return_value=kernel,create=True):
   return require_ac_power()
 def test_ac_status(self):
  self.assertEqual(self.check(1),{'external_power':True,'battery_percent':88})
 def test_disconnected_or_unknown_rejected(self):
  for ac in (0,255):
   with self.subTest(ac=ac),self.assertRaisesRegex(RuntimeError,'disconnected'):self.check(ac)
 def test_native_query_failure_is_observable(self):
  with self.assertRaisesRegex(RuntimeError,'unavailable'):self.check(1,0)

if __name__=='__main__':unittest.main()
