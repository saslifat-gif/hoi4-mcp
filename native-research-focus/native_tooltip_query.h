/* Explicit native tooltip result, through the normal owner's virtual+3a0.
 * This does not render/update Core or elect the physical mouse target. */
#ifndef HOI4_NATIVE_TOOLTIP_QUERY_H
#define HOI4_NATIVE_TOOLTIP_QUERY_H
#include "native_tooltip.h"
struct TooltipQueryCalls {
 TooltipReadable readable;
 TooltipGate paused,ui_thread;
 TooltipIntent persist_intent;
 uintptr_t (*query)(uintptr_t function,uintptr_t owner,uintptr_t output,uintptr_t widget,unsigned char secondary);
 void (*destroy)(uintptr_t function,uintptr_t output);
};
struct TooltipQueryOutcome {
 const char *reason;
 int attempted,returned,destroyed,nonempty,native_disabled;
 uintptr_t target,definition,root,tooltip_owner,tooltip_method,owner_target_before,owner_target_after;
 char title[4097],body[8193],auxiliary[4097];
 unsigned char flag60,flag400,flag401;
};
/* The explicit getter uses virtual+230, not the widget's mouse-election slot.
 * CButtonStandard overrides slot0; it is deliberately excluded from the older
 * Core election/update path but has the same audited tooltip-owner getter. */
static int tooltip_query_supported_widget(uintptr_t image,uintptr_t widget,uintptr_t root,TooltipReadable read){
 if(tooltip_supported_widget(image,widget,root,read))return 1;
 if(!read((void*)widget,160)||*(uintptr_t*)(widget+104)!=root)return 0;
 uintptr_t vt=*(uintptr_t*)widget;
 return vt==image+0x2b472e8&&read((void*)vt,0x238)&&
  *(uintptr_t*)vt==image+0x22d17d0&&*(uintptr_t*)(vt+120)==image+0x22a4440&&
  *(uintptr_t*)(vt+128)==image+0x22a4080&&*(uintptr_t*)(vt+0x230)==image+0x6773a0;
}
static int tooltip_query(uintptr_t image,uintptr_t owner,const struct TooltipSelector *selector,
 const char *request_id,const struct TooltipQueryCalls *calls,struct TooltipQueryOutcome *out){
 (void)tooltip_generate; /* Share audited string/signature/typed-widget readers only. */
 memset(out,0,sizeof *out);out->reason="bad_tooltip_request";
 if(!selector||!selector->source||!selector->name||!request_id||!calls||!calls->readable||!calls->paused||
    !calls->ui_thread||!calls->persist_intent||!calls->query||!calls->destroy||!selector->source[0]||
    !selector->name[0]||strlen(selector->source)>512||strlen(selector->name)>512)return 0;
 TooltipReadable read=calls->readable;
 out->reason="tooltip_frame_thread_required";if(!calls->ui_thread(owner))return 0;
 out->reason="pause_required";if(!calls->paused(owner))return 0;
 out->reason="tooltip_owner_changed";
 if(!read((void*)(image+0x332f698),8)||*(uintptr_t*)(image+0x332f698)!=owner||!read((void*)owner,0x730)||
    *(uintptr_t*)owner!=image+0x2968ff0||!read((void*)(image+0x2968ff0+0x3a0),8)||
    *(uintptr_t*)(image+0x2968ff0+0x3a0)!=image+0x163bb80)return 0;
 uintptr_t root=*(uintptr_t*)(owner+0x4f8);
 if(!read((void*)(image+0x34531e0),8)||*(uintptr_t*)(image+0x34531e0)!=root||
    !read((void*)root,0x150)||*(uintptr_t*)root!=image+0x294a688)return 0;
 static const unsigned char getter[]={0x48,0x89,0x5c,0x24,8,0x48,0x89,0x6c,0x24,0x18,0x48,0x89,0x74,0x24,0x20,0x48};
 static const unsigned char destructor[]={0x40,0x53,0x48,0x83,0xec,0x20,0x48,0x8b,0x51,0x58,0x48,0x8b,0xd9,0x48,0x83,0xfa};
 static const unsigned char owner_getter[]={0x48,0x8b,0x41,0x50,0xc3};
 out->reason="tooltip_implementation_changed";
 if(!tooltip_signature(image,0x163bb80,getter,sizeof getter,read)||
    !tooltip_signature(image,0x14d0d0,destructor,sizeof destructor,read)||
    !tooltip_signature(image,0x6773a0,owner_getter,sizeof owner_getter,read))return 0;
 uintptr_t match=0,definition=0;
 for(int table=0;table<2;table++){
  uintptr_t array=*(uintptr_t*)(root+(table?288:264));unsigned count=*(unsigned*)(root+(table?296:276));
  out->reason="tooltip_registry_invalid";
  if(count>500000||(!table&&count>*(unsigned*)(root+272))||(count&&!read((void*)array,(size_t)count*8)))return 0;
  for(unsigned i=0;i<count;i++){
   uintptr_t widget=((uintptr_t*)array)[i];if(!tooltip_query_supported_widget(image,widget,root,read))continue;
   if(!(*(unsigned char*)(widget+117)&8)||widget==*(uintptr_t*)(owner+0x4e8))continue;
   uintptr_t candidate=*(uintptr_t*)(widget+96);if(!read((void*)candidate,0xbb))continue;
   if(!tooltip_same_string(candidate+40,selector->name,read)||!tooltip_same_string(candidate+72,selector->source,read))continue;
   out->reason="ambiguous_tooltip_target";if(match&&match!=widget)return 0;match=widget;definition=candidate;
  }
 }
 out->reason="tooltip_target_not_found";if(!match)return 0;
 uintptr_t vt=*(uintptr_t*)match;
 out->reason="tooltip_callback_invalid";
 if(!read((void*)(vt+0x230),8)||*(uintptr_t*)(vt+0x230)!=image+0x6773a0)return 0;
 uintptr_t callback=*(uintptr_t*)(match+0x50),method=0;
 if(callback){
  if(!read((void*)callback,8))return 0;uintptr_t cvt=*(uintptr_t*)callback;
  if(!read((void*)cvt,8))return 0;method=*(uintptr_t*)cvt;
  /* Pinned PE .text bounds. No caller-supplied callback accepted. */
  if(method<image+0x1000||method>=image+0x27060d8||!read((void*)method,1))return 0;
 }
 out->target=match;out->definition=definition;out->root=root;out->tooltip_owner=callback;out->tooltip_method=method;
 out->owner_target_before=*(uintptr_t*)(owner+0x728);
 if(!read((void*)(image+0x332f61f),1))return 0;
 out->native_disabled=!!(*(unsigned char*)(image+0x332f61f)||(*(unsigned char*)(match+117)&4));
 out->reason="tooltip_intent_not_persisted";if(!calls->persist_intent(request_id))return 0;
 /* Uninitialized native return storage; getter itself constructs all fields.
  * Destructor must run exactly once after a normal return, including bad text. */
 _Alignas(16) uintptr_t storage[0x420/sizeof(uintptr_t)];
 out->attempted=1;
 uintptr_t returned=calls->query(image+0x163bb80,owner,(uintptr_t)storage,match,0);out->returned=1;
 int copied=returned==(uintptr_t)storage&&tooltip_string((uintptr_t)storage,out->title,sizeof out->title,read)&&
   tooltip_string((uintptr_t)storage+32,out->body,sizeof out->body,read)&&
   tooltip_string((uintptr_t)storage+64,out->auxiliary,sizeof out->auxiliary,read);
 out->flag60=*((unsigned char*)storage+0x60);out->flag400=*((unsigned char*)storage+0x400);out->flag401=*((unsigned char*)storage+0x401);
 calls->destroy(image+0x14d0d0,(uintptr_t)storage);out->destroyed=1;
 out->reason="tooltip_binding_changed";
 if(!tooltip_query_supported_widget(image,match,root,read)||*(uintptr_t*)(match+96)!=definition||
    *(uintptr_t*)(match+0x50)!=callback||*(uintptr_t*)(owner+0x4f8)!=root||
    *(uintptr_t*)(image+0x332f698)!=owner||*(uintptr_t*)(image+0x34531e0)!=root||
    !tooltip_same_string(definition+40,selector->name,read)||!tooltip_same_string(definition+72,selector->source,read))return 0;
 out->owner_target_after=*(uintptr_t*)(owner+0x728);
 out->reason="tooltip_result_unreadable";if(!copied)return 0;
 out->nonempty=out->title[0]||out->body[0]||out->auxiliary[0];
 out->reason=out->nonempty?"native_tooltip_result":"native_tooltip_result_empty";
 return 1; /* Empty is a completed query, never proof of a rendered tooltip. */
}
#endif
