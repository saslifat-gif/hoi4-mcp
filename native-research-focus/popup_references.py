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
 path=root/'interface/alerts.gui'
 if path.exists():
  def visit(nodes,window=None):
   for node in nodes:
    children=node['children']
    if children is None:continue
    name=scalar(children,'name');owner=(window or name) if node['key']=='containerWindowType' else window
    key=scalar(children,'pdx_tooltip')
    if name and key:tooltips.append({'window':window,'widget':name,'key':key,'source':'interface/alerts.gui'})
    visit(children,owner)
  visit(parse_script(path.read_text(encoding='utf-8-sig')))
 return {'language':language,'locales':locales,'events':events,'tooltips':tooltips}

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
 if window['source']=='interface/alerts.gui':
  names={x['name'] for x in window['icons']+window['buttons']};messages=[]
  for binding in refs['tooltips']:
   if binding['window']!=window['name'] or binding['widget'] not in names:continue
   for value in locales.get(binding['key'],[]):
    text=literal(value['raw_text'])
    messages.append({**binding,**value,'text':text,'status':'literal_reference' if text is not None else 'dynamic_template','runtime_binding_verified':False})
  window['notification_text_references']=messages
  window['notification_text_status']='script_references' if messages else 'unresolved'
 window['script_reference_language']=refs['language']
 window['script_activation_verified']=False
