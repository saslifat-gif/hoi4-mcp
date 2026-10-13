import argparse,json,hashlib,shutil
from pathlib import Path
from native_controller import NativeController
from attach_native_probe import attach
from time_controller import DLL_SHA
def install(sf):
 c=NativeController(sf);o=c.check();source=Path(__file__).parent/'hoi4-native-time.dll';dest=c.native/source.name
 if dest.exists():raise RuntimeError('Existing time installation is not automatically retried')
 if hashlib.sha256(source.read_bytes()).hexdigest()!=DLL_SHA:raise RuntimeError('Time DLL hash mismatch')
 (c.native/'expected-world.txt').write_text(o['world'][2:],encoding='ascii');shutil.copyfile(source,dest);attach(sf,dest,DLL_SHA)
 return {'stage':'installed_waiting_for_frame_callback'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--session-file',required=True);a=p.parse_args();print(json.dumps(install(a.session_file)))
