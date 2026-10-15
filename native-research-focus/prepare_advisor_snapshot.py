"""Pause an owned campaign, preserve the time request ID, then inspect via MCP."""
import argparse, asyncio, json, time, uuid
from native_controller import NativeController
from time_controller import TimeController
from inspect_advisor_mcp import inspect
p=argparse.ArgumentParser();p.add_argument('--session-file',required=True);a=p.parse_args()
c=NativeController(a.session_file);clock=TimeController(c)
report={'pause_request_id':uuid.uuid4().hex,'session_id':c.config['session_id']}
path=c.native/'advisor-initial-pause.json'
with path.open('x') as handle:json.dump(report,handle)
c.arm(True)
try:
 result=clock.submit(report['pause_request_id'],'pause',True);deadline=time.monotonic()+20
 while result['stage']=='pending':
  if time.monotonic()>=deadline:raise RuntimeError('Pause pending; preserve initial request ID')
  time.sleep(.05);result=clock.receipt(report['pause_request_id'])
 report['receipt']=result;path.write_text(json.dumps(report,indent=2))
 if result['stage']!='time_verified':raise RuntimeError('Initial pause not verified')
 while not clock.status()['paused']:
  if time.monotonic()>=deadline:raise RuntimeError('Paused readback timed out')
  time.sleep(.05)
finally:c.arm(False)
asyncio.run(inspect(a.session_file))
