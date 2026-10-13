import unittest,tempfile
from pathlib import Path
from peacetime_agent import choose,PeacetimeAgent
class Fake:
 config={'session_id':'a'*32}
 def __init__(self):self.requests={};self.actions=[];self.native={'research_read_consistent':True,'research_cost_mode':'normal','research_slots':[{'slot':1,'technology':None}],'technologies':[],'active_focus':None,'completed_focuses':[]};self.e={'status':'ready','sample_consistent':True,'available_choices':{'research':{'choices':[{'id':'basic_machine_tools','available':True}]},'national_focus':{'choices':[]}}}
 def check(self):return {}
 def snapshot(self):return self.native
 def peacetime_snapshot(self,rid):return self.e
 def load(self):return {'requests':self.requests}
 def submit(self,rid,kind,id,slot):self.actions.append(rid);self.requests[rid]={'stage':'pending'};return self.requests[rid]
 def receipt(self,rid):return self.requests[rid]
class Tests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.c=Fake();self.a=PeacetimeAgent(self.c,Path(self.tmp.name)/'ai.json')
 def test_disabled_policy_does_not_submit(self):self.assertEqual(self.a.step()['stage'],'stopped');self.assertEqual(self.c.actions,[])
 def test_budget_bool_rejected(self):self.assertRaises(ValueError,self.a.start,True)
 def test_incomplete_rejected(self):self.c.e['sample_consistent']=False;self.assertRaises(RuntimeError,choose,self.c.e,self.c.native)
 def test_cheat_rejected(self):self.c.native['research_cost_mode']='engine_override';self.assertRaises(RuntimeError,choose,self.c.e,self.c.native)
 def test_busy_not_replaced(self):self.c.native['research_slots'][0]['technology']='other';self.assertIsNone(choose(self.c.e,self.c.native))
 def test_duplicate_assignment_not_selected(self):self.c.native['research_slots'].append({'slot':2,'technology':'basic_machine_tools'});self.assertIsNone(choose(self.c.e,self.c.native))
 def test_completed_not_selected(self):self.c.native['technologies']=[{'id':'basic_machine_tools','completed':True}];self.assertIsNone(choose(self.c.e,self.c.native))
 def test_one_action_pending_no_duplicates(self):self.a.start(1);self.a.step();self.a.step();self.a.step();self.assertEqual(len(self.c.actions),1)
 def test_verify_stops_at_budget(self):self.a.start(1);self.a.step();rid=self.c.actions[0];self.c.requests[rid]={'stage':'selection_verified'};self.c.native['research_slots'][0]['technology']='basic_machine_tools';self.assertEqual(self.a.step()['stage'],'action_verified');self.assertFalse(self.a.load()['enabled'])
 def test_failed_readback_stops(self):self.a.start();self.a.step();self.c.requests[self.c.actions[0]]={'stage':'selection_verified'};self.assertEqual(self.a.step()['stage'],'stopped_postcondition_failed');self.assertFalse(self.a.load()['enabled'])
 def test_rejection_stops(self):self.a.start();self.a.step();self.c.requests[self.c.actions[0]]={'stage':'rejected'};self.assertEqual(self.a.step()['stage'],'stopped_rejected')
 def test_uncertainty_never_resubmits(self):self.a.start();self.a.step();self.c.requests[self.c.actions[0]]={'stage':'execution_uncertain'};self.assertEqual(self.a.step()['stage'],'stopped_uncertain');self.a.step();self.assertEqual(len(self.c.actions),1)
 def test_stop_retains_pending(self):self.a.start();self.a.step();self.a.stop();self.assertIsNotNone(self.a.load()['pending'])
 def test_binding_mismatch(self):self.a.start();d=self.a.load();d['session_id']='b'*32;self.a.save(d);self.assertRaises(RuntimeError,self.a.step)
 def test_sustained_idle_uses_fresh_read_and_later_selects(self):
  self.c.native['research_slots'][0]['technology']='other'
  self.a.start(2,wait_for_choices=True)
  ids=[];original=self.c.peacetime_snapshot
  self.c.peacetime_snapshot=lambda rid:(ids.append(rid) or original(rid))
  self.assertEqual(self.a.step()['stage'],'waiting_for_choice')
  self.assertTrue(self.a.load()['enabled'])
  self.c.native['research_slots'][0]['technology']=None
  self.assertEqual(self.a.step()['stage'],'action_submitted')
  self.assertNotEqual(ids[0],ids[1])
 def test_default_still_stops_at_idle(self):
  self.c.native['research_slots'][0]['technology']='other';self.a.start()
  self.assertEqual(self.a.step()['stage'],'idle_no_supported_choice')
  self.assertFalse(self.a.load()['enabled'])
if __name__=='__main__':unittest.main()
