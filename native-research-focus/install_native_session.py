"""Install the two pinned modules into a NEW already-bound authorized test session."""
import argparse,hashlib,json,shutil
from pathlib import Path
from attach_native_probe import attach
MODULES={'hoi4-native-probe.dll':'f40e2ad64c93e761942fa9d7d686e0e2eb2131f27bae3df8e37d71d4d6437928','hoi4-native-selection.dll':'dffc6a1fee8c4bfcf3ea477db60adbf171636ba75b3c84e82d60a55b348c85b6'}
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
