#ifndef HOI4_NATIVE_DEPLOYMENT_CANDIDATE_H
#define HOI4_NATIVE_DEPLOYMENT_CANDIDATE_H
/* Isolated ordinary CDeployConveyorLineCommand preparation. Caller must pin
 * executable/world/game-thread and persist request intent before execution.
 * Returns a native command only; no direct deployment state writes. */
#include <stdint.h>
#include <stddef.h>
#ifndef DEPLOY_RESOLVE
#define DEPLOY_RESOLVE(fn,id) ((uintptr_t(*)(const uint32_t*))(fn))(id)
#define DEPLOY_READY(fn,line) ((unsigned char(*)(uintptr_t,void*))(fn))(line,NULL)
#define DEPLOY_ALLOC(fn,n) ((uintptr_t(*)(size_t))(fn))(n)
#define DEPLOY_CTOR(fn,cmd,line) ((uintptr_t(*)(uintptr_t,uintptr_t))(fn))(cmd,line)
#define DEPLOY_VALIDATE(fn,cmd) ((unsigned char(*)(uintptr_t,void*))(fn))(cmd,NULL)
#define DEPLOY_DESTROY(fn,cmd) ((uintptr_t(*)(uintptr_t,unsigned))(fn))(cmd,1)
#endif
static int deploy_member(uintptr_t field,uintptr_t item,int(*readable)(const void*,size_t)){
 if(!readable((void*)field,16))return 0;
 uintptr_t data=*(uintptr_t*)field;int32_t capacity=*(int32_t*)(field+8),count=*(int32_t*)(field+12);
 if(count<0||count>capacity||capacity>100000||
    (count&&!readable((void*)data,(size_t)count*8)))return 0;
 int found=0;for(int32_t i=0;i<count;i++)if(((uintptr_t*)data)[i]==item)found++;
 return found==1;
}
static const char *deployment_prepare_line(uintptr_t image,uintptr_t country,uint32_t tag,
 const uint32_t line_id[2],int(*readable)(const void*,size_t),uintptr_t *command){
 *command=0;
 if(!tag||!line_id||!line_id[0]||!line_id[1])return "invalid_deployment_line_id";
 if(!readable((void*)country,0xf78)||*(uintptr_t*)country!=image+0x27e7360||
    *(uint32_t*)(country+8)!=tag)return "deployment_binding_changed";
 uintptr_t manager=*(uintptr_t*)(country+0xf70),line=DEPLOY_RESOLVE(image+0x221f310,line_id);
 if(!readable((void*)manager,0x58)||*(uintptr_t*)manager!=image+0x295fc38||
    !readable((void*)line,0x40)||*(uintptr_t*)line!=image+0x295e0a8||
    *(uint64_t*)(line+8)!=((uint64_t)line_id[1]<<32|line_id[0]))return "deployment_binding_changed";
 uintptr_t conveyor=*(uintptr_t*)(line+0x38);
 if(!readable((void*)conveyor,0x88)||*(uintptr_t*)conveyor!=image+0x295e100||
    !deploy_member(manager+0x48,conveyor,readable)||
    !deploy_member(conveyor+0x78,line,readable))return "deployment_binding_changed";
 uintptr_t templ=*(uintptr_t*)(conveyor+0x20),entry=*(uintptr_t*)(line+0x30);
 if(!readable((void*)templ,0x1f0)||*(uint32_t*)(templ+0x1ec)!=tag||
    !readable((void*)entry,0xc8)||*(uintptr_t*)entry!=image+0x295e020||
    *(uintptr_t*)(entry+0xb8)!=line)return "deployment_binding_changed";
 /* Outer command validator only resolves ID; this is the engine's full
  * equipment/manpower/capacity/training/location gate with no error buffer. */
 if(!DEPLOY_READY(image+0xce7d50,line))return "deployment_native_rules_rejected";
 uintptr_t cmd=DEPLOY_ALLOC(image+0x21c9af0,0x30);
 if(!cmd)return "deployment_allocation_failed";
 uintptr_t result=DEPLOY_CTOR(image+0x1ba1460,cmd,line);
 if(result!=cmd||!readable((void*)cmd,0x30)||*(uintptr_t*)cmd!=image+0x2a48de8||
    *(uint64_t*)(cmd+0x28)!=((uint64_t)line_id[1]<<32|line_id[0])||
    !DEPLOY_VALIDATE(image+0x1162ce0,cmd)){
  DEPLOY_DESTROY(image+0x22d200,cmd);return "deployment_command_binding_changed";
 }
 *command=cmd;return NULL;
}
/* Prepared command: ordinary executor image+1ba3270; deleting destructor
 * image+22d200(cmd,1). Success is NOT executor return: independent country army
 * ID difference and native unit province/template/equipment/manpower must match.
 * Source line may be recycled or deleted, so never dereference it after execute. */
#ifndef DEPLOY_QUEUE_READY
#define DEPLOY_QUEUE_READY(fn,m,t) ((unsigned char(*)(uintptr_t,uintptr_t,int,void*))(fn))(m,t,1,NULL)
#define DEPLOY_QUEUE_CTOR(fn,c,t) ((uintptr_t(*)(uintptr_t,uintptr_t,int))(fn))(c,t,0)
#endif
static const char *deployment_prepare_queue(uintptr_t image,uintptr_t country,uint32_t tag,
 const uint32_t template_id[2],int(*readable)(const void*,size_t),uintptr_t *command){
 *command=0;
 if(!tag||!template_id||!template_id[0]||!template_id[1])return "invalid_division_template_id";
 if(!readable((void*)country,0xf78)||*(uintptr_t*)country!=image+0x27e7360||
    *(uint32_t*)(country+8)!=tag)return "deployment_binding_changed";
 uintptr_t manager=*(uintptr_t*)(country+0xf70),templ=DEPLOY_RESOLVE(image+0x221f310,template_id);
 if(!readable((void*)manager,0x120)||*(uintptr_t*)manager!=image+0x295fc38||
    *(uintptr_t*)(manager+0x118)!=country||!readable((void*)templ,0x260)||
    *(uintptr_t*)templ!=image+0x294f5b0||*(uint32_t*)(templ+0x1ec)!=tag||
    *(uint64_t*)(templ+8)!=((uint64_t)template_id[1]<<32|template_id[0])||
    !deploy_member(country+0x1b8,templ,readable))return "deployment_binding_changed";
 /* Exact ordinary UI preflight and default option; never bypass native rules. */
 if(!DEPLOY_QUEUE_READY(image+0xd0e740,manager,templ+0x18))return "deployment_native_queue_rules_rejected";
 uintptr_t cmd=DEPLOY_ALLOC(image+0x21c9af0,0x38);
 if(!cmd)return "deployment_allocation_failed";
 uintptr_t result=DEPLOY_QUEUE_CTOR(image+0x1ba11b0,cmd,templ);
 if(result!=cmd||!readable((void*)cmd,0x38)||*(uintptr_t*)cmd!=image+0x2a483c0||
    *(uint64_t*)(cmd+0x28)!=((uint64_t)template_id[1]<<32|template_id[0])||
    *(int32_t*)(cmd+0x30)!=0||!DEPLOY_VALIDATE(image+0x1162ce0,cmd)){
  DEPLOY_DESTROY(image+0xdb4550,cmd);return "deployment_command_binding_changed";
 }
 *command=cmd;return NULL;
}
/* Queue prepared command: executor1ba3060; deleting destructordb4550(cmd,1).
 * Independently read a new owned conveyor ID, requested template pointer, and
 * one reciprocal line/current entry after execution. No ready-state fabrication. */
#ifndef DEPLOY_LOCATION_CTOR
#define DEPLOY_LOCATION_CTOR(fn,c,v,p) ((uintptr_t(*)(uintptr_t,uintptr_t,int32_t))(fn))(c,v,p)
#endif
static const char *deployment_prepare_location(uintptr_t image,uintptr_t country,uint32_t tag,
 const uint32_t conveyor_id[2],int32_t province,int(*readable)(const void*,size_t),uintptr_t *command){
 *command=0;
 if(!tag||!conveyor_id||!conveyor_id[0]||!conveyor_id[1]||province<=0)return "invalid_deployment_location";
 if(!readable((void*)country,0xf78)||*(uintptr_t*)country!=image+0x27e7360||
    *(uint32_t*)(country+8)!=tag)return "deployment_binding_changed";
 uintptr_t manager=*(uintptr_t*)(country+0xf70),conveyor=DEPLOY_RESOLVE(image+0x221f310,conveyor_id);
 if(!readable((void*)manager,0x120)||*(uintptr_t*)manager!=image+0x295fc38||
    *(uintptr_t*)(manager+0x118)!=country||!readable((void*)conveyor,0xa0)||
    *(uintptr_t*)conveyor!=image+0x295e100||
    *(uint64_t*)(conveyor+8)!=((uint64_t)conveyor_id[1]<<32|conveyor_id[0])||
    !deploy_member(manager+0x48,conveyor,readable))return "deployment_binding_changed";
 uintptr_t templ=*(uintptr_t*)(conveyor+0x20);
 if(!readable((void*)templ,0x260)||*(uintptr_t*)templ!=image+0x294f5b0||
    *(uint32_t*)(templ+0x1ec)!=tag||!deploy_member(country+0x1b8,templ,readable))return "deployment_binding_changed";
 uintptr_t cmd=DEPLOY_ALLOC(image+0x21c9af0,0x38);
 if(!cmd)return "deployment_allocation_failed";
 uintptr_t result=DEPLOY_LOCATION_CTOR(image+0x1ba17e0,cmd,conveyor,province);
 const char *error="deployment_command_binding_changed";
 if(result==cmd&&readable((void*)cmd,0x38)&&*(uintptr_t*)cmd==image+0x2a48618&&
    *(uint64_t*)(cmd+0x28)==((uint64_t)conveyor_id[1]<<32|conveyor_id[0])&&
    *(int32_t*)(cmd+0x30)==province){
  /* Whole ordinary validator resolves province and calls e7a580 with the
   * conveyor's actual owner/secondary country. NULL omits error CString only. */
  if(DEPLOY_VALIDATE(image+0x1ba3c10,cmd)){*command=cmd;return NULL;}
  error="deployment_native_location_rules_rejected";
 }
 DEPLOY_DESTROY(image+0xdb4550,cmd);return error;
}
#endif
