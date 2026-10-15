#ifndef HOI4_NATIVE_SAVE_CANDIDATE_H
#define HOI4_NATIVE_SAVE_CANDIDATE_H
/* Source-only ordinary local save wrapper. Caller binds the game UI/frame
   thread, pins executable and owns the unique mcp_ basename/request ledger.
   Native save can replace files: preflight both unique final and temp names.
   Native return/file existence is not restart/load verification. */
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#ifndef SAVE_STRING
#define SAVE_STRING(fn,out,text) ((void*(*)(void*,const char*))(fn))((out),(text))
#endif
#ifndef SAVE_STRING_DESTROY
#define SAVE_STRING_DESTROY(fn,s) ((void(*)(void*))(fn))(s)
#endif
#ifndef SAVE_DESCRIPTOR
#define SAVE_DESCRIPTOR(fn,d) ((void*(*)(void*))(fn))(d)
#endif
#ifndef SAVE_DESCRIPTOR_DESTROY
#define SAVE_DESCRIPTOR_DESTROY(fn,d) ((void(*)(void*))(fn))(d)
#endif
#ifndef SAVE_FILL
#define SAVE_FILL(fn,m,s,d) ((void(*)(uintptr_t,void*,void*))(fn))((m),(s),(d))
#endif
#ifndef SAVE_PATH
#define SAVE_PATH(fn,m,out,d,base) ((void*(*)(uintptr_t,void*,void*,uintptr_t))(fn))((m),(out),(d),(base))
#endif
#ifndef SAVE_SUFFIX
#define SAVE_SUFFIX(fn,m,d,ext,path) ((int(*)(uintptr_t,void*,uintptr_t,void*))(fn))((m),(d),(ext),(path))
#endif
#ifndef SAVE_EXISTS
#define SAVE_EXISTS(fn,m,d) ((unsigned char(*)(uintptr_t,void*))(fn))((m),(d))
#endif
#ifndef SAVE_REQUEST
#define SAVE_REQUEST(fn,m,d) ((unsigned char(*)(uintptr_t,void*,int))(fn))((m),(d),0)
#endif
struct save_outcome {const char *reason;int requested,native_return,final_exists,temp_exists,verified;char basename[96],path[4096],temporary_path[4096];};
static int save_native_string(uintptr_t address,int(*readable)(const void*,size_t),char *out,size_t cap){
 if(!readable((void*)address,32))return 0;
 uint64_t n=*(uint64_t*)(address+16),capacity=*(uint64_t*)(address+24);
 if(n>=cap||n>capacity||capacity>65536)return 0;
 const char *p=capacity>15?*(const char**)address:(const char*)address;
 if(!readable(p,(size_t)n+1)||p[n]||memchr(p,0,(size_t)n))return 0;
 memcpy(out,p,(size_t)n);out[n]=0;return 1;
}
static int save_owned_basename(const char*s){
 if(!s||strncmp(s,"mcp_",4))return 0;size_t n=strlen(s);
 if(n<12||n>80)return 0;
 for(size_t i=0;i<n;i++)if(!((s[i]>='a'&&s[i]<='z')||(s[i]>='0'&&s[i]<='9')||s[i]=='_'))return 0;
 return 1;
}
static int save_owned_local(uintptr_t image,uintptr_t owner,uintptr_t world,const char *basename,const char *rid,
 int(*readable)(const void*,size_t),int(*intent)(const char*),struct save_outcome*out){
 memset(out,0,sizeof *out);out->reason="invalid_owned_save_name";
 if(!save_owned_basename(basename))return 0;
 memcpy(out->basename,basename,strlen(basename)+1);
 out->reason="save_owner_or_world_changed";
 if(!readable((void*)(image+0x332f698),8)||*(uintptr_t*)(image+0x332f698)!=owner||
    !readable((void*)(image+0x332f260),8)||*(uintptr_t*)(image+0x332f260)!=world||
    !readable((void*)owner,0x778)||*(uintptr_t*)owner!=image+0x2968ff0||
    !readable((void*)(image+0x2968ff0+0x370),8)||*(uintptr_t*)(image+0x2968ff0+0x370)!=image+0xdccf20)return 0;
 uintptr_t manager=*(uintptr_t*)(owner+0x770);char extension[24];
 out->reason="save_manager_binding_changed";
 if(!readable((void*)manager,0x4c1)||!save_native_string(manager+0x88,readable,extension,sizeof extension)||strcmp(extension,".hoi4"))return 0;
 uint64_t name[4]={0},temp_name[4]={0},descriptor[28]={0},temp_descriptor[28]={0},path[4]={0},temp_path[4]={0};
 char temp[96];snprintf(temp,sizeof temp,"%s_temp",basename);
 SAVE_STRING(image+0x11e130,name,basename);SAVE_STRING(image+0x11e130,temp_name,temp);
 SAVE_DESCRIPTOR(image+0xbc0880,descriptor);SAVE_DESCRIPTOR(image+0xbc0880,temp_descriptor);
 SAVE_FILL(image+0xd9aa30,manager,name,descriptor);SAVE_FILL(image+0xd9aa30,manager,temp_name,temp_descriptor);
 int success=0;out->reason="cloud_save_not_owned_local";
 if(((unsigned char*)descriptor)[0x55]||((unsigned char*)temp_descriptor)[0x55])goto cleanup;
 SAVE_PATH(image+0xd9bea0,manager,path,descriptor,manager+0xa8);
 SAVE_SUFFIX(image+0xd99350,manager,descriptor,manager+0x88,path);
 SAVE_PATH(image+0xd9bea0,manager,temp_path,temp_descriptor,manager+0xa8);
 SAVE_SUFFIX(image+0xd99350,manager,temp_descriptor,manager+0x88,temp_path);
 out->reason="save_path_unreadable";
 if(!save_native_string((uintptr_t)path,readable,out->path,sizeof out->path)||
    !save_native_string((uintptr_t)temp_path,readable,out->temporary_path,sizeof out->temporary_path))goto cleanup;
 out->final_exists=SAVE_EXISTS(image+0xda5290,manager,descriptor)!=0;
 out->temp_exists=SAVE_EXISTS(image+0xda5290,manager,temp_descriptor)!=0;
 out->reason="owned_save_already_exists";if(out->final_exists||out->temp_exists)goto cleanup;
 out->reason="save_intent_failed";if(!intent(rid))goto cleanup;
 out->requested=1;out->native_return=SAVE_REQUEST(image+0xda3530,manager,descriptor)!=0;
 out->reason="save_postcondition_failed";
 out->final_exists=SAVE_EXISTS(image+0xda5290,manager,descriptor)!=0;
 out->temp_exists=SAVE_EXISTS(image+0xda5290,manager,temp_descriptor)!=0;
 if(readable((void*)(image+0x332f698),8)&&*(uintptr_t*)(image+0x332f698)==owner&&
    readable((void*)(image+0x332f260),8)&&*(uintptr_t*)(image+0x332f260)==world&&
    readable((void*)(owner+0x770),8)&&*(uintptr_t*)(owner+0x770)==manager&&
    out->native_return&&out->final_exists&&!out->temp_exists){out->verified=1;out->reason="owned_local_save_file_observed";success=1;}
cleanup:
 /* Descriptor and CString lifetimes follow ordinary UI stack objects; the
    save request returns before its descriptor is destroyed in normal caller. */
 SAVE_STRING_DESTROY(image+0x11ebd0,temp_path);SAVE_STRING_DESTROY(image+0x11ebd0,path);
 SAVE_DESCRIPTOR_DESTROY(image+0xbc0960,temp_descriptor);SAVE_DESCRIPTOR_DESTROY(image+0xbc0960,descriptor);
 SAVE_STRING_DESTROY(image+0x11ebd0,temp_name);SAVE_STRING_DESTROY(image+0x11ebd0,name);
 return success;
}
#endif
