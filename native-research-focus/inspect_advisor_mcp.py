"""Read-only actual-MCP check for an already paused, disarmed protected session."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from native_controller import NativeController
from time_controller import TimeController

async def inspect(session_file):
 c=NativeController(session_file);clock=TimeController(c);before=clock.status()
 if not before['paused'] or c.load()['armed']:raise RuntimeError('Expected paused, disarmed session')
 ledger=c.ledger.read_bytes();root=Path(__file__).parent
 params=StdioServerParameters(command=sys.executable,args=[str(root/'native_mcp_server.py'),'--session-file',str(session_file)],env=dict(os.environ))
 async with stdio_client(params,errlog=sys.stderr) as (rd,wr):
  async with ClientSession(rd,wr) as client:
   await client.initialize();result=await client.call_tool('hoi4_country_advisors',{})
   if result.isError:raise RuntimeError(str(result.content))
   snapshot=result.structuredContent or json.loads(result.content[0].text)
 after=clock.status();direct=c.advisor_snapshot()
 checks={'nonempty_country_roles':snapshot['listed_count']>0,
  'same_direct_readback':snapshot==direct,
  'paused_disarmed':after['paused'] and not c.load()['armed'],
  'tick_unchanged':before['native_tick']==snapshot['native_tick']==after['native_tick'],
  'ledger_unchanged':c.ledger.read_bytes()==ledger,
  'read_only':snapshot['process_writes'] is False and snapshot['uses_keyboard_or_mouse'] is False,
  'eligibility_not_claimed':snapshot['runtime_availability_verified'] is False and snapshot['cost_verified'] is False}
 report={'actual_MCP':True,'session_id':c.config['session_id'],'snapshot':snapshot,'checks':checks,'verified':all(checks.values())}
 (c.native/'advisor-reader-mcp-test.json').write_text(json.dumps(report,indent=2))
 print(json.dumps(report))
 if not report['verified']:raise RuntimeError('Advisor read-only verification failed')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--session-file',required=True)
 asyncio.run(inspect(Path(p.parse_args().session_file)))
