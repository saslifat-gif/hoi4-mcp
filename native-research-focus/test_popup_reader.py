import unittest
from popup_reader import summarize_window,window_roots,capture_popups,GuiSnapshotChanged
from unittest.mock import patch

def node(wid,name,text=None,shown=True,kind='.?AVCInstantTextBox@@'):
 return {'widget_id':wid,'name':name,'source':'interface/eventwindow.gui','native_type':kind,'text_status':'read' if text is not None else 'not_decoded_for_this_widget_type','text':text,'raw_text':text,'formatted_runs':[], 'engine_show_state':{'engine_show_state_verified':shown is not None,'engine_local_shown':shown}}
class PopupTests(unittest.TestCase):
 def root(self,*children):
  r=node('root','country_event',kind='.?AVCContainerWindow@@');r['container_children']={'children':list(children)};return r
 def test_text_and_buttons_preserve_order_and_duplicates(self):
  result=summarize_window(self.root(node('a','title','Same'),node('b','desc','Same'),node('c','option','Continue',kind='.?AVCButtonStandard@@')))
  self.assertEqual([x['text'] for x in result['text_fields']],['Same','Same','Continue'])
  self.assertEqual(result['buttons'][0]['name'],'option');self.assertIsNone(result['event_id'])
 def test_native_metadata_survives_summary(self):
  root=self.root();root['native_popup']={'status':'native_event_id','event_id':'native.1','event_id_verified':True}
  d=summarize_window(root);self.assertEqual(d['event_id'],'native.1');self.assertTrue(d['event_id_verified'])
 def test_hidden_ancestor_excludes_cached_descendant_text(self):
  parent=node('p','old_window',shown=False,kind='.?AVCContainerWindow@@');parent['container_children']={'children':[node('a','old_title','Cached')]}
  self.assertEqual(summarize_window(self.root(parent))['text_fields'],[])
 def test_unknown_show_state_remains_unresolved(self):
  result=summarize_window(self.root(node('a','option','Cached',shown=None)))
  self.assertEqual(result['text_fields'],[]);self.assertEqual(result['unresolved'][0]['reason'],'unknown_local_show_state')
 def test_nested_panels_are_grouped_under_owning_event(self):
  title=node('title','Title','Event title');desc=node('desc','Description','Event body')
  panel=node('panel','top_Window',kind='.?AVCContainerWindow@@');panel['container_children']={'children':[title]}
  option=node('option','Name','Option label');root=self.root(panel,desc,option)
  self.assertEqual(window_roots([panel,root]),[root])
  result=summarize_window(root);self.assertEqual(result['title'],'Event title');self.assertEqual(result['description'],'Event body');self.assertEqual(result['option_labels'],['Option label'])
 def test_native_option_identity_scope_survives_summary(self):
  root=self.root();root['native_popup']={'native_options':[{'native_index':0,'name_key':'event.a'}],'option_identity_scope':'event_definition_not_displayed_choices'}
  d=summarize_window(root);self.assertTrue(d['option_ids_verified']);self.assertEqual(d['native_options'][0]['name_key'],'event.a');self.assertEqual(d['option_identity_scope'],'event_definition_not_displayed_choices')
 def test_world_tension_notification_surface_is_requested(self):
  sample={'captured_start_unix':1,'captured_end_unix':2,'truncated':False,'matches':[]}
  with patch('popup_reader.capture_live_ui',return_value=sample) as read:capture_popups('session','game','world_tension')
  self.assertEqual(read.call_args.kwargs['source'],'interface/worldtensionwindowpopup.gui')
 def test_changed_registry_retries_a_read_only_sample(self):
  sample={'captured_start_unix':1,'captured_end_unix':2,'truncated':False,'matches':[]}
  with patch('popup_reader.capture_live_ui',side_effect=[GuiSnapshotChanged('changed'),sample]) as read:
   self.assertEqual(capture_popups('session','game','events')['samples'][0]['windows'],[])
  self.assertEqual(read.call_count,2)
 def test_unsupported_layout_does_not_retry(self):
  with patch('popup_reader.capture_live_ui',side_effect=RuntimeError('unsupported')) as read:
   with self.assertRaisesRegex(RuntimeError,'unsupported'):capture_popups('session','game','events')
  read.assert_called_once()
 def test_persistent_churn_returns_no_partial_sample(self):
  with patch('popup_reader.capture_live_ui',side_effect=GuiSnapshotChanged('changed')) as read:
   with self.assertRaises(GuiSnapshotChanged):capture_popups('session','game','events')
  self.assertEqual(read.call_count,3)
 def test_notification_icons_preserved_without_inventing_text(self):
  icon=node('icon','red_alert_glow',kind='.?AVCIcon@@');icon['icon_frame']={'native_frame_value':0,'frame_meaning_verified':False}
  root=self.root(icon);root['source']='interface/alerts.gui';root['name']='global_alerticon_window'
  result=summarize_window(root);self.assertEqual(result['icons'][0]['name'],'red_alert_glow');self.assertEqual(result['content_status'],'icon_only');self.assertIsNone(result['title'])
 def test_hidden_notification_icon_is_excluded(self):
  icon=node('icon','red_alert_glow',shown=False,kind='.?AVCIcon@@');icon['icon_frame']={'native_frame_value':0}
  self.assertEqual(summarize_window(self.root(icon))['icons'],[])
 def test_notification_surface_is_requested(self):
  sample={'captured_start_unix':1,'captured_end_unix':2,'truncated':False,'matches':[]}
  with patch('popup_reader.capture_live_ui',return_value=sample) as read:
   result=capture_popups('session','game','notifications')
  self.assertEqual(result['samples'][0]['category'],'notifications');self.assertEqual(read.call_args.kwargs['source'],'interface/alerts.gui')
 def test_distinct_notification_instances_keep_identical_names(self):
  a=self.root();b=self.root();a['widget_id']='a';b['widget_id']='b';a['name']=b['name']='global_alerticon_window'
  self.assertEqual(len(window_roots([a,b])),2)
 def test_generic_popup_title_body_and_button_caption(self):
  root=self.root(node('t','title','Popup title'),node('d','description','Popup body'),node('b','accept_button','Accept',kind='.?AVCButtonStandard@@'))
  root['source']='interface/popupwindow.gui';result=summarize_window(root)
  self.assertEqual((result['title'],result['description']),('Popup title','Popup body'));self.assertEqual(result['buttons'][0]['text'],'Accept');self.assertEqual(result['option_labels'],[])
 def test_hidden_popup_button_is_not_an_available_caption(self):
  root=self.root(node('b','accept_button','Cached',shown=False,kind='.?AVCButtonStandard@@'))
  self.assertEqual(summarize_window(root)['buttons'],[])
 def test_shared_descendant_is_not_duplicated(self):
  child=node('a','title','Title');result=summarize_window(self.root(child,child))
  self.assertEqual(len(result['text_fields']),1);self.assertFalse(result['complete_child_coverage']);self.assertIsNone(result['effective_visibility'])
if __name__=='__main__':unittest.main()
