#include <stdint.h>
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
static unsigned char command[64];
static uintptr_t fake_factory(uintptr_t fn);
static unsigned char fake_validate(uintptr_t fn,uintptr_t cmd,void *err);
static void fake_execute(uintptr_t fn,uintptr_t cmd);
#define POLITICS_VALIDATE(fn,cmd,err) fake_validate(fn,cmd,err)
#define POLITICS_EXECUTE(fn,cmd) fake_execute(fn,cmd)
#define POLITICS_FACTORY(fn) fake_factory(fn)
#include "native_trade_command_candidate.h"
static uintptr_t image;
static int executions=0;
static unsigned char fake_validate(uintptr_t fn,uintptr_t cmd,void *err){assert(fn==image+0x1ba56d0&&cmd==(uintptr_t)command);(void)err;return 1;}
static void fake_execute(uintptr_t fn,uintptr_t cmd){assert(fn==image+0x1ba54b0&&cmd==(uintptr_t)command);executions++;}
static int readable(const void*p,size_t n){return p!=NULL&&n<10000000;}
static int intent(const char*r){return !strcmp(r,"request-1");}
static int name(uintptr_t p,size_t off,char*out,size_t n){(void)off;return snprintf(out,n,"%s",(char*)p)>0;}
static uintptr_t fake_factory(uintptr_t fn){assert(fn==image+0x1ba53d0);memset(command,0,sizeof command);*(uintptr_t*)command=image+0x2a49150;return (uintptr_t)command;}
static uintptr_t alloc(size_t n){void*p=calloc(1,n);assert(p);return (uintptr_t)p;}
static void vec(uintptr_t p,uintptr_t list,int n){*(uintptr_t*)p=list;*(int*)(p+8)=n;*(int*)(p+12)=n;}
static int64_t allowed_raw=2400000;
static uintptr_t wanted_export_resources,wanted_resource;
static void limits(uintptr_t resources,const int32_t*actor,uintptr_t resource,int64_t*max,int64_t*existing,void*tooltip){
 assert(resources==wanted_export_resources&&resource==wanted_resource&&actor[0]==10&&!tooltip);
 *max=allowed_raw;*existing=2400000;
}
static int64_t *rate(int64_t*out,void*r,const int32_t*i,const int32_t*e,int32_t cic){assert((uintptr_t)r==wanted_resource&&i[0]==10&&e[0]==20);*out=(int64_t)cic*800000;return out;}
int main(void){
 image=alloc(0x35e1b00);uintptr_t importer=alloc(0x1200),exporter=alloc(0x1200),im=alloc(0x750),em=alloc(0x750);
 *(uint32_t*)(importer+8)=10;*(uint32_t*)(exporter+8)=20;*(uintptr_t*)(importer+0x11f8)=im;*(uintptr_t*)(exporter+0x11f8)=em;
 *(uintptr_t*)im=*(uintptr_t*)em=image+0x295c4b0;*(uint32_t*)(im+0x20)=10;*(uint32_t*)(em+0x20)=20;
 uintptr_t db=alloc(0x38),null=alloc(0xe8),resource=alloc(0xe8),list=alloc(16),names=alloc(64);
 *(uintptr_t*)(image+0x332f088)=db;*(uintptr_t*)db=image+0x2943b18;*(uintptr_t*)null=image+0x2943b48;*(uintptr_t*)resource=image+0x2951508;
 *(unsigned char*)(resource+0x10)=1;*(uint32_t*)(resource+8)=1;*(uint32_t*)(resource+0xd8)=1;
 ((uintptr_t*)list)[0]=null;((uintptr_t*)list)[1]=resource;vec(db+0x28,list,2);
 *(unsigned char*)(image+0x35e1ab0)=1;*(int*)(image+0x35e1ab4)=1;*(uintptr_t*)(image+0x35e1ae0)=names;memcpy((void*)(names+32),"steel",6);
 struct trade_binding b;assert(trade_bind(image,importer,exporter,"steel",readable,name,&b));assert(b.resource==resource&&b.index==1);
 struct trade_record_observation before;assert(trade_record(image,&b,readable,&before));assert(!before.pointer);
 uintptr_t record=alloc(0xe8),imports=alloc(8),exports=alloc(8),vectors=alloc(48);
 *(uintptr_t*)record=image+0x295c410;*(uintptr_t*)(record+0x80)=em;*(uint32_t*)(record+0x88)=10;*(uintptr_t*)(record+0x90)=resource;
 *(int32_t*)(record+0xe0)=3;*(int32_t*)(record+0xe4)=2;*(int64_t*)(record+0x98)=100000;
 *(uintptr_t*)imports=*(uintptr_t*)exports=record;vec(im+0x740,imports,1);*(uintptr_t*)(em+0x728)=vectors;vec(vectors+24,exports,1);
 assert(trade_record(image,&b,readable,&before));assert(before.required_cic==3&&before.lended_cic==2&&before.delivered_raw==100000);
 *(int*)(vectors+24+12)=0;assert(!trade_record(image,&b,readable,&before));*(int*)(vectors+24+12)=1;assert(trade_record(image,&b,readable,&before));
 trade_conversion p={24,3,300000,2400000};uintptr_t cmd=0;
 int32_t itag[2]={10,1},etag[2]={20,2};struct trade_offer_observation offer;wanted_export_resources=em;wanted_resource=resource;
 assert(trade_offer_allows(limits,&b,itag,&p,&offer));assert(offer.existing_requested_raw_units==2400000);
 allowed_raw=2300000;assert(!trade_offer_allows(limits,&b,itag,&p,&offer));allowed_raw=0;assert(!trade_offer_allows(limits,&b,itag,&p,&offer));
 int64_t nominal=0;assert(trade_nominal_requested(rate,&b,itag,etag,&before,&nominal));assert(nominal==2400000);
 assert(trade_construct(image,&b,&p,"request-1",readable,intent,&cmd)==POLITICS_OBJECT_CONSTRUCTED);
 assert(*(uint32_t*)(cmd+0x28)==10&&*(uint32_t*)(cmd+0x2c)==20&&*(uintptr_t*)(cmd+0x30)==resource&&*(int32_t*)(cmd+0x38)==24);
 *(uintptr_t*)(image+0x2a49150+9*8)=image+0x1ba56d0;*(uintptr_t*)(image+0x2a49150+10*8)=image+0x1ba54b0;
 int observed=0;char error=0;assert(trade_execute_bound(image,cmd,&b,&p,&error,"request-1",readable,intent,&before,&observed)==POLITICS_EXECUTION_RETURNED);assert(observed&&executions==1);
 assert(trade_execute_bound(image,cmd,&b,&p,NULL,"request-1",readable,intent,&before,&observed)==POLITICS_EXECUTION_RETURNED);assert(observed&&executions==2);
 assert(trade_construct(image,&b,&p,"wrong",readable,intent,&cmd)==POLITICS_INTENT_FAILED);
 *(uint32_t*)(em+0x20)=99;assert(!trade_bind(image,importer,exporter,"steel",readable,name,&b));
 return 0;
}
