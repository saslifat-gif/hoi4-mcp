"""Exercise one ordinary decision through actual MCP in an existing protected session."""
import argparse,asyncio,json,os,sys,time,uuid
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from native_controller import NativeController
from time_controller import TimeController
async def run(args):
 c=NativeController(args.session_file);clock=TimeController(c)
 if not clock.status()['paused'] or c.load()['armed']:raise RuntimeError('Paused disarmed session required')
 ids={k:uuid.uuid4().hex for k in ['speed','resume','select','pause','stop']};report={'session_id':c.config['session_id'],'decision':args.decision,'requests':ids,'actual_MCP':True};path=c.native/('decision-execution-'+ids['select']+'.json')
 def save():path.write_text(json.dumps(report,indent=2))
 with path.open('x') as out:json.dump(report,out)
 params=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).with_name('native_mcp_server.py')),'--session-file',str(args.session_file)],env=dict(os.environ))
 async with stdio_client(params,errlog=sys.stderr) as (rd,wr):
  async with ClientSession(rd,wr) as client:
   await client.initialize()
   async def call(name,arguments):
    result=await client.call_tool(name,arguments)
    if result.isError:raise RuntimeError(str(result.content))
    return result.structuredContent or json.loads(result.content[0].text)
   async def action(name,arguments,receipt,terminal):
    result=await call(name,arguments);deadline=time.monotonic()+120
    while result['stage'] not in terminal:
     if result['stage']=='execution_uncertain' and result.get('reason'):raise RuntimeError('Execution uncertain; retain original ID')
     if time.monotonic()>=deadline:raise RuntimeError('Pending request; retain original ID')
     await asyncio.sleep(.1);result=await call(receipt,{'request_id':arguments['request_id']})
    return result
   async def pause(label,value):
    result=await action('hoi4_set_paused',{'request_id':ids[label],'paused':value},'hoi4_time_receipt',{'time_verified','rejected'})
    if result['stage']=='time_verified':
     deadline=time.monotonic()+20
     while clock.status()['paused']!=value:
      if time.monotonic()>=deadline:raise RuntimeError('Clock readback pending; retain original ID')
      await asyncio.sleep(.05)
    return result
   report['before']=await call('hoi4_decision_snapshot',{});save();await call('hoi4_native_arm',{'enabled':True})
   try:
    speed=await action('hoi4_set_speed',{'request_id':ids['speed'],'speed':5},'hoi4_time_receipt',{'time_verified','rejected'})
    if speed['stage']!='time_verified' or (await pause('resume',False))['stage']!='time_verified':raise RuntimeError('Time change rejected')
    selected=await action('hoi4_select_decision',{'request_id':ids['select'],'decision':args.decision},'hoi4_native_receipt',{'decision_verified','rejected'});report['selected']=selected;save()
    if (await pause('pause',True))['stage']!='time_verified':raise RuntimeError('Pause rejected')
    report['after']=await call('hoi4_decision_snapshot',{});report['direct_after']=c.decision_snapshot();save()
    report['duplicate']=await call('hoi4_select_decision',{'request_id':ids['select'],'decision':args.decision});report['after_duplicate']=await call('hoi4_decision_snapshot',{});save()
   finally:
    try:report['final_pause']=await pause('stop',True)
    finally:c.arm(False);report['final_clock']=clock.status();report['final_armed']=c.load()['armed'];save()
 def count(s):return sum(row['native_execution_counter'] for row in s['execution_counters'] if row['decision_id']==args.decision and row['native_target_tag']==0)
 selected=report['selected'];checks={'actual_MCP':True,'native_verified':selected['stage']=='decision_verified','counter_verified':selected.get('counter_verified') is True,'positive_pp_cost':selected.get('political_power_cost_raw',0)>0,'exact_native_payment':selected.get('cost_verified') is True and selected.get('political_power_before_raw',0)-selected.get('political_power_after_raw',0)==max(0,selected.get('political_power_cost_raw',0)),'independent_counter_increment':count(report['after'])==count(report['before'])+1,'independent_snapshot_matches':report['after']==report['direct_after'],'duplicate_receipt_unchanged':report['duplicate']==selected,'duplicate_state_unchanged':report['after']==report['after_duplicate'],'paused':report['final_clock']['paused'],'disarmed':report['final_armed'] is False,'no_input':selected['uses_keyboard_or_mouse'] is False}
 report.update(checks=checks,verified=all(checks.values()));save();print(json.dumps({'report':str(path),'verified':report['verified'],'checks':checks,'selected':selected}))
 if not report['verified']:raise RuntimeError('Decision verification incomplete; preserve report/IDs')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--session-file',required=True,type=Path);p.add_argument('--decision',required=True);asyncio.run(run(p.parse_args()))
