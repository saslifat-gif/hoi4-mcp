import struct,unittest
from runtime_gui import NativeGuiReader,SUPPORTED_HASH,GuiSnapshotChanged
from native_popup import read_native_popup,SIGNATURES,NOTIFICATION_OWNERS
from test_runtime_gui import FakeProcess

class NativePopupTests(unittest.TestCase):
 def setUp(self):
  self.p=FakeProcess();self.r=NativeGuiReader(self.p,SUPPORTED_HASH);self.gui=0x22000000;self.owner=0x25000000;self.event=0x26000000;self.manager=0x27000000;self.entry=0x28000000
  for rva,code in SIGNATURES.items():self.p.put(self.p.base+rva,bytes.fromhex(code))
 def ptr(self,address,value):self.p.put(address,struct.pack('<Q',value))
 def owner_binding(self,event):
  adjust,main,secondary,offset=(56,0x29a4818,0x29a4878,0x50) if event else (40,0x29468f8,0x2946920,0x38)
  header=bytearray(160);struct.pack_into('<Q',header,80,self.owner+adjust);self.p.put(self.gui,header)
  self.ptr(self.owner,self.p.base+main);self.ptr(self.owner+adjust,self.p.base+secondary);self.ptr(self.owner+offset,self.gui-48)
  self.r.types[self.p.base+secondary]='.?AVCEventWindow@@' if event else '.?AVCGlobalAlertIcon@@'
 def event_binding(self):
  self.owner_binding(True);self.ptr(self.owner+0x68,self.event);self.ptr(self.event,self.p.base+0x2999be8);self.r.types[self.p.base+0x2999be8]='.?AVCEvent@@';self.p.put_string(self.event+0x20,'fixture.1');self.p.put(self.event+0x368,struct.pack('<QII',0,0,0))
 def alert_binding(self,count=1,key=(0,0,123,0)):
  self.owner_binding(False);self.ptr(self.owner+0x30,self.manager);self.p.put(self.owner+0x48,struct.pack('<I',8));self.ptr(self.owner+0x558,0)
  self.table=self.manager+24*(8+0xf0e);self.p.put(self.table,struct.pack('<QII',self.entry,count,count))
  for i in range(count):
   addr=self.entry+i*0x468;self.p.put(addr,b'\0');self.p.put(addr+0x438,struct.pack('<4Q',*key));self.p.put_string(addr+8,'\x11YResearch\x11!');self.p.put_string(addr+40,'Slots available',0x29000000+i*0x100)
 def options_binding(self):
  self.event_binding();self.options=0x30000000;self.option=0x31000000
  self.p.put(self.event+0x368,struct.pack('<QII',self.options,1,1));self.ptr(self.options,self.option)
  self.ptr(self.option,self.p.base+0x2999b48);self.r.types[self.p.base+0x2999b48]='.?AVCEventOption@@'
  self.p.put_string(self.option+0x178,'fixture.1.a');self.p.put(self.option+0x1f0,struct.pack('<i',0))
 def region_binding(self):
  self.alert_binding(key=(0x30000000,0,123,0));header=bytearray(160);struct.pack_into('<Q',header,80,self.owner+72);self.p.put(self.gui,header)
  self.ptr(self.owner,self.p.base+0x2a86ec8);self.ptr(self.owner+72,self.p.base+0x2a87000);self.r.types[self.p.base+0x2a87000]='.?AVCRegionAlertEntry@@'
  self.ptr(self.owner+0x40,self.gui-48);self.ptr(self.p.base+0x332f6a0,0x31000000);self.ptr(0x31000000+0x798,self.manager)
  self.p.put(self.owner+0x558,struct.pack('<I',8));self.ptr(self.owner+0x560,0x30000000)
  self.ptr(0x30000000,self.p.base+0x296d558);self.r.types[self.p.base+0x296d558]='.?AVCStrategicRegion@@'
 def test_region_observer_is_not_tooltip_provider(self):
  self.region_binding();header=bytearray(160);struct.pack_into('<Q',header,80,self.owner+56);self.p.put(self.gui,header)
  self.ptr(self.owner+56,self.p.base+0x2a86f38);self.r.types[self.p.base+0x2a86f38]='.?AVCRegionAlertEntry@@'
  self.ptr(self.owner-16,0)
  with self.assertRaisesRegex(RuntimeError,'vtable mismatch'):read_native_popup(self.r,self.gui)
 def test_theater_observer_is_not_tooltip_provider(self):
  self.theater_binding();header=bytearray(160);struct.pack_into('<Q',header,80,self.owner+56);self.p.put(self.gui,header)
  self.ptr(self.owner+56,self.p.base+0x2a869f8);self.r.types[self.p.base+0x2a869f8]='.?AVCTheaterGroupAlertEntry@@'
  self.ptr(self.owner-16,0)
  with self.assertRaisesRegex(RuntimeError,'vtable mismatch'):read_native_popup(self.r,self.gui)
 def test_region_context_must_be_strategic_region(self):
  self.region_binding();self.ptr(0x30000000,self.p.base+0x29e5c50)
  with self.assertRaisesRegex(RuntimeError,'context type mismatch'):read_native_popup(self.r,self.gui)
 def test_region_cached_identity_preserves_context_and_active_bit(self):
  self.region_binding();d=read_native_popup(self.r,self.gui)
  self.assertEqual(d['native_context_id'],'0x30000000');self.assertEqual(d['native_provider_id'],hex(self.owner+72));self.assertTrue(d['native_cache_record_active'])
  self.p.put(self.entry,b'\1');self.assertFalse(read_native_popup(self.r,self.gui)['native_cache_record_active'])
 def test_region_reads_only_its_own_cache_key(self):
  self.region_binding();d=read_native_popup(self.r,self.gui)
  self.assertEqual(d['alert_scope'],'region');self.assertEqual(d['fields']['body']['text'],'Slots available');self.assertFalse(d['buffer_freshness_verified'])
  self.p.put(self.entry+0x438,struct.pack('<4Q',0,0,123,0));self.assertEqual(read_native_popup(self.r,self.gui)['status'],'cache_missing')
 def test_region_container_binding_rejects_nested_panels(self):
  self.region_binding();self.ptr(self.owner+0x40,0x32000000);self.assertEqual(read_native_popup(self.r,self.gui)['status'],'nested_panel')
 def test_region_without_context_is_explicit(self):
  self.region_binding();self.ptr(self.owner+0x560,0);self.assertEqual(read_native_popup(self.r,self.gui)['status'],'no_region_context')
 def test_changed_region_context_is_rejected(self):
  self.region_binding();original=self.r.read;calls=0
  def read(address,size):
   nonlocal calls
   if address==self.owner+0x560:
    calls+=1
    if calls>1:return struct.pack('<Q',0x32000000)
   return original(address,size)
  self.r.read=read
  with self.assertRaises(GuiSnapshotChanged):read_native_popup(self.r,self.gui)
 def theater_binding(self,first=1,second=77,collision=False):
  self.region_binding();header=bytearray(160);struct.pack_into('<Q',header,80,self.owner+72);self.p.put(self.gui,header)
  self.ptr(self.owner,self.p.base+0x2a86988);self.ptr(self.owner+72,self.p.base+0x2a86ac0);self.r.types[self.p.base+0x2a86ac0]='.?AVCTheaterGroupAlertEntry@@'
  self.handle=(first,second);self.p.put(self.owner+0x55c,struct.pack('<2I',*self.handle));self.database=0x32000000;self.buckets=0x33000000
  root=0x3451db0 if first>0x1268 else 0x3451dc0+first*8 if first<100 else 0x3451db8
  self.ptr(self.p.base+root,self.database);header=bytearray(32);struct.pack_into('<Q',header,8,self.buckets);struct.pack_into('<i',header,20,3);header[24]=1;self.p.put(self.database,header)
  hashed=(((first<<32)+second)*0x49631a45)&0xffffffffffffffff;self.bucket=((hashed>>32)^hashed)&3
  slots=bytearray(5*24);self.target_bucket=self.bucket+int(collision)
  if collision:slots[self.bucket*24+4]=1;struct.pack_into('<2I',slots,self.bucket*24+8,first,second+1)
  slots[self.target_bucket*24+4]=1+int(collision);struct.pack_into('<2IQ',slots,self.target_bucket*24+8,first,second,0x30000000);self.p.put(self.buckets,slots)
  self.p.put(self.entry+0x438,struct.pack('<4Q',0,0x30000000,123,0));self.ptr(0x30000000,self.p.base+0x29e5c50);self.r.types[self.p.base+0x29e5c50]='.?AVCTheaterGroup@@'
 def test_theater_handle_resolves_each_native_database_route(self):
  for first in (1,100,0x1269):
   with self.subTest(first=first):
    self.theater_binding(first);d=read_native_popup(self.r,self.gui)
    self.assertEqual(d['alert_scope'],'theater');self.assertEqual(d['fields']['body']['text'],'Slots available');self.assertFalse(d['buffer_freshness_verified'])
 def test_theater_hash_collision_checks_both_handle_words(self):
  self.theater_binding(collision=True);self.assertEqual(read_native_popup(self.r,self.gui)['alert_scope'],'theater')
 def test_stale_theater_handle_does_not_read_recycled_entry(self):
  self.theater_binding();slots=bytearray(self.p.blocks[self.buckets]);struct.pack_into('<I',slots,self.target_bucket*24+12,78);self.p.put(self.buckets,slots)
  self.assertEqual(read_native_popup(self.r,self.gui)['status'],'no_theater_context')
 def test_theater_context_never_matches_region_cache(self):
  self.theater_binding();self.p.put(self.entry+0x438,struct.pack('<4Q',0x30000000,0,123,0));self.assertEqual(read_native_popup(self.r,self.gui)['status'],'cache_missing')
 def test_empty_theater_handle_is_explicit(self):
  self.theater_binding();self.p.put(self.owner+0x55c,b'\0'*8);self.assertEqual(read_native_popup(self.r,self.gui)['status'],'no_theater_context')
 def test_changed_theater_handle_is_rejected(self):
  self.theater_binding();original=self.r.read;calls=0
  def read(address,size):
   nonlocal calls
   if address==self.owner+0x55c:
    calls+=1
    if calls>1:return struct.pack('<2I',1,78)
   return original(address,size)
  self.r.read=read
  with self.assertRaises(GuiSnapshotChanged):read_native_popup(self.r,self.gui)
 def test_resolved_handle_must_be_a_native_theater_group(self):
  self.theater_binding();self.r.types[self.p.base+0x29e5c50]='.?AVCArmyGroup@@'
  with self.assertRaisesRegex(RuntimeError,'context type mismatch'):read_native_popup(self.r,self.gui)
 def test_invalid_theater_hash_extent_is_rejected(self):
  self.theater_binding();header=bytearray(self.p.blocks[self.database]);struct.pack_into('<i',header,20,2);self.p.put(self.database,header)
  with self.assertRaisesRegex(RuntimeError,'extent invalid'):read_native_popup(self.r,self.gui)
 def test_native_options_are_definition_ids_not_label_guesses(self):
  self.options_binding();d=read_native_popup(self.r,self.gui)
  self.assertEqual(d['native_options'][0]['name_key'],'fixture.1.a');self.assertEqual(d['native_options'][0]['native_index'],0)
  self.assertFalse(d['native_options'][0]['availability_verified'])
 def test_option_extent_is_rejected(self):
  self.options_binding();self.p.put(self.event+0x368,struct.pack('<QII',self.options,0,1))
  with self.assertRaisesRegex(RuntimeError,'option extent'):read_native_popup(self.r,self.gui)
 def test_wrong_option_type_is_rejected(self):
  self.options_binding();self.r.types[self.p.base+0x2999b48]='Other'
  with self.assertRaisesRegex(RuntimeError,'option type'):read_native_popup(self.r,self.gui)
 def test_option_vector_change_is_rejected(self):
  self.options_binding();original=self.r.read;calls=0
  def read(address,size):
   nonlocal calls
   if address==self.event+0x368:
    calls+=1
    if calls>1:return struct.pack('<QII',self.options,1,0)
   return original(address,size)
  self.r.read=read
  with self.assertRaises(GuiSnapshotChanged):read_native_popup(self.r,self.gui)
 def test_world_tension_state_has_verified_owner_binding(self):
  header=bytearray(160);struct.pack_into('<Q',header,80,self.owner+56);header[117]=8;self.p.put(self.gui,header)
  self.ptr(self.owner,self.p.base+0x2a133d8);self.ptr(self.owner+56,self.p.base+0x2a13478);self.ptr(self.owner+0x570,self.gui-48)
  self.r.types[self.p.base+0x2a13478]='.?AVCWorldTensionPopUpWindow@@'
  d=read_native_popup(self.r,self.gui);self.assertEqual(d['status'],'native_window_state');self.assertTrue(d['engine_local_shown']);self.assertFalse(d['physical_visibility_verified'])
  self.ptr(self.owner+0x570,0x40000000);self.assertEqual(read_native_popup(self.r,self.gui)['status'],'nested_panel')
 def test_notification_owners_bind_their_own_entry(self):
  for kind,(adjust,main,secondary,offset) in NOTIFICATION_OWNERS.items():
   with self.subTest(kind=kind):
    header=bytearray(160);struct.pack_into('<Q',header,80,self.owner+adjust);self.p.put(self.gui,header)
    self.ptr(self.owner,self.p.base+main);self.ptr(self.owner+adjust,self.p.base+secondary);self.ptr(self.owner+offset,self.gui-48);self.r.types[self.p.base+secondary]=kind
    d=read_native_popup(self.r,self.gui);self.assertEqual(d['status'],'native_notification');self.assertEqual(d['notification_native_type'],kind)
    self.ptr(self.owner+offset,0x30000000);self.assertEqual(read_native_popup(self.r,self.gui)['status'],'nested_panel')
 def test_native_id_is_bound_without_text_matching(self):
  self.event_binding();d=read_native_popup(self.r,self.gui);self.assertEqual(d['event_id'],'fixture.1');self.assertTrue(d['event_id_verified'])
 def test_nested_panel_does_not_get_owner_root_identity(self):
  self.event_binding();self.ptr(self.owner+0x50,0x30000000);self.assertEqual(read_native_popup(self.r,self.gui)['status'],'nested_panel')
 def test_unknown_owner_does_not_guess_offsets(self):
  self.owner_binding(True);self.r.types[self.p.base+0x29a4878]='Other';self.assertEqual(read_native_popup(self.r,self.gui)['status'],'unsupported_owner')
 def test_changed_implementation_is_rejected(self):
  self.event_binding();self.p.put(self.p.base+0x1180270,b'\0'*len(bytes.fromhex(SIGNATURES[0x1180270])))
  with self.assertRaisesRegex(RuntimeError,'implementation changed'):read_native_popup(self.r,self.gui)
 def test_wrong_event_type_is_rejected(self):
  self.event_binding();self.r.types[self.p.base+0x2999be8]='Wrong'
  with self.assertRaisesRegex(RuntimeError,'event type'):read_native_popup(self.r,self.gui)
 def test_missing_current_event_remains_unresolved(self):
  self.event_binding();self.ptr(self.owner+0x68,0);self.assertEqual(read_native_popup(self.r,self.gui)['status'],'no_current_event')
 def test_native_cache_text_preserves_format_and_freshness_limit(self):
  self.alert_binding();d=read_native_popup(self.r,self.gui);self.assertEqual(d['fields']['title']['text'],'Research');self.assertEqual(d['fields']['body']['text'],'Slots available');self.assertTrue(d['runtime_binding_verified']);self.assertFalse(d['buffer_freshness_verified'])
 def test_context_key_must_match_exactly(self):
  self.alert_binding(key=(0,1,0,0));self.assertEqual(read_native_popup(self.r,self.gui)['status'],'cache_missing')
 def test_duplicate_matching_entries_are_ambiguous(self):
  self.alert_binding(count=2);self.assertEqual(read_native_popup(self.r,self.gui)['status'],'cache_ambiguous')
 def test_invalid_cache_extent_is_rejected(self):
  self.alert_binding();self.p.put(self.table,struct.pack('<QII',self.entry,1,2))
  with self.assertRaisesRegex(RuntimeError,'extent invalid'):read_native_popup(self.r,self.gui)
 def test_cache_header_mutation_is_rejected(self):
  self.alert_binding();original=self.p.read;calls=0
  def read(address,size):
   nonlocal calls
   if address==self.table:
    calls+=1
    if calls>1:return struct.pack('<QII',self.entry,1,0)
   return original(address,size)
  self.r.read=read
  with self.assertRaises(GuiSnapshotChanged):read_native_popup(self.r,self.gui)
if __name__=='__main__':unittest.main()
