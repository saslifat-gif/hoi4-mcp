/* Invoke only the pinned engine tooltip generator on the paused game thread.
 * Output is freshly generated at the receipt tick, not eternally current. */
static int alert_signature(uintptr_t rva,const unsigned char *bytes,SIZE_T n){
 return readable((void*)(image+rva),n)&&!memcmp((void*)(image+rva),bytes,n);
}
static int json_alert_string(char *out,SIZE_T cap,SIZE_T *used,const unsigned char *s){
 if(!readable(s,32))return 0;
 SIZE_T len=*(const SIZE_T*)(s+16),capacity=*(const SIZE_T*)(s+24);
 if(len>4096||capacity<len||capacity>65536||(capacity<16&&capacity!=15))return 0;
 const unsigned char *text=capacity<16?s:*(const unsigned char*const*)s;
 if(len&&!readable(text,len))return 0;
 if(*used+2>=cap)return 0;out[(*used)++]='"';
 for(SIZE_T i=0;i<len;i++){
  unsigned char v=text[i];if(*used+7>=cap)return 0;
  if(v<32){*used+=(SIZE_T)sprintf(out+*used,"\\u%04x",v);}
  else{if(v=='"'||v=='\\')out[(*used)++]='\\';out[(*used)++]=(char)v;}
 }
 out[(*used)++]='"';out[*used]=0;return 1;
}
static const char *refresh_alert_result(int kind,char *out,SIZE_T cap,const char *rid,int tick){
 uintptr_t gui_root=*(uintptr_t*)(image+0x34531e0),match=0;
 if(!readable((void*)gui_root,304)||*(uintptr_t*)gui_root!=image+0x294a688)return "gui_root_mismatch";
 /* Registered vector and verified sparse dynamic slots. */
 for(int table=0;table<2;table++){
  uintptr_t array=*(uintptr_t*)(gui_root+(table?288:264));
  unsigned count=*(unsigned*)(gui_root+(table?296:276));
  if(count>500000||(!table&&count>*(unsigned*)(gui_root+272))|| (count&&!readable((void*)array,(SIZE_T)count*8)))return "registry_invalid";
  for(unsigned i=0;i<count;i++){
   uintptr_t gui=((uintptr_t*)array)[i];if(!readable((void*)gui,160))continue;
   uintptr_t vt=*(uintptr_t*)gui;if(!readable((void*)(vt+120),16)||*(uintptr_t*)(vt+120)!=image+0x22c4510||*(uintptr_t*)(vt+128)!=image+0x22be1a0||*(uintptr_t*)(gui+104)!=gui_root||!(*(unsigned char*)(gui+117)&8))continue;
   uintptr_t handler=*(uintptr_t*)(gui+80);if(handler<40||!readable((void*)(handler-40),0x560))continue;
   uintptr_t owner=handler-40;
   if(*(uintptr_t*)owner!=image+0x29468f8||*(uintptr_t*)handler!=image+0x2946920||*(uintptr_t*)(owner+0x38)+48!=gui||*(int*)(owner+0x48)!=kind)continue;
   if(match&&match!=owner)return "ambiguous_alert";match=owner;
  }
 }
 if(!match)return "alert_not_shown";
 static const unsigned char generator[]={0x48,0x8b,0xc4,0x48,0x89,0x58,0x20,0x48,0x89,0x50,0x10,0x55,0x56,0x57,0x41,0x54};
 static const unsigned char destructor[]={0x40,0x53,0x48,0x83,0xec,0x20,0x48,0x8b,0x51,0x58,0x48,0x8b,0xd9,0x48,0x83,0xfa};
 if(!alert_signature(0xb0ab70,generator,sizeof generator)||!alert_signature(0x14d0d0,destructor,sizeof destructor))return "tooltip_implementation_changed";
 uintptr_t manager=*(uintptr_t*)(match+0x30),context=*(uintptr_t*)(match+0x558);
 if(!readable((void*)(manager+24*(kind+0xf0e)),16))return "manager_unreadable";
 __declspec(align(16)) unsigned char result[0x410]={0};
 void *generated=((void*(*)(void*,void*,int,void*,void*,void*))(image+0xb0ab70))((void*)manager,result,kind,NULL,NULL,(void*)context);
 if(generated!=result)return "result_binding_mismatch";
 FILETIME now;GetSystemTimeAsFileTime(&now);ULARGE_INTEGER stamp;stamp.LowPart=now.dwLowDateTime;stamp.HighPart=now.dwHighDateTime;
 SIZE_T used=(SIZE_T)snprintf(out,cap,"{\"session_id\":\"%s\",\"request_id\":\"%s\",\"stage\":\"alert_refreshed\",\"native_alert_kind\":%d,\"native_tick\":%d,\"generated_unix_ms\":%llu,\"freshness_scope\":\"engine_generation_at_receipt_tick\",\"uses_keyboard_or_mouse\":false,\"native_callback_invoked\":true,\"ui_cache_writes\":true,\"complete_message_coverage\":false,\"raw_title\":",sid,rid,kind,tick,(unsigned long long)((stamp.QuadPart-116444736000000000ULL)/10000));
 int ok=used<cap&&json_alert_string(out,cap,&used,result);
 if(ok&&used+12<cap){memcpy(out+used,",\"raw_body\":",12);used+=12;ok=json_alert_string(out,cap,&used,result+32);}
 else ok=0;
 ((void(*)(void*))(image+0x14d0d0))(result);
 if(*(int*)(bound_world+0x468)!=tick)return "game_tick_changed_during_read";
 if(!ok||used+2>=cap)return "text_limit_or_layout";
 out[used++]='}';out[used]=0;return NULL;
}
