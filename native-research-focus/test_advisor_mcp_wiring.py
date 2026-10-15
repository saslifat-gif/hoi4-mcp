"""Mock decorator/controller wiring only; not an MCP transport or live-game test."""
import importlib.util,sys,types,unittest
from pathlib import Path
from unittest.mock import Mock,patch

class Registry:
 def __init__(self,*args,**kwargs):self.tools={}
 def tool(self):
  def register(fn):self.tools[fn.__name__]=fn;return fn
  return register

class AdvisorMcpWiringTests(unittest.TestCase):
 def test_native_role_is_forwarded_without_slot_or_character_substitution(self):
  fake=types.ModuleType('mcp.server.fastmcp');fake.FastMCP=Registry
  spec=importlib.util.spec_from_file_location('advisor_test_server',Path(__file__).with_name('native_mcp_server.py'))
  module=importlib.util.module_from_spec(spec)
  with patch.dict(sys.modules,{'mcp.server.fastmcp':fake}):spec.loader.exec_module(module)
  controller=Mock();controller.native=Path('/unused-fixture')
  registry=module.create_server(controller)
  result=registry.tools['hoi4_appoint_advisor']('b'*32,'GER_ernst_udet','ernst_udet')
  controller.submit.assert_called_once_with('b'*32,'advisor','GER_ernst_udet:ernst_udet',0)
  self.assertIs(result,controller.submit.return_value)
  self.assertIs(registry.tools['hoi4_country_advisors'](),controller.advisor_snapshot.return_value)
  controller.arm.assert_not_called()
  registry.tools['hoi4_assign_theater']('c'*32,['53:1'])
  controller.assign_theater.assert_called_once_with('c'*32,['53:1'],None)
  registry.tools['hoi4_assign_theater']('d'*32,['53:1'],'68:2')
  self.assertEqual(controller.assign_theater.call_args.args,('d'*32,['53:1'],'68:2'))
  registry.tools['hoi4_attack_province']('e'*32,'6000:1',123)
  self.assertEqual(controller.submit.call_args.args,('e'*32,'attack','6000:1',123))
  registry.tools['hoi4_stop_unit_combat']('f'*32,'6000:1')
  self.assertEqual(controller.submit.call_args.args,('f'*32,'combatstop','6000:1',0))
  self.assertIs(registry.tools['hoi4_combat_snapshot'](),controller.combat_snapshot.return_value)

if __name__=='__main__':unittest.main()
