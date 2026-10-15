import contextlib,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from direct_controller import atomic_text
from time_controller import TimeController
class PublicationTests(unittest.TestCase):
 def error(self,winerror=5):
  e=PermissionError('sharing fixture');e.winerror=winerror;return e
 def test_atomic_replace_retries_only_sharing_failures(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'request';p.write_text('old');import os;replace=os.replace;seen=[]
   def flaky(source,target):
    seen.append(Path(source).read_text());self.assertEqual(p.read_text(),'old')
    if len(seen)==1:raise self.error()
    return replace(source,target)
   with patch('direct_controller.os.replace',side_effect=flaky),patch('direct_controller.time.sleep'):
    atomic_text(p,'same-payload')
   self.assertEqual(seen,['same-payload','same-payload']);self.assertEqual(p.read_text(),'same-payload')
 def test_atomic_exhaustion_preserves_old_target(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'request';p.write_text('old')
   with patch('direct_controller.os.replace',side_effect=self.error()) as replace,patch('direct_controller.time.sleep'):
    with self.assertRaises(PermissionError):atomic_text(p,'new')
   self.assertEqual(replace.call_count,6);self.assertEqual(p.read_text(),'old');self.assertFalse(p.with_suffix('.pending').exists())
 def test_unrelated_permissions_are_not_retried(self):
  with tempfile.TemporaryDirectory() as tmp:
   with patch('direct_controller.os.replace',side_effect=self.error(13)) as replace:
    with self.assertRaises(PermissionError):atomic_text(Path(tmp)/'request','new')
   self.assertEqual(replace.call_count,1)
 def test_owned_save_has_durable_duplicate_and_zero_value(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);sid='a'*32;rid='b'*32
   n=SimpleNamespace(native=root,config={'session_id':sid},transaction=contextlib.nullcontext,load=lambda:{'armed':True})
   c=TimeController(n);c.status=lambda:{}
   self.assertEqual(c.submit(rid,'save',0)['stage'],'pending')
   self.assertEqual((root/'time-request.txt').read_text(),f'{sid}|{rid}|save|0')
   receipt={'session_id':sid,'request_id':rid,'stage':'save_file_observed'}
   (root/f'time-receipt-{rid}.json').write_text(json.dumps(receipt))
   with patch('time_controller.atomic_text') as write:
    self.assertEqual(c.submit(rid,'save',0),receipt);write.assert_not_called()
   self.assertEqual(c.submit('c'*32,'pause',True)['stage'],'pending')
   for value in [1,True,'0']:
    with self.assertRaises(ValueError):c.submit('d'*32,'save',value)
   with self.assertRaises(ValueError):c.submit('d'*32,'save',0,selector={'name':'arbitrary'})
 def test_failed_publication_retains_id_and_never_replays(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);sid='a'*32;rid='b'*32
   n=SimpleNamespace(native=root,config={'session_id':sid},transaction=contextlib.nullcontext,load=lambda:{'armed':True})
   c=TimeController(n);c.status=lambda:{}
   def fail(path,text):
    if path.name=='time-request.txt':raise self.error()
    atomic_text(path,text)
   with patch('time_controller.atomic_text',side_effect=fail):result=c.submit(rid,'pause',False)
   self.assertEqual(result['reason'],'request_publication_failed');self.assertFalse(result['native_execution_attempted'])
   with patch('time_controller.atomic_text') as write:
    self.assertEqual(c.submit(rid,'pause',False),result);write.assert_not_called()
   self.assertIn(rid,c.load()['requests']);self.assertEqual(c.submit('c'*32,'pause',True)['stage'],'pending')
   (root/f'time-receipt-{rid}.json').write_text(json.dumps({'stage':'time_verified'}))
   with self.assertRaisesRegex(RuntimeError,'Conflicting'):c.receipt(rid)
if __name__=='__main__':unittest.main()
