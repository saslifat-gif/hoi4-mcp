"""Advance only normal game time through actual MCP, then inspect training."""
import argparse,asyncio,json,os,sys,time,uuid
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from native_controller import NativeController
from time_controller import TimeController
async def run(args):
 c=NativeController(args.session_file);clock=TimeController(c);start=clock.status()
 if not start['paused'] or c.load()['armed']:raise RuntimeError('Paused disarmed protected campaign required')
 ids={key:uuid.uuid4().hex for key in ['speed','resume','pause']}
 report={'session_id':c.config['session_id'],'requests':ids,'actual_MCP':True,'before':c.deployment_snapshot(),'clock_before':start,'requested_days':args.days}
 path=c.native/f'deployment-training-{ids["resume"]}.json'
 def save():path.write_text(json.dumps(report,indent=2))
 with path.open('x') as f:json.dump(report,f)
 params=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).with_name('native_mcp_server.py')),'--session-file',str(c.path)],env=dict(os.environ))
 async with stdio_client(params,errlog=sys.stderr) as (rd,wr):
  async with ClientSession(rd,wr) as client:
   await client.initialize()
   async def call(name,payload):
    result=await client.call_tool(name,payload)
    if result.isError:raise RuntimeError(str(result.content))
    return result.structuredContent or json.loads(result.content[0].text)
   async def action(name,payload):
    result=await call(name,payload);deadline=time.monotonic()+20
    while result['stage'] not in ('time_verified','rejected'):
     if result['stage']=='execution_uncertain' and result.get('reason'):raise RuntimeError('Time request uncertain; retain original ID')
     if time.monotonic()>deadline:raise RuntimeError('Time receipt pending; retain original ID')
     await asyncio.sleep(.1);result=await call('hoi4_time_receipt',{'request_id':payload['request_id']})
    if result['stage']!='time_verified':raise RuntimeError('Normal time command rejected')
    return result
   await call('hoi4_native_arm',{'enabled':True})
   try:
    report['speed']=await action('hoi4_set_speed',{'request_id':ids['speed'],'speed':5})
    report['resume']=await action('hoi4_set_paused',{'request_id':ids['resume'],'paused':False});save()
    deadline=time.monotonic()+args.seconds
    while True:
     now=await call('hoi4_time_status',{})
     if now['native_tick']-start['native_tick']>=args.days*24:break
     if time.monotonic()>deadline:break
     await asyncio.sleep(.5)
    report['clock_running']=now;save()
   finally:
    try:
     report['pause']=await action('hoi4_set_paused',{'request_id':ids['pause'],'paused':True})
     deadline=time.monotonic()+10
     while not clock.status()['paused']:
      if time.monotonic()>deadline:raise RuntimeError('Pause readback pending')
      await asyncio.sleep(.05)
    finally:c.arm(False);report['final_clock']=clock.status();report['final_armed']=c.load()['armed'];save()
 report['after']=c.deployment_snapshot()
 old={line['line_id']:line['current_entry'] for q in report['before']['conveyors'] for line in q['lines']}
 new={line['line_id']:line['current_entry'] for q in report['after']['conveyors'] for line in q['lines']}
 checks={'actual_MCP':True,'requested_time_elapsed':report['final_clock']['native_tick']-start['native_tick']>=args.days*24,'same_lines':set(old)==set(new),'training_increased':bool(old) and all(old[k] and new[k] and new[k]['training_raw']>old[k]['training_raw'] for k in old),'paused':report['final_clock']['paused'],'disarmed':report['final_armed'] is False}
 report.update(checks=checks,verified=all(checks.values()));save();print(json.dumps({'report':str(path),'verified':report['verified'],'checks':checks,'after':report['after']}))
 if not report['verified']:raise RuntimeError('Training progression verification incomplete')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--session-file',type=Path,required=True);p.add_argument('--days',type=int,choices=range(1,61),default=30);p.add_argument('--seconds',type=int,choices=range(1,601),default=240);asyncio.run(run(p.parse_args()))
