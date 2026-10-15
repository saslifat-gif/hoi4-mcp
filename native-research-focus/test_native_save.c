#include <assert.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static void* str(void*,const char*);static void destroy(void*);static void*fake_descriptor(void*);static void descriptor_destroy(void*);
static void fill(uintptr_t,void*,void*);static void*fake_path(uintptr_t,void*,void*,uintptr_t);static int suffix(uintptr_t,void*,uintptr_t,void*);
static unsigned char exists(uintptr_t,void*);static unsigned char request(uintptr_t,void*);
#define SAVE_STRING(fn,o,t) str(o,t)
#define SAVE_STRING_DESTROY(fn,s) destroy(s)
#define SAVE_DESCRIPTOR(fn,d) fake_descriptor(d)
#define SAVE_DESCRIPTOR_DESTROY(fn,d) descriptor_destroy(d)
#define SAVE_FILL(fn,m,s,d) fill(m,s,d)
#define SAVE_PATH(fn,m,o,d,b) fake_path(m,o,d,b)
#define SAVE_SUFFIX(fn,m,d,e,p) suffix(m,d,e,p)
#define SAVE_EXISTS(fn,m,d) exists(m,d)
#define SAVE_REQUEST(fn,m,d) request(m,d)
#include "native_save_candidate.h"
static int final_present,temp_present,cloud,write_ok=1,requested,intents,created,destroyed;
static uintptr_t expected_manager;
static const char*text(void*s){uint64_t*p=s;return p[3]>15?(char*)(uintptr_t)p[0]:(char*)s;}
static void*str(void*out,const char*t){uint64_t*p=out;size_t n=strlen(t);memset(out,0,32);p[2]=n;p[3]=n>15?n:15;if(n>15){char*q=malloc(n+1);assert(q);memcpy(q,t,n+1);p[0]=(uintptr_t)q;}else memcpy(out,t,n+1);return out;}
static void destroy(void*s){uint64_t*p=s;if(p[3]>15)free((void*)(uintptr_t)p[0]);memset(s,0,32);}
static void*fake_descriptor(void*d){memset(d,0,224);str(d,"");str((char*)d+32,"");created++;return d;}
static void descriptor_destroy(void*d){destroy((char*)d+32);destroy(d);destroyed++;}
static void fill(uintptr_t m,void*s,void*d){assert(m==expected_manager);destroy((char*)d+32);str((char*)d+32,text(s));((char*)d)[0x55]=(char)cloud;}
static void*fake_path(uintptr_t m,void*out,void*d,uintptr_t base){assert(m==expected_manager&&base==m+0xa8);char b[256];snprintf(b,sizeof b,"save games/%s",text((char*)d+32));return str(out,b);}
static int suffix(uintptr_t m,void*d,uintptr_t e,void*p){(void)d;assert(m==expected_manager&&e==m+0x88);char b[300];snprintf(b,sizeof b,"%s.hoi4",text(p));destroy(p);str(p,b);return 1;}
static unsigned char exists(uintptr_t m,void*d){assert(m==expected_manager);return (unsigned char)(strstr(text((char*)d+32),"_temp")?temp_present:final_present);}
static unsigned char request(uintptr_t m,void*d){assert(m==expected_manager&&!((char*)d)[0x55]);requested++;if(write_ok){final_present=1;temp_present=0;}return 1;}
static int readable(const void*p,size_t n){return p&&n<10000000;}
static int intent(const char*rid){intents++;return !strcmp(rid,"save-1");}
int main(void){uintptr_t image=(uintptr_t)calloc(1,0x35e2000),owner=(uintptr_t)calloc(1,0x778),manager=(uintptr_t)calloc(1,0x4c1),world=0x12345;assert(image&&owner&&manager);expected_manager=manager;
 *(uintptr_t*)(image+0x332f698)=owner;*(uintptr_t*)(image+0x332f260)=world;*(uintptr_t*)owner=image+0x2968ff0;*(uintptr_t*)(owner+0x770)=manager;*(uintptr_t*)(image+0x2968ff0+0x370)=image+0xdccf20;str((void*)(manager+0x88),".hoi4");struct save_outcome out;
 assert(save_owned_local(image,owner,world,"mcp_12345678","save-1",readable,intent,&out));assert(out.requested&&out.verified&&requested==1&&intents==1&&created==destroyed);assert(!strcmp(out.path,"save games/mcp_12345678.hoi4"));assert(!strcmp(out.temporary_path,"save games/mcp_12345678_temp.hoi4"));
 assert(!save_owned_local(image,owner,world,"mcp_12345678","save-1",readable,intent,&out));assert(!strcmp(out.reason,"owned_save_already_exists")&&requested==1&&created==destroyed);
 final_present=0;temp_present=1;assert(!save_owned_local(image,owner,world,"mcp_12345678","save-1",readable,intent,&out));assert(requested==1&&intents==1);temp_present=0;
 cloud=1;assert(!save_owned_local(image,owner,world,"mcp_12345678","save-1",readable,intent,&out));assert(!strcmp(out.reason,"cloud_save_not_owned_local")&&requested==1&&created==destroyed);cloud=0;
 assert(!save_owned_local(image,owner,world,"mcp_../../evil","save-1",readable,intent,&out));assert(!strcmp(out.reason,"invalid_owned_save_name"));
 assert(!save_owned_local(image,owner,world,"mcp_12345678","wrong",readable,intent,&out));assert(!strcmp(out.reason,"save_intent_failed")&&requested==1);
 write_ok=0;assert(!save_owned_local(image,owner,world,"mcp_12345678","save-1",readable,intent,&out));assert(out.requested&&!out.verified&&requested==2&&created==destroyed);
 *(uintptr_t*)(image+0x332f260)=0;assert(!save_owned_local(image,owner,world,"mcp_12345678","save-1",readable,intent,&out));assert(!strcmp(out.reason,"save_owner_or_world_changed")&&requested==2);
 destroy((void*)(manager+0x88));free((void*)manager);free((void*)owner);free((void*)image);return 0;}
