import hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path[:0]=[str(Path(__file__).parent),str(Path(__file__).parent.parent)]
import native_controller as nc
class NativeTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.native=self.root/'native';self.native.mkdir()
  self.ident={'pid':123,'created':456,'executable':'hoi4.exe'};self.sid='a'*32
  self.sf=self.root/'session.json';self.sf.write_text(json.dumps({'country':'GER','mode':'singleplayer_test','session_id':self.sid,'process_identity':self.ident}))
  self.original=nc.DLL_SHA;nc.DLL_SHA=hashlib.sha256(b'fixture').hexdigest();(self.native/'hoi4-native-selection.dll').write_bytes(b'fixture')
  self.obs={'pid':123,'session_id':self.sid,'selection_commands_enabled':True,'world':'0x1'};self.observation()
  self.c=nc.NativeController(self.sf,identity=lambda _:self.ident)
 def tearDown(self):nc.DLL_SHA=self.original;self.temp.cleanup()
 def observation(self):(self.native/'native-observation.json').write_text(json.dumps(self.obs))
 def submit(self,rid='b'*32):return self.c.submit(rid,'research','basic_machine_tools',1)
 def terminal(self,rid='b'*32,stage='selection_verified'):(self.native/f'receipt-{rid}.json').write_text(json.dumps({'session_id':self.sid,'request_id':rid,'stage':stage}))
 def test_disarmed(self):
  with self.assertRaises(RuntimeError):self.submit()
 def test_submit_and_dedup(self):
  self.c.arm(True);self.submit();p=self.native/'request.txt';before=p.stat().st_mtime_ns
  self.submit();self.assertEqual(p.stat().st_mtime_ns,before)
 def test_payload_reuse(self):
  self.c.arm(True);self.submit()
  with self.assertRaises(ValueError):self.c.submit('b'*32,'research','improved_machine_tools',1)
 def test_pending_blocks(self):
  self.c.arm(True);self.submit()
  with self.assertRaises(RuntimeError):self.submit('c'*32)
 def test_uncertain_blocks(self):
  self.c.arm(True);self.submit();self.terminal(stage='execution_uncertain')
  with self.assertRaises(RuntimeError):self.submit('c'*32)
 def test_disarm_removes_publication(self):
  self.c.arm(True);self.submit();self.c.arm(False)
  self.assertFalse((self.native/'request.txt').exists());self.assertEqual(self.c.receipt('b'*32)['stage'],'pending')
 def test_disarm_removes_pending_time_publication_and_retains_ledger(self):
  self.c.arm(True)
  path=self.native/'time-request.txt';path.write_text('pending pause')
  ledger=self.native/'time-ledger.json';ledger.write_text('{"requests":{"existing":"pending"}}')
  before=ledger.read_bytes();self.c.arm(False)
  self.assertFalse(path.exists());self.assertEqual(ledger.read_bytes(),before)
 def test_probe_cannot_overwrite_selection_handshake(self):
  import re
  source=Path(__file__).parent
  def target(name):
   match=re.search(r'write_atomic\(L"([^"]*observation\.json)",out\)',(source/name).read_text())
   self.assertIsNotNone(match)
   return self.native/match.group(1)
  authoritative=target('native_selection.c');probe=target('native_bridge.c')
  # Reproduce the observable gap between the two native publishers each day.
  authoritative.write_text(json.dumps(self.obs))
  probe.write_text(json.dumps(dict(self.obs,selection_commands_enabled=False)))
  self.assertTrue(self.c.status()['native_callback']['selection_commands_enabled'])
 def test_world_change(self):
  self.c.arm(True);self.submit();self.terminal();self.obs['world']='0x2';self.observation()
  with self.assertRaises(RuntimeError):self.submit('c'*32)
 def test_process_change(self):
  self.c.identity=lambda _:{'pid':123,'created':999}
  with self.assertRaises(RuntimeError):self.c.status()
 def test_backend_error(self):
  (self.native/'native-error.json').write_text('{}')
  with self.assertRaises(RuntimeError):self.c.arm(True)
 def test_invalid_requests(self):
  for rid,kind,id,slot in [('bad','research','basic_machine_tools',1),('b'*32,'research','../bad',1),('b'*32,'research','x',True),('b'*32,'research','x',17),('b'*32,'focus','x',1)]:
   with self.assertRaises(ValueError):self.c.submit(rid,kind,id,slot)
 def test_exclusive_publication(self):
  (self.native/'selection.lock').write_text('')
  with self.assertRaises(FileExistsError):self.c.arm(True)
 def test_changed_dll(self):
  (self.native/'hoi4-native-selection.dll').write_bytes(b'changed')
  with self.assertRaises(RuntimeError):self.c.status()
if __name__=='__main__':unittest.main()
