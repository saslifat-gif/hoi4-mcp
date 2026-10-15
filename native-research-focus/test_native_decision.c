/* Synthetic host memory and fake native functions. Never executed inside HOI4. */
#include <assert.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
static uintptr_t image,country,manager,politics,db,array,sentinel,definition,other,command,counters;
static int intents,fail_intent,validations,executions,costs,allow,pay_pp,increment,bad_factory,change_registry;
static int64_t pp_cost,effect_pp;
static uintptr_t factory(uintptr_t),resolve_unused(uintptr_t,const uint32_t*);
static unsigned char validate(uintptr_t,uintptr_t,void*);
static void execute(uintptr_t,uintptr_t),cost(uintptr_t,uintptr_t,int64_t*,const uint32_t*);
#define POLITICS_FACTORY(fn) factory(fn)
#define POLITICS_RESOLVE(fn,id) resolve_unused((fn),(id))
#define POLITICS_VALIDATE(fn,cmd,err) validate((fn),(cmd),(err))
#define POLITICS_EXECUTE(fn,cmd) execute((fn),(cmd))
#define DECISION_COST(fn,d,out,tag) cost((fn),(d),(out),(tag))
#include "native_decision_candidate.h"
static int readable(const void *p,size_t n){uintptr_t a=(uintptr_t)p;return a>=image&&n<=0x3330000&&a-image<=0x3330000-n;}
#include "native_name.h"
static uintptr_t resolve_unused(uintptr_t fn,const uint32_t*id){(void)fn;(void)id;assert(0);return 0;}
static void name(uintptr_t where,const char *s){
 size_t n=strlen(s);memset((void*)where,0,32);
 if(n>15){*(uintptr_t*)where=where+0x800;strcpy((char*)(where+0x800),s);}else strcpy((char*)where,s);
 *(uint64_t*)(where+16)=n;*(uint64_t*)(where+24)=n>15?255:15;
}
static void typed_definition(uintptr_t address,const char *id){
 *(uintptr_t*)address=image+0x27eb3d0;*(uintptr_t*)(address+8)=image+0x27eb3e8;
 *(unsigned char*)(address+0x118)=1;name(address+0x120,id);
}
static void counter(int i,uintptr_t def,int32_t n,uint32_t target){
 uintptr_t entry=counters+(size_t)i*24;*(uintptr_t*)entry=image+0x27eb570;
 *(uintptr_t*)(entry+8)=def;*(int32_t*)(entry+0x10)=n;*(uint32_t*)(entry+0x14)=target;
}
static int intent(const char *rid){assert(!strcmp(rid,"decision-request"));intents++;return intents!=fail_intent;}
static uintptr_t factory(uintptr_t fn){
 assert(fn==image+0x114f9a0&&intents==1);return bad_factory?0:command;
}
static void cost(uintptr_t fn,uintptr_t def,int64_t *out,const uint32_t *tag){
 assert(fn==image+0x72ac30&&def==definition&&tag==(uint32_t*)(country+8)&&*tag==1);
 assert(intents==1&&!validations&&!executions);costs++;*out=pp_cost;
}
static unsigned char validate(uintptr_t fn,uintptr_t cmd,void *err){
 assert(fn==image+0x1165f10&&cmd==command&&!err&&intents==2&&costs==1);
 assert(*(uint32_t*)(cmd+0x28)==1&&*(uintptr_t*)(cmd+0x30)==definition);validations++;return (unsigned char)allow;
}
static void execute(uintptr_t fn,uintptr_t cmd){
 assert(fn==image+0x115ade0&&cmd==command&&validations==1);executions++;
 if(pay_pp&&pp_cost>0)*(int64_t*)(politics+0xe0)-=pp_cost;
 *(int64_t*)(politics+0xe0)+=effect_pp;
 if(increment){
  int count=*(int*)(manager+0x154),i=0;
  for(;i<count;i++)if(*(uintptr_t*)(counters+(size_t)i*24+8)==definition&&!*(uint32_t*)(counters+(size_t)i*24+0x14))break;
  if(i==count){counter(i,definition,0,0);*(int*)(manager+0x154)=count+1;}
  *(int32_t*)(counters+(size_t)i*24+0x10)+=increment;
 }
 if(change_registry)*(uintptr_t*)(image+0x332ee80)=0;
}
static void reset(void){
 memset((void*)image,0,0x3330000);intents=validations=executions=costs=fail_intent=bad_factory=change_registry=0;
 allow=pay_pp=increment=1;effect_pp=0;pp_cost=2500000;
 country=image+0x1000;manager=image+0x3000;politics=image+0x4000;db=image+0x5000;array=image+0x6000;
 sentinel=image+0x7000;definition=image+0x10000;other=image+0x13000;command=image+0x16000;counters=image+0x17000;
 *(uint32_t*)(country+8)=1;*(uintptr_t*)(country+0xfa0)=manager;*(uintptr_t*)(country+0xf90)=politics;
 *(uintptr_t*)manager=image+0x27eb5c0;*(uintptr_t*)(manager+8)=country;
 *(uintptr_t*)(image+0x332ee80)=db;*(uintptr_t*)db=image+0x27eb640;
 *(uintptr_t*)(db+0x28)=array;*(int*)(db+0x30)=3;*(int*)(db+0x34)=2;
 ((uintptr_t*)array)[0]=sentinel;((uintptr_t*)array)[1]=definition;*(uintptr_t*)sentinel=image+0x27ebcf0;
 typed_definition(definition,"GER_industrial_expansion");typed_definition(other,"other_decision");
 *(uintptr_t*)(manager+0x148)=counters;*(int*)(manager+0x150)=4;
 *(int64_t*)(politics+0xe0)=20000000;
 *(uintptr_t*)command=image+0x2996908;*(uintptr_t*)(image+0x2996908+72)=image+0x1165f10;*(uintptr_t*)(image+0x2996908+80)=image+0x115ade0;
}
static enum politics_result run(struct decision_outcome *out){return decision_select(image,country,1,"GER_industrial_expansion","decision-request",readable,native_name,intent,out);}
int main(void){
 (void)politics_bind_native_handle;(void)politics_resolve_idea;
 image=(uintptr_t)calloc(1,0x3330000);assert(image);struct decision_outcome out;
 reset();assert(run(&out)==POLITICS_EXECUTION_RETURNED&&out.verified&&out.counter_after==1&&out.pp_after==17500000&&executions==1);
 reset();*(int*)(manager+0x154)=1;counter(0,definition,4,0);assert(run(&out)==POLITICS_EXECUTION_RETURNED&&out.verified&&out.counter_before==4&&out.counter_after==5);
 reset();*(int*)(manager+0x154)=1;counter(0,definition,9,5);assert(run(&out)==POLITICS_EXECUTION_RETURNED&&out.verified&&out.counter_before==0&&out.counter_after==1);
 reset();pp_cost=0;assert(run(&out)==POLITICS_EXECUTION_RETURNED&&out.verified&&out.pp_after==out.pp_before);
 reset();pp_cost=-100;assert(run(&out)==POLITICS_EXECUTION_RETURNED&&out.verified&&out.pp_after==out.pp_before);
 reset();typed_definition(other,"DEBUG_MUN_fire_MUN_czech.3");((uintptr_t*)array)[1]=other;((uintptr_t*)array)[2]=definition;*(int*)(db+0x34)=3;
 assert(run(&out)==POLITICS_EXECUTION_RETURNED&&out.verified&&executions==1);
 reset();allow=0;assert(run(&out)==POLITICS_RULES_REJECTED&&!out.verified&&!executions&&validations==1);
 reset();pay_pp=0;assert(run(&out)==POLITICS_EXECUTION_RETURNED&&!out.verified&&out.counter_verified&&!out.payment_verified&&executions==1);
 reset();effect_pp=12345;assert(run(&out)==POLITICS_EXECUTION_RETURNED&&!out.verified&&out.counter_verified&&!out.payment_verified&&executions==1);
 reset();increment=0;assert(run(&out)==POLITICS_EXECUTION_RETURNED&&!out.verified&&!out.counter_verified&&out.payment_verified);
 reset();increment=2;assert(run(&out)==POLITICS_EXECUTION_RETURNED&&!out.verified&&out.counter_after==2);
 reset();change_registry=1;assert(run(&out)==POLITICS_EXECUTION_RETURNED&&!out.verified&&executions==1);
 reset();name(definition+0x120,"different_decision");assert(run(&out)==POLITICS_BAD_ARGUMENT&&!strcmp(out.reason,"unknown_decision")&&!intents);
 reset();typed_definition(other,"GER_industrial_expansion");((uintptr_t*)array)[2]=other;*(int*)(db+0x34)=3;assert(run(&out)==POLITICS_BAD_ARGUMENT&&!strcmp(out.reason,"ambiguous_decision")&&!intents);
 reset();*(uintptr_t*)definition=0;assert(run(&out)==POLITICS_BINDING_CHANGED&&!intents);
 reset();*(uintptr_t*)sentinel=0;assert(run(&out)==POLITICS_BINDING_CHANGED&&!intents);
 reset();*(int*)(db+0x34)=4;assert(run(&out)==POLITICS_BINDING_CHANGED&&!intents);
 reset();*(uintptr_t*)(manager+8)=country+1;assert(run(&out)==POLITICS_BINDING_CHANGED&&!intents);
 reset();*(uint32_t*)(country+8)=2;assert(run(&out)==POLITICS_BINDING_CHANGED&&!intents);
 reset();*(int*)(manager+0x154)=2;counter(0,definition,1,0);counter(1,definition,2,0);assert(run(&out)==POLITICS_BINDING_CHANGED&&!intents);
 reset();*(int*)(manager+0x154)=1;counter(0,definition,INT32_MAX,0);assert(run(&out)==POLITICS_BAD_ARGUMENT&&!intents&&!strcmp(out.reason,"decision_counter_overflow"));
 reset();*(int*)(manager+0x154)=1;counter(0,definition,-1,0);assert(run(&out)==POLITICS_BINDING_CHANGED&&!intents);
 reset();fail_intent=1;assert(run(&out)==POLITICS_INTENT_FAILED&&!executions&&!costs);
 reset();fail_intent=2;assert(run(&out)==POLITICS_INTENT_FAILED&&!executions&&costs==1);
 reset();bad_factory=1;assert(run(&out)==POLITICS_FACTORY_FAILED&&!costs&&!executions);
 reset();*(uintptr_t*)(image+0x2996908+72)=0;assert(run(&out)==POLITICS_BINDING_CHANGED&&!validations&&!executions);
 free((void*)image);return 0;
}
