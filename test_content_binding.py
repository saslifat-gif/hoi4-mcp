import json,tempfile,unittest,zipfile
from pathlib import Path
from content_binding import capture,verify
class ContentBinding(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.game=self.root/'game';self.user=self.root/'user'
  self.game.mkdir();self.user.mkdir();(self.user/'mod').mkdir();(self.user/'dlc_load.json').write_text(json.dumps({'enabled_mods':[],'disabled_dlcs':[]}))
 def tearDown(self):self.tmp.cleanup()
 def test_unquoted_dlc_path_and_cosmetic_mod_are_audited(self):
  dlc=self.game/'dlc/test';dlc.mkdir(parents=True);(dlc/'test.dlc').write_text('path = dlc/test/')
  with zipfile.ZipFile(dlc/'pack.zip','w') as z:z.writestr('gfx/icon.dds',b'asset')
  self.assertTrue(capture(self.game,self.user)['active_overlay_verified'])
 def test_archive_definition_override_fails_closed(self):
  dlc=self.game/'dlc/test';dlc.mkdir(parents=True);(dlc/'test.dlc').write_text('path = dlc/test/')
  with zipfile.ZipFile(dlc/'pack.zip','w') as z:z.writestr('common/buildings/override.txt','x = {}')
  with self.assertRaisesRegex(RuntimeError,'overrides'):capture(self.game,self.user)
 def test_added_base_definition_invalidates_binding(self):
  cfg={'game_root':str(self.game),'content_binding':{'user_root':str(self.user),'owned_entry':'mod/owned.mod','snapshot':capture(self.game,self.user)}}
  p=self.game/'common/units/equipment/new.txt';p.parent.mkdir(parents=True);p.write_text('equipments = {}')
  with self.assertRaisesRegex(RuntimeError,'inventory changed'):verify(cfg)
 def test_unknown_selected_content_is_not_ignored(self):
  (self.user/'dlc_load.json').write_text(json.dumps({'enabled_mods':['mod/missing.mod'],'disabled_dlcs':[]}))
  with self.assertRaises(FileNotFoundError):capture(self.game,self.user)
 def test_only_exact_owned_mod_is_excluded(self):
  (self.user/'dlc_load.json').write_text(json.dumps({'enabled_mods':['mod/owned.mod'],'disabled_dlcs':[]}))
  self.assertEqual(capture(self.game,self.user,'mod/owned.mod')['enabled_mods'],[])
 def test_missing_dlc_container_is_not_verified(self):
  p=self.game/'dlc/test.dlc';p.parent.mkdir();p.write_text('path=dlc/missing')
  with self.assertRaisesRegex(RuntimeError,'Missing'):capture(self.game,self.user)
 def test_selected_dlc_change_invalidates_session(self):
  cfg={'game_root':str(self.game),'content_binding':{'user_root':str(self.user),'owned_entry':None,'snapshot':capture(self.game,self.user)}}
  (self.user/'dlc_load.json').write_text(json.dumps({'enabled_mods':[],'disabled_dlcs':['dlc/test']}))
  with self.assertRaisesRegex(RuntimeError,'Selected content'):verify(cfg)
 def test_replace_path_is_not_mistaken_for_cosmetic_content(self):
  mod=self.root/'modfiles';mod.mkdir();(self.user/'mod/test.mod').write_text('path="'+mod.as_posix()+'" replace_path="common/buildings"')
  (self.user/'dlc_load.json').write_text(json.dumps({'enabled_mods':['mod/test.mod'],'disabled_dlcs':[]}))
  with self.assertRaisesRegex(RuntimeError,'replace_path'):capture(self.game,self.user)
 def test_duplicate_content_path_is_rejected(self):
  (self.user/'mod/test.mod').write_text('path="first" path="second"')
  (self.user/'dlc_load.json').write_text(json.dumps({'enabled_mods':['mod/test.mod'],'disabled_dlcs':[]}))
  with self.assertRaisesRegex(ValueError,'Duplicate field: path'):capture(self.game,self.user)
if __name__=='__main__':unittest.main()
