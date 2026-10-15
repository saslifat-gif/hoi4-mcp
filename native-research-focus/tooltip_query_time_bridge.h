/* Include after tooltip_time_bridge.h to reuse selector and bounded receipt
 * encoding, paused/UI-thread gates and durable-intent tracking. The existing
 * native_time dispatch must persist execution_uncertain before entering here.
 * Separate dispatch kind/stage is recommended: this returns data, not Core. */
#include "native_tooltip_query.h"
static uintptr_t tooltip_native_query(uintptr_t fn,uintptr_t owner,uintptr_t out,uintptr_t widget,unsigned char secondary){
 return ((uintptr_t(*)(uintptr_t,uintptr_t,uintptr_t,unsigned char))fn)(owner,out,widget,secondary);
}
static void tooltip_native_destroy(uintptr_t fn,uintptr_t out){((void(*)(uintptr_t))fn)(out);}
static void tooltip_query_time_result(uintptr_t idler,uintptr_t world,const char *rid,const wchar_t *receipt_name,int tick){
 struct TooltipSelectorFields fields;
 if(!tooltip_selector_file(rid,&fields)){
  char rejected[256];snprintf(rejected,sizeof rejected,"{\"session_id\":\"%s\",\"request_id\":\"%s\",\"stage\":\"rejected\",\"reason\":\"tooltip_selector_invalid\",\"attempted\":false,\"native_result_generated\":false}",sid,rid);write_atomic(receipt_name,rejected);return;
 }
 struct TooltipSelector selector={fields.source,fields.name};struct TooltipQueryOutcome result;
 struct TooltipQueryCalls calls={readable,tooltip_paused_gate,tooltip_frame_ui_thread,tooltip_persisted_gate,tooltip_native_query,tooltip_native_destroy};
 tooltip_active_rid=rid;tooltip_has_intent=1;tooltip_owned_hwnd=NULL;
 int ok=tooltip_query(image,idler,&selector,rid,&calls,&result);
 tooltip_has_intent=0;tooltip_active_rid=NULL;
 if(*(int*)(world+0x468)!=tick){ok=0;result.reason="game_tick_changed_during_tooltip_query";}
 const char *stage=ok?"tooltip_result_generated":result.attempted?"execution_uncertain":"rejected";
 char out[65536];SIZE_T used=(SIZE_T)snprintf(out,sizeof out,
  "{\"session_id\":\"%s\",\"request_id\":\"%s\",\"stage\":\"%s\",\"reason\":\"%s\",\"attempted\":%s,\"native_result_generated\":%s,\"nonempty\":%s,\"native_disabled\":%s,\"native_returned\":%s,\"native_result_destroyed\":%s,\"native_tick\":%d,\"thread_id\":%lu,\"owned_window\":\"0x%llx\",\"widget_id\":\"0x%llx\",\"definition_id\":\"0x%llx\",\"tooltip_owner_id\":\"0x%llx\",\"tooltip_method\":\"0x%llx\",\"native_owner_target_before\":\"0x%llx\",\"native_owner_target_after\":\"0x%llx\",\"flag60\":%u,\"flag400\":%u,\"flag401\":%u,\"core_updated\":false,\"uses_keyboard_or_mouse\":false,\"physical_display_verified\":false,\"independent_asset_readback_required\":true}",
  sid,rid,stage,result.reason,result.attempted?"true":"false",ok?"true":"false",ok&&result.nonempty?"true":"false",result.native_disabled?"true":"false",result.returned?"true":"false",result.destroyed?"true":"false",tick,
  (unsigned long)GetCurrentThreadId(),(unsigned long long)(uintptr_t)tooltip_owned_hwnd,(unsigned long long)result.target,(unsigned long long)result.definition,
  (unsigned long long)result.tooltip_owner,(unsigned long long)result.tooltip_method,(unsigned long long)result.owner_target_before,(unsigned long long)result.owner_target_after,
  result.flag60,result.flag400,result.flag401);
 if(used>=sizeof out||!used)return;out[--used]=0;
 int encoded=tooltip_append_pair(out,sizeof out,&used,"source",fields.source)&&tooltip_append_pair(out,sizeof out,&used,"name",fields.name)&&
  tooltip_append_pair(out,sizeof out,&used,"raw_title",result.title)&&tooltip_append_pair(out,sizeof out,&used,"raw_body",result.body)&&
  tooltip_append_pair(out,sizeof out,&used,"raw_auxiliary",result.auxiliary);
 if(!encoded||used+2>=sizeof out){
  snprintf(out,sizeof out,"{\"session_id\":\"%s\",\"request_id\":\"%s\",\"stage\":\"execution_uncertain\",\"reason\":\"tooltip_receipt_text_limit\",\"attempted\":%s}",sid,rid,result.attempted?"true":"false");
 }else{out[used++]='}';out[used]=0;}
 write_atomic(receipt_name,out);
}
