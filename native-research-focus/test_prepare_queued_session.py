"""Preparation routing and failed-backup boundaries, in real optimized subprocesses."""
import json, pathlib, subprocess, sys, tempfile, unittest
SCRIPT=pathlib.Path(__file__).with_name('prepare_queued_capacity_session.py')
BOOT=r"""
import json,pathlib,runpy,shutil,sys,types
source=pathlib.Path(sys.argv[1]); user=pathlib.Path(sys.argv[2]); root=pathlib.Path(sys.argv[3]); fail=sys.argv[4]=='bad'; country=sys.argv[5]
calls=[]
def prepare(game,root,log,country):
 root.mkdir(parents=True); (root/'session.json').write_text('{}');calls.append([str(game),str(root),str(log),country]);return {'session_id':'fixture'}
def activate(sf,user): (user/'activated').write_text(str(sf))
sys.modules['prepare_session']=types.SimpleNamespace(prepare=prepare)
sys.modules['activate_session']=types.SimpleNamespace(activate=activate)
if fail:shutil.copy2=lambda source,target:pathlib.Path(target).write_bytes(b'corrupt')
sys.argv=[str(source),'--game-root',str(user/'game'),'--user-root',str(user),'--session-root',str(root),'--country',country]
try:runpy.run_path(str(source),run_name='__main__')
finally:(user/'calls.json').write_text(json.dumps(calls))
"""
class PrepareTests(unittest.TestCase):
 def run_case(self,optimized=False,bad=False,outside=False,existing=False,country='GER'):
  with tempfile.TemporaryDirectory() as tmp:
   temp=pathlib.Path(tmp);user=temp/'user';(user/'save games').mkdir(parents=True)
   (user/'settings.txt').write_bytes(b'save_as_binary=yes');(user/'save games/autosave.hoi4').write_bytes(b'original')
   base=temp/'runtime';base.mkdir();native=base/'native-research-focus';native.mkdir();source=native/SCRIPT.name;source.write_bytes(SCRIPT.read_bytes())
   root=(temp if outside else base/'sessions')/'queued-capacity-20261013-1234abcd'
   if existing:root.mkdir(parents=True)
   run=subprocess.run([sys.executable,*(['-O'] if optimized else []),'-c',BOOT,str(source),str(user),str(root),'bad' if bad else 'ok',country],capture_output=True,text=True)
   expected_failure=bad or outside or existing
   self.assertEqual(run.returncode!=0,expected_failure,run.stderr)
   self.assertEqual((user/'activated').exists(),not expected_failure)
   self.assertEqual((user/'save games/autosave.hoi4').read_bytes(),b'original')
   if not expected_failure:
    manifest=json.loads((root/'recovery/manifest.json').read_text());self.assertEqual(len(manifest),2)
    self.assertEqual(json.loads((user/'calls.json').read_text())[0][1],str(root.resolve()))
    self.assertEqual(json.loads((user/'calls.json').read_text())[0][3],country)
 def test_explicit_root(self):self.run_case()
 def test_optimized_explicit_root(self):self.run_case(optimized=True)
 def test_italy_country_forwarded(self):self.run_case(country='ITA')
 def test_bad_backup(self):self.run_case(bad=True)
 def test_optimized_bad_backup(self):self.run_case(optimized=True,bad=True)
 def test_outside_root(self):self.run_case(outside=True)
 def test_existing_root(self):self.run_case(existing=True)
if __name__=='__main__':unittest.main()
