import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from combat_reader import read_country_land_combats
from native_handle import HANDLE_SIGNATURES
from runtime_gui import GuiSnapshotChanged


class CombatReaderTests(unittest.TestCase):
    def setUp(self):
        self.base=0x140000000;self.mem={};self.types={};self.ids={}
        self.country,self.world,self.unit,self.enemy,self.combat,self.side1,self.side2=range(0x100000,0x170000,0x10000)
        self.r=SimpleNamespace(base=self.base,read=self.read,typename=lambda a:self.types.get(a))
        self.typed(self.country,0x27e7360,'.?AVCCountry@@');self.put(self.country+8,'<I',1)
        self.put(self.base+0x332f260,'<Q',self.world);self.put(self.world+0x468,'<i',10)
        self.typed(self.world+0x260,0x2950688,'.?AVCCombatManager@@')
        self.vector(self.country+0x290,[self.unit]);self.vector(self.world+0x268,[])
        self.province=0x170000;self.put(self.world+0x2b0,'<Q',0x180000);self.put(self.world+0x2bc,'<i',4);self.put(0x180000+8,'<Q',self.province);self.put(self.province+0xa4,'<i',1)
        self.army(self.unit,1,1);self.vector(self.unit+0x1a8,[])
        for rva,code in HANDLE_SIGNATURES.items():self.raw(self.base+rva,bytes.fromhex(code))
    def raw(self,a,b):self.mem.update((a+i,x) for i,x in enumerate(b))
    def put(self,a,fmt,*v):self.raw(a,struct.pack(fmt,*v))
    def read(self,a,n):
        try:return bytes(self.mem[a+i] for i in range(n))
        except KeyError:return None
    def typed(self,a,vt,name):self.put(a,'<Q',self.base+vt);self.types[a]=name
    def vector(self,a,v):
        p=a+0x1000000;self.put(a,'<QII',p,len(v),len(v))
        if v:self.put(p,'<'+'Q'*len(v),*v)
    def army(self,a,serial,tag):
        self.typed(a,0x295a2b0,'.?AVCArmy@@');self.put(a+0x10,'<QII',self.base+0x295a490,51,serial)
        self.put(a+0x1d8,'<I',tag);self.ids[51,serial]=a+0x10
    def populated(self):
        self.army(self.enemy,2,2)
        self.typed(self.combat,0x29a83d8,'.?AVCLandCombat@@')
        self.put(self.combat+0x10,'<QII',self.base+0x29a84b8,64,1);self.ids[64,1]=self.combat+0x10
        self.put(self.combat+0x28,'<QQQ',self.side1,self.side2,self.province)
        for side,member in [(self.side1,self.unit),(self.side2,self.enemy)]:
            self.typed(side,0x29a82c0,'.?AVCLandCombatant@@');self.vector(side+0x20,[member]);self.vector(member+0x1a8,[self.combat])
        self.vector(self.world+0x268,[self.combat])
    def snapshot(self):
        with patch('combat_reader.resolve_native_handle',side_effect=lambda base,read,a,b:self.ids.get((a,b))):return read_country_land_combats(self.r,self.country,self.world)
    def test_empty_unit_combats(self):
        d=self.snapshot();self.assertEqual(d['combats'],[]);self.assertEqual(d['units'][0]['combat_ids'],[])
    def test_typed_reciprocal_combat(self):
        self.populated();d=self.snapshot();self.assertEqual(d['combats'][0]['combat_id'],'64:1');self.assertEqual(d['combats'][0]['province_id'],1)
        self.assertEqual(d['combats'][0]['sides'][1]['units'][0]['unit_id'],'51:2');self.assertTrue(d['bidirectional_membership_verified']);self.assertFalse(d['combat_result_verified'])
    def test_dynamic_unit_handle_is_not_an_object_type_code(self):
        self.populated();self.put(self.unit+0x18,'<II',4713,3966);self.ids[4713,3966]=self.unit+0x10
        self.assertEqual(self.snapshot()['units'][0]['unit_id'],'4713:3966')
    def test_combat_secondary_handle_required(self):
        self.populated();self.ids[64,1]=self.combat
        with self.assertRaises(GuiSnapshotChanged):self.snapshot()
    def test_missing_manager_combat_rejected(self):
        self.populated();self.vector(self.world+0x268,[])
        with self.assertRaisesRegex(RuntimeError,'world manager'):self.snapshot()
    def test_owned_unit_absent_from_side_rejected(self):
        self.populated();self.vector(self.side1+0x20,[])
        with self.assertRaisesRegex(GuiSnapshotChanged,'absent'):self.snapshot()
    def test_enemy_backreference_required(self):
        self.populated();self.vector(self.enemy+0x1a8,[])
        with self.assertRaisesRegex(GuiSnapshotChanged,'bidirectional'):self.snapshot()
    def test_same_unit_both_sides_rejected(self):
        self.populated();self.vector(self.side2+0x20,[self.unit])
        with self.assertRaisesRegex(GuiSnapshotChanged,'bidirectional'):self.snapshot()
    def test_cross_owner_country_list_rejected(self):
        self.put(self.unit+0x1d8,'<I',2)
        with self.assertRaisesRegex(RuntimeError,'country inventory'):self.snapshot()
    def test_changed_tick_rejected(self):
        old=self.r.read;n=[0]
        def changed(a,size):
            if a==self.world+0x468:
                n[0]+=1
                if n[0]>1:return struct.pack('<i',11)
            return old(a,size)
        self.r.read=changed
        with self.assertRaises(GuiSnapshotChanged):self.snapshot()

if __name__=='__main__':unittest.main()
