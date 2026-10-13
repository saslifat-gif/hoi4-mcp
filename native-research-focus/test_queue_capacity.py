import copy,unittest
import test_peacetime_reader as fixtures
from test_peacetime_reader import RID
from peacetime_reader import merge_frame
class QueueTests(unittest.TestCase):
 log=fixtures.PeacetimeTests.log
 frame=fixtures.PeacetimeTests.frame
 def setUp(self):
  fixtures.PeacetimeTests.setUp(self);self.cfg['native_construction']={'pid':123,'world':'0x1'}
  self.choices['construction_state_count']=1
  self.choices['construction_capacity']=[{'state_id':64,'building':b,'built':2,'built_and_queued':3,'queued':1,'queue_adjusted_limit':6,'remaining':3} for b in ('industrial_complex','arms_factory','dockyard')]
 def test_queued_levels_reduce_native_choice_quantity(self):
  r=merge_frame(self.frame(),self.choices,self.cfg,RID);self.assertEqual(r['available_choices']['construction']['choices'][0]['max_levels'],3)
 def test_full_queue_is_not_offered(self):
  for x in self.choices['construction_capacity']:x.update(built_and_queued=6,queued=4,remaining=0)
  self.assertEqual(merge_frame(self.frame(),self.choices,self.cfg,RID)['available_choices']['construction']['choices'],[])
 def test_shared_queue_affects_both_factory_choices(self):
  f=self.frame();f['construction'].append({'state_id':64,'building':'industrial_complex','max_levels':5})
  r=merge_frame(f,self.choices,self.cfg,RID)
  self.assertEqual([x['max_levels'] for x in r['available_choices']['construction']['choices']],[3,3])
 def test_incomplete_state_coverage_rejected(self):
  self.choices['construction_state_count']=2;self.assertRaises(RuntimeError,merge_frame,self.frame(),self.choices,self.cfg,RID)
 def test_missing_capacity_fails_closed(self):
  del self.choices['construction_capacity'];self.assertRaises(RuntimeError,merge_frame,self.frame(),self.choices,self.cfg,RID)
 def test_duplicate_capacity_rejected(self):
  self.choices['construction_capacity'][1]=copy.deepcopy(self.choices['construction_capacity'][0]);self.assertRaises(RuntimeError,merge_frame,self.frame(),self.choices,self.cfg,RID)
 def test_inconsistent_queue_total_rejected(self):
  self.choices['construction_capacity'][0]['queued']=2;self.assertRaises(RuntimeError,merge_frame,self.frame(),self.choices,self.cfg,RID)
 def test_negative_capacity_rejected(self):
  self.choices['construction_capacity'][0]['remaining']=-1;self.assertRaises(RuntimeError,merge_frame,self.frame(),self.choices,self.cfg,RID)
if __name__=='__main__':unittest.main()
