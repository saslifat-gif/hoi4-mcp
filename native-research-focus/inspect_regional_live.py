"""Actual MCP regional cache/UI readback; empty inventory is not message coverage."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from native_controller import NativeController
from time_controller import TimeController
from popup_reader import capture_popups

def semantic(snapshot):
 return sorted((w['widget_id'],json.dumps(w.get('native_popup',{}),sort_keys=True)) for s in snapshot['samples'] for w in s['windows'])

async def run(args):
 c=NativeController(args.session_file);clock=TimeController(c)
 if c.load()['armed'] or not clock.status()['paused']:raise RuntimeError('Paused disarmed inspection required')
 params=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).with_name('native_mcp_server.py')),'--session-file',str(c.path)],env=dict(os.environ))
 async with stdio_client(params,errlog=sys.stderr) as (rd,wr):
  async with ClientSession(rd,wr) as client:
   await client.initialize()
   async def call(name,payload={}):
    result=await client.call_tool(name,payload)
    if result.isError:raise RuntimeError(str(result.content))
    return result.structuredContent or json.loads(result.content[0].text)
   cache=await call('hoi4_regional_alert_cache');sample=await call('hoi4_popup_snapshot',{'kind':'regional_notifications'});direct_cache=c.regional_alert_cache();direct=capture_popups(c.path,c.config['game_root'],'regional_notifications')
 active={(x['alert_scope'],x['native_alert_kind'],x['native_context_id']) for x in cache['entries']};messages=[]
 for surface in sample['samples']:
  for window in surface['windows']:
   native=window.get('native_popup',{});fields=native.get('fields',{})
   if native.get('status')=='native_cached_text' and native.get('runtime_binding_verified') and native.get('native_cache_record_active') and (native.get('alert_scope'),native.get('native_alert_kind'),native.get('native_context_id')) in active and fields.get('title',{}).get('raw_text') and fields.get('body',{}).get('raw_text'):messages.append(window)
 checks={'actual_MCP':True,'cache_direct_matches':cache==direct_cache,'UI_direct_matches':semantic(sample)==semantic(direct),'not_truncated':not any(s['truncated'] for s in sample['samples']),'paused':clock.status()['paused'],'disarmed':c.load()['armed'] is False,'read_only':cache['process_writes'] is False and sample['process_writes'] is False,'no_input':sample['input_events'] is False}
 report={'session_id':c.config['session_id'],'checks':checks,'inventory_verified':all(checks.values()),'nonempty_message_verified':bool(messages) and all(checks.values()),'cache':cache,'snapshot':sample,'messages':messages,'freshness_verified':False}
 p=c.native/f'regional-message-{args.label}.json';p.write_text(json.dumps(report,indent=2));print(json.dumps({'report':str(p),'inventory_verified':report['inventory_verified'],'nonempty_message_verified':report['nonempty_message_verified'],'checks':checks,'cache_entries':cache['entries'],'messages':[{'widget_id':w['widget_id'],'name':w['name'],'native_popup':w['native_popup']} for w in messages]}))
 if not report['inventory_verified']:raise RuntimeError('Regional readback inconsistent')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--session-file',required=True,type=Path);p.add_argument('--label',choices=['before','after','current'],default='current');asyncio.run(run(p.parse_args()))
