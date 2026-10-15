"""Install the two pinned modules into a NEW already-bound authorized test session."""
import argparse,hashlib,json,shutil
from pathlib import Path
from attach_native_probe import attach
MODULES={'hoi4-native-probe.dll':'dad934b71750c9e4562e77b17dfaf82dfeb3947544193b72c76573f3dd6a9b21','hoi4-native-selection.dll':'ea4c632ab61bfe03315b952a9d5ee28b9c7c45b1d48b2428e0c9a0646a096cc0'}
def install(session_file):
 sf=Path(session_file).resolve();dest=sf.parent/'native';dest.mkdir(exist_ok=True)
 if any((dest/n).exists() for n in MODULES):raise RuntimeError('Existing installation is not automatically retried or replaced')
 source=Path(__file__).parent
 for name,digest in MODULES.items():
  p=source/name
  if hashlib.sha256(p.read_bytes()).hexdigest()!=digest:raise RuntimeError('Pinned module hash mismatch')
 for name,digest in MODULES.items():
  p=dest/name;shutil.copyfile(source/name,p);attach(sf,p,digest)
 return {'stage':'installed_waiting_for_native_daily_callback','selection_verified':False,'uses_keyboard_or_mouse':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--session-file',required=True);a=p.parse_args();print(json.dumps(install(a.session_file)))
