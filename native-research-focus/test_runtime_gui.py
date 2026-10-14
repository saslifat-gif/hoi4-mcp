"""Native runtime decoding regressions with a simulated memory reader."""
import struct
import unittest
from unittest.mock import patch
from runtime_gui import annotate_traversal_ancestors, NativeGuiReader, SUPPORTED_HASH, GUI_ROOT_RVA, GUI_ROOT_VTABLE_RVA, decode_std_string, registry_header, dynamic_slots_header, native_markup, CONTAINER_CHILD_VECTORS, decode_u32_string, ICON_DEFINITION_PARSERS

class FakeProcess:
    def __init__(self):
        self.base=0x10000000;self.image_size=0x4000000
        self.root=0x20000000;self.expected={'pid':42,'created':123,'executable':'hoi4.exe'}
        self.blocks={};self.guards=0
        self.put(self.base+GUI_ROOT_RVA,struct.pack('<Q',self.root))
        header=bytearray(312);struct.pack_into('<Q',header,0,self.base+GUI_ROOT_VTABLE_RVA)
        struct.pack_into('<QII',header,264,0x21000000,10,1)
        struct.pack_into('<QII',header,288,0x21000100,1,10)
        self.put(self.root,header)
        self.put(0x21000000,struct.pack('<Q',0x22000000))
        self.put(0x21000100,struct.pack('<Q',0x22000000))
        gui=bytearray(160)
        struct.pack_into('<Q',gui,0,self.base+0x1000)
        struct.pack_into('<Q',gui,96,0x23000000)
        struct.pack_into('<Q',gui,104,self.root)
        gui[116]=1
        self.put(0x22000000,gui)
        self.put_string(0x23000000+40,'research_speed')
        self.put_string(0x23000000+72,'interface/research.gui',0x24000000)
        self.put_string(0x22000000+272,'\x11G+1%\x11!')
    def put(self,address,data):self.blocks[address]=bytes(data)
    def put_string(self,address,text,heap=None):
        raw=text.encode('utf-8');data=bytearray(32)
        if len(raw)<=15:capacity=15;data[:len(raw)]=raw
        else:
            if heap is None:raise ValueError('heap required')
            capacity=len(raw);struct.pack_into('<Q',data,0,heap);self.put(heap,raw)
        struct.pack_into('<QQ',data,16,len(raw),capacity);self.put(address,data)
    def read(self,address,size):
        for start,data in self.blocks.items():
            if start<=address and address+size<=start+len(data):
                return data[address-start:address-start+size]
        return None
    def guard(self):self.guards+=1

class TraversalAncestorTests(unittest.TestCase):
    def record(self,name,shown,children=None):
        r={'widget_id':name,'name':name,'engine_show_state':{
            'engine_show_state_verified':shown is not None,'engine_local_shown':shown}}
        if children is not None:r['container_children']={'children':children}
        return r
    def test_locally_shown_child_retains_hidden_ancestor_evidence(self):
        child=self.record('checkbox',True)
        parent=self.record('hidden_tab',False,[child]);annotate_traversal_ancestors([parent])
        evidence=child['traversal_ancestor_state']
        self.assertTrue(evidence['has_sampled_hidden_ancestor'])
        self.assertFalse(evidence['all_sampled_ancestors_shown'])
        self.assertTrue(child['engine_show_state']['engine_local_shown'])
        self.assertIsNone(evidence['effective_visibility'])
        self.assertFalse(evidence['complete_ancestry_verified'])
    def test_unknown_ancestor_does_not_become_shown_or_hidden(self):
        child=self.record('label',True);parent=self.record('unknown',None,[child])
        annotate_traversal_ancestors([parent]);evidence=child['traversal_ancestor_state']
        self.assertFalse(evidence['has_sampled_hidden_ancestor'])
        self.assertFalse(evidence['all_sampled_ancestors_shown'])
        self.assertIsNone(evidence['ancestors'][0]['engine_local_shown'])
    def test_nested_grid_rows_keep_path_and_independent_root_context(self):
        text=self.record('text',True);row=self.record('row',True,[text])
        grid=self.record('grid',True);grid['grid_children']={'rows':[row]}
        root=self.record('popup',False,[grid]);annotate_traversal_ancestors([root])
        self.assertEqual(row['traversal_ancestor_state']['ancestors'],[
            {'widget_id':'popup','name':'popup','engine_local_shown':False},
            {'widget_id':'grid','name':'grid','engine_local_shown':True}])
        # Independent records must be separate snapshot objects, as in the reader.
        independent=self.record('text',True);annotate_traversal_ancestors([independent])
        self.assertEqual(independent['traversal_ancestor_state']['ancestors'],[])
        self.assertFalse(independent['traversal_ancestor_state']['all_sampled_ancestors_shown'])
    def test_snapshot_includes_ancestor_evidence(self):
        p=FakeProcess();reader=NativeGuiReader(p,SUPPORTED_HASH)
        reader.types[p.base+0x1000]='.?AVCInstantTextBox@@'
        result=reader.snapshot()
        self.assertEqual(result['matches'][0]['traversal_ancestor_state']['ancestors'],[])
        self.assertFalse(result['visibility_verified'])

class RuntimeGuiTests(unittest.TestCase):
    def setUp(self):
        self.p=FakeProcess();self.reader=NativeGuiReader(self.p,SUPPORTED_HASH)
        self.reader.types[self.p.base+0x1000]='.?AVCInstantTextBox@@'
    def setup_container(self):
        gui=0x26000030;full=gui-48;vt=self.p.base+0x2000
        data=bytearray(160);struct.pack_into('<Q',data,0,vt)
        struct.pack_into('<Q',data,96,0x23000000)
        struct.pack_into('<Q',data,104,self.p.root);self.p.put(gui,data)
        self.reader.types[vt]='.?AVCContainerWindow@@'
        self.p.put(vt+15*8,struct.pack('<QQ',self.p.base+0x22c4510,self.p.base+0x22be1a0))
        self.p.put(self.p.base+0x22c4510,bytes.fromhex('40574883ec2080797400488bf90f8cbb000000f64175100f85b10000004883c1d0'))
        for rva,code in [(0x22b94b0+0x94,'b201488d4b30e8a14bffff'),
                         (0x22b93e0,'40574883ec20488bf948897424384883c13033d2e8f74cffff'),
                         (0x22ae0f0,'440fb641750fb6c24180e0f7c0e003440ac044884175')]:
            self.p.put(self.p.base+rva,bytes.fromhex(code))
        for label,off,adjust in CONTAINER_CHILD_VECTORS:self.p.put(full+off,b'\0'*16)
        self.p.put(full+0x11e0,struct.pack('<QII',0x27000000,1,1))
        self.p.put(0x27000000,struct.pack('<Q',0x22000000))
        return gui,full
    def test_container_relationship_reads_native_child_text(self):
        gui,full=self.setup_container();r=self.reader.container_children(gui)
        self.assertEqual(r['children'][0]['name'],'research_speed')
        self.assertEqual(r['children'][0]['text'],'+1%')
        self.assertEqual(r['children'][0]['group'],'instant_text')
        self.assertFalse(r['complete_child_coverage']);self.assertIsNone(r['effective_visibility'])
    def test_container_formatted_text_and_markup_in_additional_vector(self):
        gui,full=self.setup_container();self.p.put(full+0x11e0,b'\0'*16)
        self.p.put(full+0x1210,struct.pack('<QII',0x27000000,1,1))
        self.reader.types[self.p.base+0x1000]='.?AVCTextBox@@'
        self.p.put_string(0x22000000+304,'\x11RBlocked\x11!')
        result=self.reader.container_children(gui)
        self.assertEqual(result['child_vectors_checked'],17)
        self.assertEqual(result['children'][0]['text'],'Blocked')
        self.assertEqual(result['children'][0]['formatted_runs'][0],{'kind':'color','code':'R'})
    def test_container_adjusted_nested_child_pointer(self):
        gui,full=self.setup_container();self.p.put(full+0x11e0,b'\0'*16)
        self.p.put(full+0x1330,struct.pack('<QII',0x27000000,1,1))
        self.p.put(0x27000000,struct.pack('<Q',0x22000000-48))
        result=self.reader.container_children(gui)
        self.assertEqual(result['children'][0]['widget_id'],hex(0x22000000))
        self.assertEqual(result['children'][0]['group'],'nested_containers')
    def setup_two_containers_first_corrupt(self):
        good,full=self.setup_container();bad=0x28000030;bad_full=bad-48
        self.p.put(bad,self.p.read(good,160))
        for label,off,adjust in CONTAINER_CHILD_VECTORS:self.p.put(bad_full+off,b'\0'*16)
        self.p.put(bad_full+0x11e0,struct.pack('<QII',0,1,2))
        h=bytearray(self.p.blocks[self.p.root]);struct.pack_into('<I',h,276,2);self.p.put(self.p.root,h)
        self.p.put(0x21000000,struct.pack('<2Q',bad,good))
        return bad,good
    def test_popup_page_skips_unselected_corrupt_container(self):
        bad,good=self.setup_two_containers_first_corrupt()
        result=self.reader.snapshot(native_type='CContainerWindow',offset=1,limit=1,expand_depth=1)
        self.assertEqual(result['match_count'],2);self.assertEqual(result['matches'][0]['widget_id'],hex(good))
        self.assertEqual(result['matches'][0]['container_children']['children'][0]['text'],'+1%')
    def test_selected_corrupt_popup_page_still_rejected(self):
        self.setup_two_containers_first_corrupt()
        with self.assertRaisesRegex(RuntimeError,'counts invalid'):
            self.reader.snapshot(native_type='CContainerWindow',offset=0,limit=1)
    def test_page_past_end_does_not_expand_any_container(self):
        self.setup_two_containers_first_corrupt()
        with patch.object(self.reader,'container_children',side_effect=AssertionError('unrequested expansion')):
            result=self.reader.snapshot(native_type='CContainerWindow',offset=2,limit=1)
        self.assertEqual(result['matches'],[]);self.assertEqual(result['match_count'],2)

    def setup_fixed_window(self):
        gui=0x2d000030;full=gui-48;vt=self.p.base+0x5000;mapvt=self.p.base+0x6000
        h=bytearray(160);struct.pack_into('<Q',h,0,vt);struct.pack_into('<Q',h,104,self.p.root)
        self.p.put(gui,h);self.reader.types[vt]='.?AVCFixedWindow@@'
        self.p.put(vt+120,struct.pack('<QQ',self.p.base+0x232a810,self.p.base+0x2327840))
        for rva,code in [(0x232a810+0x6d,'b201488bcbe86938f8ff'),(0x2327840+0x1a,'33d2488bcbe88c68f8ff'),
                         (0x22ae0f0,'440fb641750fb6c24180e0f7c0e003440ac044884175'),
                         (36029680+0x46,'488b03488b5c2430488b7424384883c4205fc3')]:self.p.put(self.p.base+rva,bytes.fromhex(code))
        self.p.put(mapvt+16,struct.pack('<Q',self.p.base+36029680))
        for off in [0x1da0,0x1c60,0x1ca0,0x1ce0,0x1d20,0x1d60]:self.p.put(full+off,struct.pack('<QQ',mapvt,0))
        offsets=(0x1ab0,0x1ae0,0x1bd0,0x1c00,0x1b10,0x1b40,0x1b70,0x1c30)
        for off,pos in zip(offsets,(128,192,256,784,848,912,976,1040)):
            self.p.put(full+off,bytes(16))
            self.p.put(self.p.base+0x2325730+pos,bytes.fromhex('488b87')+struct.pack('<I',off)+bytes.fromhex('488b0cd8'))
        self.p.put(full+0x1de0,bytes(16))
        for pos,code in ((376,'488b9fe01d0000486387ec1d0000488d0c804c8d34cb'),(415,'488b4b2048894df0488d4130'),(1094,'488b87e01c0000488bd348')):
            self.p.put(self.p.base+0x2325730+pos,bytes.fromhex(code))
        self.p.put(full+0x1da0,struct.pack('<QQ',mapvt,0x2e000000))
        node=bytearray(40);struct.pack_into('<Q',node,0,0x22000000);node[8]=ord('a');self.p.put(0x2e000000,node)
        return gui,full
    def test_fixed_window_named_map_extracts_child_text_and_hidden_state(self):
        gui,full=self.setup_fixed_window();r=self.reader.fixed_window_children(gui)
        self.assertEqual(r['children'][0]['text'],'+1%');self.assertEqual(r['state'],'engine_hidden')
        self.assertFalse(r['complete_child_coverage'])
    def test_fixed_window_map_cycle_rejected(self):
        gui,full=self.setup_fixed_window();node=bytearray(self.p.read(0x2e000000,40))
        struct.pack_into('<Q',node,32,0x2e000000);self.p.put(0x2e000000,node)
        with self.assertRaisesRegex(RuntimeError,'map cycle'):self.reader.fixed_window_children(gui)
    def test_fixed_window_unknown_map_getter_rejected(self):
        gui,full=self.setup_fixed_window();self.p.put(self.p.base+0x6000+16,b'\0'*8)
        with self.assertRaisesRegex(RuntimeError,'getter unsupported'):self.reader.fixed_window_children(gui)
    def test_fixed_window_named_map_mutation_rejected(self):
        gui,full=self.setup_fixed_window();old=self.reader.read;calls=[]
        def read(addr,size):
            if addr==0x2e000000 and size==40:
                calls.append(addr)
                if len(calls)>1:return b'\0'*40
            return old(addr,size)
        self.reader.read=read
        with self.assertRaisesRegex(RuntimeError,'children changed'):self.reader.fixed_window_children(gui)
    def setup_listbox(self):
        child,full=self.setup_container();gui=0x2a000008;vt=self.p.base+0x3100
        data=bytearray(160);struct.pack_into('<Q',data,0,vt);struct.pack_into('<Q',data,104,self.p.root)
        struct.pack_into('<QQI',data,136,0x2b000000,0x2b000000,1)
        self.p.put(gui,data);self.p.put(gui-8,struct.pack('<Q',self.p.base+0x3200))
        self.reader.types[vt]='.?AVCStandardlistbox@@'
        self.p.put(self.p.base+0x3200+0xc8,struct.pack('<Q',self.p.base+0x22ad160))
        for off,code in ((0x120,'488b9e90000000'),(0x15c,'488b01ff5060'),(0x162,'488b5b10')):
            self.p.put(self.p.base+0x22ad160+off,bytes.fromhex(code))
        self.p.put(0x2b000000,struct.pack('<QQQ',0x2c000000,0,0))
        self.p.put(0x2c000000,struct.pack('<QQ',self.p.base+0x4100,full))
        self.p.put(self.p.base+0x4100+0x60,struct.pack('<Q',self.p.base+0x2200000))
        self.p.put(self.p.base+0x2200000,bytes.fromhex('488b49084885c9740f488b41304883c13048ffa080000000c3'))
        return gui
    def test_listbox_row_binding_expands_text(self):
        gui=self.setup_listbox();r=self.reader.listbox_children(gui,1)
        self.assertEqual(r['row_count'],1)
        self.assertEqual(r['rows'][0]['container_children']['children'][0]['text'],'+1%')
        self.assertIsNone(r['effective_visibility'])
    def test_listbox_unsupported_binding_is_explicit(self):
        gui=self.setup_listbox();self.p.put(self.p.base+0x4100+0x60,struct.pack('<Q',0))
        r=self.reader.listbox_children(gui,1)
        self.assertEqual(r['rows'][0]['status'],'unsupported_row_binding')
    def test_listbox_cycle_rejected(self):
        gui=self.setup_listbox();self.p.put(0x2b000000,struct.pack('<QQQ',0x2c000000,0,0x2b000000))
        with self.assertRaisesRegex(RuntimeError,'cycle'):self.reader.listbox_children(gui)
    def test_listbox_bad_tail_rejected(self):
        gui=self.setup_listbox();data=bytearray(self.p.read(gui,160));struct.pack_into('<Q',data,144,0x2b000100);self.p.put(gui,data)
        with self.assertRaisesRegex(RuntimeError,'tail mismatch'):self.reader.listbox_children(gui)
    def test_listbox_changed_node_rejected(self):
        gui=self.setup_listbox();old=self.reader.read;calls=[]
        def read(a,n):
            if a==0x2b000000 and n==24:
                calls.append(a)
                if len(calls)>1:return bytes(24)
            return old(a,n)
        self.reader.read=read
        with self.assertRaisesRegex(RuntimeError,'changed'):self.reader.listbox_children(gui)
    def test_listbox_wrong_implementation_rejected(self):
        gui=self.setup_listbox();self.p.put(self.p.base+0x3200+0xc8,bytes(8))
        with self.assertRaisesRegex(RuntimeError,'unsupported'):self.reader.listbox_children(gui)
    def test_listbox_invalid_counts_rejected(self):
        gui=self.setup_listbox();data=bytearray(self.p.read(gui,160));struct.pack_into('<I',data,152,10001);self.p.put(gui,data)
        with self.assertRaisesRegex(RuntimeError,'counts invalid'):self.reader.listbox_children(gui)

    def setup_smooth_listbox(self):
        gui=self.setup_listbox();self.reader.types[self.p.base+0x3100]='.?AVCSmoothListbox@@'
        self.p.put(self.p.base+0x3200+0xc8,struct.pack('<Q',self.p.base+0x23018c0))
        for off,code in ((0x15e,'488bbe90000000'),(0x203,'498b06498bceff5050'),(0x20c,'488b7f10')):
            self.p.put(self.p.base+0x23018c0+off,bytes.fromhex(code))
        full=struct.unpack('<QQ',self.p.read(0x2c000000,16))[1]
        binding=bytearray(48);struct.pack_into('<Q',binding,0,self.p.base+0x4100);struct.pack_into('<Q',binding,40,full)
        self.p.put(0x2c000000,binding)
        self.p.put(self.p.base+0x2200000,bytes.fromhex('c6410800488b49284885c9740f488b41304883c13048ffa080000000c3'))
        return gui
    def test_smooth_listbox_uses_distinct_controller_offset(self):
        gui=self.setup_smooth_listbox();r=self.reader.listbox_children(gui,1)
        self.assertEqual(r['rows'][0]['container_children']['children'][0]['text'],'+1%')
    def test_smooth_listbox_standard_binding_is_not_guessed(self):
        gui=self.setup_smooth_listbox()
        self.p.put(self.p.base+0x2200000,bytes.fromhex('488b49084885c9740f488b41304883c13048ffa080000000c3')+bytes(5))
        r=self.reader.listbox_children(gui,1)
        self.assertEqual(r['rows'][0]['status'],'unsupported_row_binding')
    def test_smooth_listbox_empty_rows_are_explicit(self):
        gui=self.setup_smooth_listbox();data=bytearray(self.p.read(gui,160));data[136:156]=bytes(20);self.p.put(gui,data)
        self.assertEqual(self.reader.listbox_children(gui,1)['rows'],[])
    def test_smooth_listbox_changed_binding_rejected(self):
        gui=self.setup_smooth_listbox();old=self.reader.read;calls=[]
        def read(a,n):
            if a==0x2c000000 and n==48:
                calls.append(a)
                if len(calls)>1:return bytes(48)
            return old(a,n)
        self.reader.read=read
        with self.assertRaisesRegex(RuntimeError,'changed'):self.reader.listbox_children(gui,1)
    def test_listbox_unreadable_callback_rejected(self):
        gui=self.setup_listbox();del self.p.blocks[self.p.base+0x4100+0x60]
        with self.assertRaisesRegex(RuntimeError,'callback unavailable'):self.reader.listbox_children(gui)

    def setup_overlapping_rows(self):
        gui=self.setup_listbox();self.reader.types[self.p.base+0x3100]='.?AVCOverlappingElementsBox@@'
        h=self.p.read(gui+136,20);self.p.put(gui+184,h)
        self.p.put(gui+168,struct.pack('<Q',self.p.base+0x3300))
        self.p.put(self.p.base+0x3300+88,struct.pack('<Q',self.p.base+2238528))
        self.p.put(self.p.base+2238528,bytes.fromhex('488d4110c3'))
        self.p.put(self.p.base+0x3100+0x268,struct.pack('<Q',self.p.base+0x2386e00))
        self.p.put(self.p.base+0x2386e00,bytes.fromhex('48895c2408574883ec20488bf94881c1a8000000488b01ff5058488b184885db7416488b0b4883c138488b01ff5050488b5b104885db75ea'))
        self.p.put(0x2c000000+56,self.p.read(0x2c000000,16))
        self.p.put(0x2c000000,bytes(16))
        return gui
    def test_overlapping_rows_use_adjusted_controller_binding(self):
        gui=self.setup_overlapping_rows();r=self.reader.listbox_children(gui,1)
        self.assertEqual(r['rows'][0]['container_children']['children'][0]['text'],'+1%')
    def test_overlapping_rows_unknown_getter_rejected(self):
        gui=self.setup_overlapping_rows();self.p.put(self.p.base+2238528,bytes(5))
        with self.assertRaisesRegex(RuntimeError,'getter unsupported'):self.reader.listbox_children(gui)
    def test_overlapping_rows_changed_binding_rejected(self):
        gui=self.setup_overlapping_rows();old=self.reader.read;calls=[]
        def read(a,n):
            if a==0x2c000000+56 and n==16:
                calls.append(a)
                if len(calls)>1:return bytes(16)
            return old(a,n)
        self.reader.read=read
        with self.assertRaisesRegex(RuntimeError,'changed'):self.reader.listbox_children(gui)
    def test_overlapping_rows_do_not_guess_unadjusted_binding(self):
        gui=self.setup_overlapping_rows();self.p.put(0x2c000000+56,struct.pack('<QQ',self.p.base+0x4100,0))
        with self.assertRaisesRegex(RuntimeError,'container unavailable'):self.reader.listbox_children(gui,1)

    def test_overlapping_row_polymorphic_fixed_window_binding(self):
        gui=self.setup_overlapping_rows();child,full=self.setup_fixed_window()
        self.p.put(0x2c000000+56,struct.pack('<QQ',self.p.base+0x4100,full))
        row=self.reader.listbox_children(gui,1)['rows'][0]
        self.assertEqual(row['status'],'verified_fixed_window_binding')
        self.assertEqual(row['fixed_window_children']['children'][0]['text'],'+1%')

    def test_fixed_window_vector_child_is_deduplicated_with_map(self):
        gui,full=self.setup_fixed_window();self.p.put(full+0x1ab0,struct.pack('<QII',0x2f000000,1,1));self.p.put(0x2f000000,struct.pack('<Q',0x22000000))
        r=self.reader.fixed_window_children(gui)
        self.assertEqual(len(r['children']),1);self.assertEqual(len(r['children'][0]['groups']),2)
        self.assertEqual(r['child_vectors_checked'],9)
    def test_fixed_window_named_container_array_expands_text(self):
        child,container_full=self.setup_container();gui,full=self.setup_fixed_window()
        self.p.put(full+0x1de0,struct.pack('<QII',0x2f000000,1,1));self.p.put(0x2f000000,bytes(32)+struct.pack('<Q',container_full))
        r=self.reader.fixed_window_children(gui,1)
        self.assertEqual(r['children'][-1]['container_children']['children'][0]['text'],'+1%')
    def test_fixed_window_corrupt_vector_counts_rejected(self):
        gui,full=self.setup_fixed_window();self.p.put(full+0x1ab0,struct.pack('<QII',0,1,2))
        with self.assertRaisesRegex(RuntimeError,'counts invalid'):self.reader.fixed_window_children(gui)
    def test_fixed_window_changed_vector_rejected(self):
        gui,full=self.setup_fixed_window();self.p.put(full+0x1ab0,struct.pack('<QII',0x2f000000,1,1));self.p.put(0x2f000000,struct.pack('<Q',0x22000000));old=self.reader.read;calls=[]
        def read(a,n):
            if a==0x2f000000 and n==8:
                calls.append(a)
                if len(calls)>1:return bytes(8)
            return old(a,n)
        self.reader.read=read
        with self.assertRaisesRegex(RuntimeError,'children changed'):self.reader.fixed_window_children(gui)
    def test_fixed_window_expansion_rejects_self_cycle(self):
        gui,full=self.setup_fixed_window();self.p.put(full+0x1de0,struct.pack('<QII',0x2f000000,1,1));self.p.put(0x2f000000,bytes(32)+struct.pack('<Q',full))
        with self.assertRaisesRegex(RuntimeError,'cycle'):self.reader.fixed_window_children(gui,2)

    def setup_edit_box(self,text):
        gui=0x22000000;self.reader.types[self.p.base+0x1000]='.?AVCEditBox@@'
        self.p.put(self.p.base+0x1000+0x268,struct.pack('<Q',self.p.base+36651696))
        for rva,code in ((0x22f30a0,'40534883ec40488bd90f57c00f11442420'),(0x22f2e30+0xe0,'488b4f404c8d4f30'),(0x22f2e30+0xed,'48837f4803'),(0x22f2e30+0x10d,'4883c004')):
            self.p.put(self.p.base+rva,bytes.fromhex(code))
        raw=text.encode('utf-32-le');h=bytearray(32);n=len(raw)//4
        if n<=3:cap=3;h[:len(raw)]=raw
        else:cap=n;struct.pack_into('<Q',h,0,0x2f000000);self.p.put(0x2f000000,raw)
        struct.pack_into('<QQ',h,16,n,cap);self.p.put(gui+176,h)
        return gui
    def test_edit_input_inline_unicode_preserved(self):
        gui=self.setup_edit_box('中😀');self.assertEqual(self.reader.edit_text(gui)['text'],'中😀')
    def test_edit_input_heap_unicode_and_newline_preserved(self):
        gui=self.setup_edit_box('Test 中文\n');self.assertEqual(self.reader.edit_text(gui)['text'],'Test 中文\n')
    def test_edit_asset_path_is_not_returned_as_input(self):
        gui=self.setup_edit_box('');self.p.put_string(gui+488,'gfx/test.dds')
        self.assertEqual(self.reader.edit_text(gui)['text'],'')
    def test_edit_invalid_unicode_is_explicit(self):
        gui=self.setup_edit_box('a');h=bytearray(self.p.read(gui+176,32));struct.pack_into('<I',h,0,0x110000);self.p.put(gui+176,h)
        self.assertEqual(self.reader.edit_text(gui)['status'],'invalid_utf32')
    def test_edit_changed_buffer_rejected(self):
        gui=self.setup_edit_box('sample');old=self.reader.read;calls=[]
        def read(a,n):
            if a==gui+176 and n==32:
                calls.append(a)
                if len(calls)>1:return bytes(32)
            return old(a,n)
        self.reader.read=read
        self.assertEqual(self.reader.edit_text(gui)['status'],'changed_during_read')
    def test_edit_unknown_layout_rejected(self):
        gui=self.setup_edit_box('sample');self.p.put(self.p.base+0x1000+0x268,bytes(8))
        with self.assertRaisesRegex(RuntimeError,'unsupported'):self.reader.edit_text(gui)
    def test_edit_snapshot_reads_input_buffer(self):
        self.setup_edit_box('中文 search');self.reader.decode_edit_inputs=True;r=self.reader.snapshot(query='search')
        self.assertEqual(r['matches'][0]['text'],'中文 search')

    def test_snapshot_omits_edit_input_before_decoder_call(self):
        self.setup_edit_box('private entry')
        with patch.object(self.reader,'edit_text',side_effect=AssertionError('input decoder called')):
            result=self.reader.snapshot(native_type='CEditBox')
        self.assertEqual(result['matches'][0]['text_status'],'editable_input_text_omitted')
        self.assertIsNone(result['matches'][0]['text'])
        self.assertFalse(result['editable_input_text_decoded'])
    def test_container_traversal_omits_edit_input(self):
        container,full=self.setup_container();self.setup_edit_box('private entry')
        with patch.object(self.reader,'edit_text',side_effect=AssertionError('input decoder called')):
            result=self.reader.container_children(container)
        self.assertEqual(result['children'][0]['text_status'],'editable_input_text_omitted')
        self.assertIsNone(result['children'][0]['raw_text'])
    def test_fixed_window_traversal_omits_edit_input(self):
        fixed,full=self.setup_fixed_window();self.setup_edit_box('private entry')
        self.p.put(full+0x1ab0,struct.pack('<QII',0x2e010000,1,1));self.p.put(0x2e010000,struct.pack('<Q',0x22000000))
        with patch.object(self.reader,'edit_text',side_effect=AssertionError('input decoder called')):
            result=self.reader.fixed_window_children(fixed)
        self.assertEqual(result['children'][0]['text_status'],'editable_input_text_omitted')
    def test_edit_input_policy_requires_explicit_boolean(self):
        with self.assertRaisesRegex(ValueError,'boolean'):NativeGuiReader(self.p,SUPPORTED_HASH,decode_edit_inputs='false')

    def setup_dropdown(self):
        child,full=self.setup_container();gui=0x30000000;vt=self.p.base+0x7100
        h=bytearray(160);struct.pack_into('<Q',h,0,vt);struct.pack_into('<Q',h,104,self.p.root);self.p.put(gui,h)
        self.reader.types[vt]='.?AVCDropDownBox@@'
        self.p.put(vt+0x268,struct.pack('<QQ',self.p.base+0x2303090,self.p.base+0x2303030))
        self.p.put(self.p.base+0x2303090,bytes.fromhex('40534883ec20488bd9488b89000b00004885c97406488b01ff5078488b8b080b00004885c9741480bb180b000000740b488b41304883c130ff5078'))
        self.p.put(gui+2816,struct.pack('<3Q',0,full,0));return gui
    def setup_dropdown_button(self,text='\x11GReady\x11!'):
        gui=self.setup_dropdown();button=0x31000000;vt=self.p.base+0x7200
        h=bytearray(160);struct.pack_into('<QQ',h,96,0x23000000,self.p.root)
        struct.pack_into('<Q',h,0,vt);self.p.put(button,h)
        self.reader.types[vt]='.?AVCButtonStandard@@'
        self.p.put_string(button+392,text,0x32000000)
        self.p.put(gui+2816,struct.pack('<3Q',button,0,0))
        return gui,button
    def test_dropdown_button_caption_and_formatting_without_expansion(self):
        gui,button=self.setup_dropdown_button();r=self.reader.dropdown_components(gui)
        caption=r['children'][0]
        self.assertEqual(caption['text'],'Ready');self.assertEqual(caption['text_status'],'read')
        self.assertEqual(caption['formatted_runs'][0],{'kind':'color','code':'G'})
        self.assertFalse(caption['selection_state_verified']);self.assertIsNone(caption['buffer_last_update_unix'])
    def test_dropdown_button_empty_caption_is_read_not_missing(self):
        gui,button=self.setup_dropdown_button('');caption=self.reader.dropdown_components(gui)['children'][0]
        self.assertEqual(caption['text'],'');self.assertEqual(caption['text_length'],0)
    def test_dropdown_button_invalid_caption_remains_explicit(self):
        gui,button=self.setup_dropdown_button();self.p.put(button+392,bytes(32))
        caption=self.reader.dropdown_components(gui)['children'][0]
        self.assertEqual(caption['text_status'],'invalid_layout');self.assertIsNone(caption['text'])
    def test_dropdown_button_changed_inline_caption_rejects_snapshot(self):
        gui,button=self.setup_dropdown_button();old=self.reader.read;calls=[]
        def read(a,n):
            if a==button+392 and n==32:
                calls.append(a)
                if len(calls)>2:return bytes(32)
            return old(a,n)
        self.reader.read=read
        with self.assertRaisesRegex(RuntimeError,'changed'):self.reader.dropdown_components(gui)

    def test_dropdown_option_panel_binding_expands_text(self):
        gui=self.setup_dropdown();r=self.reader.dropdown_components(gui,1)
        self.assertEqual(r['children'][0]['role'],'option_panel')
        self.assertEqual(r['children'][0]['container_children']['children'][0]['text'],'+1%')
    def test_dropdown_unknown_layout_rejected(self):
        gui=self.setup_dropdown();self.p.put(self.p.base+0x7100+0x268,bytes(16))
        with self.assertRaisesRegex(RuntimeError,'unsupported'):self.reader.dropdown_components(gui)
    def test_dropdown_changed_binding_rejected(self):
        gui=self.setup_dropdown();old=self.reader.read;calls=[]
        def read(a,n):
            if a==gui+2816 and n==24:
                calls.append(a)
                if len(calls)>1:return bytes(24)
            return old(a,n)
        self.reader.read=read
        with self.assertRaisesRegex(RuntimeError,'changed'):self.reader.dropdown_components(gui)
    def test_dropdown_wrong_component_type_rejected(self):
        gui=self.setup_dropdown();self.p.put(gui+2816,struct.pack('<3Q',0,0x22000000-48,0))
        with self.assertRaisesRegex(RuntimeError,'type/ownership'):self.reader.dropdown_components(gui)
    def test_dropdown_empty_components_are_explicit(self):
        gui=self.setup_dropdown();self.p.put(gui+2816,bytes(24))
        self.assertEqual(self.reader.dropdown_components(gui)['children'],[])

    def setup_grid(self):
        child,full=self.setup_container();gui=0x2a000000;vt=self.p.base+0x3000
        data=bytearray(160);struct.pack_into('<Q',data,0,vt);struct.pack_into('<Q',data,104,self.p.root)
        self.p.put(gui,data);self.reader.types[vt]='.?AVCStandardGridBox@@'
        self.p.put(vt+0x268,struct.pack('<Q',self.p.base+0x22c6bd0))
        self.p.put(self.p.base+0x22c6bd0+0x30,bytes.fromhex('488b83a0010000488b0c06488b01ff5010'))
        self.p.put(gui+416,struct.pack('<QII',0x2b000000,1,1));self.p.put(0x2b000000,struct.pack('<Q',0x2c000000))
        self.p.put(0x2c000000,struct.pack('<3Q',self.p.base+0x4000,0,full))
        self.p.put(self.p.base+0x4000+16,struct.pack('<Q',self.p.base+0x1d641c0))
        self.p.put(self.p.base+0x1d641c0,bytes.fromhex('488b49104885c9740c488b41304883c13048ff6078c3'))
        return gui
    def setup_registered_grid(self):
        gui=self.setup_grid();h=bytearray(self.p.read(gui,160))
        struct.pack_into('<Q',h,96,0x23000000);self.p.put(gui,h)
        self.p.put(0x21000000,struct.pack('<Q',gui));self.p.put(0x21000100,struct.pack('<Q',gui))
        return gui
    def test_native_type_filter_excludes_edit_decoding(self):
        self.reader.types[self.p.base+0x1000]='.?AVCEditBox@@'
        self.reader.edit_text=lambda gui:(_ for _ in ()).throw(AssertionError('Unrelated edit read'))
        r=self.reader.snapshot(native_type='CStandardGridBox')
        self.assertEqual(r['matches'],[]);self.assertEqual(r['match_count'],0)
        self.assertEqual(r['native_type_filter_scope'],'top_level_widgets_only')
    def test_native_type_filter_direct_grid_rows(self):
        self.setup_registered_grid();r=self.reader.snapshot(native_type='CStandardGridBox')
        self.assertEqual(r['matches'][0]['grid_children']['row_count'],1)
        self.assertEqual(r['native_type_filter'],'CStandardGridBox')
    def test_native_type_filter_exact_and_validated(self):
        for value in (None,42,'.?AVCInstantTextBox@@','C*','x'*81):
            with self.assertRaises(ValueError):self.reader.snapshot(native_type=value)
        self.assertEqual(self.reader.snapshot(native_type='CInstantText')['matches'],[])

    def test_direct_grid_query_expands_verified_rows(self):
        self.setup_registered_grid();r=self.reader.snapshot(query='research_speed',expand_depth=1)
        self.assertEqual(r['match_count'],1)
        grid=r['matches'][0]['grid_children'];self.assertEqual(grid['row_count'],1)
        self.assertEqual(grid['rows'][0]['container_children']['children'][0]['text'],'+1%')
    def test_direct_grid_query_preserves_depth_zero_bindings(self):
        self.setup_registered_grid();row=self.reader.snapshot(expand_depth=0)['matches'][0]['grid_children']['rows'][0]
        self.assertEqual(row['status'],'verified_container_binding')
        self.assertFalse(row['descendants_expanded']);self.assertNotIn('container_children',row)
    def test_direct_grid_query_rejects_corrupt_rows(self):
        gui=self.setup_registered_grid();self.p.put(gui+416,struct.pack('<QII',0x2b000000,1,2))
        with self.assertRaisesRegex(RuntimeError,'counts invalid'):self.reader.snapshot(expand_depth=1)

    def test_grid_polymorphic_fixed_window_row(self):
        gui=self.setup_grid();child,full=self.setup_fixed_window()
        self.p.put(0x2c000000,struct.pack('<3Q',self.p.base+0x4000,0,full))
        row=self.reader.grid_children(gui,1)['rows'][0]
        self.assertEqual(row['status'],'verified_fixed_window_binding')
        self.assertEqual(row['fixed_window_children']['children'][0]['text'],'+1%')
    def test_grid_foreign_window_rejected_without_expansion(self):
        gui=self.setup_grid();child=0x26000030;data=bytearray(self.p.read(child,160));struct.pack_into('<Q',data,104,0);self.p.put(child,data)
        with self.assertRaisesRegex(RuntimeError,'container unavailable'):self.reader.grid_children(gui,0)
    def test_container_nested_fixed_window_expands_child_text(self):
        gui,full=self.setup_container();child,fixed_full=self.setup_fixed_window()
        h=bytearray(self.p.read(child,160));struct.pack_into('<Q',h,96,0x23000000);self.p.put(child,h)
        self.p.put(full+0x1330,struct.pack('<QII',0x27000100,1,1));self.p.put(0x27000100,struct.pack('<Q',fixed_full))
        result=self.reader.container_children(gui,1)
        fixed=next(c for c in result['children'] if c['native_type']=='.?AVCFixedWindow@@')
        self.assertEqual(fixed['fixed_window_children']['children'][0]['text'],'+1%')
    def test_fixed_window_nested_dropdown_expands_panels(self):
        dropdown=self.setup_dropdown();gui,full=self.setup_fixed_window()
        h=bytearray(self.p.read(dropdown,160));struct.pack_into('<Q',h,96,0x23000000);self.p.put(dropdown,h)
        self.p.put(full+0x1c30,struct.pack('<QII',0x2f001000,1,1));self.p.put(0x2f001000,struct.pack('<Q',dropdown))
        result=self.reader.fixed_window_children(gui,2)
        c=next(c for c in result['children'] if c['native_type']=='.?AVCDropDownBox@@')
        self.assertEqual(c['dropdown_components']['children'][0]['container_children']['children'][0]['text'],'+1%')

    def test_grid_controller_binding_expands_row_text(self):
        gui=self.setup_grid();r=self.reader.grid_children(gui,expand_depth=1)
        self.assertEqual(r['row_count'],1)
        self.assertEqual(r['rows'][0]['container_children']['children'][0]['text'],'+1%')
        self.assertIsNone(r['effective_visibility'])
    def test_grid_unknown_controller_binding_remains_explicit(self):
        gui=self.setup_grid();self.p.put(self.p.base+0x4000+16,b'\0'*8)
        r=self.reader.grid_children(gui,expand_depth=1)
        self.assertEqual(r['rows'][0]['status'],'unsupported_row_binding')
        self.assertNotIn('container_children',r['rows'][0])
    def test_grid_changing_controller_binding_rejects_tree(self):
        gui=self.setup_grid();old=self.reader.read;calls=[]
        def read(addr,size):
            if addr==0x2c000000 and size==24:
                calls.append(addr)
                if len(calls)>1:return b'\0'*24
            return old(addr,size)
        self.reader.read=read
        with self.assertRaisesRegex(RuntimeError,'binding changed'):self.reader.grid_children(gui,expand_depth=1)
    def test_grid_corrupt_counts_rejected(self):
        gui=self.setup_grid();self.p.put(gui+416,struct.pack('<QII',0x2b000000,1,2))
        with self.assertRaisesRegex(RuntimeError,'counts invalid'):self.reader.grid_children(gui)
    def test_container_expansion_reads_nested_window_text(self):
        gui,full=self.setup_container();nested=0x29000030;nf=nested-48
        self.p.put(nested,self.p.read(gui,160))
        for label,off,adjust in CONTAINER_CHILD_VECTORS:self.p.put(nf+off,b'\0'*16)
        self.p.put(nf+0x11e0,struct.pack('<QII',0x27000000,1,1))
        self.p.put(full+0x1330,struct.pack('<QII',0x28000000,1,1))
        self.p.put(0x28000000,struct.pack('<Q',nf))
        result=self.reader.container_children(gui,expand_depth=1)
        child=next(v for v in result['children'] if v['group']=='nested_containers')
        self.assertTrue(child['descendants_expanded'])
        self.assertEqual(child['container_children']['children'][0]['text'],'+1%')
        self.assertEqual(child['container_children']['expand_depth'],0)
    def test_container_expansion_rejects_cycle_without_partial_tree(self):
        gui,full=self.setup_container();self.p.put(full+0x1330,struct.pack('<QII',0x28000000,1,1))
        self.p.put(0x28000000,struct.pack('<Q',full))
        with self.assertRaisesRegex(RuntimeError,'hierarchy cycle'):self.reader.container_children(gui,expand_depth=2)
    def test_container_expansion_depth_is_explicit_and_validated(self):
        gui,full=self.setup_container()
        for depth in [True,-1,9]:
            with self.assertRaises(ValueError):self.reader.container_children(gui,expand_depth=depth)
        self.assertEqual(self.reader.container_children(gui,expand_depth=3)['expand_depth'],3)
    def test_container_hierarchy_node_budget_rejects_partial_tree(self):
        gui,full=self.setup_container()
        with self.assertRaisesRegex(RuntimeError,'node budget'):
            self.reader.container_children(gui,_budget=[0,float('inf')])
    def test_container_engine_shown_and_hidden_flag(self):
        gui,full=self.setup_container()
        self.assertEqual(self.reader.container_children(gui)['state'],'engine_hidden')
        data=bytearray(self.p.read(gui,160));data[117]=8;self.p.put(gui,data)
        result=self.reader.container_children(gui)
        self.assertTrue(result['engine_show_state_verified']);self.assertTrue(result['engine_local_shown'])
        self.assertEqual(result['state'],'engine_shown');self.assertIsNone(result['effective_visibility'])
    def test_container_rejects_changed_state_setter(self):
        gui,full=self.setup_container();self.p.put(self.p.base+0x22ae0f0,b'\0'*20)
        with self.assertRaisesRegex(RuntimeError,'shown-state implementation changed'):self.reader.container_children(gui)
    def test_container_rejects_unknown_show_implementation(self):
        gui,full=self.setup_container();self.p.put(self.p.base+0x2000+120,b'\0'*16)
        with self.assertRaisesRegex(RuntimeError,'implementation not verified'):self.reader.container_children(gui)
    def test_container_rejects_changed_child_array(self):
        gui,full=self.setup_container();old=self.reader.read;calls=[]
        def read(address,size):
            if address==0x27000000:
                calls.append(address)
                if len(calls)>1:return b'\0'*8
            return old(address,size)
        self.reader.read=read
        with self.assertRaisesRegex(RuntimeError,'children changed'):self.reader.container_children(gui)
    def test_container_rejects_foreign_root_child(self):
        gui,full=self.setup_container();data=bytearray(self.p.read(0x22000000,160))
        struct.pack_into('<Q',data,104,0x99999999);self.p.put(0x22000000,data)
        with self.assertRaisesRegex(RuntimeError,'ownership unavailable'):self.reader.container_children(gui)
    def test_native_unicode_and_formatting_decode(self):
        self.p.put_string(0x25000000,'科研速度')
        result=decode_std_string(self.p.read,0x25000000)
        self.assertEqual(result['text'],'科研速度')
        self.assertEqual(self.reader.snapshot()['matches'][0]['text'],'+1%')
    def test_current_ui_read_is_deduplicated_and_visibility_remains_unknown(self):
        result=self.reader.snapshot(query='research')
        self.assertEqual(result['match_count'],1)
        self.assertEqual(result['matches'][0]['registry_memberships'],['registered','dynamic_slots'])
        self.assertEqual(len(result['registries']),2)
        self.assertFalse(result['screen_capture']);self.assertFalse(result['process_writes'])
        self.assertFalse(result['visibility_verified'])
        self.assertIsNone(result['matches'][0]['effective_visibility'])
        self.assertFalse(result['atomic_game_frame'])
    def test_root_changed_rejected_before_read(self):
        self.p.put(self.p.base+GUI_ROOT_RVA,struct.pack('<Q',0x20000400))
        with self.assertRaisesRegex(RuntimeError,'root changed'):self.reader.snapshot()
    def test_process_guard_failure_is_not_stale_fallback(self):
        def fail():raise RuntimeError('process changed')
        self.p.guard=fail
        with self.assertRaisesRegex(RuntimeError,'process changed'):self.reader.snapshot()
    def test_changed_registry_rejects_partial_capture(self):
        old=self.p.read;calls=[]
        def read(addr,size):
            if addr==self.p.root and size==312:
                calls.append(addr)
                if len(calls)>1:
                    header=bytearray(old(addr,size));struct.pack_into('<I',header,276,2)
                    return bytes(header)
            return old(addr,size)
        self.reader.read=read
        with self.assertRaisesRegex(RuntimeError,'registry changed'):self.reader.snapshot()
    def test_corrupt_string_capacity_and_invalid_utf8_not_returned_as_text(self):
        self.p.put(0x25000000,b'\x00'*16+struct.pack('<QQ',20,15))
        self.assertEqual(decode_std_string(self.p.read,0x25000000)['status'],'invalid_layout')
        self.p.put(0x25000000,b'\xff'+b'\x00'*15+struct.pack('<QQ',1,15))
        result=decode_std_string(self.p.read,0x25000000)
        self.assertEqual(result['status'],'invalid_utf8');self.assertNotIn('text',result)
    def test_unknown_widget_layout_is_not_guessed(self):
        self.reader.types[self.p.base+0x1000]='.?AVCUnknownTextBox@@'
        result=self.reader.snapshot()
        self.assertEqual(result['matches'][0]['text_status'],'not_decoded_for_this_widget_type')
        self.assertIsNone(result['matches'][0]['text'])
    def test_hash_change_rejects_before_applying_offsets(self):
        with self.assertRaisesRegex(RuntimeError,'Unsupported game build'):NativeGuiReader(self.p,'new-build')
    def test_invalid_counts_and_filters_rejected(self):
        data=bytearray(312);struct.pack_into('<QII',data,264,0x21000000,1,2)
        with self.assertRaisesRegex(RuntimeError,'counts invalid'):registry_header(data,264,276,272)
        for kwargs in ({'limit':True},{'offset':-1},{'query':'x'*161}):
            with self.assertRaises(ValueError):self.reader.snapshot(**kwargs)
    def test_deadline_returns_no_partial_result(self):
        with patch('runtime_gui.time.monotonic',side_effect=[0,9]):
            with self.assertRaisesRegex(RuntimeError,'deadline exceeded'):self.reader.snapshot()
    def test_large_text_has_explicit_status_not_silent_truncation(self):
        self.p.put(0x25000000,b'\x00'*16+struct.pack('<QQ',100000,100000))
        result=decode_std_string(self.p.read,0x25000000)
        self.assertEqual(result['status'],'too_long');self.assertEqual(result['length'],100000)
    def test_unowned_gui_object_is_excluded(self):
        data=bytearray(self.p.blocks[0x22000000]);struct.pack_into('<Q',data,104,0)
        self.p.put(0x22000000,data)
        self.assertEqual(self.reader.snapshot()['matches'],[])



    def test_dynamic_sparse_slots_do_not_treat_opaque_field_as_capacity(self):
        header=bytearray(self.p.blocks[self.p.root])
        struct.pack_into('<QII',header,288,0x21000100,3,0xffffffff)
        self.p.put(self.p.root,header)
        self.p.put(0x21000100,struct.pack('<QQQ',0,0x22000000,0x26000000))
        result=self.reader.snapshot()
        self.assertEqual(result['match_count'],1)
        self.assertEqual(result['registries'][1]['slots_scanned'],3)
        self.assertEqual(result['registries'][1]['opaque_header_field'],0xffffffff)
        self.assertTrue(result['registries'][1]['sparse'])
    def test_dynamic_invalid_extent_is_rejected(self):
        header=bytearray(312);struct.pack_into('<QII',header,288,0x21000100,500001,0)
        with self.assertRaisesRegex(RuntimeError,'extent invalid'):dynamic_slots_header(header)
    def test_dynamic_opaque_bookkeeping_change_does_not_reject_snapshot(self):
        old=self.p.read;calls=[]
        def read(addr,size):
            if addr==self.p.root and size==312:
                calls.append(addr)
                if len(calls)>1:
                    header=bytearray(old(addr,size));struct.pack_into('<I',header,300,99)
                    return bytes(header)
            return old(addr,size)
        self.reader.read=read
        self.assertEqual(self.reader.snapshot()['match_count'],1)


    def test_dynamic_extent_change_still_rejects_snapshot(self):
        old=self.p.read;calls=[]
        def read(addr,size):
            if addr==self.p.root and size==312:
                calls.append(addr)
                if len(calls)>1:
                    header=bytearray(old(addr,size));struct.pack_into('<I',header,296,2)
                    return bytes(header)
            return old(addr,size)
        self.reader.read=read
        with self.assertRaisesRegex(RuntimeError,'registry changed'):self.reader.snapshot()

    def test_formatted_tooltip_buffer_uses_distinct_layout(self):
        self.reader.types[self.p.base+0x1000]='.?AVCTextBox@@'
        self.p.put_string(0x22000000+304,'控制率：\x11G0.00%\x11!\n\x13naval_dominance_texticon\x13375',0x27000000)
        result=self.reader.snapshot()
        self.assertEqual(result['matches'][0]['text'],'控制率：0.00%\n[icon:naval_dominance_texticon]375')
        self.assertIsNone(result['matches'][0]['effective_visibility'])
        self.assertFalse(result['visibility_verified'])
    def test_callback_button_uses_verified_standard_base_layout(self):
        self.reader.types[self.p.base+0x1000]='.?AVCCallbackButtonStandard@@'
        self.p.put_string(0x22000000+392,'游戏维基')
        self.assertEqual(self.reader.snapshot()['matches'][0]['text'],'游戏维基')
    def test_heap_string_changed_during_read_is_explicit(self):
        self.p.put_string(0x25000000,'a long formatted tooltip',0x27000000)
        old=self.p.read;calls=[]
        def read(addr,size):
            if addr==0x25000000 and size==32:
                calls.append(addr)
                if len(calls)>1:
                    data=bytearray(old(addr,size));struct.pack_into('<Q',data,16,10);return bytes(data)
            return old(addr,size)
        value=decode_std_string(read,0x25000000)
        self.assertEqual(value['status'],'changed_during_read')
        self.assertNotIn('text',value)


    def test_formatted_runs_preserve_colors_icons_and_reset_order(self):
        runs=native_markup('Need \x11R20\x11! \x13steel\x13')
        self.assertEqual([r['kind'] for r in runs],['text','color','text','color_reset','text','icon'])
        self.assertEqual(runs[2],{'kind':'text','text':'20','color_code':'R'})
        self.assertIsNone(runs[4]['color_code'])
        self.assertEqual(runs[-1]['name'],'steel')
    def test_incomplete_formatting_is_explicit_and_preserved(self):
        self.assertEqual(native_markup('abc\x13unclosed')[-1],{'kind':'icon','name':'unclosed','color_code':None})
        self.assertEqual(native_markup('abc\x11')[-1],{'kind':'incomplete_control','raw':'\x11'})
    def test_unpaired_live_icon_markers_do_not_swallow_map_tooltip_text(self):
        text='\x13location_pointer  \x11Y克拉科夫\x11!\n拥有国家：\x11Y\x12POL 波兰\x11!\n当地时间：\x13daynight|1 \x11H13:00\x11!\n胜利点：\x13victory_points \x11G5\x11!'
        runs=native_markup(text)
        self.assertEqual([r['name'] for r in runs if r['kind']=='icon'],['location_pointer','daynight|1','victory_points'])
        self.assertEqual(next(r['tag'] for r in runs if r['kind']=='flag'),'POL')
        readable=''.join(r['text'] for r in runs if r['kind']=='text')
        for label in ('克拉科夫','波兰','13:00','胜利点','5'):
            self.assertIn(label,readable)
    def test_unpaired_icon_keeps_later_complete_icon_and_colors(self):
        runs=native_markup('\x13location_pointer  \x11Gshown\x11! \x13steel\x13')
        self.assertEqual(runs[0]['name'],'location_pointer')
        self.assertEqual(next(r for r in runs if r.get('text')=='shown')['color_code'],'G')
        self.assertEqual(runs[-1],{'kind':'icon','name':'steel','color_code':None})
    def test_icon_pair_cannot_cross_a_color_or_unknown_control(self):
        runs=native_markup('\x13left\x11G5\x11!\x12GER \x13right\x13')
        self.assertEqual([r['name'] for r in runs if r['kind']=='icon'],['left','right'])
        self.assertEqual(next(r['tag'] for r in runs if r['kind']=='flag'),'GER')
        self.assertEqual(next(r for r in runs if r.get('text')=='5')['color_code'],'G')
    def test_plain_native_reads_unpaired_icons_across_whitespace(self):
        from runtime_gui import plain_native
        text='\x13location_pointer  \x11Y克拉科夫\x11!\n\x13daynight|1 \x11H13:00\x11!'
        plain=plain_native(text)
        self.assertIn('[icon:location_pointer]',plain);self.assertIn('[icon:daynight|1]',plain)
        self.assertIn('克拉科夫',plain);self.assertIn('13:00',plain)
        self.assertEqual(plain.count('[icon:'),2)
    def test_plain_native_reads_icons_before_color_controls(self):
        from runtime_gui import plain_native
        self.assertEqual(plain_native('\x13left\x11G5\x11!\x13right\x13'),'[icon:left]5[icon:right]')
    def test_adjacent_complete_icons_still_parse_separately(self):
        from runtime_gui import plain_native
        text='\x13steel\x13\x13oil|1\x13'
        self.assertEqual([r['name'] for r in native_markup(text)],['steel','oil|1'])
        self.assertEqual(plain_native(text),'[icon:steel][icon:oil|1]')
    def test_native_flag_token_consumes_exactly_three_characters(self):
        from runtime_gui import plain_native
        runs=native_markup('\x12GER 德国')
        self.assertEqual(runs[0]['kind'],'flag');self.assertEqual(runs[0]['tag'],'GER');self.assertFalse(runs[0]['asset_identity_verified'])
        self.assertEqual(plain_native('\x12GER 德国'),'[flag:GER] 德国')
    def test_unknown_controls_preserve_color_and_normal_whitespace(self):
        runs=native_markup('\x11G前\x1b\t后\r\n\x11!')
        unknown=next(r for r in runs if r['kind']=='unknown_control')
        self.assertEqual(unknown['color_code'],'G');self.assertFalse(unknown['meaning_verified'])
        self.assertEqual(runs[-2]['text'],'\t后\r\n')
        self.assertEqual(runs[-1]['kind'],'color_reset')
    def test_multiple_unknown_controls_are_lossless_and_do_not_consume_text(self):
        text='a\x00b\x1bc\x12d';runs=native_markup(text)
        self.assertEqual([r['codepoint'] for r in runs if r['kind']=='unknown_control'],['U+0000','U+001B'])
        self.assertEqual(''.join(r.get('raw',r.get('text','')) for r in runs),text)

    def test_native_nested_color_reset_restores_previous_selector(self):
        runs=native_markup('\x11Rred \x11Ggreen\x11! red\x11! plain')
        self.assertEqual([(r['text'],r['color_code']) for r in runs if r['kind']=='text'],[('red ','R'),('green','G'),(' red','R'),(' plain',None)])
    def test_native_icon_token_bounds_and_fixed_atlas_tokens(self):
        from runtime_gui import plain_native
        runs=native_markup('\x13steel.dot \x14 \x1a07 end')
        self.assertEqual(runs[0]['name'],'steel');self.assertEqual(runs[1]['text'],'.dot ')
        self.assertEqual([(r['atlas_index'],r['frame']) for r in runs if r['kind']=='atlas_icon'],[(0,0),(3,7)])
        self.assertEqual(plain_native('\x14\x1a07'),'[atlas:0:0][atlas:3:7]')
        self.assertEqual(len(native_markup('\x13'+'a'*130)[0]['name']),128)
    def test_malformed_flag_and_atlas_payloads_remain_explicit(self):
        self.assertEqual(native_markup('\x12G')[-1],{'kind':'incomplete_flag','raw':'\x12G'})
        self.assertEqual(native_markup('\x1aX')[-1],{'kind':'incomplete_control','raw':'\x1aX'})
        self.assertEqual(native_markup('\x13 ')[0]['reason'],'empty_icon_token')
    def test_buffer_last_update_is_not_fabricated_from_capture_time(self):
        record=self.reader.snapshot()['matches'][0]
        self.assertIsNone(record['buffer_last_update_unix'])
        self.assertEqual(record['text_freshness'],'buffer_update_time_unknown')
        self.assertEqual(record['formatted_runs'][1]['text'],'+1%')


    def test_foreground_unavailable_is_unknown_not_game_false(self):
        result=self.reader.snapshot()
        self.assertFalse(result['foreground_start']['available'])
        self.assertIsNone(result['foreground_start']['is_bound_game'])
        self.assertFalse(result['foreground_required'])
    def test_foreground_change_does_not_fabricate_stable_visibility(self):
        samples=iter([{'available':True,'pid':42,'is_bound_game':True},
                      {'available':True,'pid':9,'is_bound_game':False}])
        self.p.foreground_metadata=lambda:next(samples)
        result=self.reader.snapshot()
        self.assertTrue(result['foreground_start']['is_bound_game'])
        self.assertFalse(result['foreground_end']['is_bound_game'])
        self.assertFalse(result['visibility_verified'])


    def configure_checkbox_label(self,text='Enabled'):
        from runtime_gui import CHECKBOX_LABEL_UPDATE_SIGNATURE
        gui=0x22000000;vt=self.p.base+0x2b465d8
        h=bytearray(self.p.blocks[gui]);struct.pack_into('<Q',h,0,vt);self.p.put(gui,h)
        self.reader.types[vt]='.?AVCCheckBox@@'
        self.p.put(vt+75*8,struct.pack('<Q',self.p.base+0x22c9bd0))
        self.p.put(self.p.base+0x22c9bd0,CHECKBOX_LABEL_UPDATE_SIGNATURE)
        self.p.put_string(gui+376,text,0x27000000)
        self.p.put(gui+176,struct.pack('<I',0))
        self.p.put(self.p.base+0x22c96a0,bytes.fromhex('83b9b0000000010f94c0c3'))
        return gui,vt
    def test_checkbox_selection_native_predicate_preserves_raw_state(self):
        gui,vt=self.configure_checkbox_label()
        for state in (0,1,2,0xffffffff):
            with self.subTest(state=state):
                self.p.put(gui+176,struct.pack('<I',state));result=self.reader.checkbox_selection(gui)
                self.assertEqual(result['raw_local_state'],state)
                self.assertEqual(result['engine_selected'],state==1)
                self.assertFalse(result['gameplay_value_verified']);self.assertIsNone(result['effective_visibility'])
    def test_checkbox_selection_changed_predicate_rejected(self):
        gui,vt=self.configure_checkbox_label();self.p.put(self.p.base+0x22c96a0,b'\0'*11)
        with self.assertRaisesRegex(RuntimeError,'predicate changed'):self.reader.checkbox_selection(gui)
    def test_checkbox_selection_changed_state_rejected(self):
        gui,vt=self.configure_checkbox_label();old=self.reader.read;calls=[]
        def read(addr,size):
            if addr==gui+176:
                calls.append(1)
                if len(calls)>1:return struct.pack('<I',1)
            return old(addr,size)
        self.reader.read=read
        with self.assertRaisesRegex(RuntimeError,'changed during read'):self.reader.checkbox_selection(gui)
    def test_checkbox_selection_wrong_layout_rejected(self):
        gui,vt=self.configure_checkbox_label();h=bytearray(self.p.blocks[gui]);struct.pack_into('<Q',h,0,self.p.base+0x3000);self.p.put(gui,h)
        self.reader.types[self.p.base+0x3000]='.?AVCCheckBox@@'
        with self.assertRaisesRegex(RuntimeError,'layout unsupported'):self.reader.checkbox_selection(gui)
    def test_checkbox_selection_exposed_in_snapshot_and_container(self):
        container,full=self.setup_container();gui,vt=self.configure_checkbox_label();self.p.put(gui+176,struct.pack('<I',1))
        self.assertTrue(self.reader.snapshot(native_type='CCheckBox')['matches'][0]['checkbox_selection']['engine_selected'])
        self.assertTrue(self.reader.container_children(container)['children'][0]['checkbox_selection']['engine_selected'])

    def test_checkbox_label_unicode_and_formatting(self):
        gui,vt=self.configure_checkbox_label('启用声音 §! \x11YEnabled\x11!')
        result=self.reader.snapshot(native_type='CCheckBox')
        self.assertEqual(result['match_count'],1)
        self.assertEqual(result['matches'][0]['text'],'启用声音 §! Enabled')
        self.assertTrue(result['matches'][0]['formatted_runs'])
    def test_checkbox_label_unsupported_method_rejected(self):
        gui,vt=self.configure_checkbox_label();self.p.put(vt+75*8,b'\0'*8)
        with self.assertRaisesRegex(RuntimeError,'implementation unsupported'):self.reader.checkbox_text(gui)
    def test_checkbox_label_changed_code_rejected(self):
        gui,vt=self.configure_checkbox_label();self.p.put(self.p.base+0x22c9bd0,b'\0'*100)
        with self.assertRaisesRegex(RuntimeError,'implementation changed'):self.reader.checkbox_text(gui)
    def test_checkbox_label_owner_mismatch_rejected(self):
        gui,vt=self.configure_checkbox_label();h=bytearray(self.p.blocks[gui]);struct.pack_into('<Q',h,104,0x12345678);self.p.put(gui,h)
        with self.assertRaisesRegex(RuntimeError,'ownership unavailable'):self.reader.checkbox_text(gui)
    def test_checkbox_label_method_change_during_read_rejected(self):
        gui,vt=self.configure_checkbox_label();old=self.reader.read;calls=[]
        def read(addr,size):
            if addr==vt+75*8:
                calls.append(1)
                if len(calls)>1:return b'\0'*size
            return old(addr,size)
        self.reader.read=read
        with self.assertRaisesRegex(RuntimeError,'changed during read'):self.reader.checkbox_text(gui)
    def test_container_checkbox_child_label(self):
        gui,full=self.setup_container();self.configure_checkbox_label('Option enabled')
        result=self.reader.container_children(gui)
        self.assertEqual(result['children'][0]['text'],'Option enabled')

    def configure_core_tooltip(self,shown=False):
        owner=0x28000000
        self.p.put(self.p.base+0x332f698,struct.pack('<Q',owner))
        self.p.put(owner,struct.pack('<Q',self.p.base+0x2968ff0))
        self.reader.types[self.p.base+0x2968ff0]='.?AVCInGameIdler@@'
        for slot,rva in {12:0x29eed0,15:0x29ece0,16:0x29ece0}.items():
            self.p.put(self.p.base+0x2968ff0+slot*8,struct.pack('<Q',self.p.base+rva))
        self.reader.types[self.p.base+0x1000]='.?AVCTextBox@@'
        self.p.put(owner+1256,struct.pack('<3Q',0x22000000,0x29000000,self.p.root))
        self.p.put(self.p.base+0x1000+15*8,struct.pack('<2Q',self.p.base+0x22a4440,self.p.base+0x22a4080))
        self.p.put(self.p.base+0x22ae0f0,bytes.fromhex('440fb641750fb6c24180e0f7c0e003440ac044884175'))
        self.p.put_string(0x23000000+40,'ToolTip')
        self.p.put_string(0x23000000+72,'interface/core.gui',0x24000000)
        text='Research\n--------------\n154 days'
        self.p.put_string(0x22000000+304,text,0x27000000)
        self.p.put_string(owner+88,text,0x27001000)
        self.p.put_string(owner+1152,'Research')
        self.p.put_string(owner+1184,'154 days')
        head=bytearray(self.p.blocks[0x22000000]);head[117]=8 if shown else 0;self.p.put(0x22000000,head)
        return owner
    def configure_menu_tooltip(self):
        owner=self.configure_core_tooltip(True)
        vt=self.p.base+0x2949d50
        self.p.put(owner,struct.pack('<Q',vt));self.reader.types[vt]='.?AVCFrontEndIdler@@'
        for slot,rva in {12:0x29eed0,15:0x29ece0,16:0x29ece0}.items():
            self.p.put(vt+slot*8,struct.pack('<Q',self.p.base+rva))
        return owner,vt
    def test_menu_tooltip_uses_verified_shared_base_binding(self):
        self.configure_menu_tooltip();result=self.reader.current_tooltip()
        self.assertEqual(result['owner_native_type'],'.?AVCFrontEndIdler@@')
        self.assertEqual(result['buffers']['title_buffer']['text'],'Research')
        self.assertTrue(result['engine_local_shown']);self.assertFalse(result['process_writes'])
    def test_menu_owner_vtable_mismatch_rejected(self):
        owner,vt=self.configure_menu_tooltip()
        self.reader.types[self.p.base+0x3000]='.?AVCFrontEndIdler@@'
        self.p.put(owner,struct.pack('<Q',self.p.base+0x3000))
        with self.assertRaisesRegex(RuntimeError,'vtable mismatch'):self.reader.current_tooltip()
    def test_menu_owner_method_mismatch_rejected(self):
        owner,vt=self.configure_menu_tooltip();self.p.put(vt+12*8,b'\0'*8)
        with self.assertRaisesRegex(RuntimeError,'owner methods unsupported'):self.reader.current_tooltip()
    def test_menu_owner_vtable_change_rejected(self):
        owner,vt=self.configure_menu_tooltip();old=self.reader.read;calls=[]
        def read(addr,size):
            if addr==owner and size==8:
                calls.append(1)
                if len(calls)>2:return struct.pack('<Q',self.p.base+0x3000)
            return old(addr,size)
        self.reader.read=read
        with self.assertRaisesRegex(RuntimeError,'owner binding changed'):self.reader.current_tooltip()

    def test_heap_string_rejects_same_length_payload_change(self):
        address=0x25000000;heap=0x26000000
        self.p.put_string(address,'a'*20,heap);old=self.p.read;calls=[]
        def read(addr,size):
            if addr==heap:
                calls.append(1)
                if len(calls)>1:return b'b'*size
            return old(addr,size)
        result=decode_std_string(read,address)
        self.assertEqual(result['status'],'changed_during_read');self.assertNotIn('text',result)
    def test_heap_string_rejects_disappearing_payload(self):
        address=0x25000000;heap=0x26000000
        self.p.put_string(address,'a'*20,heap);old=self.p.read;calls=[]
        def read(addr,size):
            if addr==heap:
                calls.append(1)
                if len(calls)>1:return None
            return old(addr,size)
        self.assertEqual(decode_std_string(read,address)['status'],'changed_during_read')
    def test_tooltip_payload_mutation_after_initial_decode_rejected(self):
        self.configure_core_tooltip();old=self.reader.read;calls=[]
        def read(addr,size):
            if addr==0x27000000:
                calls.append(1)
                if len(calls)>2:return b'x'*size
            return old(addr,size)
        self.reader.read=read
        with self.assertRaisesRegex(RuntimeError,'payloads changed'):self.reader.current_tooltip()
    def test_tooltip_buffer_agreement_states_do_not_claim_freshness(self):
        owner=self.configure_core_tooltip()
        cases=[('Same','Same','rendered_equals_combined'),('Old','','rendered_nonempty_combined_empty'),
               ('','New','combined_nonempty_rendered_empty'),('Old','New','rendered_differs_from_combined')]
        for rendered,combined,state in cases:
            with self.subTest(state=state):
                self.p.put_string(0x22000000+304,rendered);self.p.put_string(owner+88,combined)
                result=self.reader.current_tooltip();self.assertEqual(result['buffer_agreement'],state)
                self.assertFalse(result['active_tooltip_verified']);self.assertFalse(result['buffer_freshness_verified'])

    def test_hidden_core_tooltip_keeps_buffer_without_claiming_active(self):
        self.configure_core_tooltip()
        result=self.reader.current_tooltip()
        self.assertEqual(result['state'],'hidden_buffer')
        self.assertFalse(result['engine_local_shown'])
        self.assertEqual(result['buffers']['title_buffer']['text'],'Research')
        self.assertIsNone(result['buffer_last_update_unix'])
    def test_engine_shown_is_distinct_from_physical_visibility(self):
        self.configure_core_tooltip(True)
        result=self.reader.current_tooltip()
        self.assertEqual(result['state'],'engine_shown')
        self.assertTrue(result['engine_show_state_verified'])
        self.assertIsNone(result['effective_visibility'])
        self.assertTrue(result['rendered_matches_owner_combined'])
    def test_unknown_show_hide_method_rejected(self):
        self.configure_core_tooltip()
        self.p.put(self.p.base+0x1000+15*8,b'\0'*16)
        with self.assertRaisesRegex(RuntimeError,'methods unsupported'):self.reader.current_tooltip()
    def test_modified_state_setter_rejected(self):
        self.configure_core_tooltip()
        self.p.put(self.p.base+0x22ae0f0,b'\0'*20)
        with self.assertRaisesRegex(RuntimeError,'setter changed'):self.reader.current_tooltip()
    def test_core_binding_wrong_gui_rejected(self):
        owner=self.configure_core_tooltip()
        self.p.put(owner+1256,struct.pack('<3Q',0x22000000,0x29000000,0x12345678))
        with self.assertRaisesRegex(RuntimeError,'binding/type mismatch'):self.reader.current_tooltip()
    def test_core_state_change_during_capture_rejected(self):
        self.configure_core_tooltip()
        old=self.p.read;calls=[]
        def read(addr,size):
            if addr==0x22000000 and size==160:
                calls.append(addr)
                if len(calls)>1:
                    head=bytearray(old(addr,size));head[117]^=8;return bytes(head)
            return old(addr,size)
        self.reader.read=read
        with self.assertRaisesRegex(RuntimeError,'state changed'):self.reader.current_tooltip()


    def test_registry_slot_change_without_header_change_rejected(self):
        old=self.p.read;calls=[]
        def read(addr,size):
            if addr==0x21000100 and size==8:
                calls.append(addr)
                if len(calls)>1:return struct.pack('<Q',0x26000000)
            return old(addr,size)
        self.reader.read=read
        with self.assertRaisesRegex(RuntimeError,'contents changed'):self.reader.snapshot()
    def test_unreadable_final_registry_is_not_accepted_as_stable(self):
        old=self.p.read;calls=[]
        def read(addr,size):
            if addr==0x21000000 and size==8:
                calls.append(addr)
                if len(calls)>1:return None
            return old(addr,size)
        self.reader.read=read
        with self.assertRaisesRegex(RuntimeError,'contents changed'):self.reader.snapshot()

    def setup_icon(self):
        gui=0x22000000;vt=self.p.base+0x1000;svt=self.p.base+0x3000;sprite=0x28000000
        self.reader.types[vt]='.?AVCIcon@@';self.reader.types[svt]='.?AVCSprite@@'
        self.p.put(vt+78*8,struct.pack('<Q',self.p.base+0x22fb5e0))
        self.p.put(self.p.base+0x22fb5e0,bytes.fromhex('488b89e8000000488b0148ff6060'))
        self.p.put(self.p.base+0x22fe4f0,bytes.fromhex('8b81a0010000c3'))
        self.p.put(self.p.base+0x22fe900,bytes.fromhex('3b91a00100008991a00100007407c681a401000001c3'))
        self.p.put(gui+232,struct.pack('<Q',sprite));self.p.put(sprite,struct.pack('<Q',svt))
        self.p.put(svt+19*8,struct.pack('<Q',self.p.base+0x22fe900))
        self.p.put(svt+22*8,struct.pack('<Q',self.p.base+0x22fe4f0));self.p.put(sprite+416,struct.pack('<I',7))
        self.p.put(sprite+16,b'\0'*8)
        return gui,sprite
    def test_icon_frame_snapshot_preserves_unverified_meaning(self):
        self.setup_icon();result=self.reader.snapshot(native_type='CIcon')['matches'][0]['icon_frame']
        self.assertEqual(result['native_frame_value'],7)
        self.assertFalse(result['frame_meaning_verified']);self.assertFalse(result['asset_identity_verified'])
        self.assertIsNone(result['effective_visibility'])
    def test_icon_rejects_changed_native_getter(self):
        gui,sprite=self.setup_icon();self.p.put(self.p.base+0x22fe4f0,b'\0'*7)
        with self.assertRaisesRegex(RuntimeError,'implementation changed'):self.reader.icon_frame(gui)
    def test_known_non_frame_icons_preserve_explicit_unsupported_state(self):
        gui,sprite=self.setup_icon()
        for kind in ('.?AVCCorneredTileSprite@@','.?AV?$C2dPieChartTemplate@USPieVertex@@@@','.?AVCProgressbarSprite@@'):
            with self.subTest(kind=kind):
                self.reader.types[self.p.base+0x3000]=kind
                result=self.reader.icon_frame(gui)
                self.assertEqual(result['status'],'unsupported_non_frame_component')
                self.assertEqual(result['component_native_type'],kind)
                self.assertIsNone(result['native_frame_value'])
                self.assertFalse(result['asset_identity_verified'])
    def test_non_frame_icon_rejects_changed_binding(self):
        gui,sprite=self.setup_icon();self.reader.types[self.p.base+0x3000]='.?AVCCorneredTileSprite@@'
        old=self.reader.read;calls=[]
        def read(address,size):
            if address==gui+232:
                calls.append(address)
                if len(calls)>1:return struct.pack('<Q',sprite+16)
            return old(address,size)
        self.reader.read=read
        with self.assertRaisesRegex(RuntimeError,'changed during read'):self.reader.icon_frame(gui)
    def test_non_frame_icon_rejects_changed_component_header(self):
        gui,sprite=self.setup_icon();self.reader.types[self.p.base+0x3000]='.?AVCCorneredTileSprite@@'
        old=self.reader.read;calls=[]
        def read(address,size):
            if address==sprite and size==8:
                calls.append(address)
                if len(calls)>1:return struct.pack('<Q',self.p.base+0x4000)
            return old(address,size)
        self.reader.read=read
        with self.assertRaisesRegex(RuntimeError,'changed during read'):self.reader.icon_frame(gui)
    def test_snapshot_keeps_known_non_frame_icon_record(self):
        self.setup_icon();self.reader.types[self.p.base+0x3000]='.?AVCCorneredTileSprite@@'
        result=self.reader.snapshot(native_type='CIcon')['matches'][0]
        self.assertEqual(result['icon_frame']['status'],'unsupported_non_frame_component')
        self.assertIsNone(result['effective_visibility'])

    def test_war_progressbar_keeps_snapshot_without_inventing_frame(self):
        self.setup_icon();self.reader.types[self.p.base+0x3000]='.?AVCProgressbarSprite@@'
        result=self.reader.snapshot(native_type='CIcon')['matches'][0]['icon_frame']
        self.assertEqual(result['status'],'unsupported_non_frame_component');self.assertIsNone(result['native_frame_value'])

    def test_icon_rejects_wrong_sprite_type(self):
        gui,sprite=self.setup_icon();self.reader.types[self.p.base+0x3000]='.?AVCEditBox@@'
        with self.assertRaisesRegex(RuntimeError,'sprite type'):self.reader.icon_frame(gui)
    def test_icon_rejects_changing_frame(self):
        gui,sprite=self.setup_icon();old=self.reader.read;calls=[]
        def read(address,size):
            if address==sprite+416:
                calls.append(address)
                if len(calls)>1:return struct.pack('<I',8)
            return old(address,size)
        self.reader.read=read
        with self.assertRaisesRegex(RuntimeError,'changed during read'):self.reader.icon_frame(gui)

    def test_icon_animated_and_shield_use_verified_frame_methods(self):
        gui,sprite=self.setup_icon()
        for kind in ('.?AVCFrameAnimatedSprite@@','.?AVCShieldObject@@'):
            with self.subTest(kind=kind):
                self.reader.types[self.p.base+0x3000]=kind
                result=self.reader.icon_frame(gui)
                self.assertEqual(result['native_frame_value'],7)
                self.assertEqual(result['component_native_type'],kind)
    def test_icon_rejects_changed_binding(self):
        gui,sprite=self.setup_icon();old=self.reader.read;calls=[]
        def read(address,size):
            if address==gui+232:
                calls.append(address)
                if len(calls)>1:return struct.pack('<Q',sprite+16)
            return old(address,size)
        self.reader.read=read
        with self.assertRaisesRegex(RuntimeError,'changed during read'):self.reader.icon_frame(gui)

    def setup_icon_assets(self):
        gui,sprite=self.setup_icon();definition=0x29000000;vt=self.p.base+0x4000
        self.p.put(sprite+16,struct.pack('<Q',definition));self.p.put(definition,struct.pack('<Q',vt))
        self.reader.types[vt]='.?AVCSpriteType@@'
        self.p.put(vt+4*8,struct.pack('<Q',self.p.base+0x2241240))
        for rva,code in ((0x22fe930+0x27,'4889bb8001000048897b10'),(0x2355fd0+0x164,'488d51104533c0498bca'),(0x2241240+0x208,'488d51704533c0498bc9'),(0x2241240+0x230,'488d51504533c0498bc9')):
            self.p.put(self.p.base+rva,bytes.fromhex(code))
        self.p.put_string(definition+16,'GFX_test')
        self.p.put_string(definition+80,'gfx/FX/test.lua')
        self.p.put_string(definition+112,'gfx/test.dds')
        return gui,sprite,definition
    def test_icon_assets_return_references_without_claiming_texture_loaded(self):
        gui,sprite,definition=self.setup_icon_assets();result=self.reader.icon_frame(gui)
        self.assertTrue(result['asset_identity_verified'])
        assets=result['asset_references'];self.assertEqual(assets['identifier']['value'],'GFX_test')
        self.assertEqual(assets['texture_reference']['value'],'gfx/test.dds')
        self.assertFalse(assets['texture_loaded_verified']);self.assertFalse(assets['gameplay_meaning_verified'])
    def test_icon_assets_reject_changed_parser(self):
        gui,sprite,definition=self.setup_icon_assets();self.p.put(self.p.base+0x2355fd0+0x164,b'\0'*10)
        with self.assertRaisesRegex(RuntimeError,'implementation changed'):self.reader.icon_frame(gui)
    def test_icon_assets_reject_changed_inline_string(self):
        gui,sprite,definition=self.setup_icon_assets();old=self.reader.read;calls=[]
        def read(address,size):
            if address==definition+16 and size==32:
                calls.append(address)
                if len(calls)>2:return b'\0'*32
            return old(address,size)
        self.reader.read=read
        with self.assertRaisesRegex(RuntimeError,'changed during read'):self.reader.icon_frame(gui)
    def test_icon_unknown_definition_keeps_frame_but_marks_assets_unsupported(self):
        gui,sprite,definition=self.setup_icon_assets();self.reader.types[self.p.base+0x4000]='.?AVCUnknownSpriteType@@'
        result=self.reader.icon_frame(gui);self.assertEqual(result['native_frame_value'],7)
        self.assertFalse(result['asset_identity_verified']);self.assertEqual(result['asset_references']['status'],'unsupported_definition_type')

    def test_derived_icon_assets_preserve_inherited_identity_and_shader_offset(self):
        for kind in ('.?AVCFrameAnimatedSpriteType@@','.?AVCMaskedSpriteType@@'):
            with self.subTest(kind=kind):
                gui,sprite,definition=self.setup_icon_assets();vt=self.p.base+0x4000
                self.reader.types[vt]=kind;rva,code,shader_offset=ICON_DEFINITION_PARSERS[kind]
                self.p.put(vt+4*8,struct.pack('<Q',self.p.base+rva))
                self.p.put(self.p.base+rva,bytes.fromhex(code))
                self.p.put_string(definition+shader_offset,'shader.lua')
                if kind=='.?AVCMaskedSpriteType@@':
                    self.p.put_string(definition+536,'overlay.dds')
                    self.p.put_string(definition+504,'mask.tga')
                result=self.reader.icon_frame(gui)['asset_references']
                self.assertEqual(result['identifier']['value'],'GFX_test')
                self.assertEqual(result['texture_reference']['value'],'gfx/test.dds')
                self.assertEqual(result['shader_reference']['value'],'shader.lua')
                if kind=='.?AVCMaskedSpriteType@@':
                    self.assertEqual(result['texture_file_1_reference']['value'],'overlay.dds')
                    self.assertEqual(result['texture_file_2_reference']['value'],'mask.tga')
    def test_derived_icon_assets_reject_changed_delegate(self):
        gui,sprite,definition=self.setup_icon_assets();vt=self.p.base+0x4000
        kind='.?AVCFrameAnimatedSpriteType@@';self.reader.types[vt]=kind;rva,code,off=ICON_DEFINITION_PARSERS[kind]
        self.p.put(vt+4*8,struct.pack('<Q',self.p.base+rva));self.p.put(self.p.base+rva,b'\0'*len(bytes.fromhex(code)))
        with self.assertRaisesRegex(RuntimeError,'Derived icon definition parser changed'):self.reader.icon_frame(gui)

    def setup_shared_show_state(self):
        gui=0x22000000;vt=self.p.base+0x1000
        self.p.put(vt+120,struct.pack('<2Q',self.p.base+0x22a4440,self.p.base+0x22a4080))
        for rva,code in ((0x22a4440,'40534883ec20f6417510488bd97519b201e89a9c0000'),(0x22a4080,'40534883ec2033d2488bd9e860a00000'),(0x22ae0f0,'440fb641750fb6c24180e0f7c0e003440ac044884175')):
            self.p.put(self.p.base+rva,bytes.fromhex(code))
        return gui
    def test_shared_widget_shown_flag_preserves_physical_visibility_unknown(self):
        gui=self.setup_shared_show_state();header=bytearray(self.p.blocks[gui]);header[117]|=8;self.p.put(gui,header)
        result=self.reader.snapshot()['matches'][0]['engine_show_state']
        self.assertTrue(result['engine_local_shown']);self.assertEqual(result['state'],'engine_shown')
        self.assertIsNone(result['effective_visibility']);self.assertFalse(result['parent_visibility_verified'])
        header[117]&=~8;self.p.put(gui,header)
        self.assertEqual(self.reader.widget_show_state(gui)['state'],'engine_hidden')
    def test_shared_widget_rejects_changed_state_setter(self):
        gui=self.setup_shared_show_state();self.p.put(self.p.base+0x22ae0f0,b'\0'*19)
        with self.assertRaisesRegex(RuntimeError,'implementation changed'):self.reader.widget_show_state(gui)
    def test_shared_widget_unknown_methods_do_not_infer_flag_meaning(self):
        result=self.reader.widget_show_state(0x22000000)
        self.assertFalse(result['engine_show_state_verified']);self.assertIsNone(result['engine_local_shown'])
    def test_shared_widget_rejects_changing_flag_header(self):
        gui=self.setup_shared_show_state();old=self.reader.read;calls=[]
        def read(address,size):
            value=old(address,size)
            if address==gui and size==160:
                calls.append(address)
                if len(calls)>1:
                    value=bytearray(value);value[117]^=8;return bytes(value)
            return value
        self.reader.read=read
        with self.assertRaisesRegex(RuntimeError,'changed during read'):self.reader.widget_show_state(gui)

    def test_shown_filter_excludes_hidden_edit_before_input_decoding(self):
        gui=self.setup_shared_show_state();self.reader.types[self.p.base+0x1000]='.?AVCEditBox@@'
        def reject_edit(gui):raise AssertionError('Hidden edit text must not be read')
        self.reader.edit_text=reject_edit
        result=self.reader.snapshot(native_type='CEditBox',engine_state='shown')
        self.assertEqual(result['matches'],[]);self.assertEqual(result['engine_state_filter'],'shown')
        self.assertEqual(result['engine_state_filter_scope'],'top_level_widgets_only')
    def test_hidden_filter_keeps_verified_hidden_text(self):
        self.setup_shared_show_state();result=self.reader.snapshot(engine_state='hidden')
        self.assertEqual(result['matches'][0]['text'],'+1%')
        self.assertFalse(result['matches'][0]['engine_show_state']['engine_local_shown'])
    def test_engine_state_filter_unknown_state_is_not_treated_as_hidden(self):
        result=self.reader.snapshot(engine_state='hidden')
        self.assertEqual(result['match_count'],0)
    def test_engine_state_filter_rejects_invalid_values(self):
        for value in ('visible','',True,None):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'engine_state'):
                self.reader.snapshot(engine_state=value)

    def test_inline_string_rejects_same_length_payload_change(self):
        address=0x25000000;self.p.put_string(address,'old');old=self.p.read;calls=[]
        def read(addr,size):
            raw=old(addr,size)
            if addr==address and size==32:
                calls.append(addr)
                if len(calls)>1:
                    value=bytearray(raw);value[:3]=b'new';return bytes(value)
            return raw
        result=decode_std_string(read,address)
        self.assertEqual(result,{'status':'changed_during_read'})
        self.assertNotIn('text',result)
    def test_inline_string_rejects_disappearing_header(self):
        address=0x25000000;self.p.put_string(address,'old');old=self.p.read;calls=[]
        def read(addr,size):
            if addr==address and size==32:
                calls.append(addr)
                if len(calls)>1:return None
            return old(addr,size)
        self.assertEqual(decode_std_string(read,address)['status'],'changed_during_read')
    def test_stable_empty_inline_string_is_read_with_final_guard(self):
        address=0x25000000;self.p.put_string(address,'');old=self.p.read;calls=[]
        def read(addr,size):
            calls.append((addr,size));return old(addr,size)
        result=decode_std_string(read,address)
        self.assertEqual(result['status'],'read');self.assertEqual(result['text'],'')
        self.assertEqual(calls,[(address,32),(address,32)])

if __name__=='__main__':unittest.main()
