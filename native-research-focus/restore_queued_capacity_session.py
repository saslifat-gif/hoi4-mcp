"""Guarded recovery of ONLY this owned native test campaign; no game/UI input."""
import ctypes,hashlib,json,os,shutil,sys,re
from pathlib import Path
from ctypes import wintypes as W
from direct_process import process_identity
from activate_session import deactivate
sf=Path(sys.argv[1]);c=json.loads(sf.read_text());root=sf.parent
if not re.fullmatch(r'queued-capacity-20261013(?:-[a-f0-9]{8})?',root.name) or c['mode']!='singleplayer_test':raise RuntimeError('Expected an owned queued-capacity test session')
manifest=json.loads((root/'recovery'/'manifest.json').read_text())
for x in manifest:
 if hashlib.sha256(Path(x['backup']).read_bytes()).hexdigest()!=x['sha256']:raise RuntimeError('Recovery backup changed; no restoration applied')
# Native interface is disarmed before ending its exact owned process.
ledger=root/'native'/'selection-ledger.json'
if ledger.exists():
 d=json.loads(ledger.read_text());d['armed']=False;ledger.write_text(json.dumps(d,indent=2))
(root/'native'/'request.txt').unlink(missing_ok=True)
import subprocess
running=subprocess.check_output(['powershell.exe','-NoProfile','-Command',"@(Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'hoi4.exe'} | Select-Object -ExpandProperty ProcessId) -join ','"],text=True).strip()
owned_stopped=False
if running:
 if running!=str(c['process_identity']['pid']):raise RuntimeError('Another HOI4 process is active; recovery refused')
 if process_identity(c['process_identity']['pid'])!=c['process_identity']:raise RuntimeError('Owned process identity changed; recovery refused')
 k=ctypes.WinDLL('kernel32',use_last_error=True);k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
 k.TerminateProcess.argtypes=[W.HANDLE,W.UINT];k.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD];k.CloseHandle.argtypes=[W.HANDLE]
 h=k.OpenProcess(0x100001,False,c['process_identity']['pid'])
 if not h:raise RuntimeError('Cannot open owned game for recovery')
 try:
  if not k.TerminateProcess(h,0):raise RuntimeError('Cannot stop owned game; restoration refused')
  if k.WaitForSingleObject(h,10000)!=0:raise RuntimeError('Owned game exit unverified; restoration refused')
 finally:k.CloseHandle(h)
 owned_stopped=True
report={'owned_game_stopped_by_recovery':owned_stopped,'no_HOI4_process_remaining':True,'session_id':c['session_id'],'restored':[],'settings_preserved':True}
for x in manifest:
 p=Path(x['path'])
 if p.name=='settings.txt':
  original=Path(x['backup']).read_bytes();current=p.read_bytes()
  value=re.findall(rb'(?m)^save_as_binary=(yes|no)',original)
  if len(value)!=1 or len(re.findall(rb'(?m)^save_as_binary=(yes|no)',current))!=1:raise RuntimeError('Save-format setting is missing or ambiguous')
  restored=re.sub(rb'(?m)(^save_as_binary=)(yes|no)',lambda m:m.group(1)+value[0],current)
  temporary=p.with_name(p.name+'.codex-restore');temporary.write_bytes(restored);os.replace(temporary,p)
  report['test_save_format_restored']=True
  report['settings_current_sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
  report['settings_original_sha256']=x['sha256']
  continue # We did not edit settings; preserve game/user updates.
 if p.exists():shutil.copy2(p,root/'private-test-autosave.hoi4')
 shutil.copyfile(x['backup'],p);os.utime(p,ns=(x['mtime_ns'],x['mtime_ns']))
 if hashlib.sha256(p.read_bytes()).hexdigest()!=x['sha256'] or p.stat().st_mtime_ns!=x['mtime_ns']:raise RuntimeError('Restored save identity mismatch')
 report['restored'].append({'file':p.name,'sha256':x['sha256'],'mtime_ns':x['mtime_ns']})
report['mod_deactivation']=deactivate(sf)
(root/'recovery-result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
