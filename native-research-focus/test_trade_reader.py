import copy, struct, unittest
from trade_reader import read_trade_bindings
class Memory:
    base=0x140000000
    def __init__(self): self.mem={}; self.changed=False
    def put(self,p,fmt,*v):
        for i,b in enumerate(struct.pack(fmt,*v)):self.mem[p+i]=b
    def read(self,p,n):return bytes(self.mem.get(p+i,0) for i in range(n))
    def typename(self,p):return '.?AVCCountry@@' if p in (0x10000,0x20000) else None
    def vt(self,p,rva):self.put(p,'<Q',self.base+rva)
    def vec(self,p,data,vals,stride=8):
        self.put(p,'<Qii',data,len(vals),len(vals))
        for i,v in enumerate(vals):self.put(data+i*stride,'<Q',v)
def fixture():
    m=Memory();m.put(0x10008,'<I',10);m.put(0x20008,'<I',20)
    for c,r,t in [(0x10000,0x30000,10),(0x20000,0x40000,20)]:
        m.put(c+0x11f8,'<Q',r);m.vt(r,0x295c4b0);m.put(r+0x20,'<I',t)
    m.put(m.base+0x332f088,'<Q',0x50000);m.vt(0x50000,0x2943b18)
    m.vec(0x50028,0x60000,[0x70000,0x80000]);m.vt(0x70000,0x2943b48)
    m.vt(0x80000,0x2951508);m.put(0x80008,'<I',15875);m.put(0x80010,'<B',1);m.put(0x800d8,'<I',1);m.put(0x800e0,'<q',800000)
    m.vec(0x30740,0x90000,[0xa0000]);m.put(0x40728,'<Q',0xb0000);m.vec(0xb0018,0xc0000,[0xa0000])
    m.vt(0xa0000,0x295c410);m.put(0xa0080,'<Q',0x40000);m.put(0xa0088,'<I',10);m.put(0xa0090,'<Q',0x80000);m.put(0xa00e0,'<ii',3,2)
    m.put(m.base+0x35e1ab0,'<B3xI',1,50000);m.put(m.base+0x35e1ae0,'<Q',0x1000000)
    m.put(0x1000000+15875*32,'<6s',b'steel\0');m.put(0x1000000+15875*32+16,'<QQ',5,15)
    return m
class Tests(unittest.TestCase):
    def test_uninitialized_cache_rejected(self):
        m=fixture();m.put(m.base+0x35e1ab0,'<B',0)
        with self.assertRaisesRegex(RuntimeError,'initialized'):read_trade_bindings(m,0x10000,0x20000)
    def test_cross_bound_record(self):
        r=read_trade_bindings(fixture(),0x10000,0x20000)['records'][0]
        self.assertEqual((r['resource_id'],r['required_civilian_factories'],r['lended_civilian_factories']),('steel',3,2))
    def test_dynamic_oil(self):
        m=fixture();m.put(0x80008,'<I',50000);m.put(0x1000000+50000*32,'<4s',b'oil\0');m.put(0x1000000+50000*32+16,'<QQ',3,15)
        self.assertEqual(read_trade_bindings(m,0x10000,0x20000)['records'][0]['resource_id'],'oil')
    def test_owner_mismatch(self):
        m=fixture();m.put(0x40020,'<I',10)
        with self.assertRaisesRegex(RuntimeError,'owner'):read_trade_bindings(m,0x10000,0x20000)
    def test_missing_cross_membership(self):
        m=fixture();m.vec(0xb0018,0xc0000,[])
        with self.assertRaisesRegex(RuntimeError,'cross-membership'):read_trade_bindings(m,0x10000,0x20000)
    def test_unknown_token(self):
        m=fixture();m.put(0x80008,'<I',0xffffffff)
        with self.assertRaisesRegex(RuntimeError,'identity'):read_trade_bindings(m,0x10000,0x20000)
    def test_invalid_vector(self):
        m=fixture();m.put(0x50028,'<Qii',0x60000,1,2)
        with self.assertRaisesRegex(RuntimeError,'extent'):read_trade_bindings(m,0x10000,0x20000)
    def test_cached_token_name_duplicate_rejected(self):
        m=fixture();m.vec(0x50028,0x60000,[0x70000,0x80000,0x81000]);m.vt(0x81000,0x2951508)
        m.put(0x81008,'<I',15875);m.put(0x81010,'<B',1);m.put(0x810d8,'<I',2)
        with self.assertRaisesRegex(RuntimeError,'identity'):read_trade_bindings(m,0x10000,0x20000)
    def test_large_dynamic_registry_capacity_is_irrelevant_to_cache(self):
        m=fixture();m.put(m.base+0x35e1ac0,'<Qii',0xd0000,73728,50292)
        self.assertEqual(read_trade_bindings(m,0x10000,0x20000)['records'][0]['resource_id'],'steel')
if __name__=='__main__':unittest.main()
