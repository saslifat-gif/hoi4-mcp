"""File-driven HOI4 commands. No mouse, keyboard, window or input APIs."""
import json
import os
from pathlib import Path
import re
import secrets
import math
import functools
import threading
import time
from command_catalog import equipment_guard, construction_state_guard

FUNCTION = 'codex_mcp_commands_'
SESSION_FLAG = 'codex_mcp_session_'
FIELDS = {'political_power': 'political_power', 'manpower': 'manpower',
          'stability': 'stability', 'war_support': 'has_war_support',
          'civilian_factories': 'num_of_civilian_factories',
          'military_factories': 'num_of_military_factories',
          'available_military_factories': 'num_of_available_military_factories',
          'divisions': 'num_divisions'}
ID = re.compile(r'^[a-z][a-z0-9_]{0,79}$')
RECEIPT = re.compile(r'CODEX_COMMAND\|([a-f0-9]{32})\|([a-f0-9]{32})\|(ACK|REJECT)\|([^\r\n]*)')
DATE = re.compile(r'\[(\d{4}\.\d{2}\.\d{2}\.\d{2})\]')
HEX_ID = re.compile(r'[a-f0-9]{32}\Z')
UNSUPPORTED = ['research_selection', 'focus_selection', 'unit_orders', 'pause_and_speed',
               'diplomacy', 'event_option_selection', 'existing_production_line_changes', 'new_game_creation']

def atomic_text(path,text):
    tmp=path.with_name(path.name+'.pending')
    try:
        with tmp.open('w',encoding='utf-8',newline='\n') as f:
            f.write(text);f.flush();os.fsync(f.fileno())
        for attempt in range(6):
            try:
                os.replace(tmp,path)
                break
            except PermissionError as error:
                if getattr(error,'winerror',None) not in (5,32) or attempt==5:raise
                time.sleep(.02)
    finally:
        if tmp.exists():tmp.unlink()

def render_hook(country,session_id,nonce,activate_on_startup=False,commands=None,catalog=None):
    if not re.fullmatch(r'[A-Z]{3}',country) or not HEX_ID.fullmatch(session_id) or not HEX_ID.fullmatch(nonce):
        raise ValueError('Invalid hook identity')
    if type(activate_on_startup) is not bool:raise ValueError('Invalid startup mode')
    startup=(f'set_country_flag = {SESSION_FLAG}{session_id}\n'
             f'log = "CODEX_COMMAND_SESSION|{session_id}|READY|country={country}"') if activate_on_startup else (
             f'clr_country_flag = {SESSION_FLAG}{session_id}\n'
             f'log = "CODEX_COMMAND_SESSION|{session_id}|INVALIDATED|country={country}"')
    daily=(f'{FUNCTION}{session_id} = yes' if commands is None else '\n'.join(
        compile_command(cid,country,command,session_id,catalog or {'equipment':{}})
        for cid,command in commands))
    return f'''# Reload nonce: {nonce}
on_actions = {{
    on_startup = {{ effect = {{ {country} = {{
        if = {{ limit = {{ is_ai = no }}
            {startup}
        }}
    }} }} }}
    on_daily_{country} = {{ effect = {{ {country} = {{
        if = {{ limit = {{ has_country_flag = {SESSION_FLAG}{session_id} }}
            log = "CODEX_COMMAND_SESSION|{session_id}|LIVE|country={country}"
            if = {{ limit = {{ tag = {country} is_ai = no }}
                {daily}
            }}
        }}
    }} }} }}
}}
'''


def snapshot_script():
    assignments = '\n'.join(f'set_temp_variable = {{ codex_{name} = {token} }}' for name, token in FIELDS.items())
    values = '|'.join(f'{name}=[?codex_{name}]' for name in FIELDS)
    return assignments, values


def compile_command(cid, country, command, session_id, catalog):
    if not isinstance(cid,str) or not HEX_ID.fullmatch(cid) or not re.fullmatch(r'[A-Z]{3}', country) or not HEX_ID.fullmatch(session_id):
        raise ValueError('Invalid command ID or country')
    if not isinstance(command, dict):
        raise ValueError('Command must be an object')
    kind = command.get('kind')
    effects, guard = '', 'always = yes'
    peacetime = ''
    if kind == 'snapshot' and set(command) == {'kind'}:
        if catalog.get('peacetime'):
            from peacetime_script import render_frame
            peacetime = render_frame(session_id,cid,catalog['peacetime'],catalog)
    elif kind == 'construct' and set(command) == {'kind', 'state_id', 'building', 'levels'}:
        state, levels, building = command['state_id'], command['levels'], command['building']
        if type(state) is not int or not 1 <= state <= 10000:
            raise ValueError('Invalid state ID')
        if type(levels) is not int or not 1 <= levels <= 5:
            raise ValueError('Levels must be an integer from 1 to 5')
        if building not in ('industrial_complex', 'arms_factory', 'dockyard'):
            raise ValueError('Only civilian factories, military factories and dockyards are supported')
        guard = f'{state} = {{ {construction_state_guard(country,building,levels)} }}'
        effects = f'{state} = {{ add_building_construction = {{ type = {building} level = {levels} instant_build = no }} }}'
        if catalog.get('construction_native'):
            effects=f'log = "CODEX_NATIVE_CONSTRUCT|{session_id}|{cid}|state={state}|building={building}|levels={levels}"'

    elif kind == 'produce' and set(command) == {'kind','equipment','factories'}:
        factories=command['factories']
        if type(factories) is not int or not 1<=factories<=15:
            raise ValueError('Requested military factories must be 1..15')
        guard=equipment_guard(catalog,command['equipment'],factories)
        effects=f'''add_equipment_production = {{
            equipment = {{ type = {command['equipment']} creator = {country} }}
            name = "MCP_{cid}"
            requested_factories = {factories}
        }}'''
    else:
        raise ValueError('Unsupported direct command. No input-simulation fallback exists.')
    assignments, values = snapshot_script()
    done = 'codex_mcp_done_' + session_id + '_' + cid
    return f'''if = {{
        limit = {{ NOT = {{ has_country_flag = {done} }} }}
        if = {{
            limit = {{ {guard} }}
            {effects}
            {peacetime}
            {assignments}
            log = "CODEX_COMMAND|{session_id}|{cid}|ACK|kind={kind}|stage=effect_ran|{values}"
        }}
        else = {{ log = "CODEX_COMMAND|{session_id}|{cid}|REJECT|kind={kind}|reason=native_guard_failed" }}
        set_country_flag = {done}
    }}'''


def render_effect(country, commands, session_id, catalog):
    parts = [compile_command(cid, country, command, session_id, catalog) for cid, command in commands]
    body = '\n'.join(parts)
    return f'''# Generated by the direct MCP adapter; no input simulation.
{FUNCTION}{session_id} = {{
    if = {{
        limit = {{ tag = {country} is_ai = no has_country_flag = {SESSION_FLAG}{session_id} }}
        {body}
    }}
}}
'''


def parse_receipt(line):
    found = RECEIPT.search(line)
    if not found:
        return None
    sid, cid, status, payload = found.groups()
    date = DATE.findall(line)
    values = {}
    for item in payload.split('|'):
        if '=' in item:
            key, value = item.split('=', 1)
            if key in values:return None
            if key in FIELDS:
                try:value=float(value)
                except ValueError:return None
                if not math.isfinite(value):return None
            values[key]=value
    return {'session_id':sid, 'command_id': cid, 'status': 'acknowledged' if status == 'ACK' else 'rejected',
            'engine_acknowledged': True, 'game_date': date[-1] if date else None,
            'data': values, 'raw_payload': payload,
            'gameplay_outcome_verified': False, 'acknowledgment_scope':'game_script_branch',
            'uses_mouse_or_keyboard':False}


def _ledger_operation(method):
    @functools.wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._ledger_lock:
            if self._ledger_depth:
                return method(self, *args, **kwargs)
            lock = self.state_path.with_suffix('.lock')
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            self._ledger_depth = 1
            try:
                if self.state_path.exists():
                    self.state = self._read_state()
                return method(self, *args, **kwargs)
            finally:
                self._ledger_depth = 0
                os.close(fd)
                lock.unlink()
    return wrapped


class DirectController:
    def __init__(self, effect_path, log_path, state_path, country='GER', process_guard=lambda: None, hook_path=None, session_id=None, catalog=None):
        self.effect_path, self.log_path, self.state_path = map(Path, (effect_path, log_path, state_path))
        self.country, self.process_guard = country, process_guard
        if not re.fullmatch(r'[A-Z]{3}', country):
            raise ValueError('Invalid country')
        if not isinstance(session_id,str) or not HEX_ID.fullmatch(session_id):
            raise ValueError('Prepared session ID required')
        self.session_id,self.catalog=session_id,catalog or {'equipment':{}}
        self._ledger_lock = threading.RLock()
        self._ledger_depth = 0
        self.hook_path = Path(hook_path) if hook_path else None
        if not self.hook_path or not self.hook_path.is_file():
            raise RuntimeError('Existing native daily hook required')
        if not self.effect_path.is_file():
            raise RuntimeError('Existing mod script required; activate the mod at game startup first')
        self.state = {'protocol':2,'session_id':session_id,'country':country,
                      'commands': [], 'receipts': {},'publication':{},'startup_seen':False,
                      'campaign_invalidated':False}
        if self.state_path.exists():
            self.state = self._read_state()
            self.state['startup_seen'] = False
        self.armed = False

    def _read_state(self):
        country, session_id = self.country, self.session_id
        state=json.loads(self.state_path.read_text(encoding='utf-8-sig'))
        if state.get('protocol')!=2 or state.get('session_id')!=session_id or state.get('country')!=country:
            raise RuntimeError('Ledger belongs to another session; it was not reset')
        if not isinstance(state.get('commands'),list) or len(state['commands'])>64:
            raise RuntimeError('Invalid command ledger')
        seen=set()
        for cid,command in state['commands']:
            if cid in seen:raise RuntimeError('Duplicate ledger command')
            compile_command(cid,country,command,session_id,self.catalog);seen.add(cid)
        if not isinstance(state.get('receipts'),dict) or not isinstance(state.get('publication'),dict) or type(state.get('startup_seen')) is not bool:
            raise RuntimeError('Invalid command ledger state')
        for cid,receipt in state['receipts'].items():
            if cid not in seen or not isinstance(receipt,dict) or receipt.get('session_id')!=session_id or receipt.get('command_id')!=cid or receipt.get('status') not in ('acknowledged','rejected'):
                raise RuntimeError('Invalid persisted receipt')
        if type(state.get('campaign_invalidated')) is not bool:
            raise RuntimeError('Invalid campaign ledger state')
        if set(state['publication'])!=seen or any(p not in ('not_published','hook_prepared_effect_pending','effect_published_hook_pending','published') for p in state['publication'].values()):
            raise RuntimeError('Invalid publication ledger')
        return state

    def _save(self):
        atomic_text(self.state_path,json.dumps(self.state,indent=2))

    def _logs(self):
        if not self.log_path.exists():
            return ''
        with self.log_path.open('rb') as f:
            f.seek(max(0, self.log_path.stat().st_size - 4 * 1024 * 1024))
            return f.read().decode('utf-8', errors='replace')

    def _refresh_pending_hook(self):
        # Live HOI4 reloads on_actions while retaining the old scripted-effect
        # expansion. Embed the commands in the reloadable daily hook instead.
        # One atomic hook publication removes future startup activation and
        # exposes the durable requests together. Rapid consecutive rewrites can
        # leave HOI4 running the first (empty) hook after its watcher coalesces them.
        self.process_guard()
        atomic_text(self.hook_path,render_hook(self.country,self.session_id,secrets.token_hex(16),
                    commands=self.state['commands'],catalog=self.catalog))

    def _construction_receipt(self,cid):
        path=self.state_path.parent/'native'/f'construction-{cid}.json'
        if not path.exists():return None
        r=json.loads(path.read_text());binding=self.catalog['construction_native'];command=dict(self.state['commands'])[cid]
        if r.get('session_id')!=self.session_id or r.get('command_id')!=cid or r.get('pid')!=binding['pid'] or r.get('world')!=binding['world']:
            raise RuntimeError('Native construction receipt binding mismatch')
        if r.get('status') not in ('acknowledged','rejected','delivery_uncertain'):
            raise RuntimeError('Invalid native construction status')
        data=r['data']
        if any(data.get(k)!=command[k] for k in ('kind','state_id','building','levels')):
            raise RuntimeError('Native construction receipt payload mismatch')
        if r['status']=='acknowledged' and (r.get('gameplay_outcome_verified') is not True or data['after_built_and_queued']!=data['before_built_and_queued']+command['levels']):
            raise RuntimeError('Native construction queue postcondition is missing')
        return r

    @_ledger_operation
    def collect(self):
        self.process_guard()
        logs = self._logs()
        changed = False
        prefix=f'CODEX_COMMAND_SESSION|{self.session_id}|'
        if prefix+f'INVALIDATED|country={self.country}' in logs:
            if not self.state['campaign_invalidated']:
                self.state['campaign_invalidated']=True;changed=True
            if self.state['startup_seen']:
                self.state['startup_seen']=False;changed=True
            self.armed=False
        ready=prefix+f'READY|country={self.country}'
        live=prefix+f'LIVE|country={self.country}'
        startup_seen=not self.state['campaign_invalidated'] and (ready in logs or live in logs)
        if self.state['startup_seen']!=startup_seen:
            self.state['startup_seen']=startup_seen;changed=True
        known=dict(self.state['commands'])
        for line in logs.splitlines():
            receipt = parse_receipt(line)
            if not receipt or receipt['session_id']!=self.session_id:continue
            cid=receipt['command_id']
            if cid not in known or receipt['data'].get('kind')!=known[cid]['kind']:continue
            if receipt['status']=='acknowledged' and receipt['data'].get('stage')!='effect_ran':continue
            if self.catalog.get('construction_native') and known[cid]['kind']=='construct' and receipt['status']=='acknowledged':
                native=self._construction_receipt(cid)
                if native is None or native['status']=='delivery_uncertain':continue
                receipt={**native,'game_date':receipt['game_date']}
            previous=self.state['receipts'].get(cid)
            if previous and previous!=receipt:
                raise RuntimeError('Conflicting engine receipts; delivery is unresolved')
            if not previous:
                self.state['receipts'][cid]=receipt;changed=True
        if changed:
            self._save()
        return logs

    @_ledger_operation
    def status(self):
        self.process_guard()
        self.collect()
        return {'transport': 'native mod hot reload and game log', 'uses_mouse_or_keyboard': False,
                'armed': self.armed, 'country': self.country,'session_id':self.session_id,
                'startup_acknowledged':self.state['startup_seen'],
                'campaign_invalidated':self.state['campaign_invalidated'],
                'pending': [cid for cid, _ in self.state['commands'] if cid not in self.state['receipts']],
                'supported_commands': ['snapshot', 'construct','produce'],
                'construction_max_levels_per_request':5 if self.catalog.get('construction_native') else 1,
                'unsupported_commands':UNSUPPORTED,
                'production_equipment_allowlist':sorted(self.catalog.get('equipment',{})),
                'excluded_equipment':self.catalog.get('excluded_equipment',{}),
                'normal_player_command_equivalence_verified':False,
                'limitations': ['requires debug mode and a running unpaused simulation',
                                'commands run on the daily hook; paused requests remain pending',
                                'DLC/mod overlays require an audited content binding; unresolved design restrictions are excluded',
                                'engine script acknowledgment does not verify the gameplay outcome']}

    @_ledger_operation
    def arm(self, enabled):
        if type(enabled) is not bool:
            raise ValueError('enabled must be boolean')
        if enabled:
            self.collect()
            if not self.state['startup_seen']:
                raise RuntimeError('Game-side startup acknowledgment is missing')
        self.armed = enabled
        return {'armed': enabled, 'uses_mouse_or_keyboard': False}

    @_ledger_operation
    def submit(self, command, request_id):
        self.process_guard()
        compile_command(request_id,self.country,command,self.session_id,self.catalog)
        self.collect()
        existing=dict(self.state['commands']).get(request_id)
        if existing is not None:
            if existing!=command:raise ValueError('Request ID has a different command')
            return self.receipt(request_id)
        if command.get('kind') == 'construct' and command['levels'] != 1 and not self.catalog.get('construction_native'):
            raise ValueError('Construction supports one level per request; queued multi-level capacity is not reliably exposed')
        if command.get('kind') != 'snapshot' and not self.armed:
            raise RuntimeError('Direct game mutations are disarmed')
        if not self.state['startup_seen']:
            raise RuntimeError('Game-side startup acknowledgment is missing')
        if any(cid not in self.state['receipts'] for cid, _ in self.state['commands']):
            raise RuntimeError('Previous command is unresolved. Check its receipt; do not resubmit.')
        if len(self.state['commands']) >= 64:
            raise RuntimeError('Session command limit reached; prepare a fresh session')
        cid = request_id
        self.state['commands'].append([cid, json.loads(json.dumps(command))])
        self.state['publication'][cid]='not_published'
        # Save the ID before publishing; after uncertainty, retain it for inspection.
        self._save()
        return self.deliver(cid)

    @_ledger_operation
    def deliver(self,cid):
        self.collect()
        known=dict(self.state['commands'])
        if cid not in known:raise ValueError('Unknown command ID')
        if cid in self.state['receipts']:return self.state['receipts'][cid]
        if known[cid]['kind']!='snapshot' and not self.armed:
            raise RuntimeError('Direct game mutations are disarmed')
        if not self.state['startup_seen']:raise RuntimeError('Game-side startup acknowledgment is missing')
        try:
            self.process_guard()
            # Remove activation in the same atomic hook publication as requests.
            # A later campaign must never reactivate this ledger.
            self._refresh_pending_hook()
            self.state['publication'][cid]='hook_prepared_effect_pending';self._save()
            atomic_text(self.effect_path,render_effect(self.country,self.state['commands'],self.session_id,self.catalog))
            self.state['publication'][cid]='effect_published_hook_pending';self._save()
            self.state['publication'][cid]='published';self._save()
        except (OSError,RuntimeError):
            self.armed=False
            return {'command_id':cid,'status':'delivery_uncertain','engine_acknowledged':False,
                    'uses_mouse_or_keyboard':False,'publication':self.state['publication'][cid],
                    'next_step':'Inspect receipt; explicitly deliver the same ID after recovery'}
        return {'command_id': cid, 'status': 'queued', 'engine_acknowledged': False,
                'gameplay_outcome_verified':False,'uses_mouse_or_keyboard': False}

    @_ledger_operation
    def receipt(self, cid):
        if not any(known == cid for known, _ in self.state['commands']):
            raise ValueError('Unknown command ID')
        self.collect()
        if self.catalog.get('construction_native') and dict(self.state['commands'])[cid]['kind']=='construct' and cid not in self.state['receipts']:
            native=self._construction_receipt(cid)
            if native and native['status']=='delivery_uncertain':return native
        return self.state['receipts'].get(cid, {'command_id': cid, 'status': 'pending',
                                              'engine_acknowledged': False,'uses_mouse_or_keyboard':False,
                                              'publication':self.state['publication'][cid],
                                              'gameplay_outcome_verified':False})
