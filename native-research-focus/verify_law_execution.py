"""One ordinary law change through actual MCP, earning PP only through game time."""
import argparse,asyncio,json,os,sys,time,uuid
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from native_controller import NativeController
from time_controller import TimeController

def laws(snapshot,group):return [i['idea_id'] for i in snapshot['ideas'] if i['group_id']==group]
def other_laws(snapshot,group):
 return sorted((i['group_id'],i['idea_id']) for i in snapshot['ideas'] if i['group_id'] in ('trade_laws','economy','mobilization_laws') and i['group_id']!=group)
def semantic(snapshot):return {k:v for k,v in snapshot.items() if k!='native_tick'}

async def run(args):
 c=NativeController(args.session_file);clock=TimeController(c)
 if c.load()['armed'] or not clock.status()['paused']:raise RuntimeError('Paused disarmed protected campaign required')
 ids={k:uuid.uuid4().hex for k in ['speed','select','resume','pause','already_resume','already','stop']}
 report={'actual_MCP':True,'session_id':c.config['session_id'],'group':args.group,'law':args.law,'requests':ids,'earned':[]};p=c.native/f'law-execution-{ids["select"]}.json'
 def save():p.write_text(json.dumps(report,indent=2))
 with p.open('x') as f:json.dump(report,f)
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
     if result['stage']=='execution_uncertain' and result.get('reason'):raise RuntimeError('Uncertain execution; retain original request')
     if time.monotonic()>=deadline:raise RuntimeError('Pending execution; retain original request')
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
   report['initial']=await call('hoi4_idea_snapshot');definition=await call('hoi4_idea_snapshot',{'idea_id':args.law});report['definition']=definition;save()
   if len(laws(report['initial'],args.group))!=1 or laws(report['initial'],args.group)==[args.law]:raise RuntimeError('A different selected law in the requested group is required')
   if not any(i['idea_id']==args.law and i['group_id']==args.group for i in definition['ideas']):raise RuntimeError('Exact native law definition missing')
   await call('hoi4_native_arm',{'enabled':True})
   try:
    speed=await action('hoi4_set_speed',{'request_id':ids['speed'],'speed':5},'hoi4_time_receipt',{'time_verified','rejected'})
    if speed['stage']!='time_verified':raise RuntimeError('Speed rejected')
    before=report['initial'];deadline=time.monotonic()+args.seconds
    for i in range(12):
     if before['political_power_raw']>=args.minimum_pp*100000:break
     if time.monotonic()>=deadline:raise RuntimeError('Natural political-power accumulation timed out')
     if len(clock.load()['requests'])>52:raise RuntimeError('Retain time-command capacity for action cleanup')
     await pause(f'earn_resume_{i}',False);await asyncio.sleep(10);await pause(f'earn_pause_{i}',True)
     before=await call('hoi4_idea_snapshot');report['earned'].append(before);save()
    if before['political_power_raw']<args.minimum_pp*100000:raise RuntimeError('Insufficient naturally earned political power')
    report['before']=before;save();await pause('resume',False)
    payload={'request_id':ids['select'],'group':args.group,'law':args.law}
    report['selected']=await action('hoi4_select_law',payload,'hoi4_native_receipt',{'law_verified','rejected'});save()
    await pause('pause',True)
    report['after']=await call('hoi4_idea_snapshot');report['direct_after']=c.idea_snapshot();report['duplicate']=await call('hoi4_select_law',payload);report['after_duplicate']=await call('hoi4_idea_snapshot');save()
    if report['selected']['stage']=='law_verified':
     await pause('already_resume',False)
     report['already']=await action('hoi4_select_law',dict(payload,request_id=ids['already']),'hoi4_native_receipt',{'law_verified','rejected'});save()
   finally:
    try:report['final_pause']=await pause('stop',True)
    finally:c.arm(False);report['final_clock']=clock.status();report['final_armed']=c.load()['armed'];report['final_snapshot']=c.idea_snapshot();save()
 selected=report['selected'];after=report['after'];before=report['before']
 checks={'actual_MCP':True,'native_law_verified':selected['stage']=='law_verified','native_cost_verified':selected.get('cost_verified') is True,'positive_charge':selected.get('computed_cost_raw',0)>0,'exact_native_charge':selected.get('balance_before_raw',0)-selected.get('balance_after_raw',0)==selected.get('computed_cost_raw',-1),'independent_new_law':laws(after,args.group)==[args.law],'old_law_removed':not set(laws(before,args.group)).intersection(laws(after,args.group)),'other_law_groups_unchanged':other_laws(before,args.group)==other_laws(after,args.group),'direct_snapshot_matches':after==report['direct_after'],'duplicate_receipt_unchanged':report['duplicate']==selected,'duplicate_state_unchanged':semantic(after)==semantic(report['after_duplicate']),'already_selected_rejected':report.get('already',{}).get('stage')=='rejected' and report['already'].get('reason')=='already_selected','already_selected_state_unchanged':laws(report['final_snapshot'],args.group)==[args.law] and other_laws(after,args.group)==other_laws(report['final_snapshot'],args.group),'paused':report['final_clock']['paused'],'disarmed':report['final_armed'] is False,'no_input':selected['uses_keyboard_or_mouse'] is False}
 report.update(checks=checks,verified=all(checks.values()));save();print(json.dumps({'report':str(p),'verified':report['verified'],'checks':checks,'selected':selected}))
 if not report['verified']:raise RuntimeError('Law verification incomplete; retain original report and request IDs')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--session-file',required=True,type=Path);p.add_argument('--group',required=True);p.add_argument('--law',required=True);p.add_argument('--minimum-pp',type=int,default=200);p.add_argument('--seconds',type=int,default=240);asyncio.run(run(p.parse_args()))
