"""Read-only actual MCP fixture inspection; candidate distance is not eligibility."""
import argparse,asyncio,hashlib,json,os,sys
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from native_controller import NativeController
from time_controller import TimeController
from runtime_gui import WindowsProcess,NativeGuiReader
from country_binding import read_country_binding
from military_reader import read_unit_ids

async def run(args):
 c=NativeController(args.session_file);clock=TimeController(c)
 if c.load()['armed'] or not clock.status()['paused']:raise RuntimeError('Paused disarmed fixture required')
 params=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).with_name('native_mcp_server.py')),'--session-file',str(c.path)],env=dict(os.environ))
 async with stdio_client(params,errlog=sys.stderr) as (rd,wr):
  async with ClientSession(rd,wr) as client:
   await client.initialize()
   async def call(name):
    result=await client.call_tool(name,{})
    if result.isError:raise RuntimeError(str(result.content))
    return result.structuredContent or json.loads(result.content[0].text)
   own=await call('hoi4_military_snapshot');combats=await call('hoi4_combat_snapshot')
 observation=c.check();exe=Path(c.config['game_root'])/'hoi4.exe';process=WindowsProcess(c.config['process_identity'],exe)
 try:
  reader=NativeGuiReader(process,hashlib.sha256(exe.read_bytes()).hexdigest());world=int(observation['world'],16)
  actor=read_country_binding(reader,world,c.config['country']);enemy=read_country_binding(reader,world,args.opponent)
  opponent=read_unit_ids(reader,enemy['country_id'],world);direct=c.combat_snapshot();process.guard()
 finally:process.close()
 positions={};mapfile=Path(c.config['game_root'])/'map/unitstacks.txt'
 for line in mapfile.read_text(encoding='utf-8-sig').splitlines():
  fields=line.split(';')
  if len(fields)==7 and fields[1]=='0':positions[int(fields[0])]=(float(fields[2]),float(fields[4]))
 idle={u['unit_id'] for u in combats['units'] if not u['combat_ids']};candidates=[]
 enemy_provinces={u['current_province_id'] for u in opponent['units']}
 for unit in own['units']:
  source=unit['current_province_id']
  if unit['unit_id'] not in idle or unit['movement_path_count'] or source not in positions:continue
  for target in enemy_provinces:
   if target==source or target not in positions:continue
   distance=sum((a-b)**2 for a,b in zip(positions[source],positions[target]))**.5
   candidates.append({'unit_id':unit['unit_id'],'source_province_id':source,'target_province_id':target,'map_distance':distance,'eligibility_verified':False})
 candidates.sort(key=lambda x:(x['map_distance'],x['unit_id'],x['target_province_id']))
 checks={'actual_MCP':True,'actor_country_matches':actor['country_id']==int(observation['country'],16),'distinct_opponent':actor['native_tag']!=enemy['native_tag'],'own_unit_inventory_matches':{u['unit_id'] for u in own['units']}=={u['unit_id'] for u in combats['units']},'direct_combat_snapshot_matches':direct==combats,'nonempty_owned_and_opponent_units':own['count']>0 and opponent['count']>0,'typed_bidirectional_combat_reader':combats['native_world_manager_verified'] and combats['bidirectional_membership_verified'],'paused':clock.status()['paused'],'disarmed':c.load()['armed'] is False,'no_input':own['uses_keyboard_or_mouse'] is False}
 report={'session_id':c.config['session_id'],'actor':actor,'opponent':enemy,'own_units':own,'opponent_units':opponent,'combats':combats,'candidates':candidates[:60],'candidate_basis':'Installed map/unitstacks.txt stack0 x/z distance only; full native war/movement rules still required.','map_sha256':hashlib.sha256(mapfile.read_bytes()).hexdigest(),'checks':checks,'verified':all(checks.values())}
 p=c.native/'combat-fixture.json';p.write_text(json.dumps(report,indent=2));print(json.dumps({'report':str(p),'verified':report['verified'],'checks':checks,'own_units':own['count'],'opponent_units':opponent['count'],'combats':len(combats['combats']),'candidates':candidates[:12]}))
 if not report['verified']:raise RuntimeError('Combat fixture inspection incomplete')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--session-file',required=True,type=Path);p.add_argument('--opponent',default='ETH');asyncio.run(run(p.parse_args()))
