"""Compile and exercise the real pause adapter with simulated engine callbacks."""
import pathlib
import shutil
import subprocess
import tempfile
import unittest


class PauseCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.exe = pathlib.Path(cls.temp.name) / 'pause-test'
        source = pathlib.Path(__file__).with_suffix('.c')
        compiler = shutil.which('cc')
        if not compiler:
            raise RuntimeError('A local C compiler is required for the offline pause tests')
        subprocess.run([compiler, '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=address,undefined', str(source), '-o', str(cls.exe)], check=True)

    def check(self, before, desired, mode=0):
        subprocess.run([str(self.exe), str(before), str(desired), str(mode)], check=True)

    def test_pause_uses_initialized_command(self): self.check(0, 1)
    def test_resume_uses_toggle_flag(self): self.check(1, 0)
    def test_already_paused_is_noop(self): self.check(1, 1)
    def test_already_running_is_noop(self): self.check(0, 0)
    def test_null_factory_never_executes(self): self.check(0, 1, 1)
    def test_unreadable_command_never_executes(self): self.check(0, 1, 2)
    def test_wrong_command_type_never_executes(self): self.check(0, 1, 3)


if __name__ == '__main__':
    unittest.main()
