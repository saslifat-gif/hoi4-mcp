#ifndef HOI4_NATIVE_TRADE_H
#define HOI4_NATIVE_TRADE_H
/* Isolated integration wrapper. Caller pins executable/game thread and manages
   duplicate request ledger and engine command lifetime. Delivery is raw only. */
#include "native_trade_command_candidate.h"
#ifndef TRADE_RATE_FN
#define TRADE_RATE_FN(image) ((trade_rate_fn)((image)+0xca7cd0))
#endif
#ifndef TRADE_COST_FN
#define TRADE_COST_FN(image) ((trade_cost_fn)((image)+0xca8160))
#endif
#ifndef TRADE_LIMITS_FN
#define TRADE_LIMITS_FN(image) ((trade_limits_fn)((image)+0xcad5a0))
#endif
#ifndef TRADE_AVAILABLE
#define TRADE_AVAILABLE(image,economy) ((int32_t(*)(uintptr_t))((image)+0xe68350))(economy)
#endif
struct trade_outcome {
 const char *reason;int verified,cost_computed,offer_checked,record_verified;
 struct trade_record_observation before,after;trade_conversion conversion;struct trade_offer_observation offer;
 uint32_t importer_tag,exporter_tag;int32_t importer_index,exporter_index;
 uintptr_t resource,partner,command;uint32_t partner_tag;int32_t partner_index;
 int32_t requested_factories,resource_units,available_cic;
 int32_t required_before,required_after,lended_before,lended_after;
 int64_t native_cost_raw,max_resource_raw,existing_requested_raw;
 int64_t nominal_requested_raw,delivered_before_raw,delivered_after_raw;
};
/* Canonical country handle/index must resolve through the bound world's exact
   arrays. No index-zero/first-tag fallback is accepted for partner lookup. */
static uintptr_t trade_country_at(uintptr_t image,uintptr_t world,uint32_t tag,
 int(*readable)(const void*,size_t),int32_t *index){
 if(!tag||(int32_t)tag<=0||!readable((void*)(world+0x310),8)||!readable((void*)(world+0x340),8))return 0;
 uintptr_t indices=*(uintptr_t*)(world+0x340),countries=*(uintptr_t*)(world+0x310);
 uintptr_t slot=indices+(uintptr_t)tag*4;
 if(!indices||!countries||!readable((void*)slot,4))return 0;
 int32_t n=*(int32_t*)slot;if(n<0||!readable((void*)(countries+(uintptr_t)n*8),8))return 0;
 uintptr_t country=((uintptr_t*)countries)[n];
 if(!readable((void*)country,0x1200)||*(uintptr_t*)country!=image+0x27e7360||*(uint32_t*)(country+8)!=tag)return 0;
 *index=n;return country;
}
/* Return1 exact lookup;0 missing;-1 invalid/ambiguous native binding. */
static int trade_partner(uintptr_t image,uintptr_t world,const char *id,
 int(*readable)(const void*,size_t),int(*name)(uintptr_t,size_t,char*,size_t),
 uintptr_t *country,uint32_t *tag,int32_t *native_index){
 *country=0;*tag=0;*native_index=0;
 if(!id||strlen(id)!=3)return 0;
 uint32_t h=0x811c9dc5;
 for(int i=0;i<3;i++){unsigned char c=(unsigned char)id[i];if(c>=128||c==0)return 0;h=(h^c)*0x1000193u;}
 if(!readable((void*)(image+0x3330d98),8))return -1;
 uintptr_t manager=*(uintptr_t*)(image+0x3330d98);
 if(!readable((void*)manager,0x80))return -1;
 uint64_t mask=*(uint64_t*)(manager+0x78);
 uintptr_t head=*(uintptr_t*)(manager+0x50),buckets=*(uintptr_t*)(manager+0x60);
 if(mask>1048575||(mask&(mask+1))||!head||!buckets||!readable((void*)(buckets+16*(h&mask)),16))return -1;
 uintptr_t first=*(uintptr_t*)(buckets+16*(h&mask)),node=*(uintptr_t*)(buckets+16*(h&mask)+8);
 int index=-1,found=0;
 if(node!=head){
  for(int traversed=0;;traversed++){
   char value[160];if(traversed>=10000||!readable((void*)node,0x34)||!name(node,0x10,value,sizeof value))return -1;
   if(!strcmp(value,id)){if(found++)return -1;index=*(int32_t*)(node+0x30);}
   if(node==first)break;
   uintptr_t next=*(uintptr_t*)(node+8);if(!next||next==node||next==head)return -1;node=next;
  }
 }
 if(!found)return 0;
 uintptr_t tags=*(uintptr_t*)(manager+0x30);int count=*(int32_t*)(manager+0x3c);
 if(count<1||count>1000000||index<0||index>=count||!readable((void*)(tags+(uintptr_t)index*4),4))return -1;
 *tag=*(uint32_t*)(tags+(uintptr_t)index*4);*country=trade_country_at(image,world,*tag,readable,native_index);
 return *country?1:-1;
}
static enum politics_result trade_select(uintptr_t image,uintptr_t country,uintptr_t world,uint32_t tag,
 const char *partner_ascii,const char *resource_ascii,int32_t factories,const char *rid,
 int(*readable)(const void*,size_t),int(*native_name)(uintptr_t,size_t,char*,size_t),
 int(*intent)(const char*),struct trade_outcome *out){
 memset(out,0,sizeof *out);out->reason="trade_binding_changed";out->requested_factories=factories;out->importer_tag=tag;
 if(!resource_ascii||!resource_ascii[0]||factories<=0){out->reason="invalid_trade_arguments";return POLITICS_BAD_ARGUMENT;}
 if(!readable((void*)(image+0x332f260),8)||*(uintptr_t*)(image+0x332f260)!=world)return POLITICS_BINDING_CHANGED;
 int32_t actor_index=0;
 if(trade_country_at(image,world,tag,readable,&actor_index)!=country)return POLITICS_BINDING_CHANGED;
 int found=trade_partner(image,world,partner_ascii,readable,native_name,&out->partner,&out->partner_tag,&out->partner_index);
 if(found<=0){out->reason=found==0?"unknown_trade_partner":"trade_partner_binding_changed";return found==0?POLITICS_BAD_ARGUMENT:POLITICS_BINDING_CHANGED;}
 out->importer_index=actor_index;out->exporter_tag=out->partner_tag;out->exporter_index=out->partner_index;
 if(out->partner==country){out->reason="trade_partner_is_actor";return POLITICS_BAD_ARGUMENT;}
 struct trade_binding b;
 if(!trade_bind(image,country,out->partner,resource_ascii,readable,native_name,&b)){out->reason="trade_resource_or_owner_binding_changed";return POLITICS_BINDING_CHANGED;}
 out->resource=b.resource;
 struct trade_record_observation before,after;
 if(!trade_record(image,&b,readable,&before))return POLITICS_BINDING_CHANGED;
 out->before=before;out->required_before=before.required_cic;out->lended_before=before.lended_cic;out->delivered_before_raw=before.delivered_raw;
 if(before.pointer&&before.required_cic==factories){out->reason="trade_already_requested";return POLITICS_BAD_ARGUMENT;}
 uintptr_t economy=*(uintptr_t*)(country+0xf68);
 if(!readable((void*)economy,0x3b4))return POLITICS_BINDING_CHANGED;
 out->available_cic=TRADE_AVAILABLE(image,economy);
 int32_t importer[2]={(int32_t)tag,actor_index},exporter[2]={(int32_t)out->partner_tag,out->partner_index};
 trade_conversion plan;
 if(!trade_convert_factories(TRADE_RATE_FN(image),TRADE_COST_FN(image),(void*)b.resource,importer,exporter,factories,out->available_cic,before.lended_cic,&plan)){
  out->reason="trade_factory_conversion_or_budget_rejected";return POLITICS_BAD_ARGUMENT;
 }
 out->conversion=plan;out->cost_computed=1;out->native_cost_raw=plan.native_cost_raw;out->resource_units=plan.resource_units;
 struct trade_offer_observation offer;
 int allowed=trade_offer_allows(TRADE_LIMITS_FN(image),&b,importer,&plan,&offer);
 out->offer=offer;out->offer_checked=1;out->max_resource_raw=offer.max_raw_units;out->existing_requested_raw=offer.existing_requested_raw_units;
 if(!allowed){out->reason="native_trade_offer_rejected";return POLITICS_RULES_REJECTED;}
 enum politics_result result=trade_construct(image,&b,&plan,rid,readable,intent,&out->command);
 out->reason="trade_construction_failed";if(result!=POLITICS_OBJECT_CONSTRUCTED)return result;
 int observed=0;out->reason="native_rules_rejected";
 result=trade_execute_bound(image,out->command,&b,&plan,NULL,rid,readable,intent,&after,&observed);
 if(result!=POLITICS_EXECUTION_RETURNED){if(result==POLITICS_BINDING_CHANGED)out->reason="trade_binding_changed";return result;}
 out->reason="trade_postcondition_failed";
 if(!readable((void*)(image+0x332f260),8)||*(uintptr_t*)(image+0x332f260)!=world||
    trade_country_at(image,world,tag,readable,&actor_index)!=country||actor_index!=out->importer_index)return result;
 uintptr_t partner=0;uint32_t partner_tag=0;int32_t partner_index=0;
 if(trade_partner(image,world,partner_ascii,readable,native_name,&partner,&partner_tag,&partner_index)!=1||partner!=out->partner||partner_tag!=out->partner_tag||partner_index!=out->partner_index)return result;
 struct trade_binding rebound;
 if(!trade_bind(image,country,partner,resource_ascii,readable,native_name,&rebound)||rebound.resource!=b.resource||
    rebound.import_resources!=b.import_resources||rebound.export_resources!=b.export_resources||!trade_record(image,&rebound,readable,&after))return result;
 out->after=after;out->record_verified=after.pointer!=0;out->required_after=after.required_cic;out->lended_after=after.lended_cic;out->delivered_after_raw=after.delivered_raw;
 if(!observed||!after.pointer||after.required_cic!=factories||before.required_cic==after.required_cic||
    !trade_nominal_requested(TRADE_RATE_FN(image),&rebound,importer,exporter,&after,&out->nominal_requested_raw)||
    out->nominal_requested_raw!=plan.native_rate_raw)return result;
 out->verified=1;out->reason="native_trade_request_verified";return result;
}
#endif
