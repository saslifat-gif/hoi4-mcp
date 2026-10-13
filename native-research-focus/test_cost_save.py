"""Invented plaintext/archive save fixtures; no live game or save mutation."""
import io,json,tempfile,unittest,zipfile
from pathlib import Path
from read_cost_save import read_save

VALID=b'HOI4txt\ndate=1936.02.01.01\ncountries={ GER={ production={ general_lines={ building={ amount=2 building={ location=64 template=arms_factory } } } } } }'
class SaveTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);self.save=self.root/'autosave.hoi4';self.save.write_bytes(VALID)
  self.session=self.root/'session.json';self.session.write_text(json.dumps({'prepared_unix':0}))
  recovery=self.root/'recovery';recovery.mkdir()
  (recovery/'manifest.json').write_text(json.dumps([{'path':str(self.save)}]))
 def test_native_queue_quantity(self):
  result=read_save(self.session)
  self.assertEqual(result['construction'][0]['amount'],'2')
  self.assertEqual(result['construction'][0]['building']['template'],'arms_factory')
 def test_pre_session_save_is_rejected(self):
  self.session.write_text(json.dumps({'prepared_unix':self.save.stat().st_mtime+10}))
  with self.assertRaisesRegex(ValueError,'predates'):read_save(self.session)
 def test_plaintext_and_country_boundaries(self):
  for data,message in [(b'HOI4bin','plaintext'),(b'HOI4txt\n','countries'),(VALID.replace(b'GER',b'FRA'),'Germany')]:
   with self.subTest(message=message):
    self.save.write_bytes(data)
    with self.assertRaisesRegex(ValueError,message):read_save(self.session)
 def test_ambiguous_archive_is_rejected(self):
  stream=io.BytesIO()
  with zipfile.ZipFile(stream,'w') as archive:
   archive.writestr('gamestate',VALID);archive.writestr('game_state',VALID)
  self.save.write_bytes(stream.getvalue())
  with self.assertRaisesRegex(ValueError,'gamestate'):read_save(self.session)
 def test_single_archive_gamestate_is_read(self):
  stream=io.BytesIO()
  with zipfile.ZipFile(stream,'w') as archive:archive.writestr('gamestate',VALID)
  self.save.write_bytes(stream.getvalue())
  self.assertEqual(read_save(self.session)['construction'][0]['amount'],'2')

if __name__=='__main__':unittest.main()
