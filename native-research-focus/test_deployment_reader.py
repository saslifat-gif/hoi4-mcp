import struct
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from deployment_reader import read_country_deployment
from native_handle import HANDLE_SIGNATURES
from runtime_gui import GuiSnapshotChanged


class DeploymentReaderTests(unittest.TestCase):
    def setUp(self):
        self.base=0x140000000; self.mem={}; self.types={}; self.handles={}
        self.country,self.world,self.manager,self.conveyor,self.line,self.entry,self.template=range(0x100000,0x170000,0x10000)
        self.r=SimpleNamespace(base=self.base,read=self.read,typename=lambda a:self.types.get(a))
        self.typed(self.country,0x27e7360,'.?AVCCountry@@')
        self.typed(self.manager,0x295fc38,'.?AVCDeploymentStatus@@')
        self.put(self.country+8,'<I',1);self.put(self.country+0xf70,'<Q',self.manager)
        self.put(self.base+0x332f260,'<Q',self.world);self.put(self.world+0x468,'<i',10)
        self.vector(self.manager+0x48,[])
        for rva,code in HANDLE_SIGNATURES.items():self.raw(self.base+rva,bytes.fromhex(code))

    def raw(self,a,b):
        self.mem.update((a+i,v) for i,v in enumerate(b))
    def put(self,a,fmt,*v):self.raw(a,struct.pack(fmt,*v))
    def read(self,a,n):
        try:return bytes(self.mem[a+i] for i in range(n))
        except KeyError:return None
    def typed(self,a,vt,name):self.put(a,'<Q',self.base+vt);self.types[a]=name
    def vector(self,a,values,width=8):
        data=a+0x1000000
        self.put(a,'<QII',data,len(values),len(values))
        for i,v in enumerate(values):self.raw(data+i*width,v if isinstance(v,bytes) else struct.pack('<Q',v))
    def identity(self,a,f,s):self.put(a+8,'<II',f,s);self.handles[f,s]=a
    def snapshot(self):
        with patch('deployment_reader.resolve_native_handle',side_effect=lambda base,read,f,s:self.handles.get((f,s))):
            return read_country_deployment(self.r,self.country,self.world)
    def populated(self):
        self.typed(self.conveyor,0x295e100,'.?AVCMilitaryDeploymentConveyor@@');self.identity(self.conveyor,71,1)
        self.typed(self.line,0x295e0a8,'.?AVCMilitaryDeploymentLine@@');self.identity(self.line,72,1)
        self.typed(self.entry,0x295e020,'.?AVCMilitaryDeployment@@')
        self.vector(self.manager+0x48,[self.conveyor]);self.vector(self.conveyor+0x78,[self.line])
        self.put(self.conveyor+0x20,'<Q',self.template);self.put(self.template+0x1ec,'<I',1)
        self.typed(self.template,0x294f5b0,'.?AVCReferencedDivisionTemplate@@');self.identity(self.template,52,3)
        self.put(self.conveyor+0x4c,'<i',123);self.put(self.line+0x38,'<Q',self.conveyor)
        self.put(self.line+0x28,'<i',0);self.put(self.line+0x30,'<Q',self.entry)
        self.put(self.entry+0xb8,'<Q',self.line);self.put(self.entry+0x60,'<q',25000)
        self.put(self.entry+0xc0,'<B',170);self.put(self.entry+0xc4,'<B',0)
        self.vector(self.entry+0x28,[struct.pack('<QQq',1,0,300),struct.pack('<QQq',2,0,0)],24)
        self.vector(self.entry+0x78,[struct.pack('<Ii',1,900),struct.pack('<Ii',2,100)])
    def test_empty_country_manager(self):
        result=self.snapshot();self.assertEqual(result['conveyors'],[]);self.assertFalse(result['command_eligibility_verified'])
    def test_populated_readiness_keeps_unknown_native_gates(self):
        self.populated();row=self.snapshot()['conveyors'][0]['lines'][0]
        self.assertEqual(row['line_id'],'72:1');self.assertIsNone(row['native_deploy_eligible'])
        self.assertEqual(row['current_entry']['manpower'],1000);self.assertTrue(row['current_entry']['equipment_nonempty'])
        self.assertIsNone(row['current_entry']['training_threshold']);self.assertIsNone(row['current_entry']['location_eligible'])
    def test_dynamic_template_handle_is_typed_by_object(self):
        self.populated();self.identity(self.template,4714,4000)
        self.assertEqual(self.snapshot()['conveyors'][0]['template_id'],'4714:4000')
    def test_foreign_conveyor_rejected(self):
        self.populated();self.put(self.template+0x1ec,'<I',2)
        with self.assertRaisesRegex(RuntimeError,'another country'):self.snapshot()
    def test_wrong_parent_rejected(self):
        self.populated();self.put(self.line+0x38,'<Q',self.manager)
        with self.assertRaisesRegex(RuntimeError,'ownership'):self.snapshot()
    def test_wrong_entry_reciprocity_rejected(self):
        self.populated();self.put(self.entry+0xb8,'<Q',self.conveyor)
        with self.assertRaisesRegex(RuntimeError,'ownership'):self.snapshot()
    def test_stale_id_rejected(self):
        self.populated();self.handles[72,1]=self.conveyor
        with self.assertRaises(GuiSnapshotChanged):self.snapshot()
    def test_duplicate_line_rejected(self):
        self.populated();self.vector(self.conveyor+0x78,[self.line,self.line])
        with self.assertRaisesRegex(RuntimeError,'duplicate'):self.snapshot()
    def test_frame_change_rejected(self):
        old=self.r.read; n=[0]
        def changing(a,size):
            if a==self.world+0x468:
                n[0]+=1
                if n[0]>1:return struct.pack('<i',11)
            return old(a,size)
        self.r.read=changing
        with self.assertRaises(GuiSnapshotChanged):self.snapshot()
    def test_wrong_manager_type_rejected(self):
        self.types[self.manager]='.?AVCMilitaryDeployment@@'
        with self.assertRaisesRegex(RuntimeError,'type mismatch'):self.snapshot()

if __name__=='__main__':unittest.main()

class DivisionTemplateTests(unittest.TestCase):
    setUp = DeploymentReaderTests.setUp
    raw = DeploymentReaderTests.raw
    put = DeploymentReaderTests.put
    read = DeploymentReaderTests.read
    typed = DeploymentReaderTests.typed
    vector = DeploymentReaderTests.vector
    identity = DeploymentReaderTests.identity
    def capture_templates(self):
        from deployment_reader import read_country_division_templates
        with patch('deployment_reader.resolve_native_handle',side_effect=lambda base,read,f,s:self.handles.get((f,s))):
            return read_country_division_templates(self.r,self.country,self.world)
    def template_fixture(self):
        self.vector(self.country+0x1b8,[self.template])
        self.typed(self.template,0x294f5b0,'.?AVCReferencedDivisionTemplate@@')
        self.identity(self.template,52,3);self.put(self.template+0x1ec,'<I',1)
        for off,name in ((0x20,b'Infantry'),(0x40,b'')):
            self.raw(self.template+off,name+b'\0'*(16-len(name))+struct.pack('<QQ',len(name),15))
    def test_owned_template_names_and_ids(self):
        self.template_fixture();row=self.capture_templates()['templates'][0]
        self.assertEqual(row['template_id'],'52:3');self.assertEqual(row['explicit_name_raw'],'Infantry')
        self.assertIsNone(row['native_create_eligible'])
    def test_template_wrong_owner(self):
        self.template_fixture();self.put(self.template+0x1ec,'<I',2)
        with self.assertRaisesRegex(RuntimeError,'another country'):self.capture_templates()
    def test_template_wrong_handle_type(self):
        self.template_fixture();self.put(self.template+8,'<II',53,3)
        with self.assertRaises(GuiSnapshotChanged):self.capture_templates()
    def test_template_bad_name_extent(self):
        self.template_fixture();self.put(self.template+0x30,'<QQ',20,15)
        with self.assertRaisesRegex(RuntimeError,'name extent'):self.capture_templates()
