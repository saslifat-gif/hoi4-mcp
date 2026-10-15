"""Actual MCP deployment test; normal readiness only, preserve original IDs."""
import argparse,asyncio,json,os,sys,time,uuid
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from native_controller import NativeController
from time_controller import TimeController

def semantic(value):
 if isinstance(value,dict):return {k:semantic(v) for k,v in value.items() if k!='native_tick'}
 if isinstance(value,list):return [semantic(v) for v in value]
 return value

async def run(args):
 c=NativeController(args.session_file);clock=TimeController(c)
 if not clock.status()['paused'] or c.load()['armed']:raise RuntimeError('Paused disarmed protected campaign required')
 ids={k:uuid.uuid4().hex for k in ['speed','resume','select','pause','stop']}
 report={'session_id':c.config['session_id'],'operation':args.operation,'requests':ids,'actual_MCP':True}
 path=c.native/('deployment-execution-'+ids['select']+'.json')
 def save():path.write_text(json.dumps(report,indent=2))
 with path.open('x') as f:json.dump(report,f)
 params=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).with_name('native_mcp_server.py')),'--session-file',str(args.session_file)],env=dict(os.environ))
 async with stdio_client(params,errlog=sys.stderr) as (rd,wr):
  async with ClientSession(rd,wr) as client:
   await client.initialize()
   async def call(name,payload):
    result=await client.call_tool(name,payload)
    if result.isError:raise RuntimeError(str(result.content))
    return result.structuredContent or json.loads(result.content[0].text)
   async def action(name,payload,receipt,terminal):
    result=await call(name,payload);deadline=time.monotonic()+120
    while result['stage'] not in terminal:
     if result['stage']=='execution_uncertain' and result.get('reason'):raise RuntimeError('Execution uncertain; preserve original ID')
     if time.monotonic()>deadline:raise RuntimeError('Request pending; preserve original ID')
     await asyncio.sleep(.1);result=await call(receipt,{'request_id':payload['request_id']})
    return result
   async def pause(label,value):
    result=await action('hoi4_set_paused',{'request_id':ids[label],'paused':value},'hoi4_time_receipt',{'time_verified','rejected'})
    if result['stage']!='time_verified':raise RuntimeError('Pause/resume rejected')
    deadline=time.monotonic()+20
    while clock.status()['paused']!=value:
     if time.monotonic()>deadline:raise RuntimeError('Clock readback pending')
     await asyncio.sleep(.05)
    return result
   report['before']=await call('hoi4_deployment_snapshot',{})
   report['templates']=await call('hoi4_division_templates',{})
   report['units_before']=await call('hoi4_military_snapshot',{});save()
   payload={'request_id':ids['select']}
   if args.operation=='queue':
    choices=report['templates']['templates']
    if not choices:raise RuntimeError('No owned template')
    payload['template_id']=args.identifier or choices[0]['template_id'];tool='hoi4_queue_division'
   elif args.operation=='location':
    choices=report['before']['conveyors']
    if not choices:raise RuntimeError('No owned queue')
    payload['conveyor_id']=args.identifier or choices[0]['conveyor_id']
    provinces=[u['current_province_id'] for u in report['units_before']['units'] if u['current_province_id']]
    if args.province is None and not provinces:raise RuntimeError('No observed candidate province')
    payload['province_id']=args.province or provinces[0];tool='hoi4_set_deployment_location'
   else:
    lines=[line for q in report['before']['conveyors'] for line in q['lines']]
    if not lines:raise RuntimeError('No owned training line')
    payload['line_id']=args.identifier or lines[0]['line_id'];tool='hoi4_deploy_division'
   report['payload']=payload;save()
   await call('hoi4_native_arm',{'enabled':True})
   try:
    speed=await action('hoi4_set_speed',{'request_id':ids['speed'],'speed':args.speed},'hoi4_time_receipt',{'time_verified','rejected'})
    if speed['stage']!='time_verified':raise RuntimeError('Speed rejected')
    await pause('resume',False)
    report['selected']=await action(tool,payload,'hoi4_native_receipt',{'deployment_verified','rejected'});save()
    await pause('pause',True)
    report['after']=await call('hoi4_deployment_snapshot',{})
    report['direct_after']=c.deployment_snapshot()
    report['units_after']=await call('hoi4_military_snapshot',{});save()
    if args.operation=='deploy' and report['selected']['stage']=='deployment_verified':report['deployed_unit']=await call('hoi4_deployed_unit',{'unit_id':report['selected']['unit_id']});save()
    report['duplicate']=await call(tool,payload)
    report['after_duplicate']=await call('hoi4_deployment_snapshot',{})
    report['units_after_duplicate']=await call('hoi4_military_snapshot',{});save()
   finally:
    try:report['final_pause']=await pause('stop',True)
    finally:c.arm(False);report['final_clock']=clock.status();report['final_armed']=c.load()['armed'];save()
 selected=report['selected'];before=report['before'];after=report['after']
 checks={'actual_MCP':True,'native_verified':selected['stage']=='deployment_verified','native_outcome':selected.get('outcome_verified') is True,'independent_snapshot_matches':semantic(after)==semantic(report['direct_after']),'duplicate_receipt_unchanged':selected==report['duplicate'],'duplicate_queue_unchanged':semantic(after)==semantic(report['after_duplicate']),'duplicate_units_unchanged':semantic(report['units_after'])==semantic(report['units_after_duplicate']),'paused':report['final_clock']['paused'],'disarmed':report['final_armed'] is False,'no_input':selected['uses_keyboard_or_mouse'] is False}
 queues={q['conveyor_id']:q for q in after['conveyors']};oldqueues={q['conveyor_id'] for q in before['conveyors']}
 oldunits={u['unit_id'] for u in report['units_before']['units']};newunits={u['unit_id'] for u in report['units_after']['units']}
 if args.operation=='queue':
  q=queues.get(selected.get('conveyor_id'),{})
  checks.update(new_queue=set(queues)-oldqueues=={selected.get('conveyor_id')},template_matches=q.get('template_id')==payload['template_id'],new_line=[l['line_id'] for l in q.get('lines',[])]==[selected.get('line_id')],unit_inventory_unchanged=oldunits==newunits)
 elif args.operation=='location':
  q=queues.get(payload['conveyor_id'],{})
  checks.update(location_matches=q.get('province_id')==payload['province_id'],queues_retained=set(queues)==oldqueues,unit_inventory_unchanged=oldunits==newunits)
 else:
  source=next(q for q in before['conveyors'] if any(l['line_id']==payload['line_id'] for l in q['lines']))
  unit=next((u for u in report['units_after']['units'] if u['unit_id']==selected.get('unit_id')), {})
  entry=next(l['current_entry'] for l in source['lines'] if l['line_id']==payload['line_id']);deployed=report.get('deployed_unit',{})
  checks.update(exact_new_unit=newunits-oldunits=={selected.get('unit_id')},old_units_retained=oldunits<=newunits,province_matches=unit.get('current_province_id')==source['province_id'],template_matches=deployed.get('template_id')==source['template_id'],equipment_amounts_match=sorted(e['quantity_raw'] for e in deployed.get('equipment',[]))==sorted(entry['equipment_quantities_raw']),manpower_matches=deployed.get('manpower')==entry['manpower'])
 report.update(checks=checks,verified=all(checks.values()));save();print(json.dumps({'report':str(path),'verified':report['verified'],'checks':checks,'selected':selected}))
 if not report['verified']:raise RuntimeError('Deployment verification incomplete; preserve receipts and IDs')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--session-file',required=True,type=Path);p.add_argument('--operation',choices=['queue','location','deploy'],required=True);p.add_argument('--identifier');p.add_argument('--province',type=int);p.add_argument('--speed',type=int,choices=range(1,6),default=3);asyncio.run(run(p.parse_args()))
