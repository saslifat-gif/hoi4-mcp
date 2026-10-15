import hashlib,tempfile,unittest
from pathlib import Path
from script_definitions import read_definitions

class PoliticsDefinitionsTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def source(self,name,text):
  p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text);return p
 def test_law_conditions_cost_and_duplicate_definitions_are_preserved(self):
  text='ideas = { economic_laws = { law = yes\n civilian_economy = { cost = 150 available = { has_war = no has_war = yes } } } }'
  p=self.source('common/ideas/laws.txt',text)
  self.source('common/ideas/other.txt','ideas = { economic_laws = { civilian_economy = { cost = 200 } } }')
  result=read_definitions(self.root,'ideas','civilian_economy');rows=result['definitions']
  self.assertEqual(len(rows),2);self.assertEqual(rows[0]['script_path'],['economic_laws','civilian_economy'])
  self.assertEqual(rows[0]['definition']['children'][1]['children'][0]['value'],'no')
  self.assertEqual(rows[0]['definition']['children'][1]['children'][1]['value'],'yes')
  self.assertEqual(rows[0]['source_sha256'],hashlib.sha256(p.read_bytes()).hexdigest())
  self.assertFalse(result['runtime_availability_verified']);self.assertFalse(result['active_overlay_verified'])
 def test_exact_query_ignores_only_files_without_requested_identifier(self):
  self.source('common/ideas/unrelated.txt','ideas = { unrelated = {')
  self.source('common/ideas/selected.txt','ideas = { laws = { selected = { cost = 150 } } }')
  result=read_definitions(self.root,'ideas','selected')
  self.assertEqual([x['script_path'] for x in result['definitions']],[['laws','selected']])
  self.assertIn('common/ideas/unrelated.txt',result['source_hashes'])
  with self.assertRaisesRegex(ValueError,'Unclosed'):read_definitions(self.root,'ideas')
  self.source('common/ideas/also-selected.txt','ideas = { selected = {')
  with self.assertRaisesRegex(ValueError,'Unclosed'):read_definitions(self.root,'ideas','selected')
 def test_advisor_role_keeps_character_context(self):
  self.source('common/characters/GER.txt','characters = { GER_person = { advisor = { idea_token = GER_advisor slot = political_advisor cost = 150 } } }')
  row=read_definitions(self.root,'characters','GER_person')['definitions'][0]
  self.assertEqual(row['definition']['children'][0]['children'][0]['value'],'GER_advisor')
  self.assertFalse(read_definitions(self.root,'characters','missing')['native_identity_verified'])
 def test_decision_target_scopes_and_resource_rules_are_retained(self):
  self.source('common/decisions/political.txt','political_actions = { negotiate = { target_trigger = { FROM = { has_war = no } } cost = var:price complete_effect = { add_political_power = -10 } } }')
  row=read_definitions(self.root,'decisions','negotiate')['definitions'][0]
  self.assertEqual(row['script_path'],['political_actions','negotiate'])
  self.assertIn('FROM',row['raw_script']);self.assertIn('var:price',row['raw_script'])
  self.source('common/resources/resources.txt','resources = { steel = { icon_frame = 2 } }')
  self.assertEqual(read_definitions(self.root,'resources')['definitions'][0]['id'],'steel')
 def test_missing_invalid_and_malformed_sources_do_not_look_like_empty_choices(self):
  with self.assertRaises(ValueError):read_definitions(self.root,'trade')
  with self.assertRaisesRegex(ValueError,'missing'):read_definitions(self.root,'ideas')
  self.source('common/ideas/broken.txt','ideas = { broken = {')
  with self.assertRaisesRegex(ValueError,'Unclosed'):read_definitions(self.root,'ideas')

if __name__=='__main__':unittest.main()
