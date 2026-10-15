"""Driver simulations only; these tests do not access HOI4, Windows or MCP."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from verify_advisor_execution import exercise


class Fixture:
    config = {'session_id': 'fixture'}
    def __init__(self, mode='normal'):
        self.mode = mode
        self.armed = False
        self.paused = True
        self.active = False
        self.pp, self.cp = 17500000, 5000000
        self.receipts = {}
        self.calls = []
        self.disarms = 0
    def load(self):
        return {'armed': self.armed}
    def status(self):
        return {'paused': self.paused}
    def arm(self, enabled):
        self.armed = enabled
        self.disarms += not enabled
    def advisor_snapshot(self):
        return {'advisors': [{'character_id': 'GER_test', 'role_id': 'test_role',
                             'listed_for_country': True, 'active': self.active}],
                'political_power_raw': self.pp, 'command_power_raw': self.cp}
    async def call(self, name, arguments):
        self.calls.append((name, copy.deepcopy(arguments)))
        if name == 'hoi4_country_advisors':
            return self.advisor_snapshot()
        if name == 'hoi4_native_receipt':
            return self.receipts[arguments['request_id']]
        if name == 'hoi4_native_arm':
            self.armed = arguments['enabled']
            return {'armed': self.armed}
        if name == 'hoi4_set_paused':
            self.paused = arguments['paused']
            return {'stage': 'time_verified'}
        if name == 'hoi4_set_speed':
            return {'stage': 'time_verified'}
        if name == 'hoi4_appoint_advisor':
            rid = arguments['request_id']
            if rid in self.receipts:
                if self.mode == 'double_charge':
                    self.cp -= 100000
                return self.receipts[rid]
            if self.mode in ('uncertain', 'pending'):
                return {'stage': 'execution_uncertain' if self.mode == 'uncertain' else 'pending'}
            if self.active:
                return {'stage': 'rejected', 'reason': 'already_selected'}
            result = {'stage': 'advisor_verified', 'cost_verified': True,
                      'political_power_cost_raw': 15000000,
                      'command_power_cost_raw': 2500000 if self.mode != 'zero_cp' else 0,
                      'political_power_before_raw': self.pp, 'command_power_before_raw': self.cp,
                      'uses_keyboard_or_mouse': False}
            self.pp -= result['political_power_cost_raw']
            self.cp -= result['command_power_cost_raw']
            result.update(political_power_after_raw=self.pp, command_power_after_raw=self.cp)
            self.active = True
            self.receipts[rid] = result
            if self.mode == 'intent_then_success':
                return {'stage': 'execution_uncertain'}
            return result
        raise AssertionError('Unexpected tool: ' + name)


class DriverTests(unittest.IsolatedAsyncioTestCase):
    async def run_fixture(self, fixture, path, seconds=1):
        return await exercise(fixture.call, fixture, fixture, 'GER_test', 'test_role', path, seconds)

    async def test_positive_costs_independent_read_and_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture()
            report = await self.run_fixture(fixture, Path(directory) / 'report.json')
            self.assertTrue(report['verified'])
            self.assertTrue(all(report['checks'].values()))
            self.assertFalse(fixture.armed)
            self.assertTrue(fixture.paused)
            self.assertEqual(len(fixture.receipts), 1)

    async def test_frame_status_can_lag_the_verified_pause_receipt(self):
        class LaggedFixture(Fixture):
            stale = None
            async def call(self, name, arguments):
                before = self.paused
                result = await super().call(name, arguments)
                if name == 'hoi4_set_paused':
                    self.stale = before
                return result
            def status(self):
                if self.stale is not None:
                    value = self.stale
                    self.stale = None
                    return {'paused': value}
                return super().status()
        with tempfile.TemporaryDirectory() as directory:
            result = await self.run_fixture(LaggedFixture(), Path(directory) / 'report.json')
            self.assertTrue(result['verified'])
            self.assertTrue(result['final_clock']['paused'])

    async def test_inflight_intent_is_observed_without_resubmission(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture('intent_then_success')
            report = await self.run_fixture(fixture, Path(directory) / 'report.json')
            self.assertTrue(report['verified'])
            self.assertEqual(len(fixture.receipts), 1)
            self.assertEqual(sum(name == 'hoi4_native_receipt' for name, _ in fixture.calls), 1)

    async def test_zero_cp_does_not_satisfy_positive_cp_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.json'
            with self.assertRaisesRegex(RuntimeError, 'verification failed'):
                await self.run_fixture(Fixture('zero_cp'), path)
            report = json.loads(path.read_text())
            self.assertFalse(report['verified'])
            self.assertFalse(report['checks']['positive_cp_charge'])

    async def test_duplicate_with_unchanged_receipt_but_changed_balance_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.json'
            with self.assertRaisesRegex(RuntimeError, 'verification failed'):
                await self.run_fixture(Fixture('double_charge'), path)
            checks = json.loads(path.read_text())['checks']
            self.assertTrue(checks['duplicate_receipt_unchanged'])
            self.assertFalse(checks['duplicate_state_unchanged'])

    async def test_pending_and_uncertain_keep_ids_and_stop_publication(self):
        for mode in ('pending', 'uncertain'):
            with tempfile.TemporaryDirectory() as directory:
                fixture = Fixture(mode)
                path = Path(directory) / 'report.json'
                with self.assertRaisesRegex(RuntimeError, 'retain the original request ID'):
                    await self.run_fixture(fixture, path, seconds=0)
                report = json.loads(path.read_text())
                calls = [args for name, args in fixture.calls if name == 'hoi4_appoint_advisor']
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0]['request_id'], report['requests']['appointment'])
                self.assertFalse(report['verified'])
                self.assertFalse(fixture.armed)
                self.assertTrue(fixture.paused)

    async def test_failed_initial_precondition_does_not_change_existing_armed_state(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture()
            fixture.armed = True
            with self.assertRaisesRegex(RuntimeError, 'paused, disarmed'):
                await self.run_fixture(fixture, Path(directory) / 'report.json')
            self.assertTrue(fixture.armed)
            self.assertEqual(fixture.calls, [])
            self.assertEqual(fixture.disarms, 0)

    async def test_existing_report_is_never_overwritten_or_replayed(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture()
            path = Path(directory) / 'report.json'
            path.write_text('retained prior IDs')
            with self.assertRaises(FileExistsError):
                await self.run_fixture(fixture, path)
            self.assertEqual(path.read_text(), 'retained prior IDs')
            self.assertEqual(fixture.calls, [])


if __name__ == '__main__':
    unittest.main()
