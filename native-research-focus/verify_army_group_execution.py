"""Verify native unit-to-army creation through actual MCP in a protected session."""
import argparse,asyncio,json,os,sys,time,uuid
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from native_controller import NativeController
from time_controller import TimeController
async def run(args):
 c=NativeController(args.session_file);clock=TimeController(c)
 if not clock.status()['paused'] or c.load()['armed']:raise RuntimeError('Paused disarmed session required')
 ids={k:uuid.uuid4().hex for k in ['speed','resume','select','pause','stop']};report={'session_id':c.config['session_id'],'requests':ids,'actual_MCP':True};path=c.native/('army-group-execution-'+ids['select']+'.json')
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
   report['before']=await call('hoi4_orders_group_snapshot',{});save()
   choices=[u['unit_id'] for u in report['before']['units'] if u['orders_group_id'] is None]
   if len(choices)<2 or not report['before']['theatres']:raise RuntimeError('Two unassigned owned units and a manager required')
   units=args.unit_id or choices[:2];manager=report['before']['theatres'][0]['theatre_id']
   if not 1<=len(units)<=64 or len(set(units))!=len(units) or not set(units)<=set(choices):raise RuntimeError('Selected units must be distinct owned unassigned units')
   payload={'request_id':ids['select'],'theatre_id':manager,'unit_ids':units};report['payload']=payload;save()
   await call('hoi4_native_arm',{'enabled':True})
   try:
    speed=await action('hoi4_set_speed',{'request_id':ids['speed'],'speed':1},'hoi4_time_receipt',{'time_verified','rejected'})
    if speed['stage']!='time_verified' or (await pause('resume',False))['stage']!='time_verified':raise RuntimeError('Time change rejected')
    selected=await action('hoi4_create_army_group',payload,'hoi4_native_receipt',{'army_group_verified','rejected'});report['selected']=selected;save()
    if (await pause('pause',True))['stage']!='time_verified':raise RuntimeError('Pause rejected')
    report['after']=await call('hoi4_orders_group_snapshot',{});report['direct_after']=c.orders_group_snapshot();save()
    report['duplicate']=await call('hoi4_create_army_group',payload);report['after_duplicate']=await call('hoi4_orders_group_snapshot',{});save()
   finally:
    try:report['final_pause']=await pause('stop',True)
    finally:c.arm(False);report['final_clock']=clock.status();report['final_armed']=c.load()['armed'];save()
 selected=report['selected'];after=report['after'];direct=report['direct_after']
 groups={g['group_id']:g for t in after['theatres'] for g in t['groups']}
 before_ids={g['group_id'] for t in report['before']['theatres'] for g in t['groups']}
 child=groups.get(selected.get('group_id'),{});parent=groups.get(selected.get('army_group_id'),{})
 assigned={u['unit_id']:u['orders_group_id'] for u in after['units']}
 def semantic(snapshot):return {k:v for k,v in snapshot.items() if k!='native_tick'} | {'theatres':[{k:v for k,v in t.items() if k!='native_tick'} for t in snapshot['theatres']]}
 checks={'actual_MCP':True,'native_verified':selected['stage']=='army_group_verified','native_membership':selected.get('membership_verified') is True,'new_child':bool(child) and child.get('group_id') not in before_ids,'new_parent':bool(parent) and parent.get('group_id') not in before_ids,'independent_units':set(child.get('unit_ids',[]))==set(units) and all(assigned.get(u)==selected.get('group_id') for u in units),'independent_parent':child.get('army_group_id')==selected.get('army_group_id') and parent.get('member_group_ids')==[selected.get('group_id')],'independent_theater':child.get('theater_id')==parent.get('theater_id')==selected.get('theater_id'),'independent_snapshot_matches':semantic(after)==semantic(direct),'duplicate_receipt_unchanged':report['duplicate']==selected,'duplicate_state_unchanged':semantic(after)==semantic(report['after_duplicate']),'paused':report['final_clock']['paused'],'disarmed':report['final_armed'] is False,'no_input':selected['uses_keyboard_or_mouse'] is False}
 report.update(checks=checks,verified=all(checks.values()));save();print(json.dumps({'report':str(path),'verified':report['verified'],'checks':checks,'selected':selected}))
 if not report['verified']:raise RuntimeError('Army-group verification incomplete; preserve report/IDs')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--session-file',required=True,type=Path);p.add_argument('--unit-id',action='append');asyncio.run(run(p.parse_args()))
