#ifndef HOI4_NATIVE_POLITICS_H
#define HOI4_NATIVE_POLITICS_H
/* Internal dispatch for ALREADY engine-constructed and source/owner-bound commands.
 * Caller must pin the executable, bind the game thread/world, resolve ownership,
 * supply an error object where required, and enforce ordinary UI arguments/costs.
 * Default construction/handle binding do not populate requests or verify outcomes.
 * MCP callers must establish those bindings and verify the resulting gameplay. */
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#ifndef POLITICS_VALIDATE
#define POLITICS_VALIDATE(fn,cmd,error) ((unsigned char(*)(uintptr_t,void*))(fn))((cmd),(error))
#endif
#ifndef POLITICS_EXECUTE
#define POLITICS_EXECUTE(fn,cmd) ((void(*)(uintptr_t))(fn))((cmd))
#endif
#ifndef POLITICS_FACTORY
#define POLITICS_FACTORY(fn) ((uintptr_t(*)(void))(fn))()
#endif
#ifndef POLITICS_RESOLVE
#define POLITICS_RESOLVE(fn,id) ((uintptr_t(*)(const uint32_t*))(fn))(id)
#endif
struct politics_method {uintptr_t vtable,validate,execute,factory;size_t size;};
static const struct politics_method politics_methods[]={
 {0x2995328,0x1161ac0,0x1151720,0x114e2f0,0x40}, /* AddIdea */
 {0x29958a0,0x1165bf0,0x1159b70,0x114f850,0x48}, /* ReplaceIdea */
 {0x2995580,0x1161560,0x11508a0,0x114e180,0x58}, /* AddAdvisor */
 {0x2995968,0x1165a90,0x1159910,0x114f740,0x60}, /* ReplaceAdvisor */
 {0x2996908,0x1165f10,0x115ade0,0x114f9a0,0x38}, /* SelectDecision */
 {0x29969d0,0x1166030,0x115b0e0,0x114fa20,0x40}, /* SelectTargetedDecision */
 {0x2a49150,0x1ba56d0,0x1ba54b0,0x1ba53d0,0x40} /* CreateTrade */
};
enum politics_result {POLITICS_UNSUPPORTED,POLITICS_BINDING_CHANGED,
 POLITICS_INTENT_FAILED,POLITICS_RULES_REJECTED,POLITICS_EXECUTION_RETURNED,POLITICS_OBJECT_CONSTRUCTED,POLITICS_FACTORY_FAILED,POLITICS_BAD_ARGUMENT};
static const struct politics_method *politics_method_for(uintptr_t vtable_rva){
 for(size_t i=0;i<sizeof politics_methods/sizeof *politics_methods;i++)
  if(vtable_rva==politics_methods[i].vtable)return &politics_methods[i];
 return NULL;
}
/* A factory constructs defaults only. Populate verified ordinary UI arguments
 * before validation/execution; never treat a default object as a ready request. */
static enum politics_result politics_construct_default(uintptr_t image,uintptr_t vtable_rva,
 const char *rid,int(*can_read)(const void*,size_t),int(*intent)(const char*),uintptr_t *out){
 *out=0;const struct politics_method *method=politics_method_for(vtable_rva);
 if(!method)return POLITICS_UNSUPPORTED;
 if(!can_read((void*)(image+method->factory),1))return POLITICS_BINDING_CHANGED;
 if(!intent(rid))return POLITICS_INTENT_FAILED;
 uintptr_t command=POLITICS_FACTORY(image+method->factory);
 if(!can_read((void*)command,method->size)||*(uintptr_t*)command!=image+method->vtable)return POLITICS_FACTORY_FAILED;
 *out=command;return POLITICS_OBJECT_CONSTRUCTED;
}
/* Payload fields proven by the engine clone methods. Keeps factory cost flags.
 * Supports resolved AddIdea/ReplaceIdea and non-targeted SelectDecision only. */
static enum politics_result politics_construct_tagged(uintptr_t image,uintptr_t vt,
 uint32_t country_tag,uintptr_t primary,uintptr_t replacement,const char *rid,
 int(*can_read)(const void*,size_t),int(*intent)(const char*),uintptr_t *out){
 *out=0;int replace=vt==0x29958a0;
 if(vt!=0x2995328&&!replace&&vt!=0x2996908)return POLITICS_UNSUPPORTED;
 if(!country_tag||!primary||(replace?(!replacement||replacement==primary):replacement!=0))return POLITICS_BAD_ARGUMENT;
 enum politics_result result=politics_construct_default(image,vt,rid,can_read,intent,out);
 if(result!=POLITICS_OBJECT_CONSTRUCTED)return result;
 *(uint32_t*)(*out+0x28)=country_tag;*(uintptr_t*)(*out+0x30)=primary;
 if(replace)*(uintptr_t*)(*out+0x38)=replacement;
 return result;
}
/* Binds an already-known native handle to an independently resolved object.
 * Canonical script-ID lookup and actor ownership are still caller obligations. */
static inline uintptr_t politics_bind_native_handle(uintptr_t image,const uint32_t id[2],
 uintptr_t expected,int(*can_read)(const void*,size_t)){
 if(!expected||!can_read(id,8)||!(id[0]|id[1]))return 0;
 uintptr_t object=POLITICS_RESOLVE(image+0x221f310,id);
 if(object!=expected||!can_read((void*)object,16))return 0;
 const uint32_t *stored=(const uint32_t*)(object+8);
 return stored[0]==id[0]&&stored[1]==id[1]?object:0;
}
/* Read-only exact definition binding; caller pins image/world/thread first.
 * Existing native_name decoder supplies the verified MSVC string layout. */
static uintptr_t politics_resolve_idea(uintptr_t image,const char *identifier,
 int(*can_read)(const void*,size_t),int(*read_name)(uintptr_t,size_t,char*,size_t)){
 if(!can_read((void*)(image+0x332ef30),8))return 0;
 uintptr_t database=*(uintptr_t*)(image+0x332ef30);
 if(!can_read((void*)database,0x78)||*(uintptr_t*)database!=image+0x293c2b0)return 0;
 uintptr_t array=*(uintptr_t*)(database+0x68),match=0;
 int capacity=*(int*)(database+0x70),count=*(int*)(database+0x74);
 if(count<1||count>capacity||capacity>100000||!can_read((void*)array,(size_t)count*8))return 0;
 for(int i=0;i<count;i++){
  uintptr_t idea=((uintptr_t*)array)[i];char name[160];
  if(!can_read((void*)idea,24))return 0;
  if(i==0){if(*(uintptr_t*)idea!=image+0x293c510||*(uintptr_t*)(idea+16)!=image+0x293c560)return 0;continue;}
  if(*(uintptr_t*)idea!=image+0x29815e0||*(uintptr_t*)(idea+16)!=image+0x2981630||!read_name(idea,24,name,sizeof name))return 0;
  if(strcmp(name,identifier))continue;
  if(match)return 0; /* An ambiguous name is never a resolved command target. */
  match=idea;
 }
 return match;
}
static enum politics_result politics_execute_resolved(uintptr_t image,uintptr_t command,
 void *engine_error,const char *request_id,int(*can_read)(const void*,size_t),
 int(*persist_execution_intent)(const char*)){
 if(!can_read((void*)command,8))return POLITICS_BINDING_CHANGED;
 uintptr_t vt=*(uintptr_t*)command;
 const struct politics_method *method=politics_method_for(vt-image);
 if(!method)return POLITICS_UNSUPPORTED;
 /* ReplaceIdea1165bf0..1165d25 and AddAdvisor1161560..1161605 do not
  * read incoming RDX. AddAdvisor UI wrappers143fec0/1440b10 pass NULL.
  * SelectDecision1165f10..1166029 overwrites RDX after its first call;
  * that leaf helper535110..5351d3 begins XOR EDX,EDX and never reads
  * the incoming argument. Pinned executable bytes captured20261015.
  * This exception does not cover targeted decisions. */
 if(engine_error?!can_read(engine_error,1):(method->vtable!=0x29958a0&&method->vtable!=0x2995580&&method->vtable!=0x2996908))return POLITICS_BINDING_CHANGED;
 if(!can_read((void*)(vt+9*8),16)||*(uintptr_t*)(vt+9*8)!=image+method->validate||*(uintptr_t*)(vt+10*8)!=image+method->execute)return POLITICS_BINDING_CHANGED;
 if(!persist_execution_intent(request_id))return POLITICS_INTENT_FAILED;
 if(!POLITICS_VALIDATE(image+method->validate,command,engine_error))return POLITICS_RULES_REJECTED;
 POLITICS_EXECUTE(image+method->execute,command);
 return POLITICS_EXECUTION_RETURNED; /* Never report selection/gameplay verified. */
}

#endif
