"""Actual MCP order, natural engagement and normal stop; never replay uncertainty."""
import argparse,asyncio,json,os,sys,time,uuid
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from native_controller import NativeController,selection_command
from time_controller import TimeController
from combat_transition import verify_engagement,verify_side_membership_removed

def semantic(snapshot):return {k:v for k,v in snapshot.items() if k!='native_tick'}

async def run(args):
 c=NativeController(args.session_file);clock=TimeController(c)
 selection_command('a'*32,'attack',args.unit_id,args.province_id)
 if c.load()['armed'] or not clock.status()['paused']:raise RuntimeError('Paused disarmed protected campaign required')
 ids={k:uuid.uuid4().hex for k in ['speed','resume','attack','attack_pause','stop_resume','stop','stop_pause','final_pause']}
 report={'session_id':c.config['session_id'],'requests':ids,'payload':{'unit_id':args.unit_id,'province_id':args.province_id},'samples':[]};p=c.native/f'combat-execution-{ids["attack"]}.json'
 def save():p.write_text(json.dumps(report,indent=2))
 with p.open('x') as out:json.dump(report,out)
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
     if result['stage']=='execution_uncertain' and result.get('reason'):raise RuntimeError('Uncertain native execution; preserve original ID')
     if time.monotonic()>=deadline:raise RuntimeError('Pending native execution; preserve original ID')
     await asyncio.sleep(.1);result=await call(receipt,{'request_id':payload['request_id']})
    return result
   async def pause(label,value):
    rid=ids.setdefault(label,uuid.uuid4().hex);save()
    result=await action('hoi4_set_paused',{'request_id':rid,'paused':value},'hoi4_time_receipt',{'time_verified','rejected'})
    if result['stage']!='time_verified':raise RuntimeError('Pause/resume rejected')
    deadline=time.monotonic()+20
    while clock.status()['paused']!=value:
     if time.monotonic()>=deadline:raise RuntimeError('Clock readback pending')
     await asyncio.sleep(.05)
    return result
   before=await call('hoi4_combat_snapshot');report['before']=before;report['before_units']=await call('hoi4_military_snapshot');save()
   rows=[u for u in before['units'] if u['unit_id']==args.unit_id]
   if len(rows)!=1 or rows[0]['combat_ids']:raise RuntimeError('One owned idle source unit required')
   payload={'request_id':ids['attack'],'unit_id':args.unit_id,'province_id':args.province_id}
   await call('hoi4_native_arm',{'enabled':True})
   try:
    speed=await action('hoi4_set_speed',{'request_id':ids['speed'],'speed':3},'hoi4_time_receipt',{'time_verified','rejected'})
    if speed['stage']!='time_verified':raise RuntimeError('Speed rejected')
    await pause('resume',False)
    report['attack']=await action('hoi4_attack_province',payload,'hoi4_native_receipt',{'military_verified','rejected'});save()
    await pause('attack_pause',True)
    if report['attack']['stage']!='military_verified':raise RuntimeError('Attack order rejected; retain report')
    report['after_order']=await call('hoi4_combat_snapshot');report['attack_duplicate']=await call('hoi4_attack_province',payload);report['after_attack_duplicate']=await call('hoi4_combat_snapshot');save()
    sample=report['after_order'];engagement=verify_engagement(before,sample,args.unit_id,args.province_id);deadline=time.monotonic()+args.seconds
    for i in range(16):
     if engagement['verified'] or time.monotonic()>=deadline:break
     await pause(f'progress_resume_{i}',False);await asyncio.sleep(2);await pause(f'progress_pause_{i}',True)
     sample=await call('hoi4_combat_snapshot');engagement=verify_engagement(before,sample,args.unit_id,args.province_id)
     report['samples'].append(sample);report['engagement']=engagement;save()
    report['engagement']=engagement;report['engaged_snapshot']=sample;save()
    if not engagement['verified']:raise RuntimeError('Actual engagement not observed; keep original request and paused campaign')
    report['direct_engaged']=c.combat_snapshot();save()
    await pause('stop_resume',False)
    stop_payload={'request_id':ids['stop'],'unit_id':args.unit_id}
    report['stop']=await action('hoi4_stop_unit_combat',stop_payload,'hoi4_native_receipt',{'military_verified','rejected'});save()
    await pause('stop_pause',True)
    report['after_stop']=await call('hoi4_combat_snapshot');report['stop_duplicate']=await call('hoi4_stop_unit_combat',stop_payload);report['after_stop_duplicate']=await call('hoi4_combat_snapshot');save()
   finally:
    try:report['final_pause']=await pause('final_pause',True)
    finally:c.arm(False);report['final_clock']=clock.status();report['final_armed']=c.load()['armed'];save()
 removed=verify_side_membership_removed(report['engaged_snapshot'],report['after_stop'],args.unit_id,report['engagement']['side_index'])
 checks={'actual_MCP':True,'native_attack_order_verified':report['attack']['stage']=='military_verified','actual_new_combat_membership':report['engagement']['verified'],'exact_target_province':report['engagement']['province_id']==args.province_id,'direct_engagement_matches':report['direct_engaged']==report['engaged_snapshot'],'native_normal_stop_verified':report['stop']['stage']=='military_verified','combat_active_at_native_stop':report['stop'].get('combat_count_before',0)>0,'native_combat_membership_decreased':report['stop'].get('combat_membership_removed') is True,'independent_combat_membership_removed':removed['verified'],'attack_duplicate_receipt_unchanged':report['attack_duplicate']==report['attack'],'attack_duplicate_state_unchanged':semantic(report['after_order'])==semantic(report['after_attack_duplicate']),'stop_duplicate_receipt_unchanged':report['stop_duplicate']==report['stop'],'stop_duplicate_state_unchanged':semantic(report['after_stop'])==semantic(report['after_stop_duplicate']),'paused':report['final_clock']['paused'],'disarmed':report['final_armed'] is False,'no_input':report['attack']['uses_keyboard_or_mouse'] is False and report['stop']['uses_keyboard_or_mouse'] is False}
 report.update(checks=checks,removal=removed,verified=all(checks.values()));save();print(json.dumps({'report':str(p),'verified':report['verified'],'checks':checks,'engagement':report['engagement'],'removal':removed}))
 if not report['verified']:raise RuntimeError('Combat execution verification incomplete; retain original report/IDs')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--session-file',required=True,type=Path);p.add_argument('--unit-id',required=True);p.add_argument('--province-id',required=True,type=int);p.add_argument('--seconds',type=int,default=120);asyncio.run(run(p.parse_args()))
