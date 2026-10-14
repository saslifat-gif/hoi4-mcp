import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from mvp_demo import demo
class MvpTests(unittest.TestCase):
 def fixtures(self,path):
  c=Mock();c.native=Path(path);c.config={'session_id':'a'*32}
  clock=Mock();clock.submit.return_value={'stage':'time_verified'}
  clock.status.side_effect=[{'paused':True},{'speed':5},{'paused':False},{'paused':True}]
  agent=Mock();agent.load.return_value={'used':4,'pending':None}
  return c,clock,agent
 def test_verified_run_pauses_disarms_and_retains_distinct_ids(self):
  with tempfile.TemporaryDirectory() as p,patch('mvp_demo.require_ac_power'),patch('mvp_demo.run',return_value={'stage':'action_verified'}):
   c,clock,agent=self.fixtures(p);report=demo(c,clock,agent)
   saved=json.loads(next(Path(p).glob('mvp-run-*.json')).read_text())
   self.assertEqual(saved['verified_actions'],4);self.assertEqual(saved,report)
   self.assertEqual(len(set(saved['requests'].values())),4)
   self.assertEqual(clock.submit.call_args.args,(saved['requests']['stop'],'pause',True));self.assertEqual(c.arm.call_args.args,(False,))
 def test_policy_failure_still_pauses_and_preserves_failure_report(self):
  with tempfile.TemporaryDirectory() as p,patch('mvp_demo.require_ac_power'),patch('mvp_demo.run',side_effect=RuntimeError('invalid observation')):
   c,clock,agent=self.fixtures(p)
   with self.assertRaisesRegex(RuntimeError,'invalid observation'):demo(c,clock,agent)
   saved=json.loads(next(Path(p).glob('mvp-run-*.json')).read_text())
   self.assertEqual(saved['stage'],'failed');self.assertEqual(saved['error'],'invalid observation');self.assertEqual(c.arm.call_args.args,(False,))
 def test_uncertain_time_result_is_not_replayed(self):
  with tempfile.TemporaryDirectory() as p,patch('mvp_demo.require_ac_power'),patch('mvp_demo.run') as run:
   c,clock,agent=self.fixtures(p);clock.submit.return_value={'stage':'execution_uncertain'}
   with self.assertRaisesRegex(RuntimeError,'retained ID'):demo(c,clock,agent)
   saved=json.loads(next(Path(p).glob('mvp-run-*.json')).read_text())
   ids=[call.args[0] for call in clock.submit.call_args_list]
   self.assertEqual(ids,[saved['requests']['pause'],saved['requests']['stop']]);run.assert_not_called();self.assertEqual(c.arm.call_args.args,(False,))
 def test_battery_or_invalid_duration_never_arms(self):
  with tempfile.TemporaryDirectory() as p,patch('mvp_demo.require_ac_power',side_effect=RuntimeError('AC required')):
   c,clock,agent=self.fixtures(p)
   with self.assertRaisesRegex(RuntimeError,'AC required'):demo(c,clock,agent)
   with self.assertRaises(ValueError):demo(c,clock,agent,0)
   c.arm.assert_not_called();self.assertEqual(list(Path(p).iterdir()),[])
if __name__=='__main__':unittest.main()
