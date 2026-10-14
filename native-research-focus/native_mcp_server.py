"""Additional native research/focus MCP server for an authorized GER test campaign."""
import argparse
from mcp.server.fastmcp import FastMCP
from native_controller import NativeController

def create_server(controller):
 from time_controller import TimeController
 time=TimeController(controller)
 from peacetime_agent import PeacetimeAgent
 agent=PeacetimeAgent(controller,controller.native/'ai-ledger.json')
 server=FastMCP('hoi4-native-peacetime',instructions='Experimental build-pinned native HOI4 research/focus selection for a bound Germany single-player test. No keyboard or mouse, no instant completion. Arm explicitly. Game must advance for daily callbacks. Keep the same request ID after uncertainty; never create a replacement ID. Busy slots and active focuses are protected. Poll receipt, then verify snapshot. Up to 64 requests per process; command allocations remain until process exit.')
 @server.tool()
 def hoi4_native_status()->dict:
  """Read the current native callback handshake, process binding and armed state."""
  return controller.status()
 @server.tool()
 def hoi4_native_arm(enabled:bool)->dict:
  """Arm/disarm this already authorized test session. Disarming removes unpublished input; in-flight execution can have started."""
  return controller.arm(enabled)
 @server.tool()
 def hoi4_native_snapshot()->dict:
  """Read coherent native research levels, completion, percentages and slot assignments, plus current focus and canonical IDs. Completion is checked against the engine completed list; percentages use the native completion threshold."""
  return controller.snapshot()
 @server.tool()
 def hoi4_popup_snapshot(kind:str='all',include_script_references:bool=False,language:str='en')->dict:
  """Read engine-shown events, generic popups and global alert/diplomatic-request containers. Text, option labels and icon metadata are read-only; no arming needed. Supported event IDs are native-bound; global alerts include native cached title/body text with unverified freshness. Physical visibility, option IDs/effects and other alert owners remain unresolved. Optional en/zh script references do not prove current messages."""
  from popup_reader import capture_popups
  return capture_popups(controller.path,controller.config['game_root'],kind,include_script_references,language)
 @server.tool()
 def hoi4_peacetime_snapshot(request_id:str)->dict:
  """Request/reconcile resources, factories, political power and available supported choices. Use a new 32-hex ID for a fresh read; repeat the same ID only to poll. Game must advance. Ready snapshots are immutable and dated; commands revalidate when executed."""
  return controller.peacetime_snapshot(request_id)
 @server.tool()
 def hoi4_start_research(request_id:str,technology:str,slot:int)->dict:
  """Start ordinary research in an EMPTY 1-based slot. Use a canonical technology ID and 32 lowercase hex request ID."""
  return controller.submit(request_id,'research',technology,slot)
 @server.tool()
 def hoi4_select_national_focus(request_id:str,focus:str)->dict:
  """Start an eligible focus in Germany's current tree only when no focus is active. Normal progress/time applies."""
  return controller.submit(request_id,'focus',focus)
 @server.tool()
 def hoi4_native_receipt(request_id:str)->dict:
  """Read durable pending/rejected/selection_verified/uncertain result. Does not republish."""
  return controller.receipt(request_id)
 @server.tool()
 def hoi4_time_status()->dict:
  """Read native pause, speed and clock with a fresh frame heartbeat; works while paused."""
  return time.status()
 @server.tool()
 def hoi4_set_paused(request_id:str,paused:bool)->dict:
  """Set pause or resume through the ordinary native command, including while paused. Requires arming."""
  return time.submit(request_id,'pause',paused)
 @server.tool()
 def hoi4_set_speed(request_id:str,speed:int)->dict:
  """Set normal game speed 1..5 using the native command. Does not change pause state."""
  return time.submit(request_id,'speed',speed)
 @server.tool()
 def hoi4_time_receipt(request_id:str)->dict:
  """Reconcile the same immutable time request ID after pending or uncertainty."""
  return time.receipt(request_id)
 @server.tool()
 def hoi4_ai_start(action_budget:int=5,wait_for_choices:bool=False)->dict:
  """Enable bounded GER research/focus policy. Set wait_for_choices to keep polling as research completes; default stops at idle. Already armed; budget 1..16."""
  return agent.start(action_budget,wait_for_choices)
 @server.tool()
 def hoi4_ai_step()->dict:
  """Advance one observe/decide/act/verify stage; poll until stopped. Uncertain intent is retained and never replaced."""
  return agent.step()
 @server.tool()
 def hoi4_ai_stop()->dict:
  """Stop new AI choices while retaining unresolved request IDs for reconciliation."""
  return agent.stop()
 return server
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--session-file',required=True);a=p.parse_args()
 create_server(NativeController(a.session_file)).run(transport='stdio')
