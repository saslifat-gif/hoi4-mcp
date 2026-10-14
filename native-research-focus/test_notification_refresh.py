import contextlib,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from time_controller import TimeController

class NotificationRefreshTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.sid='a'*32;self.rid='b'*32
  native=SimpleNamespace(native=self.root,config={'session_id':self.sid,'game_root':'game'},path=self.root/'session.json',transaction=contextlib.nullcontext,load=lambda:{'armed':True})
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
 def test_window_uses_same_ledger_and_accepts_completed_receipt(self):
  self.clock.submit(self.rid,'worldtension',True)
  self.assertEqual((self.root/'time-request.txt').read_text(),self.sid+'|'+self.rid+'|worldtension|1')
  receipt={'session_id':self.sid,'request_id':self.rid,'stage':'window_verified','after_shown':True}
  (self.root/('time-receipt-'+self.rid+'.json')).write_text(json.dumps(receipt))
  self.assertEqual(self.clock.submit(self.rid,'worldtension',True),receipt)
  self.assertEqual(self.clock.submit('c'*32,'worldtension',False)['stage'],'pending')
 def test_uncertain_window_keeps_id_and_blocks_next_action(self):
  self.clock.submit(self.rid,'worldtension',True)
  receipt={'session_id':self.sid,'request_id':self.rid,'stage':'execution_uncertain','reason':'window_binding_changed'}
  (self.root/('time-receipt-'+self.rid+'.json')).write_text(json.dumps(receipt))
  with patch('runtime_gui.capture_live_ui',return_value={'matches':[],'truncated':False}):self.assertEqual(self.clock.submit(self.rid,'worldtension',True),receipt)
  with patch('runtime_gui.capture_live_ui',return_value={'matches':[],'truncated':False}):
   with self.assertRaisesRegex(RuntimeError,'Reconcile'):self.clock.submit('c'*32,'worldtension',False)
 def test_close_fade_is_observed_without_resubmitting(self):
  self.clock.submit(self.rid,'worldtension',False)
  p=self.root/('time-receipt-'+self.rid+'.json');raw=json.dumps({'session_id':self.sid,'request_id':self.rid,'stage':'execution_uncertain','reason':'window_state_unverified'});p.write_text(raw)
  (self.root/'time-request.txt').unlink()
  sample={'matches':[{'widget_id':'0x1','native_popup':{'status':'native_window_state','engine_local_shown':False}}],'truncated':False,'captured_end_unix':123}
  with patch('runtime_gui.capture_live_ui',return_value=sample):result=self.clock.submit(self.rid,'worldtension',False)
  self.assertEqual(result['stage'],'window_observed');self.assertEqual(result['native_stage'],'execution_uncertain');self.assertEqual(p.read_text(),raw);self.assertFalse((self.root/'time-request.txt').exists())
  with patch('runtime_gui.capture_live_ui',side_effect=AssertionError('Immutable observation must be reused')):self.assertEqual(self.clock.submit(self.rid,'worldtension',False),result)
 def test_ambiguous_window_does_not_complete_uncertain_request(self):
  self.clock.submit(self.rid,'worldtension',False)
  (self.root/('time-receipt-'+self.rid+'.json')).write_text(json.dumps({'session_id':self.sid,'request_id':self.rid,'stage':'execution_uncertain','reason':'window_state_unverified'}))
  window={'native_popup':{'status':'native_window_state','engine_local_shown':False}}
  with patch('runtime_gui.capture_live_ui',return_value={'matches':[window,window],'truncated':False}):self.assertEqual(self.clock.submit(self.rid,'worldtension',False)['stage'],'execution_uncertain')
 def test_window_input_requires_boolean(self):
  for value in (1,'show',None):
   with self.assertRaises(ValueError):self.clock.submit(self.rid,'worldtension',value)
 def test_alert_kind_boundary_rejects_bool_and_unknown_enum(self):
  for value in (True,-1,82,'8'):
   with self.assertRaises(ValueError):self.clock.submit(self.rid,'alert',value)
if __name__=='__main__':unittest.main()
