import json,unittest
import test_commands as fixtures
from test_commands import CID,NEXT,SID
class NativeConstructionTests(unittest.TestCase):
 controller=fixtures.Commands.controller
 construct=fixtures.Commands.construct
 ack=fixtures.Commands.ack
 tearDown=fixtures.Commands.tearDown
 def setUp(self):
  fixtures.Commands.setUp(self);self.c.catalog={**self.c.catalog,'construction_native':{'pid':123,'world':'0x1'}}
 def native(self,status='acknowledged',levels=1):
  d={'session_id':SID,'command_id':CID,'pid':123,'world':'0x1','status':status,'engine_acknowledged':True,'gameplay_outcome_verified':status=='acknowledged','data':{'kind':'construct','state_id':64,'building':'arms_factory','levels':levels,'before_built_and_queued':3,'after_built_and_queued':3+levels}}
  p=self.root/'native'/f'construction-{CID}.json';p.parent.mkdir(exist_ok=True);p.write_text(json.dumps(d));return d,p
 def test_multilevel_publishes_native_request_without_scripted_insertion(self):
  self.c.submit(dict(self.construct(),levels=5),CID);s=self.hook.read_text();self.assertIn('CODEX_NATIVE_CONSTRUCT',s);self.assertNotIn('add_building_construction',s)
 def test_script_ack_alone_does_not_verify_native_queue(self):
  self.c.submit(self.construct(),CID);self.ack();self.assertEqual(self.c.receipt(CID)['status'],'pending')
 def test_native_postcondition_and_idempotent_receipt(self):
  command=dict(self.construct(),levels=5);self.c.submit(command,CID);self.native(levels=5);self.ack();r=self.c.receipt(CID);self.assertTrue(r['gameplay_outcome_verified']);self.assertEqual(self.c.submit(command,CID),r)
 def test_native_rejection_overrides_script_branch_ack(self):
  self.c.submit(self.construct(),CID);self.native('rejected');self.ack();self.assertEqual(self.c.receipt(CID)['status'],'rejected')
 def test_uncertainty_keeps_later_mutations_blocked(self):
  self.c.submit(self.construct(),CID);self.native('delivery_uncertain');self.ack();self.assertEqual(self.c.receipt(CID)['status'],'delivery_uncertain');self.assertRaisesRegex(RuntimeError,'unresolved',self.c.submit,self.construct(),NEXT)
 def test_receipt_process_mismatch_rejected(self):
  self.c.submit(self.construct(),CID);d,p=self.native();d['pid']=124;p.write_text(json.dumps(d));self.ack();self.assertRaises(RuntimeError,self.c.receipt,CID)
 def test_incorrect_queue_increment_rejected(self):
  self.c.submit(self.construct(),CID);d,p=self.native();d['data']['after_built_and_queued']=3;p.write_text(json.dumps(d));self.ack();self.assertRaises(RuntimeError,self.c.receipt,CID)
if __name__=='__main__':unittest.main()
