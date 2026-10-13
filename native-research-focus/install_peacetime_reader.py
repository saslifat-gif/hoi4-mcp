"""Install a pinned read-only native availability module into an owned test session."""
import argparse,hashlib,json,re,shutil
from pathlib import Path
from attach_native_probe import attach
from bind_session import verify_sources
from script_parser import parse_script
from direct_controller import atomic_text
CHOICES_SHA='c9bb633775b9da0cf7e604c439d42a8fc10879c72d45d4dca2d3d1c5d9346720'
def install(sf):
 sf=Path(sf).resolve();c=json.loads(sf.read_text());eq=verify_sources(c);game=Path(c['game_root']);dest=sf.parent/'native'
 observation=json.loads((dest/'native-observation.json').read_text())
 if observation['session_id']!=c['session_id'] or observation['pid']!=c['process_identity']['pid'] or not observation['selection_commands_enabled']:raise RuntimeError('Fresh bound native callback required')
 paths=[game/'documentation'/'dynamic_variables_documentation.md',game/'documentation'/'effects_documentation.md',game/'documentation'/'triggers_documentation.md']+sorted((game/'common'/'resources').glob('*.txt'))
 hashes={str(p.relative_to(game)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
 variables=paths[0].read_text(encoding='utf-8-sig');effects=paths[1].read_text(encoding='utf-8-sig');triggers=paths[2].read_text(encoding='utf-8-sig')
 from peacetime_script import SCALARS,RESOURCE_FIELDS
 for token in ['date','owned_states',*SCALARS.values(),*RESOURCE_FIELDS.values()]:
  if not re.search(r'^### '+re.escape(token)+r'\s*$',variables,re.M):raise RuntimeError('Shipped variable unavailable: '+token)
 if '## for_each_loop' not in effects:raise RuntimeError('Temporary array loop unavailable')
 resources=[]
 for p in paths[3:]:
  for outer in parse_script(p.read_text(encoding='utf-8-sig')):
   if outer['key']=='resources' and outer['children']:
    resources.extend(n['key'] for n in outer['children'] if n['children'] is not None)
 if len(set(resources))!=len(resources):raise RuntimeError('Ambiguous resource definitions')
 catalog={'resources':resources,'equipment_ids':sorted(eq['equipment']),'source_hashes':hashes,'state_is_coastal_supported':bool(re.search(r'^## is_coastal\s*$',triggers,re.M)),'choices_dll_sha256':CHOICES_SHA}
 p=sf.parent/'peacetime-catalog.json';atomic_text(p,json.dumps(catalog,indent=2));c['peacetime_catalog_path']=str(p);c['peacetime_catalog_sha256']=hashlib.sha256(p.read_bytes()).hexdigest();atomic_text(sf,json.dumps(c,indent=2))
 target=dest/'hoi4-native-choices.dll'
 if target.exists():raise RuntimeError('Existing availability installation is not retried')
 source=Path(__file__).parent/'hoi4-native-choices.dll';assert hashlib.sha256(source.read_bytes()).hexdigest()==CHOICES_SHA
 shutil.copyfile(source,target);(dest/'expected-thread.txt').write_text(str(observation['thread_id']),encoding='ascii');attach(sf,target,CHOICES_SHA)
 c['native_construction']={'module_sha256':CHOICES_SHA,'pid':observation['pid'],'world':observation['world']}
 atomic_text(sf,json.dumps(c,indent=2))
 print(json.dumps({'resources':resources,'read_catalog':str(p),'installed':True}))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--session-file',required=True);install(a.parse_args().session_file)
