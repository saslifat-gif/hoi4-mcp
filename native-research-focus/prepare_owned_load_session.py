"""Validate the owned save, then reuse the existing backup/activation preparation."""
import argparse,json,subprocess,sys
from pathlib import Path
from owned_load import validate_owned_load,configure_owned_load
from activate_session import activate
p=argparse.ArgumentParser();p.add_argument('--game-root',required=True);p.add_argument('--user-root',required=True);p.add_argument('--session-root',required=True);p.add_argument('--start-save',required=True);p.add_argument('--save-sha256',required=True);p.add_argument('--parent-session-file',required=True);a=p.parse_args()
spec=validate_owned_load(a.user_root,a.start_save,a.save_sha256,a.parent_session_file)
result=subprocess.run([sys.executable,str(Path(__file__).with_name('prepare_queued_capacity_session.py')),'--game-root',a.game_root,'--user-root',a.user_root,'--session-root',a.session_root,'--defer-activation'],check=True,capture_output=True,text=True)
c=configure_owned_load(Path(a.session_root)/'session.json',spec)
activate(Path(a.session_root)/'session.json',Path(a.user_root))
print(json.dumps({'session_id':c['session_id'],'root':a.session_root,'backups_verified':True,'owned_load':spec['filename']}))
