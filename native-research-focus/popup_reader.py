"""Read engine-shown event and generic popup containers; never infer screen visibility."""
from runtime_gui import capture_live_ui,GuiSnapshotChanged
SURFACES={'events':'interface/eventwindow.gui','popups':'interface/popupwindow.gui','notifications':'interface/alerts.gui','world_tension':'interface/worldtensionwindowpopup.gui'}
EDGES=('container_children','fixed_window_children','grid_children','listbox_children','dropdown_components')

def summarize_window(root):
 fields=[];buttons=[];icons=[];unresolved=[];seen=set()
 def visit(node,blocked=False):
  key=node['widget_id']
  if key in seen:return
  seen.add(key)
  state=node.get('engine_show_state',{})
  blocked=blocked or (state.get('engine_show_state_verified') and state.get('engine_local_shown') is False)
  if blocked:return
  if not state.get('engine_show_state_verified'):
   unresolved.append({'widget_id':key,'name':node.get('name'),'reason':'unknown_local_show_state'})
  elif node.get('text_status')=='read':
   item={k:node.get(k) for k in ('widget_id','name','native_type','text','raw_text','formatted_runs')}
   fields.append(item)
   if node['native_type'] in ('.?AVCButtonStandard@@','.?AVCCallbackButtonStandard@@'):buttons.append(item)
  elif node.get('text_status') not in ('not_decoded_for_this_widget_type',None):
   unresolved.append({'widget_id':key,'name':node.get('name'),'reason':node['text_status']})
  if node.get('native_type')=='.?AVCIcon@@' and state.get('engine_show_state_verified'):
   icons.append({k:node.get(k) for k in ('widget_id','name','icon_frame')})
  for edge in EDGES:
   detail=node.get(edge,{})
   for group in ('children','rows'):
    for child in detail.get(group,[]):
     if 'widget_id' in child:visit(child,blocked)
 visit(root)
 titles=[x['text'] for x in fields if x['name'] in ('Title','title')]
 descriptions=[x['text'] for x in fields if x['name'] in ('Description','description')]
 labels=[x['text'] for x in fields if x['name']=='Name'] if root['source']==SURFACES['events'] else []
 native=root.get('native_popup',{})
 return {'native_popup':native,'title':titles[0] if len(titles)==1 else None,'description':descriptions[0] if len(descriptions)==1 else None,
         'icons':icons,'content_status':'rendered_text' if any(x['text'] for x in fields) else 'icon_only',
         'option_labels':labels,'native_options':native.get('native_options',[]),'option_ids_verified':'native_options' in native,'option_enabled_state':None,'option_identity_scope':native.get('option_identity_scope'),
         'widget_id':root['widget_id'],'name':root['name'],'source':root['source'],
         'engine_local_shown':True,'text_fields':fields,'buttons':buttons,'unresolved':unresolved,
         'event_id':native.get('event_id'),'event_id_verified':native.get('event_id_verified',False),'option_effects_verified':False,'complete_child_coverage':False,
         'effective_visibility':None,'text_last_update_unix':None}

def window_roots(records):
 nested=set()
 def descendants(node):
  for edge in EDGES:
   for group in ('children','rows'):
    for child in node.get(edge,{}).get(group,[]):
     if 'widget_id' in child and child['widget_id'] not in nested:
      nested.add(child['widget_id']);descendants(child)
 for record in records:descendants(record)
 return [record for record in records if record['widget_id'] not in nested]

def capture_popups(session_file,game_root,kind='all',include_script_references=False,language='en'):
 if kind not in ('all',*SURFACES):raise ValueError('kind must be all, events, popups or notifications')
 refs=None
 if include_script_references:
  from popup_references import load_references,enrich_window
  refs=load_references(game_root,language)
 samples=[]
 for category,source in SURFACES.items():
  if kind!='all' and kind!=category:continue
  for attempt in range(3):
   try:
    sample=capture_live_ui(session_file,game_root,source=source,native_type='CContainerWindow',
                           engine_state='shown',expand_depth=3,limit=100)
    break
   except GuiSnapshotChanged:
    if attempt==2:raise
  windows=[summarize_window(x) for x in window_roots(sample['matches'])]
  if refs is not None:
   for window in windows:enrich_window(window,refs)
  samples.append({'category':category,'captured_start_unix':sample['captured_start_unix'],
                  'captured_end_unix':sample['captured_end_unix'],'truncated':sample['truncated'],
                  'root_grouping':'known_traversal_edges',
                  'windows':windows})
 return {'status':'sampled','samples':samples,'screen_capture':False,'input_events':False,
         'process_writes':False,'atomic_game_frame':False,'complete_popup_coverage':False,
         'limitations':['Engine local shown flags do not prove physical screen visibility.',
                        'Each surface is a separate sample; hidden ancestors in the returned tree are excluded.',
                        'Unsupported owner-specific data, displayed-option availability and non-global alert generation remain unresolved; native alert caches may be stale or contain untranslated localization keys.']}
