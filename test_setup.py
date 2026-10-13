"""Setup fixtures: invented executable identity and mocked Windows process API."""
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import prepare_session as prep
import bind_session as binder
from activate_session import activate, deactivate


class Setup(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.game=self.root/'game';self.game.mkdir();(self.game/'hoi4.exe').write_bytes(b'simulated-executable')
        self.expected=hashlib.sha256(b'simulated-executable').hexdigest()
        docs=self.game/'documentation';docs.mkdir()
        for name,keys in prep.REQUIRED_DOCS.items():
            (docs/name).write_text('\n'.join('## '+k+'\n' for k in keys))
        (self.game/'common/units/equipment').mkdir(parents=True)
        (self.game/'common/technologies').mkdir(parents=True)
        (self.game/'common/units/equipment/infantry.txt').write_text('equipments = { infantry_equipment_0 = { type = infantry active = yes } }')
        (self.game/'common/technologies/infantry.txt').write_text('technologies = {}')
        self.session=self.root/'session';self.log=self.root/'game.log';self.user=self.root/'user'
        self.patches=[patch.object(prep,'SUPPORTED_HASH',self.expected),patch.object(binder,'SUPPORTED_HASH',self.expected)]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in self.patches:p.stop()
        self.temp.cleanup()
    def prepare(self):
        self.config=prep.prepare(self.game,self.session,self.log);self.config_file=self.session/'session.json'
        return self.config
    def identity(self):
        return {'pid':12,'created':int((time.time()+1+11644473600)*10000000),'executable':str(self.game/'hoi4.exe')}
    def ready(self):
        self.log.write_text(f"CODEX_COMMAND_SESSION|{self.config['session_id']}|READY|country=GER\n")
    def test_prepare_does_not_activate_or_touch_user_selection(self):
        c=self.prepare()
        self.assertIsNone(c['process_identity']);self.assertFalse(self.user.exists());self.assertFalse(self.log.exists())
        self.assertIn('|READY|',Path(c['hook_path']).read_text())
        self.assertEqual(binder.verify_sources(c)['equipment']['infantry_equipment_0']['factory_kind'],'military')
    def test_existing_session_is_not_overwritten(self):
        self.prepare();before=self.config_file.read_bytes()
        with self.assertRaisesRegex(RuntimeError,'already exists'):prep.prepare(self.game,self.session,self.log)
        self.assertEqual(before,self.config_file.read_bytes())
    def test_unsupported_build_creates_no_session(self):
        (self.game/'hoi4.exe').write_bytes(b'wrong-build')
        with self.assertRaisesRegex(RuntimeError,'Unsupported'):prep.prepare(self.game,self.session,self.log)
        self.assertFalse(self.session.exists())
    def test_binding_requires_exact_native_session_handshake(self):
        self.prepare();self.log.write_text('CODEX_COMMAND_SESSION|'+'a'*32+'|READY|country=GER')
        before=self.config_file.read_bytes()
        with patch.object(binder,'process_identity',return_value=self.identity()),self.assertRaisesRegex(RuntimeError,'acknowledgment'):
            binder.bind(self.config_file,12)
        self.assertEqual(before,self.config_file.read_bytes())
    def test_preexisting_game_process_is_rejected(self):
        self.prepare();self.ready();ident=self.identity();ident['created']=int((self.config['prepared_unix']-10+11644473600)*10000000)
        with patch.object(binder,'process_identity',return_value=ident),self.assertRaisesRegex(RuntimeError,'predates'):
            binder.bind(self.config_file,12)
    def test_process_binding_and_no_rebinding(self):
        self.prepare();self.ready()
        with patch.object(binder,'process_identity',return_value=self.identity()):
            self.assertEqual(binder.bind(self.config_file,12)['pid'],12)
        before=self.config_file.read_bytes()
        with self.assertRaisesRegex(RuntimeError,'already bound'):binder.bind(self.config_file,12)
        self.assertEqual(before,self.config_file.read_bytes())
    def test_catalog_source_change_rejects_binding_and_activation(self):
        self.prepare();self.ready()
        (self.game/'common/units/equipment/infantry.txt').write_text('equipments = {}')
        with self.assertRaisesRegex(RuntimeError,'sources changed'):binder.bind(self.config_file,12)
        with self.assertRaisesRegex(RuntimeError,'sources changed'):activate(self.config_file,self.user)
        self.assertFalse(self.user.exists())
    def test_activation_and_removal_preserve_other_mods_and_fields(self):
        self.prepare();self.user.mkdir();selection=self.user/'dlc_load.json'
        old={'enabled_mods':['mod/Existing.mod'],'disabled_dlcs':['42'],'custom':{'keep':True}}
        original=json.dumps(old).encode();selection.write_bytes(original)
        result=activate(self.config_file,self.user);entry=result['installed_mod_entry']
        self.assertEqual((self.session/'dlc_load.before.json').read_bytes(),original)
        current=json.loads(selection.read_text());current['enabled_mods'].append('mod/AddedLater.mod');selection.write_text(json.dumps(current))
        deactivate(self.config_file);after=json.loads(selection.read_text())
        self.assertEqual(after['enabled_mods'],['mod/Existing.mod','mod/AddedLater.mod'])
        self.assertEqual(after['custom'],old['custom']);self.assertEqual(after['disabled_dlcs'],old['disabled_dlcs'])
        self.assertNotIn(entry,after['enabled_mods'])
    def test_changed_descriptor_is_retained_on_removal(self):
        self.prepare();activate(self.config_file,self.user)
        record=json.loads((self.session/'activation.json').read_text());path=Path(record['descriptor'])
        path.write_text('changed by user')
        self.assertTrue(deactivate(self.config_file)['changed_descriptor_retained']);self.assertTrue(path.exists())
    def test_malformed_selection_is_not_overwritten(self):
        self.prepare();self.user.mkdir();selection=self.user/'dlc_load.json';selection.write_text('{bad JSON')
        before=selection.read_bytes()
        with self.assertRaises(ValueError):activate(self.config_file,self.user)
        self.assertEqual(before,selection.read_bytes());self.assertFalse((self.session/'activation.json').exists())


if __name__=='__main__':unittest.main()
