import struct,unittest
from runtime_gui import NativeGuiReader,SUPPORTED_HASH,GuiSnapshotChanged
from test_runtime_gui import FakeProcess
from regional_cache import read_regional_cache
class RegionalCacheTests(unittest.TestCase):
 def setUp(self):
  self.p=FakeProcess();self.r=NativeGuiReader(self.p,SUPPORTED_HASH);self.manager=0x27000000;self.ui=0x26000000;self.entry=0x28000000;self.context=0x30000000
  self.p.put(self.p.base+0x332f6a0,struct.pack('<Q',self.ui));self.p.put(self.ui+0x798,struct.pack('<Q',self.manager))
  for k in range(82):self.p.put(self.manager+24*(k+0xf0e),struct.pack('<QII',0,0,0))
 def bind(self,scope='region',active=True):
  self.p.put(self.manager+24*(22+0xf0e),struct.pack('<QII',self.entry,1,1));self.p.put(self.entry,bytes([0 if active else 1]))
  self.p.put(self.entry+0x438,struct.pack('<4Q',self.context if scope=='region' else 0,self.context if scope=='theater' else 0,123,0))
  vt,ty=(0x296d558,'.?AVCStrategicRegion@@') if scope=='region' else (0x29e5c50,'.?AVCTheaterGroup@@')
  self.p.put(self.context,struct.pack('<Q',self.p.base+vt));self.r.types[self.p.base+vt]=ty;self.p.put(self.context+8,struct.pack('<2I',1,77))
 def test_empty_world_is_not_generation(self):
  d=read_regional_cache(self.r);self.assertEqual(d['entries'],[]);self.assertFalse(d['fresh_message_generated'])
 def test_active_region_matches_actual_collector_key(self):
  self.bind();d=read_regional_cache(self.r)['entries'][0];self.assertEqual(d['native_alert_kind'],22);self.assertEqual(d['native_context_type'],'.?AVCStrategicRegion@@')
 def test_dismissed_entry_excluded(self):
  self.bind(active=False);self.assertEqual(read_regional_cache(self.r)['entries'],[])
 def test_theater_preserves_real_handle(self):
  self.bind('theater');self.assertEqual(read_regional_cache(self.r)['entries'][0]['native_context_handle'],[1,77])
 def test_context_cannot_be_wrong_type(self):
  self.bind();self.p.put(self.context,struct.pack('<Q',self.p.base+999))
  with self.assertRaisesRegex(RuntimeError,'type mismatch'):read_regional_cache(self.r)
 def test_changed_entry_rejected(self):
  self.bind();read=self.r.read;calls=0
  def changing(a,n):
   nonlocal calls
   if a==self.entry:
    calls+=1
    if calls>1:return b'\1'
   return read(a,n)
  self.r.read=changing
  with self.assertRaises(GuiSnapshotChanged):read_regional_cache(self.r)
if __name__=='__main__':unittest.main()
