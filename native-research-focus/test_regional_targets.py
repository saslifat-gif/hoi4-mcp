import copy,unittest
from regional_targets import select_regional_target
class RegionalTargetsTests(unittest.TestCase):
 def setUp(self):
  self.w={'widget_id':'0x1234','name':'strategic_region_alert_entry','source':'interface/theatreselector.gui','engine_local_shown':True,
   'native_popup':{'status':'native_cached_text','alert_scope':'region','native_alert_kind':22,'native_context_id':'0x3000','native_owner_id':'0x2000','native_provider_id':'0x2048','native_cache_record_active':True,'runtime_binding_verified':True}}
 def run_select(self,windows):return select_regional_target(windows,scope='region',alert_kind=22,context_id='0x3000')
 def test_observed_unique_context_selected(self):
  self.assertEqual(self.run_select([self.w])['native_provider_id'],'0x2048')
 def test_duplicate_registry_observation_deduplicates_exact_widget(self):
  self.assertEqual(self.run_select([self.w,copy.deepcopy(self.w)])['widget_id'],'0x1234')
 def test_same_name_different_context_does_not_match(self):
  w=copy.deepcopy(self.w);w['native_popup']['native_context_id']='0x3001'
  self.assertEqual(self.run_select([self.w,w])['widget_id'],'0x1234')
 def test_same_context_different_widgets_rejected(self):
  w=copy.deepcopy(self.w);w['widget_id']='0x1235'
  with self.assertRaisesRegex(RuntimeError,'ambiguous'):self.run_select([self.w,w])
 def test_native_cache_ambiguity_rejected(self):
  self.w['native_popup']['status']='cache_ambiguous'
  with self.assertRaisesRegex(RuntimeError,'ambiguous'):self.run_select([self.w])
 def test_cache_miss_or_inactive_is_not_generation_target(self):
  for status,active in [('cache_missing',True),('native_cached_text',False)]:
   self.w['native_popup'].update(status=status,native_cache_record_active=active)
   with self.assertRaisesRegex(RuntimeError,'No observed'):self.run_select([self.w])
 def test_empty_observation_does_not_fabricate_entry(self):
  with self.assertRaisesRegex(RuntimeError,'No observed'):self.run_select([])
 def test_theater_requires_real_handle(self):
  self.w['native_popup']['alert_scope']='theater'
  with self.assertRaisesRegex(RuntimeError,'handle missing'):select_regional_target([self.w],scope='theater',alert_kind=22,context_id='0x3000')
  self.w['native_popup']['native_context_handle']=[1,77]
  self.assertEqual(select_regional_target([self.w],scope='theater',alert_kind=22,context_id='0x3000')['native_context_handle'],[1,77])
if __name__=='__main__':unittest.main()
