/* Pinned world-tension UI action; called only from the paused game frame. */
typedef void (*WorldTensionApply)(void*);
static const char *world_tension_failure_stage(const char *error){
 return !strcmp(error,"window_binding_changed")||!strcmp(error,"window_state_unverified")?"execution_uncertain":"rejected";
}
static const char *change_world_tension(uintptr_t owner,uintptr_t gui,int shown,WorldTensionApply open,WorldTensionApply close){
 if(!!(*(unsigned char*)(gui+117)&8)!=shown)(shown?open:close)((void*)owner);
 if(!readable((void*)gui,160)||*(uintptr_t*)(owner+0x570)+48!=gui)return "window_binding_changed";
 return !!(*(unsigned char*)(gui+117)&8)==shown?NULL:"window_state_unverified";
}
static const char *select_world_tension_view(uintptr_t owner,int view,WorldTensionApply apply){
 if(*(int*)(owner+0x5a0)!=view)apply((void*)owner);
 return *(int*)(owner+0x5a0)==view?NULL:"window_state_unverified";
}
static const char *world_tension_action(int shown,int *before,int *after,int view){
 uintptr_t root=*(uintptr_t*)(image+0x34531e0),match=0,window=0;
 if(!readable((void*)root,304)||*(uintptr_t*)root!=image+0x294a688)return "gui_root_mismatch";
 for(int table=0;table<2;table++){
  uintptr_t array=*(uintptr_t*)(root+(table?288:264));unsigned count=*(unsigned*)(root+(table?296:276));
  if(count>500000||(!table&&count>*(unsigned*)(root+272))||(count&&!readable((void*)array,(SIZE_T)count*8)))return "registry_invalid";
  for(unsigned i=0;i<count;i++){
   uintptr_t gui=((uintptr_t*)array)[i];if(!readable((void*)gui,160)||*(uintptr_t*)(gui+104)!=root)continue;
   uintptr_t handler=*(uintptr_t*)(gui+80);if(handler<56||!readable((void*)(handler-56),0x578))continue;
   uintptr_t owner=handler-56;
   if(*(uintptr_t*)owner!=image+0x2a133d8||*(uintptr_t*)handler!=image+0x2a13478||*(uintptr_t*)(owner+0x570)+48!=gui)continue;
   uintptr_t vt=*(uintptr_t*)gui;
   if(!readable((void*)(vt+120),16)||*(uintptr_t*)(vt+120)!=image+0x22c4510||*(uintptr_t*)(vt+128)!=image+0x22be1a0)return "window_methods_changed";
   if(match&&match!=owner)return "ambiguous_window";match=owner;window=gui;
  }
 }
 if(!match)return "window_not_found";
 static const unsigned char open_sig[]={0x40,0x53,0x48,0x83,0xec,0x20,0x48,0x8b,0xd9,0xe8,0xc2,0xe1,0x2c,0xff,0x48,0x8b};
 static const unsigned char close_sig[]={0x40,0x53,0x48,0x83,0xec,0x20,0x48,0x8b,0xd9,0x48,0x8b,0x89,0x70,0x05,0x00,0x00};
 if(!alert_signature(0x18b4340,open_sig,sizeof open_sig)||!alert_signature(0xb7cc20,close_sig,sizeof close_sig))return "window_implementation_changed";
 if(view>=0){
  if(!readable((void*)match,0x1548))return "view_binding_unavailable";
  uintptr_t glue=match+(view==4?0x1520:0x608),target=*(uintptr_t*)(glue+16);
  static const unsigned char wars_sig[]={0x83,0xb9,0xa0,0x05,0x00,0x00,0x04,0x75,0x15};
  static const unsigned char date_sig[]={0x83,0xb9,0xa0,0x05,0x00,0x00,0x00,0x75,0x15};
  if(*(uintptr_t*)(glue+32)!=match||target!=image+(view==4?0x18b3f50:0x18b3fd0)||!alert_signature(target-image,view==4?wars_sig:date_sig,9))return "view_implementation_changed";
  const char *error=select_world_tension_view(match,view,(WorldTensionApply)target);if(error)return error;
 }
 *before=!!(*(unsigned char*)(window+117)&8);
 const char *error=change_world_tension(match,window,shown,(WorldTensionApply)(image+0x18b4340),(WorldTensionApply)(image+0xb7cc20));
 if(!error)*after=!!(*(unsigned char*)(window+117)&8);return error;
}
static const char *world_tension_window(int shown,int *before,int *after){return world_tension_action(shown,before,after,-1);}
