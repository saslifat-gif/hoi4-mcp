"""Run the recovery script in real Python subprocesses with simulated Win32 calls.

All profiles, saves and process identities are fixtures in temporary directories.
No actual game process is opened, stopped or modified.
"""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BOOTSTRAP = r'''
import ctypes,json,runpy,subprocess,sys,types
from pathlib import Path
session=Path(sys.argv[1]);case=json.loads(Path(sys.argv[2]).read_text())
calls=[]
class Function:
 def __init__(self,name,result):self.name=name;self.result=result
 def __call__(self,*args):calls.append(self.name);return self.result
kernel=types.SimpleNamespace(**{name:Function(name,case.get(name,default)) for name,default in
 [('OpenProcess',1),('TerminateProcess',1),('WaitForSingleObject',0),('CloseHandle',1)]})
ctypes.WinDLL=lambda *args,**kwargs:kernel
sys.modules['direct_process']=types.SimpleNamespace(process_identity=lambda pid:case['observed_identity'])
subprocess.check_output=lambda *args,**kwargs:case['running']
source=Path(sys.argv[3]);sys.argv=[str(source),str(session)]
try:runpy.run_path(str(source),run_name='__main__')
finally:(session.parent/'simulated-calls.json').write_text(json.dumps(calls))
'''


class OptimizedRecoveryTests(unittest.TestCase):
    def fixture(self, parent):
        root = parent / 'queued-capacity-20261013-1234abcd'
        (root / 'recovery').mkdir(parents=True)
        (root / 'native').mkdir()
        user = parent / 'user'
        (user / 'mod').mkdir(parents=True)
        identity = {'pid': 123, 'created': 456, 'executable': 'fixture/hoi4.exe'}
        session = root / 'session.json'
        session.write_text(json.dumps({'session_id': 'a' * 32, 'mode': 'singleplayer_test',
                                       'process_identity': identity}))
        manifest = []
        for name, original, current in [('settings.txt', b'save_as_binary=yes\nvolume=1\n',
                                         b'save_as_binary=no\nvolume=2\n'),
                                        ('autosave.hoi4', b'original save', b'test save')]:
            backup = root / 'recovery' / name
            backup.write_bytes(original)
            target = user / name
            target.write_bytes(current)
            manifest.append({'path': str(target), 'backup': str(backup),
                             'sha256': hashlib.sha256(original).hexdigest(),
                             'mtime_ns': 1700000000000000000})
        (root / 'recovery' / 'manifest.json').write_text(json.dumps(manifest))
        descriptor = user / 'mod' / 'fixture.mod'
        descriptor.write_bytes(b'fixture descriptor')
        (user / 'dlc_load.json').write_text(json.dumps({'enabled_mods': ['mod/old.mod', 'mod/fixture.mod'],
                                                     'disabled_dlcs': ['preserve-me']}))
        (root / 'activation.json').write_text(json.dumps({'user_root': str(user),
            'descriptor': str(descriptor), 'entry': 'mod/fixture.mod',
            'descriptor_sha256': hashlib.sha256(descriptor.read_bytes()).hexdigest()}))
        ledger = {'session_id': 'a' * 32, 'armed': True,
                  'requests': {'b' * 32: {'kind': 'advisor', 'id': 'GER_test:test', 'slot': 0}}}
        (root / 'native' / 'selection-ledger.json').write_text(json.dumps(ledger))
        (root / 'native' / 'request.txt').write_text('fixture pending request')
        case = {'running': '123', 'observed_identity': identity}
        return session, user, case, ledger['requests']

    def run_script(self, parent, session, case, optimized):
        bootstrap = parent / 'bootstrap.py'
        bootstrap.write_text(BOOTSTRAP)
        case_path = parent / 'case.json'
        case_path.write_text(json.dumps(case))
        command = [sys.executable] + (['-O'] if optimized else [])
        return subprocess.run(command + [str(bootstrap), str(session), str(case_path),
            str(Path(__file__).with_name('restore_queued_capacity_session.py'))],
            capture_output=True, text=True,
            env={**__import__('os').environ, 'PYTHONPATH': str(Path(__file__).parent.parent)})

    def test_success_stops_owned_process_then_restores_without_losing_ids(self):
        for optimized in (False, True):
            with self.subTest(optimized=optimized), tempfile.TemporaryDirectory() as directory:
                parent = Path(directory)
                session, user, case, requests = self.fixture(parent)
                result = self.run_script(parent, session, case, optimized)
                self.assertEqual(result.returncode, 0, result.stderr)
                calls = json.loads((session.parent / 'simulated-calls.json').read_text())
                self.assertEqual(calls, ['OpenProcess', 'TerminateProcess', 'WaitForSingleObject', 'CloseHandle'])
                self.assertEqual((user / 'autosave.hoi4').read_bytes(), b'original save')
                self.assertEqual((user / 'autosave.hoi4').stat().st_mtime_ns, 1700000000000000000)
                self.assertEqual((session.parent / 'private-test-autosave.hoi4').read_bytes(), b'test save')
                self.assertEqual((user / 'settings.txt').read_bytes(), b'save_as_binary=yes\nvolume=2\n')
                ledger = json.loads((session.parent / 'native' / 'selection-ledger.json').read_text())
                self.assertFalse(ledger['armed'])
                self.assertEqual(ledger['requests'], requests)
                self.assertEqual(json.loads((user / 'dlc_load.json').read_text()),
                                 {'enabled_mods': ['mod/old.mod'], 'disabled_dlcs': ['preserve-me']})

    def test_failures_never_restore_while_process_exit_or_backup_is_unverified(self):
        for optimized in (False, True):
            for failure in ('corrupt_backup', 'foreign_pid', 'reused_pid',
                            'OpenProcess', 'TerminateProcess', 'WaitForSingleObject'):
                with self.subTest(optimized=optimized, failure=failure), tempfile.TemporaryDirectory() as directory:
                    parent = Path(directory)
                    session, user, case, _ = self.fixture(parent)
                    if failure == 'corrupt_backup':
                        (session.parent / 'recovery' / 'autosave.hoi4').write_bytes(b'corrupt')
                    elif failure == 'foreign_pid':
                        case['running'] = '999'
                    elif failure == 'reused_pid':
                        case['observed_identity'] = {**case['observed_identity'], 'created': 999}
                    else:
                        case[failure] = 258 if failure == 'WaitForSingleObject' else 0
                    result = self.run_script(parent, session, case, optimized)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertEqual((user / 'autosave.hoi4').read_bytes(), b'test save')
                    self.assertFalse((session.parent / 'recovery-result.json').exists())
                    calls = json.loads((session.parent / 'simulated-calls.json').read_text())
                    if failure in ('corrupt_backup', 'foreign_pid', 'reused_pid'):
                        self.assertEqual(calls, [])
                    if failure in ('TerminateProcess', 'WaitForSingleObject'):
                        self.assertEqual(calls[-1], 'CloseHandle')


if __name__ == '__main__':
    unittest.main()
