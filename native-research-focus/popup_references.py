"""Installed-script references, never native event identity or generated alert text."""
from pathlib import Path
import re
from script_parser import parse_script

LANGUAGES={'en':'english','zh':'simp_chinese'}
LOC=re.compile(r'^\s*([^\s:#]+):\d*\s+"(.*)"\s*(?:#.*)?$')

def literal(raw):
 text=re.sub('§.', '', raw).replace('\\n','\n').replace('\\"','"')
 return None if '$' in text or '[' in text else text

def scalar(nodes,key):
 values=[x for x in nodes if x['key']==key]
 return values[0]['value'] if len(values)==1 and values[0]['children'] is None else None

def load_references(game_root,language):
 if language not in LANGUAGES:raise ValueError('language must be en or zh')
 root=Path(game_root);locales={};events=[];tooltips=[]
 for path in sorted((root/'localisation').rglob('*_l_'+LANGUAGES[language]+'.yml')):
  for line in path.read_text(encoding='utf-8-sig').splitlines():
   match=LOC.match(line)
   if match:locales.setdefault(match[1],[]).append({'raw_text':match[2],'source':path.relative_to(root).as_posix()})
 for path in sorted((root/'events').rglob('*.txt')):
  for node in parse_script(path.read_text(encoding='utf-8-sig')):
   if node['key'] not in ('country_event','news_event','state_event','unit_leader_event'):continue
   children=node['children']
   if children is None:continue
   events.append({'event_id':scalar(children,'id'),'title_key':scalar(children,'title'),
                  'description_key':scalar(children,'desc'),
                  'option_keys':[scalar(x['children'],'name') for x in children if x['key']=='option' and x['children'] is not None],
                  'source':path.relative_to(root).as_posix()})
 from popup_reader import SURFACES
 from script_definitions import read_definitions
 assets=[];graphics={}
 for source in SURFACES.values():
  paths=sorted((root/source).rglob('*.gui')) if source.endswith('/') else [root/source]
  for path in paths:
   if not path.exists():continue
   if not path.resolve().is_relative_to(root.resolve()):raise ValueError('GUI source escapes game root')
   source_name=path.relative_to(root).as_posix();text=path.read_text(encoding='utf-8-sig')
   def visit(nodes,windows=()):
    for node in nodes:
     children=node['children']
     if children is None:continue
     name=scalar(children,'name')
     owners=windows+(name,) if name and node['key']=='containerWindowType' else windows
     key=scalar(children,'pdx_tooltip')
     if name and key:
      tooltips.append({'window':owners[0] if owners else None,'windows':list(owners),'widget':name,'key':key,'source':source_name})
     for field in ('font','spriteType','quadTextureSprite'):
      values=[x['value'] for x in children if x['key']==field and x['children'] is None]
      if name and values:
       assets.append({'windows':list(owners),'widget':name,'source':source_name,
                      'line':text.count('\n',0,node['start'])+1,'field':field,'identifiers':values})
     visit(children,owners)
   visit(parse_script(text))
 has_graphics=any((root/'interface').rglob('*.gfx'))
 for identifier in dict.fromkeys(v for asset in assets for v in asset['identifiers']):
  graphics[identifier]=read_definitions(root,'graphics',identifier)['definitions'] if has_graphics else []
 return {'language':language,'locales':locales,'events':events,'tooltips':tooltips,'assets':assets,'graphics':graphics}

def enrich_window(window,refs):
 locales=refs['locales']
 def exact(key):
  values=locales.get(key,[])
  return literal(values[0]['raw_text']) if len(values)==1 else None
 if window['source']=='interface/eventwindow.gui':
  candidates=[]
  for event in refs['events']:
   title=exact(event['title_key']);body=exact(event['description_key']);options=[exact(k) for k in event['option_keys']]
   if event['event_id'] and title and body and options and all(x is not None for x in options) and (title,body,options)==(window['title'],window['description'],window['option_labels']):
    candidates.append({k:event[k] for k in ('event_id','source','title_key','description_key','option_keys')})
  window['event_id_candidates']=candidates
  window['event_id_reference_status']='unique_literal_match' if len(candidates)==1 else 'ambiguous' if candidates else 'unresolved'
  window.setdefault('event_id_verified',False)
 if window['source'] in ('interface/alerts.gui','interface/theatreselector.gui'):
  names={x['name'] for x in window['icons']+window['buttons']};messages=[]
  for binding in refs['tooltips']:
   if binding['source']!=window['source'] or window['name'] not in binding['windows'] or binding['widget'] not in names:continue
   for value in locales.get(binding['key'],[]):
    text=literal(value['raw_text'])
    messages.append({**binding,**value,'text':text,'status':'literal_reference' if text is not None else 'dynamic_template','runtime_binding_verified':False})
  window['notification_text_references']=messages
  window['notification_text_status']='script_references' if messages else 'unresolved'
 references=[]
 for binding in refs['assets']:
  widgets={item['widget_id'] for item in window.get('text_fields',[])+window.get('icons',[])+window.get('buttons',[])
           if item.get('widget_id') and item['name']==binding['widget'] and item.get('source',window['source'])==binding['source']}
  if binding['source']!=window['source'] or window.get('name') not in binding['windows'] or not widgets:continue
  definitions=[row for identifier in binding['identifiers'] for row in refs['graphics'][identifier]]
  unique=len(binding['identifiers'])==1 and len(definitions)==1 and definitions[0]['id']==binding['identifiers'][0]
  references.append({**binding,'widget_ids':sorted(widgets),'definitions':definitions,
                     'status':'unique_script_reference' if unique else 'ambiguous' if definitions or len(binding['identifiers'])>1 else 'unresolved',
                     'source_scope':'installed_base_only','runtime_binding_verified':False,'asset_identity_verified':False})
 window['formatting_asset_references']=references
 window['formatting_asset_scope']='explicit_gui_fields_only_not_inline_tokens'
 window['script_reference_language']=refs['language']
 window['script_activation_verified']=False
