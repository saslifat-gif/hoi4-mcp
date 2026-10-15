/* Host-only simulation. Engine functions below are fakes, never live calls. */
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
static uintptr_t image,country,manager,politics,role,character,command,listed,active,head,node;
static int intents,validations,executions,fail_intent,allow,pay_pp,pay_cp,activate,bad_handle,bad_role,bad_copy,bad_factory;
static int64_t pp_cost,cp_cost;
static uintptr_t factory(uintptr_t),resolve(uintptr_t,const uint32_t*),lookup(uintptr_t,uintptr_t,uintptr_t),copy_name(uintptr_t,uintptr_t,uintptr_t);
static unsigned char validate(uintptr_t,uintptr_t,void*);
static void execute(uintptr_t,uintptr_t),cost(uintptr_t,uintptr_t,int64_t*);
#define POLITICS_FACTORY(fn) factory(fn)
#define POLITICS_RESOLVE(fn,id) resolve((fn),(id))
#define POLITICS_VALIDATE(fn,cmd,err) validate((fn),(cmd),(err))
#define POLITICS_EXECUTE(fn,cmd) execute((fn),(cmd))
#define ADVISOR_ROLE(fn,c,key) lookup((fn),(c),(key))
#define ADVISOR_COPY_NAME(fn,d,s) copy_name((fn),(d),(s))
#define ADVISOR_COST(fn,r,out) cost((fn),(r),(out))
#include "native_advisor.h"
static int readable(const void *p,size_t n){uintptr_t a=(uintptr_t)p;return a>=image&&n<=0x3330000&&a-image<=0x3330000-n;}
#include "native_name.h"
static void name(uintptr_t where,const char *text){
 size_t n=strlen(text);memset((void*)where,0,32);
 if(n>15){*(uintptr_t*)where=where+0x200;strcpy((char*)(where+0x200),text);}else strcpy((char*)where,text);
 *(uint64_t*)(where+16)=n;*(uint64_t*)(where+24)=n>15?63:15;
}
static int intent(const char *rid){assert(!strcmp(rid,"advisor-request"));intents++;return intents!=fail_intent;}
static uintptr_t factory(uintptr_t fn){
 assert(fn==image+0x114e180&&intents==1);if(bad_factory)return 0;
 *(unsigned char*)(command+0x30)=1;name(command+0x38,"");return command;
}
static uintptr_t resolve(uintptr_t fn,const uint32_t *id){assert(fn==image+0x221f310&&id==(uint32_t*)(character+8));return bad_handle?0:character;}
static uintptr_t lookup(uintptr_t fn,uintptr_t c,uintptr_t key){assert(fn==image+0xf9f700&&c==character&&key==node+0x20);return bad_role?0:role;}
static uintptr_t copy_name(uintptr_t fn,uintptr_t dest,uintptr_t source){
 assert(fn==image+0x11e010&&dest==command+0x38&&source==node+0x20);char text[160];assert(native_name(source,0,text,sizeof text));
 name(dest,bad_copy?"wrong":text);return dest;
}
static void cost(uintptr_t fn,uintptr_t r,int64_t *out){
 assert(r==role&&intents==1&&!validations);
 if(fn==image+0x12a24e0)*out=pp_cost;else{assert(fn==image+0x12a0af0);*out=cp_cost;}
}
static unsigned char validate(uintptr_t fn,uintptr_t cmd,void *err){
 assert(fn==image+0x1161560&&cmd==command&&!err&&intents==2);validations++;return (unsigned char)allow;
}
static void execute(uintptr_t fn,uintptr_t cmd){
 assert(fn==image+0x11508a0&&cmd==command&&validations==1);executions++;
 if(pay_pp&&pp_cost>0)*(int64_t*)(politics+0xe0)-=pp_cost;
 if(pay_cp&&cp_cost>0)*(int64_t*)(country+0x1f0)-=cp_cost;
 if(activate){((uintptr_t*)active)[0]=role;*(int*)(manager+0x64)=1;}
}
static void reset(void){
 memset((void*)image,0,0x3330000);intents=validations=executions=fail_intent=bad_handle=bad_role=bad_copy=bad_factory=0;
 allow=pay_pp=pay_cp=activate=1;pp_cost=14900000;cp_cost=1000000;
 country=image+0x1000;manager=image+0x3000;politics=image+0x4000;role=image+0x5000;character=image+0x6000;command=image+0x7000;listed=image+0x8000;active=image+0x9000;head=image+0xa000;node=image+0xb000;
 *(uint32_t*)(country+8)=1;*(uintptr_t*)(country+0xff0)=manager;*(uintptr_t*)(country+0xf90)=politics;
 *(uintptr_t*)manager=image+0x298ae18;*(uintptr_t*)(manager+8)=country;
 *(uintptr_t*)(manager+0x40)=listed;*(int*)(manager+0x48)=2;*(int*)(manager+0x4c)=1;((uintptr_t*)listed)[0]=role;
 *(uintptr_t*)(manager+0x58)=active;*(int*)(manager+0x60)=2;
 *(uintptr_t*)role=image+0x29a7d60;*(uintptr_t*)(role+0x10)=character;name(role+0x30,"ernst_udet");
 *(uintptr_t*)character=image+0x297ea60;*(uint32_t*)(character+8)=51;*(uint32_t*)(character+12)=1;*(uint32_t*)(character+0x68)=1;name(character+0x48,"GER_ernst_udet");
 *(uintptr_t*)(character+0xb0)=head;*(uint64_t*)(character+0xb8)=1;
 *(uintptr_t*)head=node;*(uintptr_t*)(head+8)=node;*(uintptr_t*)(head+0x10)=node;*(unsigned char*)(head+0x19)=1;
 *(uintptr_t*)node=head;*(uintptr_t*)(node+8)=head;*(uintptr_t*)(node+0x10)=head;*(uintptr_t*)(node+0x48)=role;
 name(node+0x20,"high_command");uint32_t hash=0x811c9dc5;
 for(const char *s="high_command";*s;s++)hash=(hash^(unsigned char)*s)*0x1000193;
 *(uint32_t*)(node+0x40)=hash;
 *(int64_t*)(politics+0xe0)=20000000;*(int64_t*)(country+0x1f0)=5000000;
 *(uintptr_t*)command=image+0x2995580;*(uintptr_t*)(image+0x2995580+72)=image+0x1161560;*(uintptr_t*)(image+0x2995580+80)=image+0x11508a0;
}
static enum politics_result run(struct advisor_outcome *out){return advisor_appoint(image,country,1,"GER_ernst_udet","ernst_udet","advisor-request",readable,native_name,intent,out);}
int main(void){
 (void)politics_construct_tagged;(void)politics_resolve_idea;
 image=(uintptr_t)calloc(1,0x3330000);assert(image);struct advisor_outcome out;
 reset();assert(run(&out)==POLITICS_EXECUTION_RETURNED&&out.verified&&executions==1);
 assert(out.pp_cost==14900000&&out.cp_cost==1000000&&out.pp_after==5100000&&out.cp_after==4000000);
 assert(!memcmp((void*)(command+0x28),(void*)(character+8),8));
 char copied_slot[160];assert(native_name(command,0x38,copied_slot,sizeof copied_slot)&&!strcmp(copied_slot,"high_command"));
 reset();allow=0;assert(run(&out)==POLITICS_RULES_REJECTED&&!out.verified&&!executions&&validations==1);
 for(int n=1;n<=2;n++){reset();fail_intent=n;assert(run(&out)==POLITICS_INTENT_FAILED&&!executions&&!validations);}
 reset();pay_pp=0;assert(run(&out)==POLITICS_EXECUTION_RETURNED&&!out.verified);
 reset();pay_cp=0;assert(run(&out)==POLITICS_EXECUTION_RETURNED&&!out.verified);
 reset();activate=0;assert(run(&out)==POLITICS_EXECUTION_RETURNED&&!out.verified);
 reset();pp_cost=cp_cost=0;assert(run(&out)==POLITICS_EXECUTION_RETURNED&&out.verified&&out.pp_after==out.pp_before&&out.cp_after==out.cp_before);
 reset();pp_cost=cp_cost=-100;assert(run(&out)==POLITICS_EXECUTION_RETURNED&&out.verified&&out.pp_after==out.pp_before&&out.cp_after==out.cp_before);
 reset();*(uint32_t*)(character+0x68)=2;assert(run(&out)==POLITICS_BINDING_CHANGED&&!intents);
 reset();bad_handle=1;assert(run(&out)==POLITICS_BINDING_CHANGED&&!intents);
 reset();bad_role=1;assert(run(&out)==POLITICS_BINDING_CHANGED&&!intents);
 reset();bad_copy=1;assert(run(&out)==POLITICS_BINDING_CHANGED&&!executions);
 reset();bad_factory=1;assert(run(&out)==POLITICS_FACTORY_FAILED&&!executions);
 reset();*(int*)(manager+0x4c)=2;((uintptr_t*)listed)[1]=role;assert(run(&out)==POLITICS_BAD_ARGUMENT&&!strcmp(out.reason,"ambiguous_advisor")&&!intents);
 reset();*(int*)(manager+0x64)=1;((uintptr_t*)active)[0]=role;assert(run(&out)==POLITICS_BAD_ARGUMENT&&!strcmp(out.reason,"already_selected")&&!intents);
 reset();name(role+0x30,"another_role");assert(run(&out)==POLITICS_BAD_ARGUMENT&&!strcmp(out.reason,"advisor_not_in_country")&&!intents);
 reset();*(int*)(manager+0x4c)=3;assert(run(&out)==POLITICS_BINDING_CHANGED&&!intents);
 reset();*(int*)(manager+0x64)=3;assert(run(&out)==POLITICS_BINDING_CHANGED&&!intents);
 reset();*(uintptr_t*)(image+0x2995580+72)=0;assert(run(&out)==POLITICS_BINDING_CHANGED&&!executions&&!validations);
 reset();*(int64_t*)(politics+0xe0)=INT64_MIN;pay_pp=0;assert(run(&out)==POLITICS_EXECUTION_RETURNED&&!out.verified);
 reset();name(role+0x30,"long_native_role-name");
 assert(advisor_appoint(image,country,1,"GER_ernst_udet","long_native_role-name","advisor-request",readable,native_name,intent,&out)==POLITICS_EXECUTION_RETURNED&&out.verified);
 assert(*(uintptr_t*)(command+0x38)!=*(uintptr_t*)(role+0x30));
 free((void*)image);return 0;
}
