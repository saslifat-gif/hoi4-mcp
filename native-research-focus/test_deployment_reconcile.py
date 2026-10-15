import copy,unittest
from deployment_reconcile import verify_created_queue
class QueueReconcileTests(unittest.TestCase):
 def setUp(self):
  self.before={'conveyors':[],'country_tag_native':1,'native_tick':1}
  self.after={'conveyors':[{'conveyor_id':'64:1','template_id':'52:1','lines':[{'line_id':'63:1','current_entry':{'manpower':1}}]}],'country_tag_native':1,'native_tick':2,'country_to_manager_binding_verified':True,'process_writes':False}
  self.units={'units':[{'unit_id':'51:1'}]}
 def check(self,after=None,units=None):return verify_created_queue(self.before,after or self.after,'52:1',self.units,units or self.units)
 def test_exact_new_queue(self):self.assertEqual(self.check()['line_id'],'63:1')
 def test_no_new_or_two_new_queues(self):
  for rows in [[],self.after['conveyors']+[dict(self.after['conveyors'][0],conveyor_id='64:2')]]:
   after=dict(self.after,conveyors=rows)
   with self.assertRaises(RuntimeError):self.check(after)
 def test_wrong_template_or_missing_entry(self):
  for key,value in [('template_id','52:2'),('lines',[{'line_id':'63:1','current_entry':None}])]:
   after=copy.deepcopy(self.after);after['conveyors'][0][key]=value
   with self.assertRaises(RuntimeError):self.check(after)
 def test_country_time_and_inventory_changes_reject(self):
  for key,value in [('country_tag_native',2),('native_tick',0),('process_writes',True),('country_to_manager_binding_verified',False)]:
   with self.assertRaises(RuntimeError):self.check(dict(self.after,**{key:value}))
  with self.assertRaises(RuntimeError):self.check(units={'units':[]})
if __name__=='__main__':unittest.main()
