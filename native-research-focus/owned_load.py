"""Prepare a fresh protected session to load one independently verified owned save."""
import hashlib,json,re
from pathlib import Path
from direct_controller import SESSION_FLAG,atomic_text
from save_paths import owned_save_path

def validate_owned_load(user_root,filename,digest,parent_session_file):
 match=re.fullmatch(r'mcp_([a-f0-9]{32})_([a-f0-9]{32})\.hoi4',filename)
 if not match or not re.fullmatch('[a-f0-9]{64}',digest):raise ValueError('Exact owned save filename/hash required')
 sid,rid=match.groups();parent=Path(parent_session_file).resolve();config=json.loads(parent.read_text())
 if config['session_id']!=sid or config['mode']!='singleplayer_test' or config['country']!='GER':raise RuntimeError('Parent campaign binding mismatch')
 receipt=json.loads((parent.parent/'native'/f'time-receipt-{rid}.json').read_text())
 report=json.loads((parent.parent/'native'/f'save-reconciled-{rid}.json').read_text())
 if receipt['session_id']!=sid or receipt['request_id']!=rid or receipt['stage']!='save_file_observed' or report['verified'] is not True or report['request_id']!=rid or report['file']['sha256']!=digest:raise RuntimeError('Verified parent save receipt required')
 path=owned_save_path(user_root,receipt['path'],filename[:-5]);data=path.read_bytes()
 if hashlib.sha256(data).hexdigest()!=digest or not data.startswith((b'HOI4bin',b'HOI4txt')):raise RuntimeError('Owned save bytes changed')
 descriptor=parent.parent/'CodexCommands.mod';activation=json.loads((parent.parent/'activation.json').read_text());descriptor_bytes=descriptor.read_text(encoding='utf-8').encode('utf-8')
 if hashlib.sha256(descriptor_bytes).hexdigest()!=activation['descriptor_sha256']:raise RuntimeError('Parent mod descriptor changed')
 names=re.findall(r'^name="([^"\r\n]+)"$',descriptor_bytes.decode('utf-8'),re.M)
 if len(names)!=1:raise RuntimeError('Parent fixture mod name ambiguous')
 native=parent.parent/'native';paths=[native/'selection-ledger.json',native/'time-ledger.json',*sorted(native.glob('*receipt-*.json'))]
 if json.loads(paths[0].read_text())['armed']:raise RuntimeError('Disarmed parent ledger required')
 return {'filename':filename,'sha256':digest,'path':str(path),'parent_session_file':str(parent),'parent_session_id':sid,'save_request_id':rid,'required_mod_name':names[0],'retained_requests':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}

def configure_owned_load(session_file,spec):
 sf=Path(session_file);c=json.loads(sf.read_text());sid=c['session_id'];country=c['country'];hook=Path(c['hook_path']);text=hook.read_text()
 if c.get('process_identity') or c.get('owned_load'):raise RuntimeError('Only an unbound fresh load session may be configured')
 anchor=f'on_daily_{country} = {{ effect = {{ {country} = {{\n'
 if text.count(anchor)!=1:raise RuntimeError('Owned daily hook shape changed')
 # A loaded save may predate this session flag. Bootstrap ONLY interface logging;
 # no research/resources/readiness/combat fields or old commands are applied.
 bootstrap=f'''        if = {{ limit = {{ is_ai = no NOT = {{ has_country_flag = {SESSION_FLAG}{sid} }} }}
            set_country_flag = {SESSION_FLAG}{sid}
            log = "CODEX_COMMAND_SESSION|{sid}|READY|country={country}"
        }}
'''
 atomic_text(hook,text.replace(anchor,anchor+bootstrap,1))
 # The native loader compares saved mod DISPLAY NAMES to enabled mod names.
 # Keep this same logging-only fixture's name while using a fresh SID/path.
 for descriptor in (sf.parent/'CodexCommands.mod',sf.parent/'mod/descriptor.mod'):
  original=descriptor.read_text();renamed,count=re.subn(r'^name="[^"\r\n]*"$',lambda m:'name='+json.dumps(spec['required_mod_name']),original,count=1,flags=re.M)
  if count!=1:raise RuntimeError('Fresh fixture descriptor name missing')
  atomic_text(descriptor,renamed)
 c['owned_load']=spec;atomic_text(sf,json.dumps(c,indent=2));return c
