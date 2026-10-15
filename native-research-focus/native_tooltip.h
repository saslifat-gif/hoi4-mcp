/* Pinned normal GUI tooltip target election/update. Integrate only on the
 * existing paused CInGameIdler::frame hook. No input synthesis/text setters. */
#ifndef HOI4_NATIVE_TOOLTIP_H
#define HOI4_NATIVE_TOOLTIP_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>

typedef int (*TooltipReadable)(const void*,size_t);
typedef void (*TooltipElect)(uintptr_t,uintptr_t,int);
typedef void (*TooltipUpdate)(uintptr_t,uintptr_t,unsigned char);
typedef int (*TooltipGate)(uintptr_t);
typedef int (*TooltipIntent)(const char*);
struct TooltipCalls {
 TooltipReadable readable;
 TooltipElect elect;
 TooltipUpdate update;
 TooltipGate paused,ui_thread;
 TooltipIntent persist_intent;
};
struct TooltipSelector {const char *source,*name;};
struct TooltipOutcome {
 const char *reason;
 int attempted,updated,nonempty,rendered_equals_combined,local_shown;
 uintptr_t target,before_target,core;
 int depth;
 char rendered[8193],combined[8193],title[4097],body[8193];
};
static int tooltip_string(uintptr_t address,char *out,size_t cap,TooltipReadable read){
 if(!read((void*)address,32))return 0;
 uint64_t length=*(uint64_t*)(address+16),capacity=*(uint64_t*)(address+24);
 if(length>=cap||capacity<length||capacity>1048576||(capacity<16&&capacity!=15))return 0;
 uintptr_t data=capacity==15?address:*(uintptr_t*)address;
 if(length&&(!read((void*)data,(size_t)length)||memchr((void*)data,0,(size_t)length)))return 0;
 if(length)memcpy(out,(void*)data,(size_t)length);out[length]=0;return 1;
}
static int tooltip_same_string(uintptr_t address,const char *expected,TooltipReadable read){
 char value[513];return strlen(expected)<sizeof value&&tooltip_string(address,value,sizeof value,read)&&!strcmp(value,expected);
}
static int tooltip_signature(uintptr_t image,uintptr_t rva,const unsigned char *bytes,size_t n,TooltipReadable read){
 return read((void*)(image+rva),n)&&!memcmp((void*)(image+rva),bytes,n);
}
static int tooltip_supported_widget(uintptr_t image,uintptr_t widget,uintptr_t root,TooltipReadable read){
 if(!read((void*)widget,160)||*(uintptr_t*)(widget+104)!=root)return 0;
 uintptr_t vt=*(uintptr_t*)widget,rva=vt-image;
 if(rva!=0x2b454f0&&rva!=0x2b468c8&&rva!=0x2b421d8)return 0;
 if(!read((void*)vt,136)||*(uintptr_t*)vt!=image+0x22ae010)return 0;
 uintptr_t show=rva==0x2b454f0?0x22c4510:0x22a4440;
 uintptr_t hide=rva==0x2b454f0?0x22be1a0:0x22a4080;
 return *(uintptr_t*)(vt+120)==image+show&&*(uintptr_t*)(vt+128)==image+hide;
}
/* Returns1 only after native update and coherent nonempty core/owner readback.
 * Any failure after attempted=1 is uncertain and must never be replayed by an
 * acknowledgment retry. Caller owns ledger/session/world/requestID validation. */
static int tooltip_generate(uintptr_t image,uintptr_t owner,const struct TooltipSelector *selector,
 const char *request_id,const struct TooltipCalls *calls,struct TooltipOutcome *out){
 memset(out,0,sizeof *out);out->reason="bad_tooltip_request";
 if(!selector||!selector->source||!selector->name||!request_id||!calls||!calls->readable||
    !calls->elect||!calls->update||!calls->paused||!calls->ui_thread||!calls->persist_intent||
    !selector->source[0]||!selector->name[0]||strlen(selector->source)>512||strlen(selector->name)>512)return 0;
 TooltipReadable read=calls->readable;
 out->reason="tooltip_frame_thread_required";if(!calls->ui_thread(owner))return 0;
 out->reason="tooltip_owner_changed";
 if(!read((void*)(image+0x332f698),8)||*(uintptr_t*)(image+0x332f698)!=owner||
    !read((void*)owner,0x5b1)||*(uintptr_t*)owner!=image+0x2968ff0)return 0;
 uintptr_t root=*(uintptr_t*)(owner+0x4f8),core=*(uintptr_t*)(owner+0x4e8);
 if(!read((void*)(image+0x34531e0),8)||*(uintptr_t*)(image+0x34531e0)!=root||
    !read((void*)root,0x150)||*(uintptr_t*)root!=image+0x294a688||
    !read((void*)core,0x150)||*(uintptr_t*)core!=image+0x2b421d8||*(uintptr_t*)(core+104)!=root)return 0;
 out->reason="pause_required";if(!calls->paused(owner))return 0;
 out->core=core;
 /* Match the native routine's two early-return gates. Otherwise a nonempty
  * preexisting buffer could be mistaken for a newly generated native tooltip. */
 static const unsigned char gate_global[]={0x48,0x8b,0x05,0x21,0x4e,0x13,0x03,0xc3};
 static const unsigned char gate_field[]={0x48,0x8d,0x81,0x78,0x01,0x00,0x00,0xc3};
 out->reason="tooltip_generation_disabled";
 if(!tooltip_signature(image,0x1fa5e0,gate_global,sizeof gate_global,read)||
    !tooltip_signature(image,0x1fae70,gate_field,sizeof gate_field,read)||
    !read((void*)(image+0x332f408),8))return 0;
 uintptr_t settings=*(uintptr_t*)(image+0x332f408);
 if(!read((void*)(settings+0x188),1)||!*(unsigned char*)(settings+0x188)||*(unsigned char*)(owner+0x5b0))return 0;
 static const unsigned char elect_sig[]={0x44,0x8b,0x49,0x58,0x44,0x0f,0xb6,0x41,0x75,0x41,0x83,0xf9,0xff,0x74,0x2b};
 static const unsigned char update_sig[]={0x48,0x8b,0xc4,0x48,0x89,0x58,0x08,0x88,0x50,0x10,0x55,0x56,0x57,0x41,0x54};
 out->reason="tooltip_implementation_changed";
 if(!tooltip_signature(image,0x22ae010,elect_sig,sizeof elect_sig,read)||!tooltip_signature(image,0x2a44a0,update_sig,sizeof update_sig,read))return 0;
 uintptr_t match=0,definition=0;
 for(int table=0;table<2;table++){
  uintptr_t array=*(uintptr_t*)(root+(table?288:264));unsigned count=*(unsigned*)(root+(table?296:276));
  out->reason="tooltip_registry_invalid";
  if(count>500000||(!table&&count>*(unsigned*)(root+272))||(count&&!read((void*)array,(size_t)count*8)))return 0;
  for(unsigned i=0;i<count;i++){
   uintptr_t widget=((uintptr_t*)array)[i];if(!tooltip_supported_widget(image,widget,root,read))continue;
   if(!(*(unsigned char*)(widget+117)&8)||*(int*)(widget+0x58)<-1||widget==core)continue;
   uintptr_t candidate=*(uintptr_t*)(widget+96);if(!read((void*)candidate,104))continue;
   if(!tooltip_same_string(candidate+40,selector->name,read)||!tooltip_same_string(candidate+72,selector->source,read))continue;
   out->reason="ambiguous_tooltip_target";if(match&&match!=widget)return 0;match=widget;definition=candidate;
  }
 }
 out->reason="tooltip_target_not_found";if(!match)return 0;
 out->target=match;out->depth=*(int*)(match+0x58);out->before_target=*(uintptr_t*)(root+0x140);
 out->reason="tooltip_intent_not_persisted";if(!calls->persist_intent(request_id))return 0;
 out->attempted=1;
 calls->elect(image+0x22ae010,match,out->depth);
 out->reason="tooltip_target_election_unverified";
 if(*(uintptr_t*)(root+0x140)!=match||!(*(unsigned char*)(match+117)&0x20))return 0;
 calls->update(image+0x2a44a0,owner,1);out->updated=1;
 out->reason="tooltip_binding_changed";
 if(!tooltip_supported_widget(image,match,root,read)||*(uintptr_t*)(match+96)!=definition||
    *(uintptr_t*)(root+0x140)!=match||*(uintptr_t*)(owner+0x4f8)!=root||*(uintptr_t*)(owner+0x4e8)!=core||
    *(uintptr_t*)(image+0x332f698)!=owner||*(uintptr_t*)(image+0x34531e0)!=root||
    !tooltip_same_string(definition+40,selector->name,read)||!tooltip_same_string(definition+72,selector->source,read))return 0;
 out->reason="tooltip_text_unreadable";
 if(!tooltip_string(core+0x130,out->rendered,sizeof out->rendered,read)||
    !tooltip_string(owner+0x58,out->combined,sizeof out->combined,read)||
    !tooltip_string(owner+0x480,out->title,sizeof out->title,read)||
    !tooltip_string(owner+0x4a0,out->body,sizeof out->body,read))return 0;
 out->rendered_equals_combined=!strcmp(out->rendered,out->combined);
 out->local_shown=!!(*(unsigned char*)(core+117)&8);
 out->nonempty=out->rendered[0]&&out->combined[0];
 out->reason=out->nonempty?"native_tooltip_generated":"native_tooltip_empty";
 return out->nonempty;
}
#endif
