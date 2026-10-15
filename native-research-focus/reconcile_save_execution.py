"""Observe the original completed native save and its duplicate without saving again."""
import argparse,asyncio,hashlib,json,os,sys
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from native_controller import NativeController
from time_controller import TimeController
from save_paths import owned_save_path
async def run(args):
 c=NativeController(args.session_file);clock=TimeController(c);rid=args.request_id
 if c.load()['armed'] or not clock.status()['paused']:raise RuntimeError('Paused disarmed protected campaign required')
 report_path=c.native/f'save-execution-{rid}.json';before=json.loads(report_path.read_text());receipt=clock.receipt(rid)
 if receipt['stage']!='save_file_observed' or before['selected']!=receipt:raise RuntimeError('Original completed save receipt required')
 basename=f'mcp_{c.config["session_id"]}_{rid}';user=json.loads((c.path.parent/'activation.json').read_text())['user_root']
 path=owned_save_path(user,receipt['path'],basename);temporary=owned_save_path(user,receipt['temporary_path'],basename+'_temp')
 data=path.read_bytes();stat=path.stat();original=(c.native/f'time-receipt-{rid}.json').read_bytes();ledger=clock.path.read_bytes()
 params=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).with_name('native_mcp_server.py')),'--session-file',str(c.path)],env=dict(os.environ))
 async with stdio_client(params,errlog=sys.stderr) as (rd,wr):
  async with ClientSession(rd,wr) as client:
   await client.initialize()
   async def call(name):
    result=await client.call_tool(name,{'request_id':rid})
    if result.isError:raise RuntimeError(str(result.content))
    return result.structuredContent or json.loads(result.content[0].text)
   actual=await call('hoi4_time_receipt');duplicate=await call('hoi4_save_campaign')
 after=path.read_bytes();after_stat=path.stat();now=clock.status()
 checks={'actual_MCP':True,'native_file_observed':actual['native_file_observation_verified'],'exact_owned_basename':actual['basename']==basename,'inside_user_save_root':True,'nonempty_file':len(data)>1024,'temporary_absent':temporary.parent==path.parent and not temporary.exists(),'native_receipt_unchanged':original==(c.native/f'time-receipt-{rid}.json').read_bytes(),'request_ledger_unchanged':ledger==clock.path.read_bytes(),'duplicate_receipt_unchanged':receipt==actual==duplicate,'duplicate_bytes_unchanged':after==data,'duplicate_timestamp_unchanged':stat.st_mtime_ns==after_stat.st_mtime_ns,'game_tick_unchanged':now['native_tick']==before['before_clock']['native_tick'],'paused':now['paused'],'disarmed':c.load()['armed'] is False,'no_input':actual['uses_keyboard_or_mouse'] is False}
 report={'session_id':c.config['session_id'],'request_id':rid,'checks':checks,'verified':all(checks.values()),'file':{'path':str(path),'sha256':hashlib.sha256(data).hexdigest(),'size':len(data),'mtime_ns':stat.st_mtime_ns,'magic_hex':data[:16].hex()},'native_receipt':receipt,'reload_verified':False,'boundary':'Native unique file creation and independent stable file/duplicate checks; campaign contents and restart/load remain separate.'}
 out=c.native/f'save-reconciled-{rid}.json';out.write_text(json.dumps(report,indent=2));print(json.dumps({'report':str(out),'verified':report['verified'],'checks':checks,'file':report['file'],'reload_verified':False}))
 if not report['verified']:raise RuntimeError('Read-only save verification incomplete')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--session-file',type=Path,required=True);p.add_argument('--request-id',required=True);asyncio.run(run(p.parse_args()))
