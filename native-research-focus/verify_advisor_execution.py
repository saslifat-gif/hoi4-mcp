"""Exercise one appointment in an already bound protected campaign via real MCP.

The caller owns campaign launch and profile recovery. This script ends paused and
disarmed when the backends remain reachable. It never changes balances or saves.
"""
import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path


def evidence_checks(report):
    selected = report['appointment']
    key = (report['character'], report['role'])
    def active(snapshot):
        return sum((row['character_id'], row['role_id']) == key and row['active']
                   for row in snapshot['advisors'])
    def paid(resource):
        return (selected[f'{resource}_before_raw'] - selected[f'{resource}_after_raw']
                == max(0, selected[f'{resource}_cost_raw']))
    return {
        'actual_mcp': report['actual_MCP'] is True,
        'previously_inactive': active(report['before']) == 0,
        'native_verified': selected['stage'] == 'advisor_verified' and selected['cost_verified'] is True,
        'positive_pp_charge': selected['political_power_cost_raw'] > 0,
        'positive_cp_charge': selected['command_power_cost_raw'] > 0,
        'exact_pp_charge': paid('political_power'),
        'exact_cp_charge': paid('command_power'),
        'independent_membership': active(report['after']) == active(report['direct_after']) == 1,
        'direct_snapshot_matches': report['after'] == report['direct_after'],
        'duplicate_receipt_unchanged': report['duplicate'] == selected,
        'duplicate_state_unchanged': report['after_duplicate'] == report['after'],
        'already_selected_rejected': report['already']['stage'] == 'rejected'
            and report['already']['reason'] == 'already_selected',
        'no_input': selected['uses_keyboard_or_mouse'] is False,
        'paused': report['final_clock']['paused'] is True,
        'disarmed': report['final_armed'] is False,
    }


async def exercise(call, controller, clock, character, role, path, seconds):
    ids = {name: uuid.uuid4().hex for name in
           ('speed', 'resume', 'appointment', 'pause', 'already_resume', 'already', 'stop')}
    report = {'actual_MCP': True, 'session_id': controller.config['session_id'],
              'character': character, 'role': role, 'requests': ids, 'verified': False}
    arm_attempted = False
    def save():
        path.write_text(json.dumps(report, indent=2))
    async def poll(name, args, receipt, terminal):
        result = await call(name, args)
        deadline = time.monotonic() + seconds
        while result['stage'] not in terminal:
            if result['stage'] == 'execution_uncertain' and result.get('reason'):
                raise RuntimeError('Uncertain execution; retain the original request ID')
            if time.monotonic() >= deadline:
                raise RuntimeError('Receipt pending; retain the original request ID')
            await asyncio.sleep(.1)
            result = await call(receipt, {'request_id': args['request_id']})
        return result
    async def pause(label, value):
        result = await poll('hoi4_set_paused', {'request_id': ids[label], 'paused': value},
                            'hoi4_time_receipt', {'time_verified', 'rejected'})
        if result['stage'] == 'time_verified':
            deadline = time.monotonic() + seconds
            while clock.status()['paused'] != value:
                if time.monotonic() >= deadline:
                    raise RuntimeError('Clock readback pending; retain the original request ID')
                await asyncio.sleep(.05)
        return result
    async def appoint(label):
        result = await poll('hoi4_appoint_advisor',
                            {'request_id': ids[label], 'character': character, 'role': role},
                            'hoi4_native_receipt', {'advisor_verified', 'rejected'})
        report[label] = result
        save()
        return result
    # Write IDs before any publication. Never replace them after uncertainty.
    with path.open('x') as handle:
        json.dump(report, handle, indent=2)
    try:
        before_clock = clock.status()
        if not before_clock['paused'] or controller.load()['armed']:
            raise RuntimeError('Expected an already paused, disarmed protected campaign')
        report['before'] = await call('hoi4_country_advisors', {})
        matches = [row for row in report['before']['advisors']
                   if (row['character_id'], row['role_id']) == (character, role)]
        if len(matches) != 1 or matches[0]['active'] or not matches[0]['listed_for_country']:
            raise RuntimeError('Exact inactive country-listed role required')
        arm_attempted = True
        await call('hoi4_native_arm', {'enabled': True})
        speed = await poll('hoi4_set_speed', {'request_id': ids['speed'], 'speed': 1},
                           'hoi4_time_receipt', {'time_verified', 'rejected'})
        if speed['stage'] != 'time_verified':
            raise RuntimeError('Speed change rejected')
        if (await pause('resume', False))['stage'] != 'time_verified':
            raise RuntimeError('Resume rejected')
        selected = await appoint('appointment')
        if selected['stage'] != 'advisor_verified':
            raise RuntimeError('Ordinary native appointment rejected')
        if (await pause('pause', True))['stage'] != 'time_verified':
            raise RuntimeError('Pause rejected')
        report['after'] = await call('hoi4_country_advisors', {})
        report['direct_after'] = controller.advisor_snapshot()
        report['duplicate'] = await call('hoi4_appoint_advisor',
            {'request_id': ids['appointment'], 'character': character, 'role': role})
        report['after_duplicate'] = await call('hoi4_country_advisors', {})
        if (await pause('already_resume', False))['stage'] != 'time_verified':
            raise RuntimeError('Resume rejected')
        await appoint('already')
    except Exception as error:
        report['failure'] = str(error)
        save()
        raise
    finally:
        try:
            if arm_attempted and controller.load()['armed']:
                await pause('stop', True)
        finally:
            if arm_attempted:
                controller.arm(False)
            save()
    report['final_clock'] = clock.status()
    report['final_armed'] = controller.load()['armed']
    report['checks'] = evidence_checks(report)
    report['verified'] = all(report['checks'].values())
    save()
    if not report['verified']:
        raise RuntimeError('Advisor verification failed; retain report and request IDs')
    return report


async def main(args):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from native_controller import NativeController
    from time_controller import TimeController
    controller = NativeController(args.session_file)
    output = controller.native / 'advisor-execution-mcp-test.json'
    params = StdioServerParameters(command=sys.executable,
        args=[str(Path(__file__).with_name('native_mcp_server.py')),
              '--session-file', str(args.session_file)], env=dict(os.environ))
    async with stdio_client(params, errlog=sys.stderr) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            async def call(name, arguments):
                result = await client.call_tool(name, arguments)
                if result.isError:
                    raise RuntimeError(str(result.content))
                return result.structuredContent or json.loads(result.content[0].text)
            report = await exercise(call, controller, TimeController(controller),
                                    args.character, args.role, output, args.seconds)
            print(json.dumps({'verified': report['verified'], 'checks': report['checks']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session-file', required=True, type=Path)
    parser.add_argument('--character', required=True)
    parser.add_argument('--role', required=True)
    parser.add_argument('--seconds', type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 120:
        parser.error('seconds must be between 1 and 120 per receipt')
    asyncio.run(main(args))
