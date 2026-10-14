import struct,unittest
from runtime_gui import NativeGuiReader,SUPPORTED_HASH,GuiSnapshotChanged
from native_popup import read_native_popup,SIGNATURES
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
   addr=self.entry+i*0x468;self.p.put(addr+0x438,struct.pack('<4Q',*key));self.p.put_string(addr+8,'\x11YResearch\x11!');self.p.put_string(addr+40,'Slots available',0x29000000+i*0x100)
 def options_binding(self):
  self.event_binding();self.options=0x30000000;self.option=0x31000000
  self.p.put(self.event+0x368,struct.pack('<QII',self.options,1,1));self.ptr(self.options,self.option)
  self.ptr(self.option,self.p.base+0x2999b48);self.r.types[self.p.base+0x2999b48]='.?AVCEventOption@@'
  self.p.put_string(self.option+0x178,'fixture.1.a');self.p.put(self.option+0x1f0,struct.pack('<i',0))
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
