"""Exercise one ordinary resource import through actual MCP in an existing protected session."""
import argparse,asyncio,json,os,sys,time,uuid
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from native_controller import NativeController
from time_controller import TimeController
async def run(args):
 c=NativeController(args.session_file);clock=TimeController(c)
 if not clock.status()['paused'] or c.load()['armed']:raise RuntimeError('Paused disarmed session required')
 ids={k:uuid.uuid4().hex for k in ['speed','resume','select','pause','stop','already','resume_already','pause_already']};report={'session_id':c.config['session_id'],'partner':'SOV','resource':'oil','factories':1,'requests':ids,'actual_MCP':True};path=c.native/('trade-execution-'+ids['select']+'.json')
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
   report['before']=await call('hoi4_trade_snapshot',{'partner_country':'SOV'});save();await call('hoi4_native_arm',{'enabled':True})
   try:
    speed=await action('hoi4_set_speed',{'request_id':ids['speed'],'speed':5},'hoi4_time_receipt',{'time_verified','rejected'})
    if speed['stage']!='time_verified' or (await pause('resume',False))['stage']!='time_verified':raise RuntimeError('Time change rejected')
    selected=await action('hoi4_import_resource',{'request_id':ids['select'],'partner_country':'SOV','resource':'oil','factories':1},'hoi4_native_receipt',{'trade_verified','rejected'});report['selected']=selected;save()
    if selected['stage']=='trade_verified':
     tick=clock.status()['native_tick'];deadline=time.monotonic()+60
     while clock.status()['native_tick']<tick+24:
      if time.monotonic()>deadline:raise RuntimeError('Trade allocation advancement timed out')
      await asyncio.sleep(.1)
    if (await pause('pause',True))['stage']!='time_verified':raise RuntimeError('Pause rejected')
    report['after']=await call('hoi4_trade_snapshot',{'partner_country':'SOV'});report['direct_after']=c.trade_snapshot('SOV');save()
    report['duplicate']=await call('hoi4_import_resource',{'request_id':ids['select'],'partner_country':'SOV','resource':'oil','factories':1});report['after_duplicate']=await call('hoi4_trade_snapshot',{'partner_country':'SOV'});save()
    if selected['stage']=='trade_verified':
     await pause('resume_already',False)
     report['already']=await action('hoi4_import_resource',{'request_id':ids['already'],'partner_country':'SOV','resource':'oil','factories':1},'hoi4_native_receipt',{'trade_verified','rejected'});save()
     await pause('pause_already',True);report['after_already']=await call('hoi4_trade_snapshot',{'partner_country':'SOV'});save()
   finally:
    try:report['final_pause']=await pause('stop',True)
    finally:c.arm(False);report['final_clock']=clock.status();report['final_armed']=c.load()['armed'];save()
 def oil(snapshot):return next((r for r in snapshot['records'] if r['resource_id']=='oil'),{})
 selected=report['selected'];before=oil(report['before']);after=oil(report['after'])
 checks={'actual_MCP':True,'native_verified':selected['stage']=='trade_verified','computed_cost':selected.get('cost_computed') is True,'normal_offer_checked':selected.get('offer_checked') is True,'exact_cic_cost':(selected.get('native_cost_raw',0)+99999)//100000==1,'normal_offer_bound':selected.get('max_resource_raw',0)>=selected.get('resource_units',0)*100000>0,'independent_new_request':before.get('required_civilian_factories',0)!=1 and after.get('required_civilian_factories')==1,'independent_lended_cic':after.get('lended_civilian_factories')==1,'independent_snapshot_matches':report['after']==report['direct_after'],'duplicate_receipt_unchanged':report['duplicate']==selected,'duplicate_state_unchanged':report['after']==report['after_duplicate'],'already_requested_rejected':report.get('already',{}).get('reason')=='trade_already_requested','already_requested_state_unchanged':oil(report.get('after_already',{'records':[]})).get('required_civilian_factories')==1,'paused':report['final_clock']['paused'],'disarmed':report['final_armed'] is False,'no_input':selected['uses_keyboard_or_mouse'] is False}
 report.update(checks=checks,verified=all(checks.values()));save();print(json.dumps({'report':str(path),'verified':report['verified'],'checks':checks,'selected':selected}))
 if not report['verified']:raise RuntimeError('Trade verification incomplete; preserve report/IDs')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--session-file',required=True,type=Path);asyncio.run(run(p.parse_args()))
