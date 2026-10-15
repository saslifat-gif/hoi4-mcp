import tempfile,unittest
from pathlib import Path
from script_definitions import read_definitions

class GraphicsDefinitionsTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);(self.root/'interface').mkdir()
 def tearDown(self):self.tmp.cleanup()
 def source(self,name,text):(self.root/'interface'/name).write_text(text)
 def test_exact_sprite_keeps_texture_frames_and_duplicate_matches(self):
  self.source('icons.gfx','spriteTypes = { spriteType = { name = "GFX_steel" texturefile = "gfx/interface/steel.dds" noOfFrames = 4 } spriteType = { name = "GFX_steel" texturefile = "other.dds" } }')
  result=read_definitions(self.root,'graphics','GFX_steel');rows=result['definitions']
  self.assertEqual(len(rows),2);self.assertEqual(rows[0]['id'],'GFX_steel')
  self.assertEqual(rows[0]['definition']['children'][2]['value'],'4')
  self.assertEqual(rows[0]['script_path'],['spriteTypes','spriteType'])
  self.assertFalse(result['native_identity_verified']);self.assertFalse(result['active_overlay_verified'])
  self.assertEqual(read_definitions(self.root,'graphics','steel')['definitions'],[])
 def test_font_name_and_file_rules_are_retained_without_rendering_claims(self):
  self.source('fonts.gfx','bitmapfonts = { bitmapfont = { name = "hoi_20b" fontfiles = { "gfx/fonts/latin.fnt" "gfx/fonts/chinese.fnt" } } }')
  row=read_definitions(self.root,'graphics','hoi_20b')['definitions'][0]
  self.assertEqual(row['definition_type'],'bitmapfont')
  self.assertEqual([n['value'] for n in row['definition']['children'][1]['children']],['gfx/fonts/latin.fnt','gfx/fonts/chinese.fnt'])
  self.assertNotIn('texture_loaded_verified',row)
 def test_duplicate_name_fields_do_not_pick_a_winner(self):
  self.source('bad.gfx','spriteTypes = { spriteType = { name = "one" name = "two" } }')
  row=read_definitions(self.root,'graphics','one')['definitions'][0]
  self.assertIsNone(row['id']);self.assertEqual(row['name_literals'],['one','two'])
 def test_listing_omits_full_bodies_and_only_indexes_named_blocks(self):
  self.source('a.gfx','spriteTypes = { spriteType = { name = "icon" texturefile = "x.dds" } }')
  rows=read_definitions(self.root,'graphics')['definitions']
  self.assertEqual([r['id'] for r in rows],['icon']);self.assertNotIn('definition',rows[0])

if __name__=='__main__':unittest.main()
