"""Verify unique ordinary native save creation through actual MCP; no reload claim."""
import argparse,asyncio,hashlib,json,os,sys,time,uuid
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from native_controller import NativeController
from time_controller import TimeController
from save_paths import owned_save_path
async def run(args):
 c=NativeController(args.session_file);clock=TimeController(c);start=clock.status()
 if not start['paused'] or c.load()['armed']:raise RuntimeError('Paused disarmed protected campaign required')
 rid=uuid.uuid4().hex;basename=f'mcp_{c.config["session_id"]}_{rid}'
 report={'request_id':rid,'session_id':c.config['session_id'],'actual_MCP':True,'before_clock':start,'before_units':c.military_snapshot(),'before_deployment':c.deployment_snapshot(),'reload_verified':False};p=c.native/f'save-execution-{rid}.json'
 def save():p.write_text(json.dumps(report,indent=2))
 with p.open('x') as f:json.dump(report,f)
 user=Path(json.loads((c.path.parent/'activation.json').read_text())['user_root']);owned_directory=(user/'save games').resolve()
 if list(owned_directory.rglob(basename+'*.hoi4')):raise RuntimeError('Owned unique save already exists')
 params=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).with_name('native_mcp_server.py')),'--session-file',str(c.path)],env=dict(os.environ))
 async with stdio_client(params,errlog=sys.stderr) as (rd,wr):
  async with ClientSession(rd,wr) as client:
   await client.initialize()
   async def call(name,payload):
    result=await client.call_tool(name,payload)
    if result.isError:raise RuntimeError(str(result.content))
    return result.structuredContent or json.loads(result.content[0].text)
   await call('hoi4_native_arm',{'enabled':True})
   try:
    result=await call('hoi4_save_campaign',{'request_id':rid});deadline=time.monotonic()+120
    while result['stage'] not in ('save_file_observed','rejected'):
     if result['stage']=='execution_uncertain' and result.get('reason'):raise RuntimeError('Save uncertain; preserve original ID')
     if time.monotonic()>deadline:raise RuntimeError('Save pending; preserve original ID')
     await asyncio.sleep(.1);result=await call('hoi4_time_receipt',{'request_id':rid})
    report['selected']=result;save()
    if result['stage']!='save_file_observed':raise RuntimeError('Native save rejected')
    path=owned_save_path(user,result['path'],basename);temporary=owned_save_path(user,result['temporary_path'],basename+'_temp')
    if path.name!=basename+'.hoi4':raise RuntimeError('Native save filename differs from owned basename')
    data=path.read_bytes();digest=hashlib.sha256(data).hexdigest();stat=path.stat()
    report['file']={'path':str(path),'sha256':digest,'size':len(data),'mtime_ns':stat.st_mtime_ns,'magic_hex':data[:16].hex()}
    report['duplicate']=await call('hoi4_save_campaign',{'request_id':rid});after=path.read_bytes();after_stat=path.stat()
    report['checks']={'actual_MCP':True,'native_file_observed':result['native_file_observation_verified'],'unique_owned_basename':result['basename']==basename,'inside_protected_profile':True,'file_nonempty':len(data)>1024,'temporary_absent':not temporary.exists() and temporary.parent==path.parent,'duplicate_receipt_unchanged':result==report['duplicate'],'file_bytes_unchanged':after==data,'file_timestamp_unchanged':stat.st_mtime_ns==after_stat.st_mtime_ns,'clock_unchanged':clock.status()['native_tick']==start['native_tick'],'paused':clock.status()['paused'],'no_input':result['uses_keyboard_or_mouse'] is False};save()
   finally:c.arm(False);report['final_clock']=clock.status();report['final_armed']=c.load()['armed'];save()
 report['checks']['disarmed']=report['final_armed'] is False;report['verified']=all(report['checks'].values());save();print(json.dumps({'report':str(p),'verified':report['verified'],'checks':report['checks'],'file':report.get('file'),'reload_verified':False}))
 if not report['verified']:raise RuntimeError('Native save file verification incomplete')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--session-file',type=Path,required=True);asyncio.run(run(p.parse_args()))
