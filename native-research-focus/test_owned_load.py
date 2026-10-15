import hashlib,json,tempfile,unittest
from unittest.mock import patch
from activate_session import activate
from pathlib import Path
from owned_load import validate_owned_load,configure_owned_load
from direct_controller import render_hook
class OwnedLoadTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.user=self.root/'user';self.parent=self.root/'parent';(self.parent/'native').mkdir(parents=True);(self.user/'save games').mkdir(parents=True)
  self.sid='a'*32;self.rid='b'*32;self.name=f'mcp_{self.sid}_{self.rid}.hoi4';self.data=b'HOI4bin'+b'fixture'*200;self.digest=hashlib.sha256(self.data).hexdigest();self.file=self.user/'save games'/self.name;self.file.write_bytes(self.data)
  self.sf=self.parent/'session.json';self.sf.write_text(json.dumps({'session_id':self.sid,'country':'GER','mode':'singleplayer_test'}))
  descriptor=self.parent/'CodexCommands.mod';descriptor.write_text('name="Codex game-side commands aaaaaaaa"\npath="parent/mod"\n');(self.parent/'activation.json').write_text(json.dumps({'descriptor_sha256':hashlib.sha256(descriptor.read_text(encoding='utf-8').encode('utf-8')).hexdigest()}))
  n=self.parent/'native';(n/'selection-ledger.json').write_text(json.dumps({'armed':False}));(n/'time-ledger.json').write_text('{}')
  (n/f'time-receipt-{self.rid}.json').write_text(json.dumps({'session_id':self.sid,'request_id':self.rid,'stage':'save_file_observed','path':'save games/'+self.name}))
  (n/f'save-reconciled-{self.rid}.json').write_text(json.dumps({'verified':True,'request_id':self.rid,'file':{'sha256':self.digest}}))
 def tearDown(self):self.tmp.cleanup()
 def validate(self):return validate_owned_load(self.user,self.name,self.digest,self.sf)
 def test_exact_verified_owned_save_and_retained_requests(self):
  spec=self.validate();self.assertEqual(spec['parent_session_id'],self.sid);self.assertEqual(len(spec['retained_requests']),3)
 def test_windows_descriptor_newlines_match_activation_text_hash(self):
  p=self.parent/'CodexCommands.mod';p.write_bytes(p.read_text().replace('\n','\r\n').encode('utf-8'))
  self.assertEqual(self.validate()['required_mod_name'],'Codex game-side commands aaaaaaaa')
 def test_changed_parent_mod_identity_refused(self):
  (self.parent/'CodexCommands.mod').write_text('name="different fixture"\n')
  with self.assertRaisesRegex(RuntimeError,'descriptor changed'):self.validate()
 def test_changed_save_refused(self):
  self.file.write_bytes(b'HOI4binchanged')
  with self.assertRaises(RuntimeError):self.validate()
 def test_invalid_name_and_parent_refused(self):
  with self.assertRaises(ValueError):validate_owned_load(self.user,'../'+self.name,self.digest,self.sf)
  self.sf.write_text(json.dumps({'session_id':'c'*32,'country':'GER','mode':'singleplayer_test'}))
  with self.assertRaises(RuntimeError):self.validate()
 def test_unverified_and_armed_parent_refused(self):
  (self.parent/'native/selection-ledger.json').write_text('{"armed":true}')
  with self.assertRaises(RuntimeError):self.validate()
  (self.parent/'native/selection-ledger.json').write_text('{"armed":false}')
  p=self.parent/'native'/f'save-reconciled-{self.rid}.json';x=json.loads(p.read_text());x['verified']=False;p.write_text(json.dumps(x))
  with self.assertRaises(RuntimeError):self.validate()
 def test_load_bootstrap_changes_only_new_hook_and_metadata(self):
  spec=self.validate();new=self.root/'fresh';new.mkdir();(new/'mod').mkdir();(new/'CodexCommands.mod').write_text('name="fresh fixture"\npath="new/mod"\n');(new/'mod/descriptor.mod').write_text('name="fresh fixture"\n');hook=new/'hook.txt';sid='c'*32;original=render_hook('GER',sid,'d'*32,True);hook.write_text(original)
  sf=new/'session.json';sf.write_text(json.dumps({'session_id':sid,'country':'GER','hook_path':str(hook),'process_identity':None}));parent_before=self.sf.read_bytes();result=configure_owned_load(sf,spec)
  text=hook.read_text();self.assertEqual(text.count('set_country_flag = codex_mcp_session_'+sid),2);self.assertIn('NOT = { has_country_flag',text);self.assertEqual(self.sf.read_bytes(),parent_before);self.assertEqual(result['owned_load'],spec);self.assertIn('Codex game-side commands aaaaaaaa',(new/'CodexCommands.mod').read_text());self.assertEqual(result['session_id'],sid);self.assertIn(spec['required_mod_name'],(new/'mod/descriptor.mod').read_text())
  with patch('activate_session.verify_sources'):
   activate(sf,self.user)
  installed=self.user/'mod'/f'CodexCommands_{sid}.mod'
  self.assertIn('name="'+spec['required_mod_name']+'"',installed.read_text())
  self.assertIn('path="new/mod"',installed.read_text())
  with self.assertRaises(RuntimeError):configure_owned_load(sf,spec)
 def test_bound_session_refuses_reconfiguration(self):
  sf=self.root/'bound.json';sf.write_text(json.dumps({'session_id':'c'*32,'country':'GER','hook_path':str(self.sf),'process_identity':{'pid':1}}))
  with self.assertRaises(RuntimeError):configure_owned_load(sf,self.validate())
if __name__=='__main__':unittest.main()
