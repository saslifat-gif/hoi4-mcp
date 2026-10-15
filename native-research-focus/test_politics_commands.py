"""Offline command preparation with real source files/journals; no native actions."""
import unittest
import test_native_controller as fixture
from politics_commands import prepare_command

class PoliticsCommandTests(unittest.TestCase):
 observation=fixture.NativeTests.observation
 def setUp(self):
  fixture.NativeTests.setUp(self);self.c.config['game_root']=str(self.root/'game')
  self.source('common/ideas/laws.txt','ideas = { economic_laws = { law = yes available = { has_war = no } civilian_economy = { cost = var:law_cost } } spirit = { bonus = { cost = 10 } } }')
  self.source('common/characters/GER.txt','characters = { GER_person = { advisor = { slot = political_advisor idea_token = GER_person_idea cost = 150 available = { has_war = no has_war = yes } } } }')
  self.source('common/decisions/political.txt','political_actions = { visible = { tag = GER } negotiate = { target_trigger = { FROM = { has_war = no } } cost = var:decision_cost } }')
  self.source('common/resources/resources.txt','resources = { steel = { icon_frame = 2 } }')
 def tearDown(self):fixture.NativeTests.tearDown(self)
 def source(self,name,text):
  p=self.root/'game'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text);return p
 def prepare(self,command):return prepare_command(self.c.config['game_root'],'GER',command)
 def test_law_keeps_group_rules_and_dynamic_cost_without_evaluating_them(self):
  result=self.prepare({'kind':'law','group':'economic_laws','law':'civilian_economy'})
  self.assertEqual(result['selected_definition']['children'][0]['value'],'var:law_cost')
  self.assertIn('has_war',result['source_reference']['raw_script']);self.assertFalse(result['cost_verified'])
  with self.assertRaisesRegex(ValueError,'law group'):self.prepare({'kind':'law','group':'spirit','law':'bonus'})
 def test_advisor_requires_one_matching_role_and_preserves_repeated_conditions(self):
  command={'kind':'advisor','character':'GER_person','slot':'political_advisor'}
  result=self.prepare(command);conditions=result['selected_definition']['children'][3]['children']
  self.assertEqual([x['value'] for x in conditions],['no','yes'])
  self.source('common/characters/GER.txt','characters = { GER_person = { advisor = { slot = political_advisor } advisor = { slot = political_advisor } } }')
  with self.assertRaisesRegex(ValueError,'ambiguous advisor'):self.prepare(command)
 def test_decision_keeps_target_and_category_context(self):
  result=self.prepare({'kind':'decision','category':'political_actions','decision':'negotiate','target_country':'POL'})
  self.assertEqual(result['command']['target_country'],'POL');self.assertIn('visible',result['source_reference']['raw_script'])
  self.assertIn('FROM',str(result['selected_definition']));self.assertFalse(result['runtime_availability_verified'])
 def test_trade_validates_request_without_guessing_native_quantity(self):
  command={'kind':'trade','partner_country':'SOV','resource':'steel','factories':2}
  result=self.prepare(command);self.assertEqual(result['command']['factories'],2);self.assertFalse(result['native_execution_implemented'])
  for patch in ({'factories':True},{'factories':0},{'partner_country':'GER'},{'partner_country':'../POL'},{'resource':'missing'}):
   with self.assertRaises(ValueError):self.prepare(dict(command,**patch))
 def test_all_four_prepare_offline_without_arming_or_process_access(self):
  self.c.identity=lambda _:(_ for _ in ()).throw(AssertionError('Process access during offline preparation'))
  commands=[{'kind':'law','group':'economic_laws','law':'civilian_economy'}, {'kind':'advisor','character':'GER_person','slot':'political_advisor'}, {'kind':'decision','category':'political_actions','decision':'negotiate','target_country':None}, {'kind':'trade','partner_country':'SOV','resource':'steel','factories':1}]
  for i,command in enumerate(commands):
   result=self.c.prepare_politics(f'{i:032x}',command);self.assertEqual(result['stage'],'prepared_not_executed');self.assertFalse(result['gameplay_changed'])
  self.assertEqual(self.c.load()['requests'],{});self.assertFalse((self.native/'request.txt').exists())
 def test_prepared_intent_is_immutable_and_explicitly_as_of_preparation(self):
  command={'kind':'trade','partner_country':'SOV','resource':'steel','factories':1}
  result=self.c.prepare_politics('b'*32,command);before=self.c.ledger.stat().st_mtime_ns
  self.source('common/resources/resources.txt','broken = {')
  self.assertEqual(self.c.prepare_politics('b'*32,command),result);self.assertEqual(self.c.ledger.stat().st_mtime_ns,before)
  self.assertEqual(result['source_freshness'],'as_of_preparation')
  with self.assertRaises(ValueError):self.c.prepare_politics('b'*32,dict(command,factories=2))
 def test_reserved_politics_id_cannot_publish_native_or_batch_actions(self):
  self.c.prepare_politics('b'*32,{'kind':'trade','partner_country':'SOV','resource':'steel','factories':1});self.c.arm(True)
  with self.assertRaisesRegex(ValueError,'reserved'):self.c.submit('b'*32,'cancel','51:1')
  with self.assertRaises(ValueError):self.c.order_units('b'*32,'cancel',['51:1'])
  self.assertFalse((self.native/'request.txt').exists())
 def test_ambiguous_sources_and_extra_fields_fail_before_saving(self):
  self.source('common/resources/duplicate.txt','resources = { steel = { icon_frame = 3 } }')
  command={'kind':'trade','partner_country':'SOV','resource':'steel','factories':1}
  with self.assertRaisesRegex(ValueError,'ambiguous'):self.c.prepare_politics('b'*32,command)
  with self.assertRaisesRegex(ValueError,'fields'):self.c.prepare_politics('c'*32,dict(command,instant=True))
  self.assertFalse(self.c.ledger.exists())

if __name__=='__main__':unittest.main()
