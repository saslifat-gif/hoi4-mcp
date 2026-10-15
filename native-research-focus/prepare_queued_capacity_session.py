"""Prepare an owned peacetime-reader validation campaign with verified recovery copies."""
import argparse,hashlib,json,shutil,uuid,re
from pathlib import Path
from prepare_session import prepare
from activate_session import activate
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--game-root',required=True);parser.add_argument('--user-root',required=True)
parser.add_argument('--session-root')
parser.add_argument('--defer-activation',action='store_true')
parser.add_argument('--country',choices=('GER','ITA'),default='GER')
args=parser.parse_args()
base=Path(__file__).resolve().parent.parent;user=Path(args.user_root).resolve()
root=Path(args.session_root).resolve() if args.session_root else base/'sessions'/('queued-capacity-20261013-'+uuid.uuid4().hex[:8])
if root.parent!=base/'sessions' or not re.fullmatch(r'queued-capacity-20261013-[a-f0-9]{8}',root.name) or root.exists():raise RuntimeError('New owned session directory required')
c=prepare(Path(args.game_root),root,user/'logs'/'game.log',country=args.country)
recovery=root/'recovery';recovery.mkdir();manifest=[]
for name,p in [('settings.txt',user/'settings.txt'),('autosave.hoi4',user/'save games'/'autosave.hoi4')]:
 backup=recovery/name;shutil.copy2(p,backup);h=hashlib.sha256(p.read_bytes()).hexdigest()
 if hashlib.sha256(backup.read_bytes()).hexdigest()!=h:raise RuntimeError('Recovery backup verification failed; mod not activated')
 manifest.append({'path':str(p),'backup':str(backup),'sha256':h,'mtime_ns':p.stat().st_mtime_ns})
(recovery/'manifest.json').write_text(json.dumps(manifest,indent=2))
if not args.defer_activation:activate(root/'session.json',user)
print(json.dumps({'session_id':c['session_id'],'root':str(root),'backups_verified':True}))
