"""Actual MCP tooltip generation in an existing paused protected campaign."""
import asyncio,json,os,sys,time,uuid
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from native_controller import NativeController
from time_controller import TimeController
async def run(sf,target='pol_power'):
 c=NativeController(sf);clock=TimeController(c)
 if not clock.status()['paused'] or c.load()['armed']:raise RuntimeError('Paused/disarmed session required')
 rid=uuid.uuid4().hex;payload={'request_id':rid,'source':'interface/topbar.gui','name':target}
 report={'session_id':c.config['session_id'],'payload':payload,'actual_MCP':True};path=c.native/f'tooltip-query-{rid}.json'
 with path.open('x') as f:json.dump(report,f)
 def save():path.write_text(json.dumps(report,indent=2))
 params=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).with_name('native_mcp_server.py')),'--session-file',str(sf)],env=dict(os.environ))
 async with stdio_client(params,errlog=sys.stderr) as (rd,wr):
  async with ClientSession(rd,wr) as client:
   await client.initialize()
   async def call(name,args):
    r=await client.call_tool(name,args)
    if r.isError:raise RuntimeError(str(r.content))
    return r.structuredContent or json.loads(r.content[0].text)
   report['before']=await call('hoi4_tooltip_assets',{});save()
   await call('hoi4_native_arm',{'enabled':True})
   try:
    result=await call('hoi4_query_tooltip',payload);deadline=time.monotonic()+20
    while result['stage'] in ('pending','execution_uncertain') and not result.get('reason'):
     if time.monotonic()>deadline:raise RuntimeError('Pending original tooltip ID; do not replay')
     await asyncio.sleep(.05);result=await call('hoi4_time_receipt',{'request_id':rid})
    report['receipt']=result;save()
    if result['stage']=='tooltip_result_generated':
     report['assets']=await call('hoi4_tooltip_result_assets',{'request_id':rid});report['direct_assets']=c.tooltip_result_assets(rid);save()
    report['after']=await call('hoi4_tooltip_assets',{});report['direct_after']=c.tooltip_assets();save()
    ledger=clock.path.read_bytes();report['duplicate']=await call('hoi4_query_tooltip',payload)
    report['ledger_unchanged']=ledger==clock.path.read_bytes();save()
   finally:
    c.arm(False);report['paused']=clock.status()['paused'];report['armed']=c.load()['armed'];save()
 def stable(value):
  if isinstance(value,dict):return {k:stable(v) for k,v in value.items() if k not in ('captured_start_unix','captured_end_unix')}
  if isinstance(value,list):return [stable(v) for v in value]
  return value
 r=report['receipt'];assets=report.get('assets',{});channels=assets.get('channels',{})
 checks={'actual_MCP':True,'generated':r['stage']=='tooltip_result_generated','nonempty':r.get('nonempty') is True,'native_lifetime_complete':r.get('native_returned') is True and r.get('native_result_destroyed') is True,'no_input':r.get('uses_keyboard_or_mouse') is False,'core_not_falsely_claimed':r.get('core_updated') is False,'native_channel_assets':bool(channels) and all(v['raw_text']==r['raw_'+k] and v['process_writes'] is False for k,v in channels.items()),'independent_asset_snapshot_matches':stable(assets)==stable(report.get('direct_assets',{})),'duplicate_receipt_unchanged':report['duplicate']==r,'ledger_unchanged':report['ledger_unchanged'],'paused':report['paused'],'disarmed':report['armed'] is False}
 report.update(checks=checks,verified=all(checks.values()));save();print(json.dumps({'report':str(path),'checks':checks,'verified':report['verified'],'receipt':r},ensure_ascii=True))
if __name__=='__main__':asyncio.run(run(Path(sys.argv[1]),sys.argv[2] if len(sys.argv)>2 else 'pol_power'))
