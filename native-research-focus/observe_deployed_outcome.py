"""Read-only actual MCP evidence after a deployment postcondition failure."""
import asyncio,json,os,sys
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from native_controller import NativeController
from time_controller import TimeController
async def main():
 c=NativeController(sys.argv[1]);rid=sys.argv[2];unit_id=sys.argv[3];clock=TimeController(c)
 if c.load()['armed'] or not clock.status()['paused']:raise RuntimeError('Paused disarmed campaign required')
 before=json.loads((c.native/f'deployment-execution-{rid}.json').read_text());original=(c.native/f'receipt-{rid}.json').read_bytes();ledger=c.ledger.read_bytes()
 params=StdioServerParameters(command=sys.executable,args=[str(Path(sys.modules[NativeController.__module__].__file__).with_name('native_mcp_server.py')),'--session-file',str(c.path)],env=dict(os.environ))
 async with stdio_client(params,errlog=sys.stderr) as (rd,wr):
  async with ClientSession(rd,wr) as client:
   await client.initialize()
   async def call(name,arguments):
    result=await client.call_tool(name,arguments)
    if result.isError:raise RuntimeError(str(result.content))
    return result.structuredContent or json.loads(result.content[0].text)
   unit=await call('hoi4_deployed_unit',{'unit_id':unit_id});units=await call('hoi4_military_snapshot',{});receipt=await call('hoi4_native_receipt',{'request_id':rid})
 source=next(q for q in before['before']['conveyors'] if any(l['line_id']==before['payload']['line_id'] for l in q['lines']))
 entry=next(l['current_entry'] for l in source['lines'] if l['line_id']==before['payload']['line_id'])
 oldids={u['unit_id'] for u in before['units_before']['units']};newids={u['unit_id'] for u in units['units']}
 checks={'actual_MCP':True,'exact_one_new_unit':newids-oldids=={unit_id},'all_old_units_retained':oldids<=newids,'template_matches':unit['template_id']==source['template_id'],'province_matches':unit['current_province_id']==source['province_id'],'raw_equipment_amounts_match':sorted(e['quantity_raw'] for e in unit['equipment'])==sorted(entry['equipment_quantities_raw']),'raw_manpower_matches':unit['manpower']==entry['manpower'],'independent_readback_matches':unit==c.deployed_unit_snapshot(unit_id),'original_receipt_preserved':original==(c.native/f'receipt-{rid}.json').read_bytes(),'ledger_unchanged':ledger==c.ledger.read_bytes(),'native_uncertainty_preserved':receipt['stage']=='execution_uncertain','paused':clock.status()['paused'],'disarmed':c.load()['armed'] is False,'read_only':unit['process_writes'] is False}
 report={'request_id':rid,'session_id':c.config['session_id'],'unit':unit,'native_receipt':receipt,'checks':checks,'verified':all(checks.values()),'resource_identity_matches_source_verified':False,'native_deployment_verified':False,'boundary':'Independent identity/province/resource amounts observed; original native failed postcondition retained. Exact source equipment identities await corrected native verification.'}
 p=c.native/f'deployed-outcome-observed-{rid}.json';p.write_text(json.dumps(report,indent=2));print(json.dumps({'report':str(p),'verified':report['verified'],'checks':checks,'unit':unit}))
 if not report['verified']:raise RuntimeError('Observed deployed unit verification incomplete')
asyncio.run(main())
