import hashlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).parent),str(Path(__file__).parent.parent)]
import native_controller as nc
class NativeTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.native=self.root/'native';self.native.mkdir()
  self.ident={'pid':123,'created':456,'executable':'hoi4.exe'};self.sid='a'*32
  self.sf=self.root/'session.json';self.sf.write_text(json.dumps({'country':'GER','mode':'singleplayer_test','session_id':self.sid,'process_identity':self.ident}))
  self.original=nc.DLL_SHA;nc.DLL_SHA=hashlib.sha256(b'fixture').hexdigest();(self.native/'hoi4-native-selection.dll').write_bytes(b'fixture')
  self.obs={'pid':123,'session_id':self.sid,'country_code':'GER','selection_commands_enabled':True,'world':'0x1'};self.observation()
  self.c=nc.NativeController(self.sf,identity=lambda _:self.ident)
 def tearDown(self):nc.DLL_SHA=self.original;self.temp.cleanup()
 def observation(self):(self.native/'native-observation.json').write_text(json.dumps(self.obs))
 def submit(self,rid='b'*32):return self.c.submit(rid,'research','basic_machine_tools',1)
 def terminal(self,rid='b'*32,stage='selection_verified'):(self.native/f'receipt-{rid}.json').write_text(json.dumps({'session_id':self.sid,'request_id':rid,'stage':stage}))
 def test_decision_uses_existing_durable_duplicate_ledger(self):
  self.c.arm(True);self.c.submit('b'*32,'decision','anti_communist_raids',0)
  self.assertEqual((self.native/'request.txt').read_text(),self.sid+'|'+'b'*32+'|decision|anti_communist_raids|0')
  self.terminal(stage='decision_verified');before=(self.native/'request.txt').stat().st_mtime_ns
  self.assertEqual(self.c.submit('b'*32,'decision','anti_communist_raids',0)['stage'],'decision_verified')
  self.assertEqual((self.native/'request.txt').stat().st_mtime_ns,before)
  self.c.submit('c'*32,'decision','another_decision',0)
 def test_decision_rejects_target_or_slot_payload(self):
  for identifier,slot in [('decision:ENG',0),('decision',1),('decision|x',0)]:
   with self.assertRaises(ValueError):nc.selection_command('b'*32,'decision',identifier,slot)
 def test_group_creation_keeps_payload_and_duplicate_identity(self):
  self.c.arm(True);rid='b'*32
  self.c.create_army_group(rid,'51:10',['52:1','52:2'])
  payload=self.native/f'army-units-{rid}.txt'
  self.assertEqual(payload.read_text(),self.sid+'|'+rid+'|52:1,52:2')
  self.assertEqual((self.native/'request.txt').read_text(),self.sid+'|'+rid+'|armygroup|51:10|2')
  self.terminal(rid,stage='army_group_verified');payload.unlink()
  self.assertEqual(self.c.create_army_group(rid,'51:10',['52:1','52:2'])['stage'],'army_group_verified')
  self.assertFalse(payload.exists())
  with self.assertRaises(ValueError):self.c.create_army_group(rid,'51:10',['52:3'])
 def test_theater_payload_duplicate_and_changed_target(self):
  self.c.arm(True);rid='b'*32
  self.c.assign_theater(rid,['53:1','6000:2'])
  path=self.native/f'theater-groups-{rid}.txt'
  self.assertEqual(path.read_text(),self.sid+'|'+rid+'|53:1,6000:2')
  self.assertEqual((self.native/'request.txt').read_text(),self.sid+'|'+rid+'|theater|new|2')
  self.terminal(rid,'theater_verified');before=(self.native/'request.txt').read_bytes();path.unlink()
  self.assertEqual(self.c.assign_theater(rid,['53:1','6000:2'])['stage'],'theater_verified')
  self.assertFalse(path.exists());self.assertEqual((self.native/'request.txt').read_bytes(),before)
  with self.assertRaises(ValueError):self.c.assign_theater(rid,['53:1','6000:2'],'68:1')
  self.c.assign_theater('c'*32,['53:1'],'68:1')
 def test_theater_reservation_and_immutable_publication(self):
  self.c.arm(True);rid='b'*32;original=nc.atomic_text
  def fail(path,text):
   if path.name.startswith('theater-groups-'):raise PermissionError('fixture')
   original(path,text)
  with patch.object(nc,'atomic_text',side_effect=fail):
   with self.assertRaises(PermissionError):self.c.assign_theater(rid,['53:1'])
  self.assertNotIn(rid,self.c.load()['requests'])
  with self.assertRaises(ValueError):self.submit(rid)
  with self.assertRaises(ValueError):self.c.create_army_group(rid,'67:1',['51:1'])
  with self.assertRaises(ValueError):self.c.prepare_politics(rid,{})
  with self.assertRaises(ValueError):self.c.order_units(rid,'cancel',['51:1'])
  (self.native/f'theater-groups-{rid}.txt').write_text('changed')
  with self.assertRaisesRegex(RuntimeError,'payload changed'):self.c.assign_theater(rid,['53:1'])
 def test_theater_requires_reserved_payload_and_valid_unique_ids(self):
  self.c.arm(True)
  with self.assertRaisesRegex(RuntimeError,'Owned group payload'):self.c.submit('b'*32,'theater','new',1)
  for groups,target in [([],None),(['53:1','53:1'],None),(['053:1'],None),(['53:1'],'0:0')]:
   with self.assertRaises(ValueError):self.c.assign_theater('b'*32,groups,target)
 def test_group_creation_rejects_duplicate_and_missing_payload(self):
  self.c.arm(True)
  with self.assertRaises(ValueError):self.c.create_army_group('b'*32,'51:10',['52:1','52:1'])
  with self.assertRaisesRegex(RuntimeError,'Owned unit payload'):self.c.submit('b'*32,'armygroup','51:10',1)
 def test_group_payload_reserves_id_before_publication(self):
  self.c.arm(True);rid='b'*32
  d=self.c.load();d['army_group_payloads']={rid:{'theatre_id':'51:10','unit_ids':['52:1']}};self.c.save(d)
  with self.assertRaisesRegex(ValueError,'reserved'):self.c.submit(rid,'research','basic_machine_tools',1)
 def test_group_payload_write_failure_can_recover_before_publication(self):
  self.c.arm(True);rid='b'*32;original=nc.atomic_text
  def fail_payload(path,text):
   if path.name.startswith('army-units-'):raise PermissionError('fixture sharing failure')
   return original(path,text)
  with patch.object(nc,'atomic_text',side_effect=fail_payload):
   with self.assertRaises(PermissionError):self.c.create_army_group(rid,'51:10',['52:1'])
  self.assertIn(rid,self.c.load()['army_group_payloads'])
  self.assertNotIn(rid,self.c.load()['requests']);self.assertFalse((self.native/'request.txt').exists())
  self.c.create_army_group(rid,'51:10',['52:1'])
  self.assertIn(rid,self.c.load()['requests'])
 def test_group_existing_unpublished_payload_cannot_change(self):
  self.c.arm(True);rid='b'*32
  d=self.c.load();d['army_group_payloads']={rid:{'theatre_id':'51:10','unit_ids':['52:1']}};self.c.save(d)
  (self.native/f'army-units-{rid}.txt').write_text('tampered')
  with self.assertRaisesRegex(RuntimeError,'payload changed'):self.c.create_army_group(rid,'51:10',['52:1'])
  self.assertNotIn(rid,self.c.load()['requests'])
 def test_group_reservation_blocks_prepared_politics(self):
  rid='b'*32;d=self.c.load();d['army_group_payloads']={rid:{'theatre_id':'51:10','unit_ids':['52:1']}};self.c.save(d)
  with self.assertRaisesRegex(ValueError,'another command'):self.c.prepare_politics(rid,{})
 def test_group_cannot_reserve_military_child_id(self):
  self.c.arm(True);rid='b'*32;d=self.c.load()
  d['military_orders']={'c'*32:{'request_ids':[rid]}};self.c.save(d)
  with self.assertRaisesRegex(ValueError,'reserved'):self.c.create_army_group(rid,'51:10',['52:1'])
  self.assertNotIn(rid,self.c.load().get('army_group_payloads',{}))
 def test_queue_reconciliation_preserves_native_intent_and_deduplicates(self):
  rid='b'*32;self.c.arm(True);self.c.submit(rid,'queue','52:1',0);self.terminal(stage='execution_uncertain');self.c.arm(False)
  before={'country_tag_native':1,'native_tick':1,'conveyors':[]}
  after={'country_tag_native':1,'native_tick':2,'conveyors':[{'conveyor_id':'64:1','template_id':'52:1','lines':[{'line_id':'63:1','current_entry':{'manpower':1}}]}],'country_to_manager_binding_verified':True,'process_writes':False}
  units={'units':[{'unit_id':'51:1'}]}
  report={'session_id':self.sid,'operation':'queue','payload':{'request_id':rid,'template_id':'52:1'},'before':before,'units_before':units}
  (self.native/f'deployment-execution-{rid}.json').write_text(json.dumps(report));original=(self.native/f'receipt-{rid}.json').read_bytes()
  with patch('time_controller.TimeController.status',return_value={'paused':True}),patch.object(self.c,'deployment_snapshot',return_value=after),patch.object(self.c,'military_snapshot',return_value=units):
   result=self.c.reconcile_deployment(rid);self.assertEqual(result['stage'],'deployment_observed')
   self.assertEqual(self.c.reconcile_deployment(rid),result);self.assertEqual(self.c.receipt(rid),result)
  self.assertEqual((self.native/f'receipt-{rid}.json').read_bytes(),original)
  self.c.arm(True);self.c.submit('c'*32,'queue','52:2',0)
 def test_queue_reconcile_rejects_changed_native_receipt(self):
  rid='b'*32;self.c.arm(True);self.c.submit(rid,'queue','52:1',0);self.terminal(stage='execution_uncertain');self.c.arm(False)
  with patch('time_controller.TimeController.status',return_value={'paused':True}):
   with self.assertRaises(FileNotFoundError):self.c.reconcile_deployment(rid)
  self.assertFalse((self.native/f'deployment-observation-{rid}.json').exists())
 def test_deployment_uses_durable_payloads_and_terminal_receipts(self):
  self.c.arm(True)
  for n,(kind,identifier,slot) in enumerate([('queue','52:1',0),('deployloc','71:1',123),('deploy','73:1',0)]):
   rid=f'{n+1:032x}';self.c.submit(rid,kind,identifier,slot)
   self.assertEqual((self.native/'request.txt').read_text(),f'{self.sid}|{rid}|{kind}|{identifier}|{slot}')
   self.terminal(rid,'deployment_verified');before=(self.native/'request.txt').read_bytes()
   self.assertEqual(self.c.submit(rid,kind,identifier,slot)['stage'],'deployment_verified')
   self.assertEqual((self.native/'request.txt').read_bytes(),before)
   with self.assertRaises(ValueError):self.c.submit(rid,kind,identifier,slot+1)
 def test_deployment_rejects_invalid_identity_and_location(self):
  for kind,identifier,slot in [('queue','52:0',0),('queue','52:01',0),('queue','52:1',1),('deployloc','71:1',0),('deploy','73:1',1),('deployloc','71:1',True)]:
   with self.assertRaises(ValueError):nc.selection_command('b'*32,kind,identifier,slot)
 def test_deployment_uncertainty_blocks_new_native_actions(self):
  self.c.arm(True);self.c.submit('b'*32,'queue','52:1',0);self.terminal(stage='execution_uncertain')
  with self.assertRaisesRegex(RuntimeError,'unresolved'):self.c.submit('c'*32,'queue','52:2',0)
 def test_trade_native_payload_and_duplicate(self):
  self.c.arm(True);rid='b'*32
  self.c.submit(rid,'trade','SOV:steel',1)
  self.assertEqual((self.native/'request.txt').read_text(),self.sid+'|'+rid+'|trade|SOV:steel|1')
  self.terminal(rid,stage='trade_verified');before=(self.native/'request.txt').stat().st_mtime_ns
  self.assertEqual(self.c.submit(rid,'trade','SOV:steel',1)['stage'],'trade_verified')
  self.assertEqual((self.native/'request.txt').stat().st_mtime_ns,before)
  for identifier,count in [('sov:steel',1),('SOV:steel',0),('SOV:steel',True),('SOV:steel',1001),('SOV:steel:oil',1)]:
   with self.assertRaises(ValueError):nc.selection_command('c'*32,'trade',identifier,count)
  with self.assertRaisesRegex(ValueError,'different payload'):self.c.submit(rid,'trade','SOV:oil',1)
  self.assertEqual(self.c.submit('c'*32,'trade','SOV:steel',2)['stage'],'pending')
 def test_disarmed(self):
  with self.assertRaises(RuntimeError):self.submit()
 def test_supported_country_binding_and_attack_payload(self):
  self.c.config['country']='ITA';self.obs['country_code']='ITA';self.observation();self.c.arm(True)
  self.c.submit('b'*32,'attack','6000:7',123)
  self.assertEqual((self.native/'request.txt').read_text(),self.sid+'|'+'b'*32+'|attack|6000:7|123')
  self.terminal(stage='military_verified');before=(self.native/'request.txt').read_bytes()
  self.c.submit('b'*32,'attack','6000:7',123);self.assertEqual((self.native/'request.txt').read_bytes(),before)
  self.c.submit('c'*32,'combatstop','6000:7',0)
  self.assertEqual((self.native/'request.txt').read_text(),self.sid+'|'+'c'*32+'|combatstop|6000:7|0')
  with self.assertRaises(ValueError):nc.selection_command('d'*32,'combatstop','6000:7',1)
  self.obs['country_code']='GER';self.observation()
  with self.assertRaisesRegex(RuntimeError,'country binding'):self.c.check()
 def test_submit_and_dedup(self):
  self.c.arm(True);self.submit();p=self.native/'request.txt';before=p.stat().st_mtime_ns
  self.submit();self.assertEqual(p.stat().st_mtime_ns,before)
 def test_payload_reuse(self):
  self.c.arm(True);self.submit()
  with self.assertRaises(ValueError):self.c.submit('b'*32,'research','improved_machine_tools',1)
 def test_pending_blocks(self):
  self.c.arm(True);self.submit()
  with self.assertRaises(RuntimeError):self.submit('c'*32)
 def test_uncertain_blocks(self):
  self.c.arm(True);self.submit();self.terminal(stage='execution_uncertain')
  with self.assertRaises(RuntimeError):self.submit('c'*32)
 def test_disarm_removes_publication(self):
  self.c.arm(True);self.submit();self.c.arm(False)
  self.assertFalse((self.native/'request.txt').exists());self.assertEqual(self.c.receipt('b'*32)['stage'],'pending')
 def test_disarm_removes_pending_time_publication_and_retains_ledger(self):
  self.c.arm(True)
  path=self.native/'time-request.txt';path.write_text('pending pause')
  ledger=self.native/'time-ledger.json';ledger.write_text('{"requests":{"existing":"pending"}}')
  before=ledger.read_bytes();self.c.arm(False)
  self.assertFalse(path.exists());self.assertEqual(ledger.read_bytes(),before)
 def test_probe_cannot_overwrite_selection_handshake(self):
  import re
  source=Path(__file__).parent
  def target(name):
   match=re.search(r'write_atomic\(L"([^"]*observation\.json)",out\)',(source/name).read_text())
   self.assertIsNotNone(match)
   return self.native/match.group(1)
  authoritative=target('native_selection.c');probe=target('native_bridge.c')
  # Reproduce the observable gap between the two native publishers each day.
  authoritative.write_text(json.dumps(self.obs))
  probe.write_text(json.dumps(dict(self.obs,selection_commands_enabled=False)))
  self.assertTrue(self.c.status()['native_callback']['selection_commands_enabled'])
 def test_world_change(self):
  self.c.arm(True);self.submit();self.terminal();self.obs['world']='0x2';self.observation()
  with self.assertRaises(RuntimeError):self.submit('c'*32)
 def test_process_change(self):
  self.c.identity=lambda _:{'pid':123,'created':999}
  with self.assertRaises(RuntimeError):self.c.status()
 def test_backend_error(self):
  (self.native/'native-error.json').write_text('{}')
  with self.assertRaises(RuntimeError):self.c.arm(True)
 def test_cancel_requires_canonical_unit_id(self):
  for value in ('0:1','51:0','051:1','51:01','4294967296:1','51:4294967296','51:1|focus'):
   with self.assertRaises(ValueError):self.c.submit('b'*32,'cancel',value,0)
 def test_cancel_shares_idempotent_ledger_and_publication(self):
  self.c.arm(True);self.c.submit('b'*32,'cancel','51:1',0)
  path=self.native/'request.txt';before=path.stat().st_mtime_ns
  self.assertEqual(path.read_text(),self.sid+'|'+'b'*32+'|cancel|51:1|0')
  self.c.submit('b'*32,'cancel','51:1',0);self.assertEqual(path.stat().st_mtime_ns,before)
  with self.assertRaises(ValueError):self.c.submit('b'*32,'cancel','51:2',0)
 def test_verified_military_command_allows_next_request(self):
  self.c.arm(True);self.c.submit('b'*32,'cancel','51:1',0);self.terminal(stage='military_verified')
  self.submit('c'*32)
 def test_move_validates_destination_and_native_id(self):
  for value in (0,-1,True,0x80000000):
   with self.assertRaises(ValueError):self.c.submit('b'*32,'move','51:1',value)
  with self.assertRaises(ValueError):self.c.submit('b'*32,'move','051:1',10)
 def test_move_payload_is_immutable(self):
  self.c.arm(True);self.c.submit('b'*32,'move','51:1',10)
  self.assertEqual((self.c.native/'request.txt').read_text(),self.sid+'|'+'b'*32+'|move|51:1|10')
  self.c.submit('b'*32,'move','51:1',10)
  with self.assertRaises(ValueError):self.c.submit('b'*32,'move','51:1',11)
 def test_cancel_cannot_use_research_slot(self):
  with self.assertRaises(ValueError):self.c.submit('b'*32,'cancel','51:1',1)
 def test_invalid_requests(self):
  for rid,kind,id,slot in [('bad','research','basic_machine_tools',1),('b'*32,'research','../bad',1),('b'*32,'research','x',True),('b'*32,'research','x',17),('b'*32,'focus','x',1)]:
   with self.assertRaises(ValueError):self.c.submit(rid,kind,id,slot)
 def test_law_validates_wire_payload_and_preserves_idempotency(self):
  for identifier in ('free_trade',':free_trade','trade_laws:','trade:laws:free','../laws:free','a'*150+':free_trade'):
   with self.assertRaises(ValueError):self.c.submit('b'*32,'law',identifier)
  with self.assertRaises(ValueError):self.c.submit('b'*32,'law','trade_laws:free_trade',1)
  self.c.arm(True);self.c.submit('b'*32,'law','trade_laws:free_trade')
  p=self.native/'request.txt';before=p.stat().st_mtime_ns
  self.assertEqual(p.read_text(),self.sid+'|'+'b'*32+'|law|trade_laws:free_trade|0')
  self.c.submit('b'*32,'law','trade_laws:free_trade');self.assertEqual(p.stat().st_mtime_ns,before)
  with self.assertRaises(ValueError):self.c.submit('b'*32,'law','trade_laws:limited_exports')
  self.terminal(stage='law_verified');self.submit('c'*32)
 def test_uncertain_law_payment_blocks_further_actions(self):
  self.c.arm(True);self.c.submit('b'*32,'law','trade_laws:free_trade');self.terminal(stage='execution_uncertain')
  with self.assertRaisesRegex(RuntimeError,'unresolved'):self.submit('c'*32)
 def test_law_receipt_controls_batch_and_snapshot_publication(self):
  self.check_politics_receipt_gates('law','trade_laws:free_trade','law_verified')
 def check_politics_receipt_gates(self,kind,identifier,verified):
  from unittest.mock import patch
  self.c.arm(True);self.c.submit('b'*32,kind,identifier)
  self.c.military_snapshot=lambda:{'units':[{'unit_id':'51:1'}]}
  catalog=self.root/'catalog.json';catalog.write_text(json.dumps({'source_hashes':{},'choices_dll_sha256':hashlib.sha256(b'choices').hexdigest()}))
  (self.native/'hoi4-native-choices.dll').write_bytes(b'choices')
  self.c.config.update(peacetime_catalog_path=str(catalog),peacetime_catalog_sha256=hashlib.sha256(catalog.read_bytes()).hexdigest(),game_root=str(self.root),effect_path='effect',log_path='log',state_path='state',hook_path='hook')
  with patch('bind_session.verify_sources',return_value={}),patch('direct_controller.DirectController') as controller:
   core=controller.return_value;core.state={'commands':{}};core.submit.return_value={'status':'delivery_uncertain'}
   self.terminal(stage='execution_uncertain')
   with self.assertRaisesRegex(RuntimeError,'unresolved'):self.c.order_units('c'*32,'cancel',['51:1'])
   with self.assertRaisesRegex(RuntimeError,'pending gameplay'):self.c.peacetime_snapshot('d'*32)
   controller.assert_not_called()
   self.terminal(stage=verified)
   self.assertEqual(self.c.peacetime_snapshot('d'*32)['status'],'delivery_uncertain')
   self.assertEqual(self.c.order_units('c'*32,'cancel',['51:1'])['stage'],'pending')
 def test_advisor_payload_and_receipt_preserve_idempotency(self):
  for identifier in ('ernst_udet',':ernst_udet','GER_ernst_udet:','a:b:c','../GER:role','GER:role|bad','a'*150+':ernst_udet'):
   with self.assertRaises(ValueError):self.c.submit('b'*32,'advisor',identifier)
  with self.assertRaises(ValueError):self.c.submit('b'*32,'advisor','GER_ernst_udet:ernst_udet',1)
  self.c.arm(True);self.c.submit('b'*32,'advisor','GER_ernst_udet:ernst_udet')
  p=self.native/'request.txt';before=p.stat().st_mtime_ns
  self.assertEqual(p.read_text(),self.sid+'|'+'b'*32+'|advisor|GER_ernst_udet:ernst_udet|0')
  self.c.submit('b'*32,'advisor','GER_ernst_udet:ernst_udet');self.assertEqual(p.stat().st_mtime_ns,before)
  with self.assertRaises(ValueError):self.c.submit('b'*32,'advisor','GER_ernst_udet:another_role')
  self.terminal(stage='execution_uncertain')
  with self.assertRaisesRegex(RuntimeError,'unresolved'):self.submit('c'*32)
  self.terminal(stage='advisor_verified');self.c.submit('c'*32,'advisor','GER_test:long_role-name')
 def test_advisor_receipt_controls_batch_and_snapshot_publication(self):
  self.check_politics_receipt_gates('advisor','GER_ernst_udet:ernst_udet','advisor_verified')
 def test_exclusive_publication(self):
  (self.native/'selection.lock').write_text('')
  with self.assertRaises(FileExistsError):self.c.arm(True)
 def test_changed_dll(self):
  (self.native/'hoi4-native-selection.dll').write_bytes(b'changed')
  with self.assertRaises(RuntimeError):self.c.status()
if __name__=='__main__':unittest.main()
