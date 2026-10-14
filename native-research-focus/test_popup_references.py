import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from popup_references import load_references,enrich_window
from popup_reader import capture_popups

class ReferenceTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  for folder in ('events','localisation','interface'):(self.root/folder).mkdir()
  self.write('events/fixture.txt','country_event = { id = sample.1 title = TITLE desc = BODY option = { name = OPT } }')
  self.write('localisation/fixture_l_english.yml','l_english:\n TITLE:0 "Test title"\n BODY:0 "Test body"\n OPT:0 "Continue"\n ALERT:0 "No research selected"\n')
  self.write('interface/alerts.gui','guiTypes = { containerWindowType = { name = "global_alerticon_window" buttonType = { name = "alert_button" pdx_tooltip = "ALERT" } } }')
 def write(self,path,text):(self.root/path).write_text(text,encoding='utf-8-sig')
 def event(self):return {'source':'interface/eventwindow.gui','title':'Test title','description':'Test body','option_labels':['Continue'],'event_id':None}
 def alert(self,name='global_alerticon_window'):
  return {'source':'interface/alerts.gui','name':name,'icons':[],'buttons':[{'name':'alert_button'}],'content_status':'icon_only'}
 def enrich(self,window):enrich_window(window,load_references(self.root,'en'));return window
 def test_exact_event_fingerprint_yields_candidate_not_native_identity(self):
  w=self.enrich(self.event());self.assertEqual(w['event_id_candidates'][0]['event_id'],'sample.1');self.assertEqual(w['event_id_reference_status'],'unique_literal_match');self.assertIsNone(w['event_id']);self.assertFalse(w['event_id_verified'])
 def test_script_reference_does_not_downgrade_verified_native_identity(self):
  w=self.event();w.update(event_id='native.1',event_id_verified=True);self.enrich(w)
  self.assertEqual(w['event_id'],'native.1');self.assertTrue(w['event_id_verified'])
 def test_duplicate_event_fingerprint_is_ambiguous(self):
  self.write('events/second.txt','news_event = { id = other.2 title = TITLE desc = BODY option = { name = OPT } }')
  self.assertEqual(self.enrich(self.event())['event_id_reference_status'],'ambiguous')
 def test_options_must_match_full_ordered_list(self):
  w=self.event();w['option_labels']=['Other'];self.assertEqual(self.enrich(w)['event_id_candidates'],[])
 def test_dynamic_localization_does_not_guess_event_id(self):
  self.write('localisation/fixture_l_english.yml','l_english:\n TITLE:0 "Test title"\n BODY:0 "[ROOT.GetName]"\n OPT:0 "Continue"')
  self.assertEqual(self.enrich(self.event())['event_id_candidates'],[])
 def test_repeated_option_name_does_not_abort_or_guess(self):
  self.write('events/fixture.txt','country_event = { id = sample.1 title = TITLE desc = BODY option = { name = OPT name = OTHER } }')
  self.assertEqual(self.enrich(self.event())['event_id_candidates'],[])
 def test_conditional_and_literal_description_does_not_guess(self):
  self.write('events/fixture.txt','country_event = { id = sample.1 title = TITLE desc = BODY desc = { trigger = { always = yes } text = OTHER } option = { name = OPT } }')
  self.assertEqual(self.enrich(self.event())['event_id_candidates'],[])
 def test_duplicate_localization_keys_do_not_assume_load_order(self):
  self.write('localisation/duplicate_l_english.yml','l_english:\n TITLE:0 "Test title"')
  self.assertEqual(self.enrich(self.event())['event_id_candidates'],[])
 def test_icon_only_alert_gets_explicit_tooltip_reference(self):
  w=self.enrich(self.alert());self.assertEqual(w['notification_text_references'][0]['text'],'No research selected');self.assertFalse(w['notification_text_references'][0]['runtime_binding_verified']);self.assertEqual(w['content_status'],'icon_only')
 def test_nested_notification_panel_keeps_outer_window_binding(self):
  self.write('interface/alerts.gui','guiTypes = { containerWindowType = { name = "global_alerticon_window" containerWindowType = { name = "inner_panel" buttonType = { name = "alert_button" pdx_tooltip = "ALERT" } } } }')
  w=self.enrich(self.alert());self.assertEqual(w['notification_text_references'][0]['text'],'No research selected')
 def test_same_button_in_other_window_does_not_match(self):
  self.assertEqual(self.enrich(self.alert('other_window'))['notification_text_references'],[])
 def test_dynamic_notification_keeps_template_without_fabricated_text(self):
  self.write('localisation/fixture_l_english.yml','l_english:\n ALERT:0 "[ROOT.GetName] has $COUNT$ alerts"')
  m=self.enrich(self.alert())['notification_text_references'][0];self.assertEqual(m['status'],'dynamic_template');self.assertIsNone(m['text']);self.assertIn('$COUNT$',m['raw_text'])
 def test_chinese_locale_is_selected_explicitly(self):
  self.write('localisation/fixture_l_simp_chinese.yml','l_simp_chinese:\n ALERT:0 "未选择研究"')
  w=self.alert();enrich_window(w,load_references(self.root,'zh'));self.assertEqual(w['notification_text_references'][0]['text'],'未选择研究')
 def test_malformed_script_fails_instead_of_partial_index(self):
  self.write('events/bad.txt','country_event = {')
  with self.assertRaises(ValueError):load_references(self.root,'en')
 def test_references_are_optional_and_no_native_read_is_added(self):
  sample={'captured_start_unix':1,'captured_end_unix':2,'truncated':False,'matches':[]}
  with patch('popup_reader.capture_live_ui',return_value=sample) as read:
   out=capture_popups('session',self.root,'notifications',True,'en')
  read.assert_called_once();self.assertFalse(out['process_writes'])
if __name__=='__main__':unittest.main()
