"""Bind one prepared session to its actual new HOI4 process; no game writes."""
import argparse
import json
from pathlib import Path
from direct_controller import atomic_text
from direct_process import process_identity
from prepare_session import SUPPORTED_HASH, sha


def verify_sources(config):
    from content_binding import verify
    verify(config)
    root = Path(config['game_root'])
    if config.get('protocol') != 2 or config.get('mode') != 'singleplayer_test':
        raise RuntimeError('Only the prepared single-player test protocol is supported')
    if config.get('game_sha256') != SUPPORTED_HASH or sha(root / 'hoi4.exe') != SUPPORTED_HASH:
        raise RuntimeError('Unsupported or changed game executable')
    catalog_path = Path(config['catalog_path'])
    if sha(catalog_path) != config['catalog_sha256']:
        raise RuntimeError('Equipment allowlist changed')
    catalog = json.loads(catalog_path.read_text(encoding='utf-8-sig'))
    for source, expected in catalog['source_hashes'].items():
        path = (root / source).resolve()
        if not path.is_relative_to(root.resolve()) or sha(path) != expected:
            raise RuntimeError('Installed equipment/technology sources changed')
    for name, expected in config['documentation_sha256'].items():
        if sha(root / 'documentation' / name) != expected:
            raise RuntimeError('Shipped game interface documentation changed')
    native=config.get('native_construction')
    if native:
        from install_peacetime_reader import CHOICES_SHA
        dll=Path(config['state_path']).parent/'native'/'hoi4-native-choices.dll'
        if native['module_sha256']!=CHOICES_SHA or sha(dll)!=CHOICES_SHA or native['pid']!=config['process_identity']['pid']:
            raise RuntimeError('Queued construction backend binding changed')
        catalog['construction_native']=native
    return catalog


def bind(session_file, pid):
    path = Path(session_file); config = json.loads(path.read_text(encoding='utf-8-sig'))
    if config.get('process_identity') is not None or Path(config['state_path']).exists():
        raise RuntimeError('Session is already bound or has a ledger; prepare a new session')
    verify_sources(config)
    ident = process_identity(pid)
    if Path(ident['executable']).resolve() != (Path(config['game_root']) / 'hoi4.exe').resolve():
        raise RuntimeError('Process executable differs from the prepared game')
    created_unix = ident['created'] / 10000000 - 11644473600
    if created_unix < config['prepared_unix']:
        raise RuntimeError('Game process predates this mod session')
    marker = f"CODEX_COMMAND_SESSION|{config['session_id']}|READY|country={config['country']}"
    logs = Path(config['log_path']).read_text(encoding='utf-8', errors='replace')
    if marker not in logs:
        raise RuntimeError('Matching game-side startup acknowledgment not found; no binding written')
    config['process_identity'] = ident
    atomic_text(path, json.dumps(config, indent=2))
    return ident


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--session-file', required=True); p.add_argument('--pid', required=True, type=int)
    args = p.parse_args()
    print(json.dumps({'bound_process': bind(args.session_file, args.pid), 'input_events': False}))


if __name__ == '__main__':
    main()
