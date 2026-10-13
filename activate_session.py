"""Install/remove only this prepared mod entry, with recovery copies.

No game is launched, stopped, unpaused or driven through input events.
"""
import argparse
import hashlib
import json
from pathlib import Path
from bind_session import verify_sources
from direct_controller import atomic_text, HEX_ID


def selection(path):
    data = json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {'enabled_mods': [], 'disabled_dlcs': []}
    if not isinstance(data, dict) or not isinstance(data.get('enabled_mods'), list) or any(not isinstance(v, str) for v in data['enabled_mods']):
        raise ValueError('Invalid mod selection; no changes applied')
    return data


def activate(session_file, user_root):
    path = Path(session_file); root = path.parent
    config = json.loads(path.read_text(encoding='utf-8-sig'))
    verify_sources(config)
    sid = config['session_id']
    if not isinstance(sid, str) or not HEX_ID.fullmatch(sid):
        raise ValueError('Invalid session ID')
    receipt = root / 'activation.json'
    if receipt.exists() or config.get('process_identity') is not None:
        raise RuntimeError('Session already activated or bound; it was not reset')
    user = Path(user_root).resolve(); target = user / 'dlc_load.json'
    descriptor = user / 'mod' / ('CodexCommands_' + sid + '.mod')
    data = selection(target); entry = 'mod/' + descriptor.name
    if descriptor.exists() or entry in data['enabled_mods']:
        raise RuntimeError('Mod entry exists; nothing overwritten')
    content = (root / 'CodexCommands.mod').read_text(encoding='utf-8')
    user.mkdir(parents=True, exist_ok=True); descriptor.parent.mkdir(exist_ok=True)
    backup = root / 'dlc_load.before.json'
    if target.exists():
        with backup.open('xb') as f:
            f.write(target.read_bytes())
    record = {'user_root': str(user), 'descriptor': str(descriptor), 'entry': entry,
              'descriptor_sha256': hashlib.sha256(content.encode('utf-8')).hexdigest(),
              'previous_selection_existed': target.exists()}
    # A recovery record exists even if descriptor or selection publication fails.
    atomic_text(receipt, json.dumps(record, indent=2))
    atomic_text(descriptor, content)
    data['enabled_mods'].append(entry)
    atomic_text(target, json.dumps(data, indent=2))
    return {'installed_mod_entry': entry, 'game_restart_required': True, 'input_events': False}


def deactivate(session_file):
    root = Path(session_file).parent; receipt = root / 'activation.json'
    record = json.loads(receipt.read_text(encoding='utf-8'))
    target = Path(record['user_root']) / 'dlc_load.json'; data = selection(target)
    data['enabled_mods'] = [v for v in data['enabled_mods'] if v != record['entry']]
    atomic_text(target, json.dumps(data, indent=2))
    descriptor = Path(record['descriptor'])
    retained = False
    if descriptor.exists():
        if hashlib.sha256(descriptor.read_bytes()).hexdigest() == record['descriptor_sha256']:
            descriptor.unlink()
        else:
            retained = True  # A changed file is never silently removed.
    return {'removed_mod_entry': record['entry'], 'changed_descriptor_retained': retained,
            'other_selection_fields_preserved': True, 'input_events': False}


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('operation', choices=('activate', 'deactivate'))
    p.add_argument('--session-file', required=True); p.add_argument('--user-root')
    args = p.parse_args()
    if args.operation == 'activate':
        if not args.user_root:
            p.error('--user-root is required for activation')
        result = activate(args.session_file, args.user_root)
    else:
        result = deactivate(args.session_file)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
