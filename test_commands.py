"""Offline regression fixtures. No live HOI4 execution is represented here."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import direct_controller as dc
from command_catalog import build_catalog, equipment_guard
from script_parser import parse_script

SID='b'*32; CID='a'*32; NEXT='c'*32
CAT={'equipment':{'infantry_equipment_1':{'factory_kind':'military','base_active':False,
                                        'unlock_technologies_any':['infantry_weapons']}}}


class Commands(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.effect=self.root/'effect.txt';self.hook=self.root/'hook.txt';self.log=self.root/'game.log'
        self.effect.write_text(dc.render_effect('GER',[],SID,CAT))
        self.hook.write_text(dc.render_hook('GER',SID,NEXT))
        self.log.write_text(f'CODEX_COMMAND_SESSION|{SID}|READY|country=GER\n')
        self.c=self.controller();self.c.arm(True)
    def tearDown(self):self.temp.cleanup()
    def controller(self):
        return dc.DirectController(self.effect,self.log,self.root/'ledger.json',hook_path=self.hook,session_id=SID,catalog=CAT)
    def compile(self,command):return dc.compile_command(CID,'GER',command,SID,CAT)
    def ack(self,cid=CID,sid=SID,kind='construct',status='ACK',suffix='stage=effect_ran'):
        with self.log.open('a') as f:
            f.write(f'[12:00:00][1936.01.02.24] CODEX_COMMAND|{sid}|{cid}|{status}|kind={kind}|{suffix}\n')
    def construct(self):return {'kind':'construct','state_id':64,'building':'arms_factory','levels':1}
    def test_queued_is_not_success(self):
        r=self.c.submit(self.construct(),CID)
        self.assertEqual(r['status'],'queued');self.assertFalse(r['engine_acknowledged'])
        self.assertFalse(r['gameplay_outcome_verified'])
        self.assertEqual(self.c.receipt(CID)['status'],'pending')
    def test_stale_bridge_preserves_another_readers_snapshot(self):
        reader=self.controller()
        reader.submit({'kind':'snapshot'},NEXT)
        self.ack(cid=NEXT,kind='snapshot')
        self.c.submit(self.construct(),CID)
        ledger=json.loads((self.root/'ledger.json').read_text())
        self.assertEqual([cid for cid,_ in ledger['commands']],[NEXT,CID])
        self.assertEqual(ledger['receipts'][NEXT]['status'],'acknowledged')
        self.assertEqual(self.c.receipt(NEXT)['status'],'acknowledged')
    def test_another_ledger_writer_blocks_publication(self):
        before=(self.effect.read_bytes(),self.hook.read_bytes(),(self.root/'ledger.json').read_bytes())
        lock=self.root/'ledger.lock';lock.write_text('owned by another writer')
        with self.assertRaises(FileExistsError):self.c.submit(self.construct(),CID)
        self.assertEqual(before,(self.effect.read_bytes(),self.hook.read_bytes(),(self.root/'ledger.json').read_bytes()))
        lock.unlink()
        self.assertEqual(self.c.submit(self.construct(),CID)['status'],'queued')
    def test_construction_cost_time_and_ownership_guards(self):
        text=self.compile(self.construct())
        self.assertIn('instant_build = no',text);self.assertIn('is_owned_and_controlled_by = GER',text)
        self.assertIn('free_building_slots',text);parse_script(text)
    def test_dockyard_guard_matches_coastal_availability(self):
        dockyard=dict(self.construct(),building='dockyard')
        text=self.compile(dockyard)
        self.assertIn('is_coastal = yes',text)
        self.assertNotIn('is_coastal = yes',self.compile(self.construct()))
        parse_script(text)
    def test_military_factory_dmz_restriction_matches_available_choices(self):
        from peacetime_script import render_frame
        text=self.compile(self.construct())
        self.assertIn('is_demilitarized_zone = no',text)
        for building in ('industrial_complex','dockyard'):
            self.assertNotIn('is_demilitarized_zone',self.compile(dict(self.construct(),building=building)))
        frame=render_frame(SID,CID,{'resources':['steel'],'state_is_coastal_supported':True},CAT)
        self.assertEqual(frame.count('is_demilitarized_zone = no'),1)
        parse_script(frame)
    def test_new_multilevel_construction_is_rejected_without_publication(self):
        before=(self.effect.read_bytes(),self.hook.read_bytes())
        with self.assertRaisesRegex(ValueError,'one level per request'):
            self.c.submit(dict(self.construct(),levels=2),CID)
        self.assertEqual(before,(self.effect.read_bytes(),self.hook.read_bytes()))
        self.assertNotIn(CID,dict(self.c.state['commands']))
    def test_legacy_multilevel_receipt_can_be_reconciled(self):
        old=dict(self.construct(),levels=2)
        self.c.state['commands'].append([CID,old]);self.c.state['publication'][CID]='published';self.c._save();self.ack()
        self.assertEqual(self.c.submit(old,CID)['status'],'acknowledged')
    def test_choices_only_offer_one_level_even_with_unqueued_free_slots(self):
        from peacetime_script import render_frame
        frame=render_frame(SID,CID,{'resources':['steel']},CAT)
        self.assertIn('max_levels=1',frame)
        self.assertNotIn('max_levels=2',frame)
    def test_construction_uses_engine_eligibility_for_commands_and_choices(self):
        from peacetime_script import render_frame
        frame=render_frame(SID,CID,{'resources':['steel'],'state_is_coastal_supported':True},CAT)
        for building in ('industrial_complex','arms_factory','dockyard'):
            trigger='can_construct_building = '+building
            self.assertIn(trigger,self.compile(dict(self.construct(),building=building)))
            self.assertEqual(frame.count(trigger),1)
        parse_script(frame)
    def test_production_guards_unlock_and_available_factories_without_grants(self):
        text=self.compile({'kind':'produce','equipment':'infantry_equipment_1','factories':3})
        self.assertIn('num_of_available_military_factories > 2',text)
        self.assertIn('has_tech = infantry_weapons',text);self.assertIn('requested_factories = 3',text)
        for cheat in ('add_equipment_to_stockpile','set_technology','progress =','efficiency ='):
            self.assertNotIn(cheat,text)
        parse_script(text)
    def test_raw_input_cheats_and_script_injection_are_rejected_without_publication(self):
        before=self.effect.read_bytes()
        for command in ({'kind':'keys','keys':['space']},{'kind':'click','x':0.5,'y':0.5},
                        {'kind':'complete_national_focus','focus':'GER_rhineland'},
                        {'kind':'construct','state_id':64,'building':'arms_factory } log = bad','levels':1},
                        {'kind':'produce','equipment':'infantry_equipment_1 } bad = yes','factories':1},
                        {'kind':'construct','state_id':True,'building':'arms_factory','levels':1},
                        {'kind':'snapshot','extra':'anything'}):
            with self.subTest(command=command),self.assertRaises(ValueError):self.c.submit(command,CID)
        self.assertEqual(self.c.state['commands'],[]);self.assertEqual(before,self.effect.read_bytes())
    def test_mutations_are_disarmed_after_restart(self):
        self.c.submit(self.construct(),CID);self.ack()
        c=self.controller();self.assertFalse(c.armed)
        with self.assertRaisesRegex(RuntimeError,'disarmed'):c.submit(self.construct(),NEXT)
    def test_startup_must_be_acknowledged_for_exact_session_and_country(self):
        self.log.write_text(f'CODEX_COMMAND_SESSION|{NEXT}|READY|country=GER\n')
        c=self.controller()
        with self.assertRaisesRegex(RuntimeError,'startup'):c.arm(True)
        with self.assertRaisesRegex(RuntimeError,'startup'):c.submit({'kind':'snapshot'},CID)
    def test_idempotent_resubmission_does_not_republish(self):
        command=self.construct();self.c.submit(command,CID)
        effect=self.effect.read_bytes();hook=self.hook.read_bytes()
        self.assertEqual(self.c.submit(command,CID)['status'],'pending')
        self.assertEqual(self.effect.read_bytes(),effect);self.assertEqual(self.hook.read_bytes(),hook)
        self.assertEqual(len(self.c.state['commands']),1)
    def test_id_reuse_with_different_payload_is_rejected(self):
        self.c.submit(self.construct(),CID)
        with self.assertRaisesRegex(ValueError,'different command'):self.c.submit({'kind':'snapshot'},CID)
    def test_different_request_blocked_while_delivery_unresolved(self):
        self.c.submit(self.construct(),CID)
        with self.assertRaisesRegex(RuntimeError,'unresolved'):self.c.submit(self.construct(),NEXT)
    def test_engine_ack_is_not_outcome_verification(self):
        self.c.submit(self.construct(),CID);self.ack()
        r=self.c.receipt(CID)
        self.assertEqual(r['status'],'acknowledged');self.assertTrue(r['engine_acknowledged'])
        self.assertFalse(r['gameplay_outcome_verified']);self.assertEqual(r['game_date'],'1936.01.02.24')
    def test_old_session_unknown_id_or_wrong_command_receipts_are_ignored(self):
        self.c.submit(self.construct(),CID)
        self.ack(sid=NEXT);self.ack(cid=NEXT);self.ack(kind='produce')
        self.assertEqual(self.c.receipt(CID)['status'],'pending')
    def test_ack_without_effect_stage_is_ignored(self):
        self.c.submit(self.construct(),CID);self.ack(suffix='political_power=20')
        self.assertEqual(self.c.receipt(CID)['status'],'pending')
    def test_rejection_and_conflicting_receipts_are_observable(self):
        self.c.submit(self.construct(),CID);self.ack(status='REJECT',suffix='reason=native_guard_failed')
        self.assertEqual(self.c.receipt(CID)['status'],'rejected')
        self.ack()
        with self.assertRaisesRegex(RuntimeError,'Conflicting'):self.c.receipt(CID)
    def test_read_calls_do_not_refresh_game_mod_files(self):
        self.c.submit(self.construct(),CID);before=(self.effect.read_bytes(),self.hook.read_bytes())
        self.c.status();self.c.receipt(CID)
        self.assertEqual(before,(self.effect.read_bytes(),self.hook.read_bytes()))
    def test_explicit_delivery_preserves_id_and_done_flag(self):
        self.c.submit(self.construct(),CID);before=self.hook.read_bytes()
        self.c.deliver(CID)
        self.assertNotEqual(self.hook.read_bytes(),before)
        self.assertIn('codex_mcp_done_'+SID+'_'+CID,self.effect.read_text())
        self.assertEqual(len(self.c.state['commands']),1)
    def test_publication_failure_retains_id_and_disarms(self):
        original=dc.atomic_text
        def fail_hook(path,text):
            if path==self.hook:raise OSError('fixture publication failure')
            return original(path,text)
        with patch.object(dc,'atomic_text',side_effect=fail_hook):r=self.c.submit(self.construct(),CID)
        self.assertEqual(r['status'],'delivery_uncertain');self.assertFalse(self.c.armed)
        self.assertEqual(r['publication'],'not_published')
        self.assertEqual(self.effect.read_text(),dc.render_effect('GER',[],SID,CAT))
        c=self.controller();c.arm(True);c.deliver(CID)
        self.assertEqual(len(c.state['commands']),1)
    def test_known_ack_prevents_explicit_republication(self):
        self.c.submit(self.construct(),CID);self.ack();self.c.receipt(CID)
        before=(self.effect.read_bytes(),self.hook.read_bytes());self.c.deliver(CID)
        self.assertEqual(before,(self.effect.read_bytes(),self.hook.read_bytes()))
    def test_source_caller_objects_cannot_mutate_a_persisted_request(self):
        command=self.construct();self.c.submit(command,CID);command['levels']=5
        self.assertEqual(self.c.state['commands'][0][1]['levels'],1)
    def test_wrong_session_ledger_is_rejected_without_reset(self):
        self.c.submit(self.construct(),CID);path=self.root/'ledger.json';state=json.loads(path.read_text())
        state['session_id']=NEXT;path.write_text(json.dumps(state));before=path.read_bytes()
        with self.assertRaisesRegex(RuntimeError,'another session'):self.controller()
        self.assertEqual(before,path.read_bytes())
    def test_process_change_rejects_before_any_publication(self):
        def stopped():raise RuntimeError('fixture process stopped')
        self.c.process_guard=stopped;before=self.effect.read_bytes()
        with self.assertRaisesRegex(RuntimeError,'stopped'):self.c.submit(self.construct(),CID)
        self.assertEqual(self.effect.read_bytes(),before);self.assertEqual(self.c.state['commands'],[])
    def test_complete_generated_mod_is_strictly_parseable_and_human_session_gated(self):
        self.c.submit(self.construct(),CID)
        parse_script(self.hook.read_text());parse_script(self.effect.read_text())
        self.assertIn('is_ai = no',self.effect.read_text());self.assertIn('has_country_flag = codex_mcp_session_'+SID,self.effect.read_text())
    def test_nonfinite_and_duplicate_native_values_are_rejected(self):
        for value in ('political_power=nan','political_power=inf','kind=construct|kind=produce'):
            self.assertIsNone(dc.parse_receipt(f'CODEX_COMMAND|{SID}|{CID}|ACK|{value}'))
    def test_new_campaign_invalidates_old_requests_even_with_same_process(self):
        self.c.submit(self.construct(),CID)
        with self.log.open('a') as f:f.write(f'CODEX_COMMAND_SESSION|{SID}|INVALIDATED|country=GER\n')
        status=self.c.status()
        self.assertTrue(status['campaign_invalidated']);self.assertFalse(status['armed'])
        self.assertFalse(status['startup_acknowledged'])
        with self.assertRaisesRegex(RuntimeError,'startup'):self.c.arm(True)
        self.assertIn('clr_country_flag = codex_mcp_session_'+SID,self.hook.read_text())
    def test_daily_hook_embeds_commands_without_cached_effect_reference(self):
        self.c.submit(self.construct(),CID)
        hook=self.hook.read_text()
        self.assertIn('on_daily_GER = { effect = { GER = {',hook)
        self.assertIn('add_building_construction',hook)
        self.assertIn('CODEX_COMMAND|'+SID+'|'+CID+'|ACK',hook)
        self.assertNotIn(dc.FUNCTION+SID+' = yes',hook)
        self.assertIn('codex_mcp_done_'+SID+'_'+CID,hook)
        parse_script(hook)
    def test_single_hook_publication_removes_startup_activation(self):
        events=[];original=dc.atomic_text
        def record(path,text):events.append((path,text));return original(path,text)
        with patch.object(dc,'atomic_text',side_effect=record):self.c.submit(self.construct(),CID)
        hook_i=next(i for i,(p,_) in enumerate(events) if p==self.hook)
        effect_i=next(i for i,(p,_) in enumerate(events) if p==self.effect)
        self.assertLess(hook_i,effect_i)
        self.assertIn('INVALIDATED',events[hook_i][1]);self.assertNotIn('|READY|',events[hook_i][1])
        self.assertIn('add_building_construction',events[hook_i][1])
        self.assertEqual(sum(p==self.hook for p,_ in events),1)


class Catalog(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        (self.root/'common/units/equipment').mkdir(parents=True)
        (self.root/'common/technologies').mkdir(parents=True)
        self.e=self.root/'common/units/equipment/infantry.txt';self.t=self.root/'common/technologies/infantry.txt'
        self.e.write_text('equipments = { infantry = { is_archetype = yes type = infantry } infantry_equipment_0 = { parent = infantry active = yes } infantry_equipment_1 = { parent = infantry active = no } unknown_1 = { type = unknown active = yes } }')
        self.t.write_text('technologies = { infantry_weapons = { enable_equipments = { infantry_equipment_1 } } }')
    def tearDown(self):self.temp.cleanup()
    def test_inherited_land_type_and_unlock_provenance(self):
        c=build_catalog(self.root)
        self.assertEqual(set(c['equipment']),{'infantry_equipment_0','infantry_equipment_1'})
        self.assertEqual(c['equipment']['infantry_equipment_1']['unlock_technologies_any'],['infantry_weapons'])
        self.assertFalse(c['active_overlay_verified']);self.assertEqual(len(c['source_hashes']),2)
    def test_modular_and_conditional_equipment_never_bypass_unresolved_rules(self):
        self.e.write_text('equipments = { infantry = { is_archetype = yes type = infantry } safe = { archetype = infantry active = yes } restricted = { archetype = infantry active = yes can_be_produced = { always = no } } modular = { archetype = infantry active = yes module_slots = { slot = { required = yes } } } }')
        c=build_catalog(self.root)
        self.assertEqual(set(c['equipment']),{'safe'})
        self.assertEqual(set(c['excluded_equipment']),{'restricted','modular'})
    def test_inherited_production_conditions_remain_fail_closed(self):
        self.e.write_text('equipments = { restricted_base = { is_archetype = yes type = armor can_be_produced = { has_dlc = example } } child = { archetype = restricted_base active = yes } }')
        self.assertEqual(build_catalog(self.root)['equipment'],{})
    def test_unknown_or_malformed_allowlist_cannot_enable_production(self):
        with self.assertRaises(ValueError):equipment_guard(CAT,'unknown_equipment',1)
        bad=json.loads(json.dumps(CAT));bad['equipment']['infantry_equipment_1']['base_active']='no'
        with self.assertRaises(ValueError):equipment_guard(bad,'infantry_equipment_1',1)
    def test_duplicate_equipment_definitions_remain_ambiguous(self):
        (self.e.parent/'duplicate.txt').write_text(self.e.read_text())
        with self.assertRaisesRegex(ValueError,'Ambiguous'):build_catalog(self.root)
    def test_parent_cycles_are_rejected(self):
        self.e.write_text('equipments = { first = { parent = second active = yes } second = { parent = first active = yes } }')
        with self.assertRaisesRegex(ValueError,'cycle'):build_catalog(self.root)
    def test_malformed_shipped_source_is_not_silently_recovered(self):
        self.t.write_text('technologies = { broken = {')
        with self.assertRaises(ValueError):build_catalog(self.root)


if __name__=='__main__':unittest.main()
