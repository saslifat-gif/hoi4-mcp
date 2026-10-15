"""Offline orchestration tests using real journals and simulated engine receipts."""
import copy,unittest
import test_native_controller as fixture
from native_controller import NativeController

class MilitaryOrderTests(unittest.TestCase):
 observation=fixture.NativeTests.observation
 def setUp(self):
  fixture.NativeTests.setUp(self);self.c.arm(True)
  self.units=[{'unit_id':f'51:{i}','current_province_id':10,'destination_province_id':None,'movement_path_count':0,'movement_path_target_province_id':None} for i in (1,2)]
  self.snapshot=lambda:{'units':copy.deepcopy(self.units),'native_tick':123}
  self.c.military_snapshot=self.snapshot
 def tearDown(self):fixture.NativeTests.tearDown(self)
 def order(self,order='move',province=20):return self.c.order_units('b'*32,order,['51:1','51:2'],province)
 def complete(self,rid,stage='military_verified'):fixture.NativeTests.terminal(self,rid,stage)
 def test_sequential_move_survives_controller_restart_without_republishing(self):
  first=self.order();rid=first['active_request_id'];publication=self.native/'request.txt';before=publication.stat().st_mtime_ns
  self.assertEqual(self.order(),first);self.assertEqual(publication.stat().st_mtime_ns,before)
  self.c=NativeController(self.sf,identity=lambda _:self.ident);self.c.military_snapshot=self.snapshot
  self.complete(rid);second=self.order();self.assertEqual(second['completed_request_ids'],[rid]);self.assertNotEqual(second['active_request_id'],rid)
  self.complete(second['active_request_id'])
  for unit in self.units:unit.update(destination_province_id=None,movement_path_target_province_id=20,movement_path_count=3)
  final=self.order();self.assertEqual(final['stage'],'orders_verified');self.assertFalse(final['arrival_verified']);self.assertFalse(final['atomic'])
  self.units[0]['movement_path_target_province_id']=30
  self.assertEqual(self.order(),final);self.assertEqual(len(self.c.load()['requests']),2)
 def test_rejection_stops_without_submitting_remaining_units(self):
  first=self.order();self.complete(first['active_request_id'],'rejected')
  result=self.order();self.assertEqual(result['stage'],'stopped_rejected');self.assertEqual(len(self.c.load()['requests']),1)
  self.assertEqual(self.order(),result)
 def test_uncertainty_retains_ids_and_blocks_other_actions(self):
  first=self.order();self.complete(first['active_request_id'],'execution_uncertain')
  result=self.order();self.assertEqual(result['stage'],'stopped_uncertain');self.assertEqual(result['child_request_ids'],first['child_request_ids'])
  with self.assertRaisesRegex(RuntimeError,'unresolved'):self.c.submit('d'*32,'cancel','51:2')
 def test_whole_batch_validation_precedes_any_action(self):
  for ids in ([],['51:1','51:1'],['51:1','51:999'],['51:1','051:2']):
   with self.assertRaises(ValueError):self.c.order_units('b'*32,'move',ids,20)
  self.assertEqual(self.c.load()['requests'],{});self.assertFalse((self.native/'request.txt').exists())
 def test_active_batch_cannot_be_changed_or_interleaved(self):
  self.order()
  with self.assertRaises(ValueError):self.c.order_units('b'*32,'move',['51:2','51:1'],20)
  with self.assertRaisesRegex(RuntimeError,'active military'):self.c.submit('d'*32,'cancel','51:2')
  with self.assertRaisesRegex(RuntimeError,'active military'):self.c.order_units('d'*32,'cancel',['51:2'])
 def test_cancel_requires_cleared_path_and_destination(self):
  first=self.order('cancel',None);self.complete(first['active_request_id']);second=self.order('cancel',None);self.complete(second['active_request_id'])
  self.units[1]['movement_path_count']=1
  self.assertEqual(self.order('cancel',None)['stage'],'stopped_postcondition_failed')
 def test_move_accepts_arrival_but_not_a_different_destination(self):
  first=self.order();self.complete(first['active_request_id']);second=self.order();self.complete(second['active_request_id'])
  for unit in self.units:unit['current_province_id']=20
  self.assertEqual(self.order()['stage'],'orders_verified')
 def test_reserved_child_cannot_be_repurposed_or_started_after_batch_stops(self):
  first=self.order();reserved=first['child_request_ids'][1]
  with self.assertRaisesRegex(ValueError,'reserved'):self.c.submit(reserved,'research','basic_machine_tools',1)
  self.complete(first['active_request_id'],'rejected');self.order()
  with self.assertRaisesRegex(ValueError,'closed'):self.c.submit(reserved,'move','51:2',20)
  with self.assertRaises(ValueError):self.c.order_units(reserved,'cancel',['51:2'])
 def test_partial_rejection_reports_completed_units(self):
  first=self.order();self.complete(first['active_request_id']);second=self.order();self.complete(second['active_request_id'],'rejected')
  result=self.order();self.assertEqual(result['stage'],'stopped_rejected');self.assertEqual(result['completed_request_ids'],[first['active_request_id']])
 def test_single_command_id_cannot_be_reused_as_batch_id(self):
  self.c.submit('b'*32,'cancel','51:1');self.complete('b'*32)
  with self.assertRaises(ValueError):self.order()

if __name__=='__main__':unittest.main()
