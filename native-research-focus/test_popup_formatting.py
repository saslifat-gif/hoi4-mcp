import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from popup_reader import capture_popups, summarize_window
from popup_references import load_references, enrich_window


class PopupFormattingTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);(self.root/'interface').mkdir();(self.root/'localisation').mkdir()
  self.gui('instantTextBoxType = { name = message font = font_zh } iconType = { name = alert spriteType = exact_icon }')
  self.write('interface/format.gfx','bitmapfonts = { bitmapfont = { name = font_zh fontfiles = { latin.fnt chinese.fnt } } } spriteTypes = { spriteType = { name = exact_icon texturefile = gfx/alert.dds noOfFrames = 3 } }')
 def write(self,path,text):
  (self.root/path).parent.mkdir(parents=True,exist_ok=True);(self.root/path).write_text(text,encoding='utf-8-sig')
 def gui(self,body):
  self.write('interface/theatreselector.gui','guiTypes = { containerWindowType = { name = strategic_region_alert_entry '+body+' } }')
 def window(self):
  source='interface/theatreselector.gui'
  return {'source':source,'name':'strategic_region_alert_entry','icons':[{'widget_id':'i','name':'alert','source':source}],
          'buttons':[],'text_fields':[{'widget_id':'t','name':'message','source':source,'raw_text':'未选择\x13steel\x13','formatted_runs':[{'kind':'icon','name':'steel'}]}]}
 def enrich(self,window=None,language='en'):
  window=self.window() if window is None else window
  enrich_window(window,load_references(self.root,language));return window
 def test_exact_font_and_sprite_definitions_keep_file_order_frames_and_provenance(self):
  refs=self.enrich()['formatting_asset_references'];self.assertEqual([r['field'] for r in refs],['font','spriteType'])
  font,sprite=[r['definitions'][0] for r in refs]
  self.assertEqual([n['value'] for n in font['definition']['children'][1]['children']],['latin.fnt','chinese.fnt'])
  self.assertEqual(sprite['definition']['children'][2]['value'],'3');self.assertEqual(len(font['source_sha256']),64)
  self.assertTrue(all(not r['runtime_binding_verified'] and not r['asset_identity_verified'] for r in refs))
 def test_chinese_content_and_inline_tokens_are_untouched(self):
  window=self.window();original=dict(window['text_fields'][0]);self.enrich(window,'zh')
  self.assertEqual(window['text_fields'][0],original)
  self.assertEqual(window['formatting_asset_scope'],'explicit_gui_fields_only_not_inline_tokens')
 def test_duplicate_graphics_definitions_are_ambiguous(self):
  self.write('interface/duplicate.gfx','bitmapfonts = { bitmapfont = { name = font_zh fontfiles = { override.fnt } } }')
  ref=self.enrich()['formatting_asset_references'][0]
  self.assertEqual(ref['status'],'ambiguous');self.assertEqual(len(ref['definitions']),2)
 def test_duplicate_font_fields_are_not_resolved_to_first_value(self):
  self.gui('instantTextBoxType = { name = message font = font_zh font = missing }')
  ref=self.enrich()['formatting_asset_references'][0]
  self.assertEqual(ref['identifiers'],['font_zh','missing']);self.assertEqual(ref['status'],'ambiguous')
 def test_duplicate_name_inside_graphic_is_ambiguous(self):
  self.write('interface/format.gfx','bitmapfonts = { bitmapfont = { name = font_zh name = other } }')
  ref=self.enrich()['formatting_asset_references'][0]
  self.assertEqual(ref['status'],'ambiguous');self.assertIsNone(ref['definitions'][0]['id'])
 def test_missing_graphics_remain_unresolved(self):
  (self.root/'interface/format.gfx').unlink()
  self.assertTrue(all(r['status']=='unresolved' and r['definitions']==[] for r in self.enrich()['formatting_asset_references']))
 def test_no_guessed_gfx_prefix_or_inline_token_mapping(self):
  self.gui('iconType = { name = alert spriteType = steel }')
  self.write('interface/format.gfx','spriteTypes = { spriteType = { name = GFX_steel texturefile = steel.dds } }')
  ref=self.enrich()['formatting_asset_references'][0];self.assertEqual(ref['definitions'],[])
 def test_same_widget_name_in_other_source_or_window_is_excluded(self):
  for field,value in [('source','interface/alerts.gui'),('name','other')]:
   with self.subTest(field=field):
    window=self.window();window[field]=value;self.assertEqual(self.enrich(window)['formatting_asset_references'],[])
  window=self.window();window['text_fields'][0]['source']='interface/other.gui'
  self.assertEqual([r['field'] for r in self.enrich(window)['formatting_asset_references']],['spriteType'])
 def test_nested_entry_and_repeated_widget_declarations_preserve_candidates(self):
  self.gui('containerWindowType = { name = inner instantTextBoxType = { name = message font = font_zh } instantTextBoxType = { name = message font = missing } }')
  window=self.window();window['name']='inner';refs=self.enrich(window)['formatting_asset_references']
  self.assertEqual(len(refs),2);self.assertEqual(refs[0]['windows'],['strategic_region_alert_entry','inner'])
 def test_regional_tooltip_uses_explicit_locale_without_global_cross_match(self):
  self.gui('buttonType = { name = alert_button pdx_tooltip = REGION font = font_zh quadTextureSprite = exact_icon }')
  self.write('interface/alerts.gui','guiTypes = { containerWindowType = { name = strategic_region_alert_entry buttonType = { name = alert_button pdx_tooltip = GLOBAL } } }')
  self.write('localisation/test_l_simp_chinese.yml','l_simp_chinese:\n REGION:0 "地区警报"\n GLOBAL:0 "错误警报"')
  window=self.window();window['buttons']=[{'widget_id':'b','name':'alert_button','source':window['source']}]
  out=self.enrich(window,'zh');self.assertEqual([m['text'] for m in out['notification_text_references']],['地区警报'])
  self.assertEqual([r['field'] for r in out['formatting_asset_references']],['font','quadTextureSprite'])
 def test_notification_subdirectory_is_scanned(self):
  self.write('interface/notifications/test.gui','guiTypes = { containerWindowType = { name = note instantTextBoxType = { name = message font = font_zh } } }')
  window=self.window();window.update(source='interface/notifications/test.gui',name='note')
  window['text_fields'][0]['source']=window['source']
  self.assertEqual(self.enrich(window)['formatting_asset_references'][0]['identifiers'],['font_zh'])
 def test_malformed_relevant_graphics_fail_without_partial_references(self):
  self.write('interface/bad.gfx','bitmapfonts = { bitmapfont = { name = font_zh')
  with self.assertRaises(ValueError):self.enrich()
 def test_optional_mcp_snapshot_enriches_without_extra_process_reads(self):
  source='interface/theatreselector.gui'
  child={'widget_id':'t','name':'message','source':source,'native_type':'.?AVCInstantTextBox@@','text_status':'read','text':'地区警报','raw_text':'地区警报','formatted_runs':[],
         'engine_show_state':{'engine_show_state_verified':True,'engine_local_shown':True}}
  root={'widget_id':'r','name':'strategic_region_alert_entry','source':source,'native_type':'.?AVCContainerWindow@@','owner_native_type':'.?AVCRegionAlertEntry@@',
        'native_popup':{'status':'cache_missing'},'engine_show_state':child['engine_show_state'],'container_children':{'children':[child]}}
  sample={'captured_start_unix':1,'captured_end_unix':2,'truncated':False,'matches':[root]}
  with patch('popup_reader.capture_live_ui',return_value=sample) as read:
   result=capture_popups('session',self.root,'regional_notifications',True,'zh')
  read.assert_called_once();window=result['samples'][0]['windows'][0]
  self.assertEqual(window['text_fields'][0]['source'],source)
  self.assertEqual(window['formatting_asset_references'][0]['identifiers'],['font_zh'])
  self.assertEqual(window['native_popup']['status'],'cache_missing');self.assertFalse(result['process_writes'])
  with patch('popup_reader.capture_live_ui',return_value=sample),patch('popup_references.load_references',side_effect=AssertionError('unexpected script read')):
   result=capture_popups('session',self.root,'regional_notifications')
  self.assertNotIn('formatting_asset_references',result['samples'][0]['windows'][0])

if __name__=='__main__':unittest.main()
