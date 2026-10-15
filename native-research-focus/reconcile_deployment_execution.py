"""Actual MCP read-only reconciliation of an original uncertain queue request."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from native_controller import NativeController
from time_controller import TimeController
from verify_deployment_execution import semantic

async def run(args):
 c=NativeController(args.session_file);clock=TimeController(c);rid=args.request_id
 if c.load()['armed'] or not clock.status()['paused']:raise RuntimeError('Paused disarmed session required')
 original=(c.native/f'receipt-{rid}.json').read_bytes();ledger=c.ledger.read_bytes();before=c.deployment_snapshot()
 report={'request_id':rid,'session_id':c.config['session_id'],'actual_MCP':True}
 params=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).with_name('native_mcp_server.py')),'--session-file',str(c.path)],env=dict(os.environ))
 async with stdio_client(params,errlog=sys.stderr) as (rd,wr):
  async with ClientSession(rd,wr) as client:
   await client.initialize()
   async def call(name):
    result=await client.call_tool(name,{'request_id':rid})
    if result.isError:raise RuntimeError(str(result.content))
    return result.structuredContent or json.loads(result.content[0].text)
   report['observed']=await call('hoi4_reconcile_deployment')
   report['receipt']=await call('hoi4_native_receipt')
   report['duplicate']=await call('hoi4_reconcile_deployment')
 after=c.deployment_snapshot();observed=report['observed']
 checks={'actual_MCP':True,'outcome_independently_observed':observed['stage']=='deployment_observed' and observed['outcome_verified'],'native_receipt_preserved':original==(c.native/f'receipt-{rid}.json').read_bytes(),'native_stage_retained':observed['native_stage']=='execution_uncertain','ledger_unchanged':ledger==c.ledger.read_bytes(),'snapshot_unchanged':semantic(before)==semantic(after),'receipt_matches':observed==report['receipt'],'duplicate_unchanged':observed==report['duplicate'],'read_only':observed['process_writes'] is False,'paused':clock.status()['paused'],'disarmed':c.load()['armed'] is False,'no_input':observed['uses_keyboard_or_mouse'] is False}
 report.update(checks=checks,verified=all(checks.values()));path=c.native/f'deployment-reconciled-{rid}.json';path.write_text(json.dumps(report,indent=2));print(json.dumps({'report':str(path),'verified':report['verified'],'checks':checks,'queue':observed['conveyor_id'],'line':observed['line_id']}))
 if not report['verified']:raise RuntimeError('Independent queue reconciliation failed')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--session-file',type=Path,required=True);p.add_argument('--request-id',required=True);asyncio.run(run(p.parse_args()))
