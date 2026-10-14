import subprocess,tempfile,shutil,unittest
from pathlib import Path

@unittest.skipUnless(shutil.which('cc'),'C fixture requires a local C compiler')
class WorldTensionWindowTests(unittest.TestCase):
 def test_native_state_change_idempotency_and_failures(self):
  r=Path(__file__).parent
  with tempfile.TemporaryDirectory() as d:
   executable=Path(d)/'world-window'
   subprocess.run(['cc','-fms-extensions','-fsanitize=address,undefined',str(r/'test_world_tension_window.c'),'-o',str(executable)],check=True,capture_output=True)
   subprocess.run([str(executable)],check=True,capture_output=True)
