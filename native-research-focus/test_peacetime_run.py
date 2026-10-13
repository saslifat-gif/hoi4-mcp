import unittest
from unittest.mock import Mock,patch
import peacetime_run

class RunnerTests(unittest.TestCase):
 def agent(self):
  agent=Mock();agent.load.return_value={'enabled':True}
  agent.step.return_value={'stage':'waiting_for_choice'}
  return agent
 def test_deadline_stops_idle_run(self):
  agent=self.agent()
  with patch.object(peacetime_run,'require_ac_power'),patch.object(peacetime_run.time,'monotonic',side_effect=[0,0,0,2]),patch.object(peacetime_run.time,'sleep'):
   self.assertEqual(peacetime_run.run(agent,seconds=1)['stage'],'duration_complete')
  agent.step.assert_called_once();agent.stop.assert_called_once()
 def test_changing_snapshot_waits_then_resumes(self):
  agent=self.agent();agent.step.side_effect=[peacetime_run.SnapshotChanged('tick changed'),{'stage':'stopped'}]
  with patch.object(peacetime_run,'require_ac_power'),patch.object(peacetime_run.time,'monotonic',side_effect=[0,0,0,1]),patch.object(peacetime_run.time,'sleep'):
   self.assertEqual(peacetime_run.run(agent,seconds=5)['stage'],'stopped')
  self.assertEqual(agent.step.call_count,2);agent.stop.assert_called_once()
 def test_invalid_snapshot_still_fails(self):
  from research_reader import ResearchReadError
  agent=self.agent();agent.step.side_effect=ResearchReadError('bad owner')
  with patch.object(peacetime_run,'require_ac_power'):
   with self.assertRaisesRegex(ResearchReadError,'bad owner'):peacetime_run.run(agent)
  agent.step.assert_called_once();agent.stop.assert_called_once()
 def test_unplugging_stops_without_another_action(self):
  agent=self.agent()
  with patch.object(peacetime_run,'require_ac_power',side_effect=[None,RuntimeError('unplugged')]):
   with self.assertRaisesRegex(RuntimeError,'unplugged'):peacetime_run.run(agent)
  agent.step.assert_not_called();agent.stop.assert_called_once()
 def test_disconnected_never_starts(self):
  agent=self.agent()
  with patch.object(peacetime_run,'require_ac_power',side_effect=RuntimeError('unplugged')):
   with self.assertRaises(RuntimeError):peacetime_run.run(agent)
  agent.start.assert_not_called();agent.step.assert_not_called()
 def test_uncertainty_exits_poll_loop(self):
  agent=self.agent();agent.step.return_value={'stage':'stopped_uncertain'}
  with patch.object(peacetime_run,'require_ac_power'):
   self.assertEqual(peacetime_run.run(agent)['stage'],'stopped_uncertain')
  agent.step.assert_called_once();agent.stop.assert_called_once()

if __name__=='__main__':unittest.main()
