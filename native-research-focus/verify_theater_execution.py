"""Actual MCP verification of normal theater creation and assignment."""
import argparse,asyncio,json,os,sys,time,uuid
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from native_controller import NativeController
from time_controller import TimeController

def semantic(snapshot):
 return {k:v for k,v in snapshot.items() if k!='native_tick'} | {'theatres':[{k:v for k,v in t.items() if k!='native_tick'} for t in snapshot['theatres']]}

def groups(snapshot):
 return {g['group_id']:g for t in snapshot['theatres'] for g in t['groups']}

async def run(args):
 c=NativeController(args.session_file);clock=TimeController(c)
 if c.load()['armed'] or not clock.status()['paused']:raise RuntimeError('Paused disarmed protected session required')
 ids={k:uuid.uuid4().hex for k in ['speed','resume','resume_already','select','pause','stop','already']}
 report={'session_id':c.config['session_id'],'operation':args.operation,'requests':ids};path=c.native/f'theater-execution-{ids["select"]}.json'
 def save():path.write_text(json.dumps(report,indent=2))
 with path.open('x') as f:json.dump(report,f)
 params=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).with_name('native_mcp_server.py')),'--session-file',str(c.path)],env=dict(os.environ))
 async with stdio_client(params,errlog=sys.stderr) as (rd,wr):
  async with ClientSession(rd,wr) as client:
   await client.initialize()
   async def call(name,payload={}):
    result=await client.call_tool(name,payload)
    if result.isError:raise RuntimeError(str(result.content))
    return result.structuredContent or json.loads(result.content[0].text)
   async def action(name,payload,receipt,terminal):
    result=await call(name,payload);deadline=time.monotonic()+120
    while result['stage'] not in terminal:
     if result['stage']=='execution_uncertain' and result.get('reason'):raise RuntimeError('Uncertain execution; retain original ID')
     if time.monotonic()>=deadline:raise RuntimeError('Pending execution; retain original ID')
     await asyncio.sleep(.1);result=await call(receipt,{'request_id':payload['request_id']})
    return result
   async def pause(label,value):
    result=await action('hoi4_set_paused',{'request_id':ids[label],'paused':value},'hoi4_time_receipt',{'time_verified','rejected'})
    if result['stage']!='time_verified':raise RuntimeError('Pause/resume rejected')
    deadline=time.monotonic()+20
    while clock.status()['paused']!=value:
     if time.monotonic()>=deadline:raise RuntimeError('Clock readback pending')
     await asyncio.sleep(.05)
    return result
   before=await call('hoi4_orders_group_snapshot');report['before']=before;save();rows=groups(before)
   parents=[g for g in rows.values() if g['kind']=='army_group' and g['member_group_ids']]
   if len(parents)<2:raise RuntimeError('Two owned populated army-groups required')
   source=parents[0];affected={source['group_id'],*source['member_group_ids']}
   target=None
   if args.operation=='assign':
    candidates=[t for manager in before['theatres'] for t in manager['theater_ids'] if t!=source['theater_id']]
    if not candidates:raise RuntimeError('Another owned theater required')
    target=candidates[0]
   payload={'request_id':ids['select'],'group_ids':[source['group_id']],'theater_id':target};report['payload']=payload;report['affected']=sorted(affected);save()
   await call('hoi4_native_arm',{'enabled':True})
   try:
    speed=await action('hoi4_set_speed',{'request_id':ids['speed'],'speed':1},'hoi4_time_receipt',{'time_verified','rejected'})
    if speed['stage']!='time_verified':raise RuntimeError('Speed rejected')
    await pause('resume',False)
    selected=await action('hoi4_assign_theater',payload,'hoi4_native_receipt',{'theater_verified','rejected'});report['selected']=selected;save()
    await pause('pause',True)
    after=await call('hoi4_orders_group_snapshot');report['after']=after;report['direct_after']=c.orders_group_snapshot();save()
    report['duplicate']=await call('hoi4_assign_theater',payload);report['after_duplicate']=await call('hoi4_orders_group_snapshot');save()
    if args.operation=='assign' and selected['stage']=='theater_verified':
     await pause('resume_already',False)
     report['already']=await action('hoi4_assign_theater',dict(payload,request_id=ids['already']),'hoi4_native_receipt',{'theater_verified','rejected'});save()
   finally:
    try:report['final_pause']=await pause('stop',True)
    finally:c.arm(False);report['final_clock']=clock.status();report['final_armed']=c.load()['armed'];report['final_groups']=c.orders_group_snapshot();save()
 selected=report['selected'];after=report['after'];newrows=groups(after);observed=selected.get('theater_id');oldtheaters={t for m in before['theatres'] for t in m['theater_ids']}
 checks={'actual_MCP':True,'native_verified':selected['stage']=='theater_verified','native_membership':selected.get('membership_verified') is True,'native_recursive_count':selected.get('affected_groups')==len(affected),'new_or_exact_target':observed not in oldtheaters if target is None else observed==target,'independent_recursive_membership':all(newrows.get(g,{}).get('theater_id')==observed for g in affected),'other_groups_unchanged':all(newrows.get(g)==row for g,row in rows.items() if g not in affected),'unit_assignments_unchanged':before['units']==after['units'],'group_ids_unchanged':set(rows)==set(newrows),'independent_snapshot_matches':semantic(after)==semantic(report['direct_after']),'duplicate_receipt_unchanged':report['duplicate']==selected,'duplicate_state_unchanged':semantic(after)==semantic(report['after_duplicate']),'paused':report['final_clock']['paused'],'disarmed':report['final_armed'] is False,'no_input':selected['uses_keyboard_or_mouse'] is False}
 if args.operation=='assign':
  checks['already_assigned_rejected']=report.get('already',{}).get('stage')=='rejected' and report['already'].get('reason')=='already_assigned'
  checks['already_assigned_state_unchanged']=semantic(after)==semantic(report['final_groups'])
 report.update(checks=checks,verified=all(checks.values()));save();print(json.dumps({'report':str(path),'verified':report['verified'],'checks':checks,'selected':selected}))
 if not report['verified']:raise RuntimeError('Theater verification incomplete; retain report and original IDs')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--session-file',required=True,type=Path);p.add_argument('--operation',choices=['create','assign'],required=True);asyncio.run(run(p.parse_args()))
