import struct
import unittest
from font_binding import read_font_binding,CODE_GUARDS
from runtime_gui import decode_std_string,GuiSnapshotChanged

class Memory:
    base=0x140000000
    root=0x500000
    widget=0x600000
    graphics=0x700000
    sprite=0x800000
    font_a=0x900000
    font_b=0x910000
    node_a=0xa00000
    node_b=0xa10000
    table=0xb00000
    def __init__(self):
        self.bytes={};self.calls={};self.mutate=None;self.guard_count=0;self.heap=0xc00000
        for r,code in CODE_GUARDS.items():self.put(self.base+r,bytes.fromhex(code))
        self.q(self.widget,self.base+0x2b421d8);self.q(self.widget+104,self.root)
        self.q(self.widget+0x80,self.graphics);self.q(self.widget+0x88,self.sprite)
        self.q(self.widget+0x190,self.font_a)
        self.q(self.graphics,self.base+0x2b3d5f8);self.q(self.sprite,self.base+0x2b47f60)
        self.q(self.sprite+0x228,self.graphics)
        self.q(self.base+0x2b47f60+0x188,self.base+0x22d69d0)
        self.string(self.widget+0xb8,'fontA');self.string(self.sprite+0x208,'fontA')
        self.put(self.graphics+0xd4,struct.pack('<IQ',3,self.table))
        self.put(self.table,struct.pack('<3Q',self.node_b,0,self.node_a))
        self.put(self.node_a,struct.pack('<2Q',self.font_a,0));self.put(self.node_b,struct.pack('<2Q',self.font_b,0))
        for obj,vt,name in [(self.font_a,0x29e6be8,'fontA'),(self.font_b,0x2b41888,'fontB')]:
            self.q(obj,self.base+vt);self.q(obj+0x48,self.graphics);self.string(obj+0x10,name)
    def put(self,a,b):self.bytes.update({a+i:v for i,v in enumerate(b)})
    def q(self,a,v):self.put(a,struct.pack('<Q',v))
    def string(self,a,s):
        data=s.encode();header=bytearray(32)
        if len(data)<=15:header[:len(data)]=data;cap=15
        else:
            pointer=self.heap;self.heap+=0x1000;self.put(pointer,data);struct.pack_into('<Q',header,0,pointer);cap=max(16,len(data))
        struct.pack_into('<QQ',header,16,len(data),cap);self.put(a,header)
    def read(self,a,n):
        key=(a,n);self.calls[key]=self.calls.get(key,0)+1
        if self.mutate:self.mutate(self,a,n,self.calls[key])
        try:return bytes(self.bytes[a+i] for i in range(n))
        except KeyError:return None
    def _string(self,a,n):return decode_std_string(self.read,a,n)
    def _guard_root(self):self.guard_count+=1

class FontBindingTests(unittest.TestCase):
    def test_exact_drawable_font_and_independent_cached_pointer(self):
        r=Memory();v=read_font_binding(r,r.widget)
        self.assertEqual(v['selected_font']['object_id'],hex(r.font_a))
        self.assertEqual(v['lookup_outcome'],'exact_name');self.assertTrue(v['requested_names_match'])
        self.assertTrue(v['widget_cached_font_matches_selected']);self.assertEqual(r.guard_count,2)
        self.assertFalse(v['font_texture_identity_verified']);self.assertFalse(v['physical_display_verified'])
    def test_game_graphics_zero_offset_base_supported(self):
        r=Memory();r.q(r.graphics,r.base+0x294a338)
        self.assertEqual(read_font_binding(r,r.widget)['selected_font']['name'],'fontA')
    def test_native_missing_name_fallback_first_bucket(self):
        r=Memory();r.string(r.sprite+0x208,'missing')
        v=read_font_binding(r,r.widget)
        self.assertEqual(v['selected_font']['object_id'],hex(r.font_b))
        self.assertEqual(v['lookup_outcome'],'native_first_font_fallback')
        self.assertFalse(v['requested_names_match']);self.assertFalse(v['widget_cached_font_matches_selected'])
    def test_drawable_name_wins_over_widget_script_like_name(self):
        r=Memory();r.string(r.sprite+0x208,'fontB')
        v=read_font_binding(r,r.widget)
        self.assertEqual(v['selected_font']['name'],'fontB');self.assertFalse(v['requested_names_match'])
    def test_duplicate_font_name_rejected(self):
        r=Memory();r.string(r.font_b+0x10,'fontA')
        with self.assertRaisesRegex(RuntimeError,'Ambiguous'):read_font_binding(r,r.widget)
    def test_cyclic_node_rejected(self):
        r=Memory();r.q(r.node_b+8,r.node_b)
        with self.assertRaisesRegex(RuntimeError,'cyclic'):read_font_binding(r,r.widget)
    def test_mutated_bucket_table_rejected(self):
        r=Memory()
        def change(m,a,n,c):
            if a==m.table and c==2:m.q(m.table,0)
        r.mutate=change
        with self.assertRaises(GuiSnapshotChanged):read_font_binding(r,r.widget)
    def test_heap_payload_mutation_rejected(self):
        r=Memory();long_name='long_game_font_name';r.string(r.sprite+0x208,long_name)
        payload=struct.unpack('<Q',r.read(r.sprite+0x208,8))[0]
        def change(m,a,n,c):
            if a==payload and c==2:m.put(payload,b'x'+long_name[1:].encode())
        r.mutate=change
        with self.assertRaises(GuiSnapshotChanged):read_font_binding(r,r.widget)
    def test_wrong_graphics_owner_rejected(self):
        r=Memory();r.q(r.sprite+0x228,0xdead0000)
        with self.assertRaisesRegex(RuntimeError,'ownership'):read_font_binding(r,r.widget)
    def test_font_graphics_owner_rejected(self):
        r=Memory();r.q(r.font_a+0x48,0xdead0000)
        with self.assertRaisesRegex(RuntimeError,'ownership'):read_font_binding(r,r.widget)
    def test_extent_bound_rejected(self):
        r=Memory()
        with self.assertRaisesRegex(RuntimeError,'extent'):read_font_binding(r,r.widget,max_buckets=2)
    def test_code_guard_failure_rejected(self):
        r=Memory();r.put(r.base+0x22d6e03,b'\xcc')
        with self.assertRaisesRegex(RuntimeError,'implementation'):read_font_binding(r,r.widget)
    def test_unsupported_font_type_rejected(self):
        r=Memory();r.q(r.font_a,r.base+123)
        with self.assertRaisesRegex(RuntimeError,'font type'):read_font_binding(r,r.widget)
if __name__=='__main__':unittest.main()
