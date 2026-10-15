"""Installed gameplay/graphics definitions; never runtime eligibility or rendering."""
import hashlib
from pathlib import Path
from script_parser import parse_script

SOURCES={'ideas':('common/ideas','*.txt','ideas'),'characters':('common/characters','*.txt','characters'),
         'decisions':('common/decisions','*.txt',None),'resources':('common/resources','*.txt','resources'),
         'graphics':('interface','*.gfx',None)}

def read_definitions(game_root,category,identifier=None):
 if category not in SOURCES:raise ValueError('Unknown script category: '+str(category))
 if identifier is not None and (not isinstance(identifier,str) or not identifier or len(identifier)>159):
  raise ValueError('An exact script identifier is required')
 root=Path(game_root).resolve();directory,pattern,wrapper=SOURCES[category];records=[];hashes={}
 files=sorted((root/directory).rglob(pattern))
 if not files:raise ValueError('Installed scripts missing: '+directory)
 for path in files:
  if not path.resolve().is_relative_to(root):raise ValueError('Script source escapes game root')
  raw=path.read_bytes();text=raw.decode('utf-8-sig');source=path.relative_to(root).as_posix()
  digest=hashlib.sha256(raw).hexdigest();hashes[source]=digest
  # Exact queries cannot match a file that never contains the identifier.
  if identifier is not None and identifier not in text:continue
  nodes=parse_script(text)
  if wrapper:nodes=[child for node in nodes if node['key']==wrapper and node['children'] is not None for child in node['children']]
  def visit(items,parents=()):
   for node in items:
    if node['children'] is None:continue
    route=parents+(node['key'],)
    names=[child['value'] for child in node['children'] if child['key']=='name' and child['children'] is None] if category=='graphics' else [node['key']]
    # Graphics identity comes from literal name fields, never a guessed prefix.
    if names and (identifier is None or identifier in names):
     record={'id':names[0] if len(names)==1 else None,'script_path':list(route),'source':source,
             'source_sha256':digest,'line':text.count('\n',0,node['start'])+1}
     if category=='graphics':record.update(name_literals=names,definition_type=node['key'])
     if identifier is not None:record.update(definition=node,raw_script=text[node['start']:node['end']])
     records.append(record)
    if identifier is not None or category=='graphics':visit(node['children'],route)
  visit(nodes)
 return {'category':category,'identifier':identifier,'definitions':records,'source_hashes':hashes,
         'source_scope':'installed_base_only','active_overlay_verified':False,
         'runtime_availability_verified':False,'native_identity_verified':False,
         'uses_keyboard_or_mouse':False,'process_writes':False}
