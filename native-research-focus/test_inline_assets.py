import struct
import unittest
from inline_assets import read_inline_assets,native_token_frame,INLINE_GUARDS,FLAG_GUARDS,native_sprite_hash
from test_font_binding import Memory
from runtime_gui import GuiSnapshotChanged

class InlineMemory(Memory):
    sprite_table=0xd00000
    sprite_node=0xd10000
    definition=0xd20000
    textures=0xe00000
    texture_records=0xe10000
    atlas=0xf00000
    def __init__(self,text='\x13test|2\x13'):
        super().__init__()
        for r,c in INLINE_GUARDS.items():self.put(self.base+r,bytes.fromhex(c))
        self.q(self.font_a+0x3620,self.graphics);self.string(self.widget+0x130,text)
        self.put(self.graphics+0x104,struct.pack('<IQ',2,self.sprite_table))
        self.put(self.sprite_table,struct.pack('<2Q',self.sprite_node,0))
        self.put(self.sprite_node,struct.pack('<2Q',self.definition,0))
        self.q(self.definition,self.base+0x2b3dd58);self.string(self.definition+0x10,'GFX_test')
        self.string(self.definition+0x70,'gfx/interface/test.dds')
        self.put(self.definition+0x90,struct.pack('<i',3));self.put(self.definition+0x1a0,struct.pack('<i',0))
        self.q(self.base+0x2b3dd58+0x78,self.base+0x22403e0)
        self.q(self.graphics+0x170,self.textures);self.q(self.textures+8,self.texture_records)
        self.put(self.textures+0x14,struct.pack('<i',2))
        self.put(self.texture_records,bytes(144))
        for i,path in enumerate(['gfx/interface/test.dds','gfx/interface/atlas.dds']):
            a=self.texture_records+72*i;self.q(a,0x10000000+i*0x1000);self.string(a+8,path);self.put(a+0x38,b'\1')
        self.q(self.font_a+0x3628,self.atlas);self.put(self.font_a+0x3630,b'\1');self.put(self.atlas,bytes(96))
        entry=struct.pack('<iiffii',1,10,1.0,1.0,16,16)
        self.put(self.atlas,entry);self.put(self.atlas+72,entry)

class InlineAssetTests(unittest.TestCase):
    def test_pinned_hash_unsigned_wrap_and_signed_bytes(self):
        self.assertEqual(native_sprite_hash('GFX_test'),0x7a61444c)
        self.assertEqual(native_sprite_hash('test'),0x611fdafc)
        self.assertEqual(native_sprite_hash('é'),0xfffc74a0)
    def test_unrelated_huge_or_cyclic_bucket_is_not_traversed(self):
        r=InlineMemory();r.put(r.sprite_table+8,struct.pack('<Q',r.sprite_node+0x1000))
        r.put(r.sprite_node+0x1000,struct.pack('<2Q',r.definition,r.sprite_node+0x1000))
        self.assertEqual(read_inline_assets(r,r.widget,max_nodes=1)['assets'][0]['resolved_name'],'GFX_test')
    def test_native_first_match_does_not_traverse_poisoned_tail(self):
        r=InlineMemory();r.put(r.sprite_node+8,struct.pack('<Q',r.sprite_node))
        self.assertEqual(read_inline_assets(r,r.widget)['assets'][0]['resolved_name'],'GFX_test')
    def test_native_result_uses_real_font_and_texture_without_changing_buffer(self):
        r=InlineMemory(text='current Core buffer');before=r._string(r.widget+0x130,65536)
        v=read_inline_assets(r,r.widget,raw_text='\x13test|2\x13')
        self.assertEqual(v['text_source'],'provided_native_result');self.assertEqual(v['assets'][0]['resolved_name'],'GFX_test')
        self.assertEqual(r._string(r.widget+0x130,65536),before)
        self.assertFalse(v['process_writes']);self.assertFalse(v['native_invocation'])
    def test_named_sprite_bound_to_actual_native_record(self):
        r=InlineMemory();v=read_inline_assets(r,r.widget);a=v['assets'][0]
        self.assertEqual(a['resolved_name'],'GFX_test');self.assertEqual(a['native_frame'],1)
        self.assertEqual(a['frame_count'],3);self.assertTrue(a['frame_in_range'])
        self.assertEqual(a['texture']['texture_reference'],'gfx/interface/test.dds')
        self.assertTrue(a['texture']['native_texture_nonnull'])
        self.assertFalse(a['texture']['file_bytes_verified']);self.assertFalse(v['physical_display_verified'])
    def test_texture_index_is_1a0_not_neighbor_a0(self):
        r=InlineMemory();r.put(r.definition+0xa0,struct.pack('<i',999))
        self.assertEqual(read_inline_assets(r,r.widget)['assets'][0]['texture']['native_texture_index'],0)
    def test_native_bare_name_fallback(self):
        r=InlineMemory();r.string(r.definition+0x10,'test')
        self.assertEqual(read_inline_assets(r,r.widget)['assets'][0]['resolved_name'],'test')
    def test_missing_native_sprite_remains_missing(self):
        r=InlineMemory('\x13missing\x13');a=read_inline_assets(r,r.widget)['assets'][0]
        self.assertEqual(a['status'],'native_sprite_not_found')
    def test_atlas_controls_zero_and_three_share_proven_record_mapping(self):
        r=InlineMemory('\x14 / \x1a03');a=read_inline_assets(r,r.widget)['assets']
        self.assertEqual([i['atlas_index'] for i in a],[0,3])
        self.assertEqual([i['native_frame'] for i in a],[0,3])
        self.assertEqual([i['texture']['texture_reference'] for i in a],['gfx/interface/atlas.dds']*2)
    def test_atlas_never_initialized_does_not_invoke_initializer(self):
        r=InlineMemory('\x14');r.put(r.font_a+0x3630,b'\0')
        self.assertEqual(read_inline_assets(r,r.widget)['assets'][0]['status'],'atlas_not_initialized')
    def test_masked_named_icon_uses_primary_texture_and_constant_one_frame(self):
        r=InlineMemory('\x13test\x13');r.q(r.definition,r.base+0x29e6dc0)
        r.q(r.base+0x29e6dc0+0x78,r.base+0x29c820)
        a=read_inline_assets(r,r.widget)['assets'][0]
        self.assertEqual(a['frame_count'],1);self.assertTrue(a['inline_renderer_uses_primary_texture_only'])
        self.assertEqual(a['texture']['texture_reference'],'gfx/interface/test.dds')
    def test_out_of_range_texture_index_preserved(self):
        r=InlineMemory();r.put(r.definition+0x1a0,struct.pack('<i',2))
        a=read_inline_assets(r,r.widget)['assets'][0]
        self.assertEqual(a['texture']['status'],'texture_index_out_of_range')
    def test_frame_uses_native_one_based_conversion_without_clamping(self):
        self.assertEqual(native_token_frame('test|0'),('test',-1))
        self.assertEqual(native_token_frame('test|'),('test',-1))
        self.assertEqual(native_token_frame('test|bad'),('test',0))
        self.assertEqual(native_token_frame('test'),('test',0))
        self.assertEqual(native_token_frame('test|4294967297'),('test',0))
    def test_texture_pointer_mutation_rejected(self):
        r=InlineMemory()
        def mutate(m,a,n,c):
            if a==m.texture_records and n==72 and c==2:m.q(a,0x12300000)
        r.mutate=mutate
        with self.assertRaises(GuiSnapshotChanged):read_inline_assets(r,r.widget)
    def test_text_payload_mutation_rejected(self):
        r=InlineMemory()
        def mutate(m,a,n,c):
            if a==m.widget+0x130 and n==32 and c==4:m.string(a,'changed')
        r.mutate=mutate
        with self.assertRaises(GuiSnapshotChanged):read_inline_assets(r,r.widget)
    def test_texture_not_loaded_is_distinct_from_binding(self):
        r=InlineMemory();r.q(r.texture_records,0)
        a=read_inline_assets(r,r.widget)['assets'][0]
        self.assertEqual(a['texture']['status'],'bound_native_texture_record')
        self.assertFalse(a['texture']['native_texture_nonnull'])

class FlagMemory(InlineMemory):
    tag_manager=0x1400000
    tag_head=0x1410000
    tag_buckets=0x1420000
    tag_node=0x1430000
    tags=0x1440000
    world=0x1450000
    country_to_flag=0x1460000
    flag_records=0x1470000
    flag_atlases=0x1480000
    def __init__(self,text='\x12GER'):
        super().__init__(text)
        for r,c in FLAG_GUARDS.items():self.put(self.base+r,bytes.fromhex(c))
        self.q(self.base+0x3330d98,self.tag_manager)
        self.q(self.tag_manager+0x78,1);self.q(self.tag_manager+0x50,self.tag_head)
        self.q(self.tag_manager+0x60,self.tag_buckets)
        self.put(self.tag_buckets,struct.pack('<4Q',self.tag_head,self.tag_head,self.tag_head,self.tag_head))
        h=0x811c9dc5
        for ch in b'GER':h=((h^ch)*0x1000193)&0xffffffff
        self.put(self.tag_buckets+16*(h&1),struct.pack('<2Q',self.tag_node,self.tag_node))
        self.string(self.tag_node+0x10,'GER');self.put(self.tag_node+0x30,struct.pack('<i',1))
        self.q(self.tag_manager+0x30,self.tags);self.put(self.tag_manager+0x3c,struct.pack('<i',3))
        self.put(self.tags,struct.pack('<3i',0,7,8))
        self.q(self.base+0x332f260,self.world);self.q(self.world+0x340,self.country_to_flag)
        self.put(self.country_to_flag,struct.pack('<8i',0,0,0,0,0,0,0,1))
        self.q(self.graphics+0x328b8,self.flag_records);self.put(self.graphics+0x328c4,struct.pack('<i',2))
        self.put(self.flag_records,bytes(48))
        for i in range(2):
            self.put(self.flag_records+24*i,struct.pack('<4f',0.25*i,0.,0.25,0.5))
            self.put(self.flag_records+24*i+0x10,bytes([1,i]))
        self.q(self.graphics+0x328a0,self.flag_atlases)
        self.put(self.flag_atlases,struct.pack('<2Q',0x30000000,0x30001000))

class FlagAssetTests(unittest.TestCase):
    def test_country_flag_native_world_mapping_and_atlas_identity(self):
        r=FlagMemory();a=read_inline_assets(r,r.widget)['assets'][0]
        self.assertEqual(a['status'],'verified_native_flag_atlas_identity')
        self.assertEqual(a['native_country_tag'],7);self.assertEqual(a['native_flag_index'],1)
        self.assertEqual(a['native_atlas_index'],1);self.assertEqual(a['native_texture_id'],'0x30001000')
        self.assertFalse(a['file_reference_verified']);self.assertFalse(a['gpu_pixels_verified'])
    def test_country_tag_missing_uses_native_first_tag_fallback(self):
        r=FlagMemory('\x12ZZZ');a=read_inline_assets(r,r.widget)['assets'][0]
        self.assertEqual(a['country_tag_lookup'],'native_first_tag_fallback')
        self.assertEqual(a['native_country_tag'],0);self.assertEqual(a['record_index'],0)
    def test_native_flag_record_out_of_range_falls_back_first_record(self):
        r=FlagMemory();r.put(r.country_to_flag+28,struct.pack('<i',5))
        a=read_inline_assets(r,r.widget)['assets'][0]
        self.assertEqual(a['native_flag_index'],5);self.assertEqual(a['record_index'],0)
    def test_world_absent_uses_native_tag_then_flag_record_fallback(self):
        r=FlagMemory();r.q(r.base+0x332f260,0)
        a=read_inline_assets(r,r.widget)['assets'][0]
        self.assertEqual(a['native_flag_index'],7);self.assertEqual(a['record_index'],0)
    def test_disabled_flag_does_not_read_or_invent_atlas_identity(self):
        r=FlagMemory();r.put(r.flag_records+24+0x10,b'\0')
        a=read_inline_assets(r,r.widget)['assets'][0]
        self.assertEqual(a['status'],'native_flag_record_disabled');self.assertNotIn('native_texture_id',a)
    def test_world_mapping_mutation_rejected(self):
        r=FlagMemory()
        def change(m,a,n,c):
            if a==m.country_to_flag+28 and c==2:m.put(a,struct.pack('<i',0))
        r.mutate=change
        with self.assertRaises(GuiSnapshotChanged):read_inline_assets(r,r.widget)
    def test_non_ascii_tag_encoding_not_guessed(self):
        r=FlagMemory('\x12德国国');a=read_inline_assets(r,r.widget)['assets'][0]
        self.assertEqual(a['status'],'unsupported_flag_tag_encoding')

if __name__=='__main__':unittest.main()
