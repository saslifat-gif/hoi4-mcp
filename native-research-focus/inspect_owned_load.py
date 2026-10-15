"""Actual MCP readback of a protected reload and retained parent request files."""
import argparse,asyncio,hashlib,json,os,sys
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from native_controller import NativeController
from time_controller import TimeController
async def run(args):
 c=NativeController(args.session_file);spec=c.config['owned_load'];parent=Path(spec['parent_session_file']);old=json.loads(parent.read_text());oldnative=parent.parent/'native'
 source=json.loads((oldnative/f'save-execution-{spec["save_request_id"]}.json').read_text());deployed=[json.loads(p.read_text()) for p in oldnative.glob('deployment-execution-*.json')];deployed=next(x for x in deployed if x['operation']=='deploy' and x.get('verified'))
 clock=TimeController(c)
 if c.load()['armed'] or not clock.status()['paused']:raise RuntimeError('Paused disarmed loaded session required')
 params=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).with_name('native_mcp_server.py')),'--session-file',str(c.path)],env=dict(os.environ))
 async with stdio_client(params,errlog=sys.stderr) as (rd,wr):
  async with ClientSession(rd,wr) as client:
   await client.initialize()
   async def call(name,payload={}):
    result=await client.call_tool(name,payload)
    if result.isError:raise RuntimeError(str(result.content))
    return result.structuredContent or json.loads(result.content[0].text)
   status=await call('hoi4_native_status');units=await call('hoi4_military_snapshot');queues=await call('hoi4_deployment_snapshot');time=await call('hoi4_time_status');unit=await call('hoi4_deployed_unit',{'unit_id':deployed['selected']['unit_id']});research=await call('hoi4_native_snapshot')
 old_rejected=False;old_error=''
 try:NativeController(parent).status()
 except (OSError,RuntimeError) as error:
  old_error=str(error);old_rejected=(isinstance(error,OSError) and getattr(error,'winerror',None)==87) or str(error) in ('Bound game process changed or exited','Bound HOI4 process has stopped','Bound HOI4 process is unavailable','Bound process is not HOI4')
 def queue_ids(snapshot):return {(q['conveyor_id'],q['template_id'],q['province_id'],tuple(l['line_id'] for l in q['lines'])) for q in snapshot['conveyors']}
 previous=deployed['deployed_unit'];oldids=set(json.loads((oldnative/'selection-ledger.json').read_text())['requests']);newids=set(c.load()['requests'])
 checks={'actual_MCP':True,'fresh_process':c.config['process_identity']!=old['process_identity'],'fresh_session':c.config['session_id']!=old['session_id'],'bound_world_matches_clock':status['native_callback']['world']==time['world'],'saved_date_retained':0<=time['native_tick']-source['before_clock']['native_tick']<=72,'all_saved_unit_ids_retained':{u['unit_id'] for u in units['units']}=={u['unit_id'] for u in source['before_units']['units']},'queue_identities_retained':queue_ids(queues)==queue_ids(source['before_deployment']),'deployed_template_province_retained':(unit['template_id'],unit['current_province_id'])==(previous['template_id'],previous['current_province_id']),'deployed_equipment_amounts_retained':sorted(e['quantity_raw'] for e in unit['equipment'])==sorted(e['quantity_raw'] for e in previous['equipment']),'deployed_manpower_retained':unit['manpower']==previous['manpower'],'parent_request_files_unchanged':all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest for p,digest in spec['retained_requests'].items()),'old_process_binding_rejected':old_rejected,'no_old_native_ids_republished':not oldids.intersection(newids),'fresh_native_snapshot':bool(research),'paused':time['paused'],'disarmed':status['armed'] is False,'no_input':units['uses_keyboard_or_mouse'] is False}
 report={'session_id':c.config['session_id'],'parent_session_id':old['session_id'],'save_filename':spec['filename'],'checks':checks,'verified':all(checks.values()),'status':status,'clock':time,'unit':unit,'units':units,'queues':queues,'research':research,'old_binding_error':old_error};p=c.native/'owned-load-mcp-test.json';p.write_text(json.dumps(report,indent=2));print(json.dumps({'report':str(p),'verified':report['verified'],'checks':checks,'clock':time}))
 if not report['verified']:raise RuntimeError('Owned-save reload verification incomplete')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--session-file',required=True,type=Path);asyncio.run(run(p.parse_args()))
