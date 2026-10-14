"""Run the MVP policy, then pause and disarm while retaining every request ID."""
import argparse,json,time,uuid
from pathlib import Path
from direct_controller import atomic_text
from direct_process import require_ac_power
from peacetime_agent import PeacetimeAgent
from peacetime_run import run

def time_request(clock,request_id,kind,value):
 result=clock.submit(request_id,kind,value);deadline=time.monotonic()+12
 while result['stage']=='pending':
  if time.monotonic()>=deadline:raise RuntimeError('Time request pending; retained ID: '+request_id)
  time.sleep(.05);result=clock.receipt(request_id)
 if result['stage']!='time_verified':raise RuntimeError('Time request not verified; retained ID: '+request_id)
 while True:
  state=clock.status()
  if state['paused']==value if kind=='pause' else state['speed']==value:return state
  if time.monotonic()>=deadline:raise RuntimeError('Time readback pending; retained ID: '+request_id)
  time.sleep(.05)

def demo(controller,clock,agent,seconds=180):
 if type(seconds)!=int or not 1<=seconds<=600:raise ValueError('MVP duration must be 1..600 seconds')
 require_ac_power()
 report_path=controller.native/('mvp-run-'+uuid.uuid4().hex+'.json')
 report={'session_id':controller.config['session_id'],'requests':{k:uuid.uuid4().hex for k in ('pause','speed','resume','stop')},'stage':'starting'}
 atomic_text(report_path,json.dumps(report,indent=2));ids=report['requests'];controller.arm(True)
 try:
  time_request(clock,ids['pause'],'pause',True)
  time_request(clock,ids['speed'],'speed',5)
  time_request(clock,ids['resume'],'pause',False)
  report['result']=run(agent,seconds,action_budget=4)
  report['verified_actions']=agent.load()['used'];report['stage']='finished'
  if agent.load()['pending'] or report['result']['stage'] in ('stopped_uncertain','stopped_rejected','stopped_postcondition_failed'):
   raise RuntimeError('AI stopped before verification; inspect retained report and ledger')
  return report
 except Exception as error:
  report.update(stage='failed',error=str(error));raise
 finally:
  try:
   report['final_pause']=time_request(clock,ids['stop'],'pause',True)
  finally:
   try:controller.arm(False)
   finally:atomic_text(report_path,json.dumps(report,indent=2))

def main():
 from native_controller import NativeController
 from time_controller import TimeController
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--session-file',required=True);p.add_argument('--seconds',type=int,default=180);a=p.parse_args()
 c=NativeController(a.session_file);agent=PeacetimeAgent(c,c.native/'ai-ledger.json')
 print(json.dumps(demo(c,TimeController(c),agent,a.seconds)),flush=True)
if __name__=='__main__':main()
