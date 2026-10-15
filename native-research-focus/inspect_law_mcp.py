"""Actual MCP exercise in a new protected campaign; never replay uncertain IDs."""
import argparse,asyncio,json,os,sys,time,uuid
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from native_controller import NativeController
from time_controller import TimeController
from mvp_demo import time_request
p=argparse.ArgumentParser();p.add_argument('--session-file',required=True);p.add_argument('--seconds',type=int,default=180);a=p.parse_args()
c=NativeController(a.session_file);clock=TimeController(c);r=Path(__file__).parent
report={'session_id':c.config['session_id'],'actual_MCP':True,'requests':{k:uuid.uuid4().hex for k in ('pause','speed','resume','unaffordable','wrong_group','negative_pause','positive_resume','select','positive_pause','already_resume','already_selected','stop')}}
path=c.native/'law-mcp-test.json';ids=report['requests']
def save():path.write_text(json.dumps(report,indent=2))
def advance(label,kind,value):
 rid=ids.setdefault(label,uuid.uuid4().hex);save();return time_request(clock,rid,kind,value)
save();c.arm(True)
async def main():
 advance('pause','pause',True)
 params=StdioServerParameters(command=sys.executable,args=[str(r/'native_mcp_server.py'),'--session-file',a.session_file],env=dict(os.environ))
 async with stdio_client(params,errlog=sys.stdout) as (rd,wr):
  async with ClientSession(rd,wr) as client:
   await client.initialize()
   async def call(name,args):
    result=await client.call_tool(name,args)
    if result.isError:raise RuntimeError(str(result.content))
    return result.structuredContent or json.loads(result.content[0].text)
   async def select(label,group,law):
    rid=ids[label];await call('hoi4_select_law',dict(request_id=rid,group=group,law=law));deadline=time.monotonic()+20
    while True:
     result=await call('hoi4_native_receipt',{'request_id':rid})
     if result['stage'] in ('law_verified','rejected','execution_uncertain'):
      report[label]=result;save()
      if result['stage']=='execution_uncertain':raise RuntimeError('Law execution uncertain; retain original ID and stop')
      return result
     if time.monotonic()>deadline:raise RuntimeError('Law pending; retain original ID and stop')
     await asyncio.sleep(.1)
   before=await call('hoi4_idea_snapshot',{});report['before']=before;save()
   def law(snapshot):return [v['idea_id'] for v in snapshot['ideas'] if v['group_id']=='trade_laws']
   if law(before)!=['limited_exports'] or before['political_power_raw']>=10000000:raise RuntimeError('Unexpected initial campaign; no law submitted')
   advance('speed','speed',5);advance('resume','pause',False)
   negative=await select('unaffordable','trade_laws','free_trade')
   if negative['stage']!='rejected' or negative['reason']!='native_rules_rejected':raise RuntimeError('Expected ordinary insufficient-power rejection')
   wrong=await select('wrong_group','economy','free_trade')
   if wrong['stage']!='rejected' or wrong['reason']!='not_requested_law_group':raise RuntimeError('Group binding rejection failed')
   advance('negative_pause','pause',True);unchanged=await call('hoi4_idea_snapshot',{});report['after_rejections']=unchanged;save()
   if law(unchanged)!=law(before):raise RuntimeError('Rejected law changed membership')
   # Earn resources through normal game time; no balance/setter/cheat command.
   deadline=time.monotonic()+a.seconds
   for i in range(12):
    if unchanged['political_power_raw']>=20000000:break
    if time.monotonic()>=deadline:raise RuntimeError('Normal political-power accumulation timed out')
    advance('earn_resume_'+str(i),'pause',False)
    await asyncio.sleep(min(10,max(.1,deadline-time.monotonic())))
    advance('earn_pause_'+str(i),'pause',True);unchanged=await call('hoi4_idea_snapshot',{})
    report['earned']=unchanged;save()
   if unchanged['political_power_raw']<20000000:raise RuntimeError('Insufficient earned political power')
   advance('positive_resume','pause',False);selected=await select('select','trade_laws','free_trade')
   advance('positive_pause','pause',True);after=await call('hoi4_idea_snapshot',{});report['after']=after;save()
   if selected['stage']!='law_verified':raise RuntimeError('Positive native law change was rejected')
   duplicate=await call('hoi4_select_law',dict(request_id=ids['select'],group='trade_laws',law='free_trade'))
   advance('already_resume','pause',False);already=await select('already_selected','trade_laws','free_trade')
   advance('stop','pause',True)
   checks={'normal_rules_rejected':negative['stage']=='rejected','wrong_group_rejected':wrong['stage']=='rejected','rejections_preserved_law':law(unchanged)==law(before),'native_paid_law_verified':selected['stage']=='law_verified' and selected['cost_verified'],'exact_charge':selected['balance_before_raw']-selected['balance_after_raw']==max(0,selected['computed_cost_raw']),'positive_charge':selected['computed_cost_raw']>0,'independent_membership':law(after)==['free_trade'],'duplicate_idempotent':duplicate==selected,'already_selected_rejected':already['stage']=='rejected' and already['reason']=='already_selected','input_free':selected['uses_keyboard_or_mouse'] is False,'paused':clock.status()['paused']}
   report.update(checks=checks,verified=all(checks.values()));save();print(json.dumps({'checks':checks,'verified':report['verified']}),flush=True)
   if not report['verified']:raise RuntimeError('Law check failed; retained report and IDs')
try:asyncio.run(main())
finally:
 try:advance('stop','pause',True)
 finally:c.arm(False)
