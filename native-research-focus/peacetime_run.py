"""Bounded sustained policy runner; game time remains controlled by the time MCP.

Requires an already armed, advancing, owned Germany test session on AC power.
Stopping retains pending gameplay IDs; it does not close or pause the game.
"""
import argparse,json,time
from peacetime_agent import PeacetimeAgent
from direct_process import require_ac_power
from research_reader import SnapshotChanged

def run(agent,seconds=300,action_budget=16):
 if type(seconds)!=int or not 1<=seconds<=3600:raise ValueError('Duration must be 1..3600 seconds')
 require_ac_power()
 agent.start(action_budget,wait_for_choices=True)
 deadline=time.monotonic()+seconds
 try:
  while time.monotonic()<deadline:
   require_ac_power()
   try:result=agent.step()
   except SnapshotChanged:result={'stage':'waiting_for_consistent_observation'}
   print(json.dumps(result),flush=True)
   if result['stage'].startswith('stopped'):break
   if not agent.load()['enabled']:break
   remaining=deadline-time.monotonic()
   if remaining<=0:result={'stage':'duration_complete'};break
   time.sleep(min(5,remaining))
  else:result={'stage':'duration_complete'}
  return result
 finally:agent.stop()

def main():
 from native_controller import NativeController
 from time_controller import TimeController
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--session-file',required=True)
 parser.add_argument('--seconds',type=int,default=300)
 parser.add_argument('--action-budget',type=int,default=16)
 args=parser.parse_args()
 controller=NativeController(args.session_file)
 if not controller.load()['armed']:raise RuntimeError('Arm the owned session first')
 if TimeController(controller).status()['paused']:raise RuntimeError('Resume game time through the native MCP first')
 agent=PeacetimeAgent(controller,controller.native/'ai-ledger.json')
 print(json.dumps(run(agent,args.seconds,args.action_budget)),flush=True)

if __name__=='__main__':main()
