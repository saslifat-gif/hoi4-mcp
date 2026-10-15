#ifndef HOI4_NATIVE_DECISION_CANDIDATE_H
#define HOI4_NATIVE_DECISION_CANDIDATE_H
/* Isolated candidate: pinned executable, game-thread/world binding and request
 * duplicate ledger are caller obligations. No deployment/live result is implied.
 * Normal SelectDecision validates and applies effects/costs inside the engine. */
#include "native_politics.h"
#include <limits.h>
#ifndef DECISION_COST
#define DECISION_COST(fn,definition,out,tag) ((int64_t*(*)(uintptr_t,int64_t*,const uint32_t*,uintptr_t))(fn))((definition),(out),(tag),0)
#endif
struct decision_outcome {
 const char *reason;uintptr_t requested;
 int verified,cost_computed,counter_verified,payment_verified;
 int32_t counter_before,counter_after;int64_t pp_cost,pp_before,pp_after;
};
enum decision_lookup_result {DECISION_REGISTRY_CHANGED=-1,DECISION_NOT_FOUND,DECISION_FOUND,DECISION_AMBIGUOUS};
static enum decision_lookup_result decision_resolve(uintptr_t image,const char *id,
 int(*can_read)(const void*,size_t),int(*read_name)(uintptr_t,size_t,char*,size_t),uintptr_t *out){
 *out=0;
 /*170612 publishes the CDecisionDatabase;725f50 appends canonical definitions
  * at+28;722cc0 looks up matching hashed names. Index0 is its null sentinel. */
 if(!can_read((void*)(image+0x332ee80),8))return DECISION_REGISTRY_CHANGED;
 uintptr_t db=*(uintptr_t*)(image+0x332ee80);
 if(!can_read((void*)db,0x38)||*(uintptr_t*)db!=image+0x27eb640)return DECISION_REGISTRY_CHANGED;
 uintptr_t array=*(uintptr_t*)(db+0x28);
 int capacity=*(int*)(db+0x30),count=*(int*)(db+0x34);
 if(count<1||count>capacity||capacity>100000||!can_read((void*)array,(size_t)count*8))return DECISION_REGISTRY_CHANGED;
 for(int i=0;i<count;i++){
  uintptr_t def=((uintptr_t*)array)[i];char name[256];
  if(!can_read((void*)def,0xd38))return DECISION_REGISTRY_CHANGED;
  if(!i){if(*(uintptr_t*)def!=image+0x27ebcf0||*(unsigned char*)(def+0x118))return DECISION_REGISTRY_CHANGED;continue;}
  if(*(uintptr_t*)def!=image+0x27eb3d0||*(uintptr_t*)(def+8)!=image+0x27eb3e8||
     !*(unsigned char*)(def+0x118)||!read_name(def,0x120,name,sizeof name))return DECISION_REGISTRY_CHANGED;
  if(strcmp(name,id))continue;
  if(*out)return DECISION_AMBIGUOUS;
  *out=def;
 }
 return *out?DECISION_FOUND:DECISION_NOT_FOUND;
}
static int decision_counter(uintptr_t image,uintptr_t manager,const char *id,
 int(*can_read)(const void*,size_t),int(*read_name)(uintptr_t,size_t,char*,size_t),int32_t *out){
 *out=0;
 if(!can_read((void*)(manager+0x148),16))return 0;
 uintptr_t array=*(uintptr_t*)(manager+0x148);
 int capacity=*(int*)(manager+0x150),count=*(int*)(manager+0x154),found=0;
 if(count<0||count>capacity||capacity>100000||(count&&!can_read((void*)array,(size_t)count*24)))return 0;
 for(int i=0;i<count;i++){
  uintptr_t record=array+(size_t)i*24,def=*(uintptr_t*)(record+8);char name[256];
  if(*(uintptr_t*)record!=image+0x27eb570||!can_read((void*)def,0x144)||
     *(uintptr_t*)def!=image+0x27eb3d0||!read_name(def,0x120,name,sizeof name)||
     *(int32_t*)(record+0x10)<0)return 0;
  /*72dda0 compares exact name and raw target tag. Ordinary selection uses0. */
  if(*(uint32_t*)(record+0x14)||strcmp(name,id))continue;
  if(found++)return 0;
  *out=*(int32_t*)(record+0x10);
 }
 return 1;
}
static enum politics_result decision_select(uintptr_t image,uintptr_t country,uint32_t tag,
 const char *id,const char *rid,int(*can_read)(const void*,size_t),
 int(*read_name)(uintptr_t,size_t,char*,size_t),int(*intent)(const char*),struct decision_outcome *out){
 memset(out,0,sizeof *out);out->reason="decision_binding_changed";
 if(!tag||!can_read((void*)country,0xfa8)||*(uint32_t*)(country+8)!=tag)return POLITICS_BINDING_CHANGED;
 uintptr_t manager=*(uintptr_t*)(country+0xfa0),politics=*(uintptr_t*)(country+0xf90);
 if(!can_read((void*)manager,0x158)||*(uintptr_t*)manager!=image+0x27eb5c0||
    *(uintptr_t*)(manager+8)!=country||!can_read((void*)politics,0xe8))return POLITICS_BINDING_CHANGED;
 enum decision_lookup_result lookup=decision_resolve(image,id,can_read,read_name,&out->requested);
 if(lookup!=DECISION_FOUND){
  if(lookup==DECISION_REGISTRY_CHANGED)return POLITICS_BINDING_CHANGED;
  out->reason=lookup==DECISION_AMBIGUOUS?"ambiguous_decision":"unknown_decision";return POLITICS_BAD_ARGUMENT;
 }
 if(!decision_counter(image,manager,id,can_read,read_name,&out->counter_before))return POLITICS_BINDING_CHANGED;
 out->reason="decision_counter_overflow";if(out->counter_before==INT32_MAX)return POLITICS_BAD_ARGUMENT;
 uintptr_t command=0;
 enum politics_result result=politics_construct_tagged(image,0x2996908,tag,out->requested,0,rid,can_read,intent,&command);
 out->reason="decision_construction_failed";if(result!=POLITICS_OBJECT_CONSTRUCTED)return result;
 /*72ac30 is the normal native dynamic PP-cost getter. It binds the country,
  * evaluates definition+510, and preserves the same suppression/mission branches
  * used in727ae0. No custom script-context or resource writes are performed. */
 DECISION_COST(image+0x72ac30,out->requested,&out->pp_cost,(const uint32_t*)(country+8));
 out->cost_computed=1;out->pp_before=*(int64_t*)(politics+0xe0);
 out->reason="native_rules_rejected";
 result=politics_execute_resolved(image,command,NULL,rid,can_read,intent);
 if(result==POLITICS_BINDING_CHANGED)out->reason="decision_binding_changed";
 if(result!=POLITICS_EXECUTION_RETURNED)return result;
 out->reason="decision_postcondition_failed";
 uintptr_t resolved=0;
 if(!can_read((void*)country,0xfa8)||*(uint32_t*)(country+8)!=tag||
    *(uintptr_t*)(country+0xfa0)!=manager||*(uintptr_t*)(country+0xf90)!=politics||
    !can_read((void*)manager,0x158)||*(uintptr_t*)manager!=image+0x27eb5c0||
    *(uintptr_t*)(manager+8)!=country||
    decision_resolve(image,id,can_read,read_name,&resolved)!=DECISION_FOUND||resolved!=out->requested||
    !can_read((void*)(politics+0xe0),8)||
    !decision_counter(image,manager,id,can_read,read_name,&out->counter_after))return result;
 out->pp_after=*(int64_t*)(politics+0xe0);
 out->counter_verified=out->counter_after==out->counter_before+1;
 int64_t charged=out->pp_cost>0?out->pp_cost:0;
 if(out->pp_before>=INT64_MIN+charged)out->payment_verified=out->pp_after==out->pp_before-charged;
 out->verified=out->counter_verified&&out->payment_verified;
 /*Effects that themselves alter PP can make the payment delta inconclusive.
  * Keep the executed request uncertain; never repeat automatically. */
 if(out->verified)out->reason="native_decision_counter_and_payment_verified";
 return result;
}
#endif
