"""Prepare a fresh mod session; never activates it or changes existing ledgers."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import secrets
import time
from command_catalog import build_catalog
from direct_controller import render_effect, render_hook

SUPPORTED_HASH = '7dc947be34970da1e1c787bcddbe7f62b610ff258aebf8f06aa8b348f3a031d5'
REQUIRED_DOCS = {
    'effects_documentation.md': ['add_building_construction', 'add_equipment_production', 'log', 'set_country_flag'],
    'triggers_documentation.md': ['free_building_slots', 'is_owned_and_controlled_by', 'is_ai', 'has_tech', 'num_of_available_military_factories'],
}


def sha(path):
    with Path(path).open('rb') as f:
        digest = hashlib.sha256()
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def prepare(game_root, session_root, log_path, country='GER'):
    game, root = Path(game_root).resolve(), Path(session_root).resolve()
    if not re.fullmatch(r'[A-Z]{3}', country):
        raise ValueError('Invalid country')
    if root.exists():
        raise RuntimeError('Session directory already exists; nothing was overwritten')
    if sha(game / 'hoi4.exe') != SUPPORTED_HASH:
        raise RuntimeError('Unsupported HOI4 executable; no session created')
    docs = {}
    for name, keys in REQUIRED_DOCS.items():
        path = game / 'documentation' / name
        text = path.read_text(encoding='utf-8-sig')
        for key in keys:
            if not re.search(r'^## ' + re.escape(key) + r'\s*$', text, re.MULTILINE):
                raise RuntimeError('Required shipped interface missing: ' + key)
        docs[name] = sha(path)
    catalog = build_catalog(game)
    sid = secrets.token_hex(16)
    effect = root / 'mod/common/scripted_effects/codex_commands.txt'
    hook = root / 'mod/common/on_actions/codex_commands.txt'
    content_binding=None
    user=Path(log_path).resolve().parent.parent
    if (user/'dlc_load.json').is_file():
        from content_binding import capture
        owned='mod/CodexCommands_'+sid+'.mod'
        content_binding={'user_root':str(user),'owned_entry':owned,'snapshot':capture(game,user,owned)}
    # Validate everything before creating a new session tree.
    root.mkdir(parents=True)
    effect.parent.mkdir(parents=True); hook.parent.mkdir(parents=True)
    effect.write_text(render_effect(country, [], sid, catalog), encoding='utf-8')
    hook.write_text(render_hook(country, sid, secrets.token_hex(16),activate_on_startup=True), encoding='utf-8')
    catalog_path = root / 'equipment-catalog.json'
    catalog_path.write_text(json.dumps(catalog, indent=2), encoding='utf-8')
    descriptor = f'name="Codex game-side commands {sid[:8]}"\npath="{(root / "mod").as_posix()}"\n'
    (root / 'CodexCommands.mod').write_text(descriptor, encoding='utf-8')
    (root / 'mod/descriptor.mod').write_text(f'name="Codex game-side commands {sid[:8]}"\n', encoding='utf-8')
    config = {'protocol': 2, 'mode': 'singleplayer_test', 'session_id': sid, 'country': country,
              'prepared_unix': time.time(), 'game_root': str(game), 'game_sha256': SUPPORTED_HASH,
              'documentation_sha256': docs, 'effect_path': str(effect), 'hook_path': str(hook),
              'catalog_path': str(catalog_path), 'catalog_sha256': sha(catalog_path),
              'log_path': str(Path(log_path).resolve()), 'state_path': str(root / 'ledger.json'),
              'process_identity': None}
    if content_binding is not None:config['content_binding']=content_binding
    (root / 'session.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
    return config


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--game-root', required=True); p.add_argument('--session-root', required=True)
    p.add_argument('--log-path', required=True); p.add_argument('--country', default='GER')
    args = p.parse_args()
    c = prepare(args.game_root, args.session_root, args.log_path, args.country)
    print(json.dumps({'session_id': c['session_id'], 'prepared': True, 'activated': False,
                      'game_verified': False, 'uses_mouse_or_keyboard': False}))


if __name__ == '__main__':
    main()
