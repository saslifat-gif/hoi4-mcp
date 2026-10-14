import contextlib,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from time_controller import TimeController

class NotificationRefreshTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.sid='a'*32;self.rid='b'*32
  native=SimpleNamespace(native=self.root,config={'session_id':self.sid},transaction=contextlib.nullcontext,load=lambda:{'armed':True})
  self.clock=TimeController(native);self.clock.status=lambda:{'paused':True}
 def test_refresh_uses_existing_durable_request_channel(self):
  self.assertEqual(self.clock.submit(self.rid,'alert',8)['stage'],'pending')
  self.assertEqual((self.root/'time-request.txt').read_text(),self.sid+'|'+self.rid+'|alert|8')
 def test_refreshed_receipt_reuses_id_without_resubmission(self):
  self.clock.submit(self.rid,'alert',8)
  receipt={'session_id':self.sid,'request_id':self.rid,'stage':'alert_refreshed','native_tick':42,'raw_title':'Research','raw_body':'Slots available'}
  (self.root/('time-receipt-'+self.rid+'.json')).write_text(json.dumps(receipt))
  (self.root/'time-request.txt').unlink()
  self.assertEqual(self.clock.submit(self.rid,'alert',8),receipt);self.assertFalse((self.root/'time-request.txt').exists())
 def test_request_identity_cannot_change_alert(self):
  self.clock.submit(self.rid,'alert',8)
  with self.assertRaisesRegex(ValueError,'payload mismatch'):self.clock.submit(self.rid,'alert',11)
 def test_uncertain_refresh_blocks_following_command(self):
  self.clock.submit(self.rid,'alert',8)
  with self.assertRaisesRegex(RuntimeError,'Reconcile'):self.clock.submit('c'*32,'pause',False)
 def test_completed_refresh_allows_following_time_command(self):
  self.clock.submit(self.rid,'alert',8)
  (self.root/('time-receipt-'+self.rid+'.json')).write_text(json.dumps({'session_id':self.sid,'request_id':self.rid,'stage':'alert_refreshed'}))
  self.assertEqual(self.clock.submit('c'*32,'pause',False)['stage'],'pending')
 def test_alert_kind_boundary_rejects_bool_and_unknown_enum(self):
  for value in (True,-1,82,'8'):
   with self.assertRaises(ValueError):self.clock.submit(self.rid,'alert',value)
if __name__=='__main__':unittest.main()
