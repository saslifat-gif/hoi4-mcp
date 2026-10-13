import sys,unittest
from pathlib import Path
sys.path[:0]=[str(Path(__file__).parent),str(Path(__file__).parent.parent)]
from peacetime_reader import parse_frame,merge_frame,number,state_scope_id
from peacetime_script import render_frame,SCALARS,RESOURCE_FIELDS
SID='a'*32;RID='b'*32
class PeacetimeTests(unittest.TestCase):
 def setUp(self):
  self.cat={'resources':['steel','oil'],'equipment_ids':['infantry_equipment_1'],'state_is_coastal_supported':True}
  self.cfg={'session_id':SID,'process_identity':{'pid':123}}
  self.choices={'session_id':SID,'request_id':RID,'pid':123,'native_tick':10,'world':'0x1','stage':'validated','empty_research_slots':[1],'focus_busy':False,'research':[{'id':'basic_machine_tools','engine_allowed':True,'backend_guard_allowed':True,'available':True}],'focuses':[{'id':'GER_focus','engine_allowed':True,'available':True}]}
  self.rows=[('BEGIN',{}),('DATA',{k:('1' if k=='owned_state_count' else '2') for k in SCALARS})]
  self.rows.extend(('RESOURCE',{'id':r,**{k:('5' if k!='surplus' else '-3') for k in RESOURCE_FIELDS}}) for r in self.cat['resources'])
  self.rows += [('STATE',{'id':'-10737.4176'}),('CONSTRUCTION',{'state':'-10737.4176','building':'arms_factory','max_levels':'2'}),('PRODUCTION',{'id':'infantry_equipment_1'}),('END',{})]
 def log(self,rows=None):return '\n'.join('[12:00:00][1936.01.01.24] CODEX_PEACETIME|'+SID+'|'+RID+'|'+kind+'|frame_marker=1'+''.join('|'+k+'='+v for k,v in values.items()) for kind,values in (rows or self.rows))
 def frame(self):return parse_frame(self.log(),SID,RID,self.cat)
 def test_full_native_frame(self):
  r=merge_frame(self.frame(),self.choices,self.cfg,RID);self.assertEqual(r['status'],'ready');self.assertEqual(r['resources']['steel']['surplus'],-3);self.assertEqual(r['factories']['military']['available'],2)
 def test_incomplete_frame_is_pending(self):self.assertIsNone(parse_frame(self.log(self.rows[:-1]),SID,RID,self.cat))
 def test_wrong_request_ignored(self):self.assertIsNone(parse_frame(self.log(),SID,'c'*32,self.cat))
 def test_missing_resource_fails(self):
  with self.assertRaisesRegex(ValueError,'Incomplete'):parse_frame(self.log([x for x in self.rows if not(x[0]=='RESOURCE' and x[1]['id']=='oil')]),SID,RID,self.cat)
 def test_duplicate_resource_fails(self):
  with self.assertRaises(ValueError):parse_frame(self.log(self.rows[:-1]+[self.rows[2],self.rows[-1]]),SID,RID,self.cat)
 def test_mixed_tick_fails(self):
  with self.assertRaisesRegex(ValueError,'frame marker'):parse_frame(self.log().replace('DATA|frame_marker=1','DATA|frame_marker=2'),SID,RID,self.cat)
 def test_mixed_date_fails(self):
  with self.assertRaisesRegex(ValueError,'Mixed'):parse_frame(self.log().replace('[1936.01.01.24] CODEX_PEACETIME|'+SID+'|'+RID+'|DATA','[1936.01.02.24] CODEX_PEACETIME|'+SID+'|'+RID+'|DATA'),SID,RID,self.cat)
 def test_non_finite_fails(self):
  for x in ('NaN','Infinity','-Infinity'):
   with self.assertRaises(ValueError):number(x)
 def test_fractional_factory_fails(self):
  with self.assertRaises(ValueError):parse_frame(self.log().replace('military_total=2','military_total=2.5'),SID,RID,self.cat)
 def test_unknown_equipment_fails(self):
  with self.assertRaises(ValueError):parse_frame(self.log().replace('id=infantry_equipment_1','id=unknown'),SID,RID,self.cat)
 def test_state_enumeration_must_be_complete(self):
  with self.assertRaisesRegex(ValueError,'owned-state'):parse_frame(self.log().replace('owned_state_count=1','owned_state_count=2'),SID,RID,self.cat)
 def test_native_pid_mismatch_fails(self):
  self.choices['pid']=999
  with self.assertRaises(RuntimeError):merge_frame(self.frame(),self.choices,self.cfg,RID)
 def test_missing_native_clock_fails(self):
  self.choices['native_tick']=None
  with self.assertRaises(RuntimeError):merge_frame(self.frame(),self.choices,self.cfg,RID)
 def test_native_failure_not_empty_success(self):
  self.choices['stage']='error'
  with self.assertRaises(RuntimeError):merge_frame(self.frame(),self.choices,self.cfg,RID)
 def test_full_slots_cannot_offer_research(self):
  self.choices['empty_research_slots']=[]
  with self.assertRaises(RuntimeError):merge_frame(self.frame(),self.choices,self.cfg,RID)
 def test_busy_focus_cannot_offer_replacement(self):
  self.choices['focus_busy']=True
  with self.assertRaises(RuntimeError):merge_frame(self.frame(),self.choices,self.cfg,RID)
 def test_no_native_permission_cannot_offer_choice(self):
  self.choices['research'][0]['engine_allowed']=False
  with self.assertRaises(RuntimeError):merge_frame(self.frame(),self.choices,self.cfg,RID)
 def test_factory_limit_capped_to_supported_15(self):
  frame=self.frame();frame['scalars']['military_available']=25;r=merge_frame(frame,self.choices,self.cfg,RID);self.assertEqual(r['available_choices']['production']['choices'][0]['max_factories'],15)
 def test_production_with_zero_factories_fails(self):
  frame=self.frame();frame['scalars']['military_available']=0
  with self.assertRaises(RuntimeError):merge_frame(frame,self.choices,self.cfg,RID)
 def test_tagged_state_scope(self):
  self.assertEqual(state_scope_id('-10737.4176'),64)
  self.assertEqual(state_scope_id('-10737.41819'),5)
 def test_non_state_scope_rejected(self):
  for value in ('64','-21474.83647','NaN'):
   with self.assertRaises(ValueError):state_scope_id(value)
 def test_render_uses_temporary_values_only(self):
  eq={'equipment':{'infantry_equipment_1':{'factory_kind':'military','base_active':False,'unlock_technologies_any':['infantry_weapons']}}}
  s=render_frame(SID,RID,self.cat,eq)
  self.assertIn('resource_produced@steel',s);self.assertIn('array = owned_states',s);self.assertIn('is_coastal = yes',s)
  for x in ('add_equipment','add_building','set_variable =','complete_national_focus','set_technology'):self.assertNotIn(x,s)
 def test_render_rejects_identifier_injection(self):
  self.cat['resources']=['steel } log = bad']
  with self.assertRaises(ValueError):render_frame(SID,RID,self.cat,{'equipment':{}})
if __name__=='__main__':unittest.main()
