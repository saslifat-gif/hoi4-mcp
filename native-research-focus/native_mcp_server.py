"""Additional native research/focus MCP server for an authorized GER test campaign."""
import argparse
from mcp.server.fastmcp import FastMCP
from native_controller import NativeController

def create_server(controller):
 from time_controller import TimeController
 time=TimeController(controller)
 from peacetime_agent import PeacetimeAgent
 agent=PeacetimeAgent(controller,controller.native/'ai-ledger.json')
 server=FastMCP('hoi4-native-peacetime',instructions='Experimental build-pinned native HOI4 research/focus/law selection, advisor appointments and military orders for a bound Germany single-player test. No keyboard or mouse, no instant completion. Arm explicitly. Game must advance for daily callbacks. Keep the same request ID after uncertainty; never create a replacement ID. Busy slots and active focuses are protected. Poll receipt, then verify snapshot. Up to 64 requests per process; command allocations remain until process exit.')
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
  """Read engine-shown events, generic popups and global alert/diplomatic-request containers. Text, option labels and icon metadata are read-only; no arming needed. Supported event IDs are native-bound; global alerts include native cached title/body text with unverified freshness. Native option name keys and indices describe event definitions, not displayed availability or effects. World-tension popup text is also sampled. Physical visibility, option availability/effects and other owner-specific data remain unresolved. Optional en/zh script references do not prove current messages."""
  from popup_reader import capture_popups
  return capture_popups(controller.path,controller.config['game_root'],kind,include_script_references,language)
 @server.tool()
 def hoi4_regional_alert_cache()->dict:
  """Read active typed region/theater alert-cache contexts without formatting or changing them. Entries may lack a visible UI row; cached text freshness and UI entry existence are not implied."""
  return controller.regional_alert_cache()
 @server.tool()
 def hoi4_tooltip_assets()->dict:
  """Read the engine-owned tooltip buffers, active font and ordered native inline sprite/atlas/flag texture bindings. Includes hidden-buffer state and explicit unsupported controls. Read-only, no arming. Native texture identity does not prove physical display, GPU pixels or cache freshness."""
  return controller.tooltip_assets()
 @server.tool()
 def hoi4_generate_tooltip(request_id:str,source:str,name:str)->dict:
  """Generate a tooltip for an exact currently registered and locally shown GUI source/name through its normal native handler. Requires paused/armed session and owned UI thread. UI state writes occur, no input synthesis. Keep the same ID after uncertainty; tooltip_generated with nonempty=false is a completed empty result. Read tooltip_assets independently afterward."""
  return time.submit(request_id,'tooltip',0,selector={'source':source,'name':name})
 @server.tool()
 def hoi4_query_tooltip(request_id:str,source:str,name:str)->dict:
  """Query fresh native title/body/auxiliary for an exact locally shown widget through the ordinary explicit-widget getter. Requires paused/armed UI-frame session. Native owner tracking changes; Core rendering is not updated. Empty is a completed result, not a retry condition. Preserve the same ID after uncertainty."""
  return time.submit(request_id,'tooltipquery',0,selector={'source':source,'name':name})
 @server.tool()
 def hoi4_tooltip_result_assets(request_id:str)->dict:
  """Bind a completed immutable native tooltip result's ordered inline controls to loaded native sprites/atlas/flags using the current CoreToolTip font. Returns title/body/auxiliary separately. Read-only; result rendering and GPU pixels are not asserted."""
  return controller.tooltip_result_assets(request_id)
 @server.tool()
 def hoi4_world_tension_window(request_id:str,shown:bool)->dict:
  """Open/close the world-tension panel through its native UI handler while paused and armed. UI state writes occur. No input or gameplay setters; poll the same ID and read popup_snapshot(kind='world_tension') afterward."""
  return time.submit(request_id,'worldtension',shown)
 @server.tool()
 def hoi4_world_tension_view(request_id:str,view:str)->dict:
  """Select tension or wars through the bound native panel handler while paused and armed, then read popup_snapshot. No keyboard or mouse."""
  if view not in ('tension','wars'):raise ValueError('View must be tension or wars')
  return time.submit(request_id,'worldview',4 if view=='wars' else 0)
 @server.tool()
 def hoi4_notification_message(request_id:str,native_alert_kind:int)->dict:
  """Generate one currently shown global-alert message on the paused game thread. Requires arming and the fresh-read time backend. Native UI cache writes occur; no input or gameplay setters. Keep the same request ID to poll. Freshness is at the returned receipt tick, not later turns."""
  return time.submit(request_id,'alert',native_alert_kind)
 @server.tool()
 def hoi4_peacetime_snapshot(request_id:str)->dict:
  """Request/reconcile resources, factories, political power and available supported choices. Use a new 32-hex ID for a fresh read; repeat the same ID only to poll. Game must advance. Ready snapshots are immutable and dated; commands revalidate when executed."""
  return controller.peacetime_snapshot(request_id)
 @server.tool()
 def hoi4_politics_definitions(category:str,identifier:str|None=None)->dict:
  """Read installed script definitions for ideas (including law groups), characters (including advisor roles), decisions or resources. An optional exact identifier returns every matching block with its source and ordered rules. These are base-script references, not live choices, native handles or executable commands; mods/DLC precedence and dynamic conditions remain unverified."""
  from script_definitions import read_definitions
  return read_definitions(controller.config['game_root'],category,identifier)
 @server.tool()
 def hoi4_graphics_definitions(identifier:str)->dict:
  """Read every exact named .gfx declaration for a font or sprite, including ordered texture/frame fields and source hashes. Use an explicit definition name from native metadata or a script. Does not infer token-to-sprite mappings, atlas indices, DLC/mod precedence, loaded textures or rendered appearance."""
  from script_definitions import read_definitions
  return read_definitions(controller.config['game_root'],'graphics',identifier)
 @server.tool()
 def hoi4_prepare_law(request_id:str,group:str,law:str)->dict:
  """Prepare a source-bound law selection. Saves source intent only; this preparation does not execute, check current availability or compute cost. Use a separate request ID with hoi4_select_law to execute."""
  return controller.prepare_politics(request_id,{'kind':'law','group':group,'law':law})
 @server.tool()
 def hoi4_select_law(request_id:str,group:str,law:str)->dict:
  """Replace the current law in an exact native group under normal engine rules. Requires arming and game advancement. law_verified requires both membership and the engine-computed payment delta; it does not imply later effects. Keep the same request ID after uncertainty. Combined group:law ID is limited to 159 characters."""
  return controller.submit(request_id,'law',group+':'+law,0)
 @server.tool()
 def hoi4_country_advisors()->dict:
  """Read country-owned character and advisor-role IDs, active membership and coherent raw PP/CP balances. Listed roles are not verified eligible choices. Slot codes remain native numeric values; computed costs, CP display scale and slot names are not verified. Read-only, no arming required."""
  return controller.advisor_snapshot()
 @server.tool()
 def hoi4_appoint_advisor(request_id:str,character:str,role:str)->dict:
  """Appoint an exact country-owned character/role from hoi4_country_advisors under normal engine rules. Requires arming and game advancement. advisor_verified confirms active membership and both native political-power/command-power charges. Combined character:role is limited to 159 characters. Retain the same request ID after uncertainty."""
  return controller.submit(request_id,'advisor',character+':'+role,0)
 @server.tool()
 def hoi4_prepare_advisor(request_id:str,character:str,slot:str)->dict:
  """Prepare a character's exact advisor role in a slot. Saves intent only; no appointment, native handles, eligibility or cost verification."""
  return controller.prepare_politics(request_id,{'kind':'advisor','character':character,'slot':slot})
 @server.tool()
 def hoi4_decision_snapshot(include_registry:bool=False)->dict:
  """Read country decision-manager membership and native per-ID/target execution counters. Optional canonical registry is installed definitions, not eligible choices. No arming or writes; effects, availability and counter persistence are not implied."""
  return controller.decision_snapshot(include_registry)
 @server.tool()
 def hoi4_select_decision(request_id:str,decision:str)->dict:
  """Select an ordinary non-targeted decision by exact native registry ID under engine rules. Requires arming and game advancement. decision_verified requires one native counter increment and the engine-computed PP payment. Effects that change PP may leave execution uncertain: retain the ID and never replay it."""
  return controller.submit(request_id,'decision',decision,0)
 @server.tool()
 def hoi4_prepare_decision(request_id:str,category:str,decision:str,target_country:str|None=None)->dict:
  """Prepare a decision and optional country target, retaining category/decision rules. Saves intent only; no execution or target/availability/cost verification. State-targeted decisions are not supported."""
  return controller.prepare_politics(request_id,{'kind':'decision','category':category,'decision':decision,'target_country':target_country})
 @server.tool()
 def hoi4_trade_snapshot(partner_country:str)->dict:
  """Read canonical resources and existing imports from an exact native partner country. Independently checks importer/exporter ownership and reciprocal record membership. Requested/lended civilian factories and raw serialized delivery are separate; no delivery, eligibility or command-history guarantee."""
  return controller.trade_snapshot(partner_country)
 @server.tool()
 def hoi4_import_resource(request_id:str,partner_country:str,resource:str,factories:int)->dict:
  """Request an import by dedicating civilian factories under current native diplomacy, resource bounds and cost conversion. Requires arming/advancement. trade_verified confirms a changed native requested-CIC record with independent membership, not completed delivery. Keep the original ID after uncertainty and read trade_snapshot afterward."""
  return controller.submit(request_id,'trade',partner_country+':'+resource,factories)
 @server.tool()
 def hoi4_prepare_trade(request_id:str,partner_country:str,resource:str,factories:int)->dict:
  """Prepare a request to dedicate civilian factories to importing a resource. Saves intent only; no trade execution, partner availability, factory allocation or native quantity conversion is implemented/verified."""
  return controller.prepare_politics(request_id,{'kind':'trade','partner_country':partner_country,'resource':resource,'factories':factories})
 @server.tool()
 def hoi4_idea_snapshot(idea_id:str|None=None)->dict:
  """Read selected law/spirit IDs, or resolve one exact idea_id. Includes native group/category IDs, cost resource type and political-power balance. selected_for_country distinguishes a definition from an active idea. No pointers or writes; source overlays, computed costs and eligibility remain unverified."""
  return controller.idea_snapshot(idea_id)
 @server.tool()
 def hoi4_deployed_unit(unit_id:str)->dict:
  """Read one owned typed unit, its resolved division template, province and raw equipment/manpower rows. IDs are opaque native handles. Read-only; resource identity matching to a prior training entry is a separate verification."""
  return controller.deployed_unit_snapshot(unit_id)
 @server.tool()
 def hoi4_deployment_snapshot()->dict:
  """Read the owned native training queue, line IDs, template IDs and current raw manpower/equipment/training fields. Read-only; native readiness, location eligibility, availability and deployment outcome remain separate."""
  return controller.deployment_snapshot()
 @server.tool()
 def hoi4_division_templates()->dict:
  """Read country-listed native division-template IDs and their explicit names or automatic-name keys. Templates are identity references, not verified recruitable choices. No arming or writes."""
  return controller.deployment_snapshot(templates=True)
 @server.tool()
 def hoi4_reconcile_deployment(request_id:str)->dict:
  """Observe one original unresolved queue request against its retained pre-action report and independent typed inventory. Requires paused/disarmed state. Never resubmits or writes gameplay state; deployment_observed preserves the original native receipt."""
  return controller.reconcile_deployment(request_id)
 @server.tool()
 def hoi4_queue_division(request_id:str,template_id:str)->dict:
  """Create one ordinary training queue from an owned native division template. Requires arming and advancement. deployment_verified confirms new reciprocal queue/line identities, not readiness or deployed units. Preserve the ID after uncertainty."""
  return controller.submit(request_id,'queue',template_id,0)
 @server.tool()
 def hoi4_set_deployment_location(request_id:str,conveyor_id:str,province_id:int)->dict:
  """Set an owned training queue location under the full native location rules. Requires arming/advancement. Read deployment_snapshot afterward; no direct field setter or eligibility bypass."""
  return controller.submit(request_id,'deployloc',conveyor_id,province_id)
 @server.tool()
 def hoi4_deploy_division(request_id:str,line_id:str)->dict:
  """Deploy one owned training line only when the native equipment/manpower/training/capacity/location gate permits. deployment_verified confirms exactly one new owned unit with the source template, province and resources. Preserve the original ID after uncertainty."""
  return controller.submit(request_id,'deploy',line_id,0)
 @server.tool()
 def hoi4_orders_group_snapshot()->dict:
  """Read owned native theater managers, armies/army-groups, theaters and reciprocal unit membership. IDs resolve independently. Read-only; command eligibility and combat outcomes are not implied."""
  return controller.orders_group_snapshot()
 @server.tool()
 def hoi4_assign_theater(request_id:str,group_ids:list[str],theater_id:str|None=None)->dict:
  """Assign owned armies/groups to an existing theater, or create a new theater when theater_id is omitted. Use group IDs from orders_group_snapshot, not unit IDs or manager IDs. Normal native rules and recursive army-group children apply. Retain original IDs on uncertainty."""
  return controller.assign_theater(request_id,group_ids,theater_id)
 @server.tool()
 def hoi4_create_army_group(request_id:str,theatre_id:str,unit_ids:list[str])->dict:
  """Create an ordinary army containing 1..64 owned unit IDs and its parent army-group through the normal native command. Use a manager theatre_id from orders_group_snapshot. Requires arming/advancement. army_group_verified means typed new IDs and reciprocal unit/group/theater membership; retain IDs on uncertainty."""
  return controller.create_army_group(request_id,theatre_id,unit_ids)
 @server.tool()
 def hoi4_combat_snapshot()->dict:
  """Read typed active land-combat membership, provinces and opposing native country IDs. Independent reciprocal unit/side/world-manager binding; side roles and battle results are not inferred."""
  return controller.combat_snapshot()
 @server.tool()
 def hoi4_attack_province(request_id:str,unit_id:str,province_id:int)->dict:
  """Order ordinary movement into a foreign-controlled province during an existing native war. Preserves full native movement eligibility. military_verified confirms the path order only; observe combat_snapshot to verify actual engagement. Retain the original request on uncertainty."""
  return controller.submit(request_id,'attack',unit_id,province_id)
 @server.tool()
 def hoi4_stop_unit_combat(request_id:str,unit_id:str)->dict:
  """Request normal unit cancellation, preserving native combat restrictions. Requires active combat at execution; military_verified confirms cleared movement and decreased combat membership. Independently verify removal from the intended battle."""
  return controller.submit(request_id,'combatstop',unit_id,0)
 @server.tool()
 def hoi4_military_snapshot()->dict:
  """Read country-listed unit IDs, current/destination province IDs and path counts without input or process writes. Unit and province references are checked against native databases. This does not prove order eligibility or combat support."""
  return controller.military_snapshot()
 @server.tool()
 def hoi4_cancel_unit_movement(request_id:str,unit_id:str)->dict:
  """Cancel movement for one native ID in Germany's current unit list, using ordinary engine rules. Requires arming and game advancement. Preserve the request ID after uncertainty; military_verified means the native destination/path are cleared."""
  return controller.submit(request_id,'cancel',unit_id,0)
 @server.tool()
 def hoi4_move_unit(request_id:str,unit_id:str,province_id:int)->dict:
  """Order one country-owned unit to a native province ID under normal engine rules. Requires arming and game advancement. military_verified confirms the destination was set, not arrival. Keep the same request ID after uncertainty."""
  return controller.submit(request_id,'move',unit_id,province_id)
 @server.tool()
 def hoi4_order_units(request_id:str,order:str,unit_ids:list[str],province_id:int|None=None)->dict:
  """Move or cancel movement for 1..16 owned units, one native request at a time. order is move or cancel; only move takes a province. Poll the SAME batch ID and identical payload. Partial execution is possible; rejection/uncertainty stops remaining units and retains every child ID. orders_verified confirms destination/arrival or cleared movement at the returned tick, not combat success. Requires arming and game advancement."""
  return controller.order_units(request_id,order,unit_ids,province_id)
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
  """Read durable pending, rejected, verified or execution_uncertain result. Does not republish."""
  return controller.receipt(request_id)
 @server.tool()
 def hoi4_save_campaign(request_id:str)->dict:
  """Save this protected campaign through the ordinary native local-save path while paused/armed. Uses a unique session/request-owned basename and refuses existing final/temp files. save_file_observed is native file existence, not independent contents or restart/load proof. Keep the same ID after uncertainty."""
  return time.submit(request_id,'save',0)
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
