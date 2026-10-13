"""Bounded real MCP/native engine regression for partial/shared/batched queues."""
import asyncio,json,os,subprocess,sys,uuid
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from native_controller import NativeController
from time_controller import TimeController
from direct_controller import atomic_text
from direct_process import require_ac_power
from read_cost_save import read_save
async def main():
 sf=Path(sys.argv[1]);root=Path(__file__).parent;base=root.parent;c=NativeController(sf);clock=TimeController(c)
 out=sf.parent/'native/QUEUED_CAPACITY_LIVE_VALIDATION.json';report={'verified':False,'actual_HOI4':True,'actual_MCP':True,'uses_keyboard_or_mouse':False,'commands':[]};bridge=None
 def save():atomic_text(out,json.dumps(report,indent=2))
 def check_power():
  report['power']=require_ac_power()
 async def set_time(kind,value):
  rid=uuid.uuid4().hex;r=clock.submit(rid,kind,value)
  for _ in range(60):
   if r['stage']!='pending':break
   await asyncio.sleep(.25);r=clock.receipt(rid)
  assert r['stage']=='time_verified',r
 async def sample(label):
  check_power()
  rid=uuid.uuid4().hex;report[label+'_request_id']=rid;save()
  for _ in range(180):
   r=c.peacetime_snapshot(rid)
   if r['status']=='ready':report[label]=r;save();return r
   assert r['status']=='pending',r
   await asyncio.sleep(.5)
  raise RuntimeError('Snapshot pending; retain recorded ID')
 def caps(e):return {(x['state_id'],x['building']):x for x in e['available_choices']['construction']['capacity']}
 try:
  check_power()
  c.arm(True);await set_time('speed',3);await set_time('pause',False);initial=await sample('initial');capacities=caps(initial)
  offered={(x['state_id'],x['building']) for x in initial['available_choices']['construction']['choices']}
  state=next(s for s,b in offered if b=='industrial_complex' and (s,'arms_factory') in offered and 3<=capacities[(s,b)]['remaining']<=5 and capacities[(s,b)]['queued']==0 and capacities[(s,'arms_factory')]['queued']==0)
  capacity=capacities[(state,'industrial_complex')]['remaining'];report.update(state_id=state,initial_capacity=capacity);save()
  env=dict(os.environ,PYTHONPATH=str(base)+os.pathsep+str(root));token=sf.parent/'queue-test-token';log=(sf.parent/'queue-bridge.log').open('w')
  bridge=subprocess.Popen([sys.executable,str(base/'direct_bridge.py'),'--session-file',str(sf),'--port','18780','--token-file',str(token)],env=env,stdout=log,stderr=log)
  for _ in range(40):
   if token.exists():break
   if bridge.poll() is not None:raise RuntimeError('Bridge exited')
   await asyncio.sleep(.25)
  assert token.exists()
  params=StdioServerParameters(command=sys.executable,args=[str(base/'direct_mcp_server.py'),'--url','http://127.0.0.1:18780','--token-file',str(token)],env=env)
  async with stdio_client(params) as (r,w):
   async with ClientSession(r,w) as client:
    await client.initialize()
    async def call(name,args):
     result=await client.call_tool(name,args)
     if result.isError:raise RuntimeError(str(result.content))
     return result.structuredContent or json.loads(result.content[0].text)
    await call('hoi4_arm',{'enabled':True})
    async def request(s,building,levels,expected):
     check_power()
     args={'request_id':uuid.uuid4().hex,'state_id':s,'building':building,'levels':levels};entry={'arguments':args,'expected':expected};report['commands'].append(entry);save()
     result=await call('hoi4_construct',args)
     for i in range(90):
      if result['status'] in ('acknowledged','rejected'):break
      assert result['status'] in ('queued','pending'),result
      if i==24:await call('hoi4_deliver',{'command_id':args['request_id']})
      await asyncio.sleep(.5);result=await call('hoi4_receipt',{'command_id':args['request_id']})
     entry['receipt']=result;save();assert result['status']==expected,result
     assert await call('hoi4_construct',args)==result
     if expected=='acknowledged':assert result['gameplay_outcome_verified'] and result['data']['after_built_and_queued']-result['data']['before_built_and_queued']==levels,result
     print(f'{building} x{levels}: {expected}',flush=True);return result
    await request(state,'industrial_complex',1,'acknowledged');after_one=await sample('after_one');a=caps(after_one)
    assert a[(state,'industrial_complex')]['remaining']==capacity-1
    assert a[(state,'arms_factory')]['remaining']==capacities[(state,'arms_factory')]['remaining']-1
    assert a[(state,'industrial_complex')]['built']==capacities[(state,'industrial_complex')]['built']
    await request(state,'industrial_complex',capacity,'rejected');after_reject=await sample('after_oversized_rejection');b=caps(after_reject)
    assert b[(state,'industrial_complex')]==a[(state,'industrial_complex')]
    await request(state,'arms_factory',b[(state,'arms_factory')]['remaining'],'acknowledged');full=await sample('full');f=caps(full)
    assert f[(state,'industrial_complex')]['remaining']==0 and f[(state,'arms_factory')]['remaining']==0
    assert not any(x['state_id']==state for x in full['available_choices']['construction']['choices'])
    await request(state,'industrial_complex',1,'rejected');await request(state,'arms_factory',1,'rejected')
    dock=next(x['state_id'] for x in full['available_choices']['construction']['choices'] if x['building']=='dockyard' and x['max_levels']>=2)
    await request(dock,'dockyard',2,'acknowledged');report['dockyard_state']=dock
    fresh=await sample('before_five');batch=next(x['state_id'] for x in fresh['available_choices']['construction']['choices'] if x['building']=='industrial_complex' and x['max_levels']==5 and x['state_id'] not in (state,dock))
    await request(batch,'industrial_complex',5,'acknowledged');report['five_level_state']=batch
    await call('hoi4_arm',{'enabled':False})
  bridge.terminate();bridge.wait(timeout=10);bridge=None;log.close()
  final=await sample('final')
  manifest=json.loads((sf.parent/'recovery/manifest.json').read_text());autosave=Path(next(x['path'] for x in manifest if Path(x['path']).name=='autosave.hoi4'));mtime=autosave.stat().st_mtime_ns
  for _ in range(240):
   if _%10==0:check_power()
   await asyncio.sleep(1)
   if autosave.stat().st_mtime_ns>mtime:
    try:native_save=read_save(sf)
    except (AssertionError,ValueError,UnicodeError):continue
    break
  else:raise RuntimeError('Fresh native save did not arrive')
  await set_time('pause',True);report['save_after']=native_save
  expected={(state,'industrial_complex'):1,(state,'arms_factory'):capacity-1,(dock,'dockyard'):2,(batch,'industrial_complex'):5}
  for (s,building),amount in expected.items():
   rows=[x for x in native_save['construction'] if x['building'].get('location')==str(s) and x['building'].get('template')==building]
   assert sum(int(x['amount']) for x in rows)==amount,(s,building,amount,rows)
  ledger=json.loads(Path(c.config['state_path']).read_text())
  retained={rid for rid,_ in ledger['commands']}
  expected_ids={value for key,value in report.items() if key.endswith('_request_id')}
  expected_ids.update(x['arguments']['request_id'] for x in report['commands'])
  if not expected_ids<=retained:raise RuntimeError('Read/action request IDs were lost from the ledger')
  report['request_ledger_verified']=True
  report['verified']=True;save();print(json.dumps({'verified':True,'initial_capacity':capacity,'two_level_dockyard_verified':True,'five_level_civilian_verified':True,'independent_native_save_verified':True,'request_ledger_verified':True}))
 except BaseException as exc:report['error']=repr(exc);save();raise
 finally:
  if bridge is not None:bridge.terminate();bridge.wait(timeout=10)
  try:
   if not clock.status()['paused']:await set_time('pause',True)
   c.arm(False)
  except Exception as exc:report['cleanup_error']=repr(exc);save()
asyncio.run(main())
