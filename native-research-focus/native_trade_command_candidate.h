#ifndef HOI4_NATIVE_TRADE_COMMAND_CANDIDATE_H
#define HOI4_NATIVE_TRADE_COMMAND_CANDIDATE_H
/* Source-only candidate. Caller pins executable, game thread/world, stable
   country/script-ID resolution, normal offer eligibility and ledger lifecycle.
   NULL error is supported by pinned transitive proof trade-null-error-proof.json.
   This header does not claim successful execution from a void engine return. */
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include "native_politics.h"
#include "native_trade_conversion_candidate.h"
struct trade_record_observation {uintptr_t pointer;int32_t required_cic,lended_cic;int64_t delivered_raw;};
struct trade_binding {uintptr_t importer,exporter,import_resources,export_resources,resource;uint32_t importer_tag,exporter_tag,index;};
static int trade_array(uintptr_t header,int limit,int(*readable)(const void*,size_t),uintptr_t *data,int *count){
 if(!readable((void*)header,16))return 0;
 int cap=*(int*)(header+8),n=*(int*)(header+12);
 uintptr_t a=*(uintptr_t*)header;
 if(n<0||n>cap||cap>limit||(n&&!readable((void*)a,(size_t)n*8)))return 0;
 *data=a;*count=n;return 1;
}
/* Native24bc260 returns cached 32-byte std::string at token*32. Reading
   requires its existing initialized table; never calls the lazy initializer. */
static int trade_token_name(uintptr_t image,uint32_t token,int(*readable)(const void*,size_t),
 int(*name)(uintptr_t,size_t,char*,size_t),char *out,size_t n){
 if(!readable((void*)(image+0x35e1ab0),8)||!readable((void*)(image+0x35e1ae0),8)||
    !*(unsigned char*)(image+0x35e1ab0))return 0;
 int max=*(int*)(image+0x35e1ab4);uintptr_t table=*(uintptr_t*)(image+0x35e1ae0);
 if(max<0||token>(uint32_t)max||!table)return 0;
 return name(table+(uintptr_t)token*32,0,out,n);
}
static uintptr_t trade_resource(uintptr_t image,const char *id,int(*readable)(const void*,size_t),
 int(*name)(uintptr_t,size_t,char*,size_t),uint32_t *index){
 uintptr_t list,match=0;int n;
 if(!readable((void*)(image+0x332f088),8))return 0;
 uintptr_t db=*(uintptr_t*)(image+0x332f088);
 if(!readable((void*)db,0x38)||*(uintptr_t*)db!=image+0x2943b18||!trade_array(db+0x28,4096,readable,&list,&n)||n<1)return 0;
 for(int i=0;i<n;i++){
  uintptr_t p=((uintptr_t*)list)[i];char value[160];
  if(!readable((void*)p,0xe8))return 0;
  if(i==0){if(*(uintptr_t*)p!=image+0x2943b48||*(unsigned char*)(p+0x10))return 0;continue;}
  if(*(uintptr_t*)p!=image+0x2951508||*(unsigned char*)(p+0x10)!=1||*(uint32_t*)(p+0xd8)!=(uint32_t)i||
     !trade_token_name(image,*(uint32_t*)(p+8),readable,name,value,sizeof value))return 0;
  if(strcmp(id,value))continue;
  if(match)return 0;
  match=p;*index=(uint32_t)i;
 }
 return match;
}
static int trade_bind(uintptr_t image,uintptr_t importer,uintptr_t exporter,
 const char *resource_id,int(*readable)(const void*,size_t),int(*name)(uintptr_t,size_t,char*,size_t),
 struct trade_binding *out){
 if(!importer||!exporter||importer==exporter||!readable((void*)importer,0x1200)||!readable((void*)exporter,0x1200))return 0;
 memset(out,0,sizeof *out);out->importer=importer;out->exporter=exporter;
 out->importer_tag=*(uint32_t*)(importer+8);out->exporter_tag=*(uint32_t*)(exporter+8);
 if((int32_t)out->importer_tag<=0||(int32_t)out->exporter_tag<=0||out->importer_tag==out->exporter_tag)return 0;
 out->import_resources=*(uintptr_t*)(importer+0x11f8);out->export_resources=*(uintptr_t*)(exporter+0x11f8);
 uintptr_t r[2]={out->import_resources,out->export_resources};uint32_t tags[2]={out->importer_tag,out->exporter_tag};
 for(int i=0;i<2;i++)if(!readable((void*)r[i],0x750)||*(uintptr_t*)r[i]!=image+0x295c4b0||*(uint32_t*)(r[i]+0x20)!=tags[i])return 0;
 out->resource=trade_resource(image,resource_id,readable,name,&out->index);
 return out->resource!=0;
}
static int trade_record(uintptr_t image,const struct trade_binding *b,int(*readable)(const void*,size_t),struct trade_record_observation *out){
 uintptr_t list;int n;memset(out,0,sizeof *out);
 if(!trade_array(b->import_resources+0x740,65536,readable,&list,&n))return 0;
 for(int i=0;i<n;i++){
  uintptr_t p=((uintptr_t*)list)[i];
  if(!readable((void*)p,0xe8)||*(uintptr_t*)p!=image+0x295c410)return 0;
  if(*(uintptr_t*)(p+0x80)!=b->export_resources)continue;
  if(*(uint32_t*)(p+0x88)!=b->importer_tag)return 0;
  if(*(uintptr_t*)(p+0x90)!=b->resource)continue;
  if(out->pointer)return 0;
  out->pointer=p;out->required_cic=*(int32_t*)(p+0xe0);out->lended_cic=*(int32_t*)(p+0xe4);out->delivered_raw=*(int64_t*)(p+0x98);
  if(out->required_cic<0||out->lended_cic<0||out->lended_cic>out->required_cic)return 0;
 }
 if(out->pointer){
  if(!readable((void*)(b->export_resources+0x728),8))return 0;
  uintptr_t vectors=*(uintptr_t*)(b->export_resources+0x728),exports;int count,found=0;
  if(!trade_array(vectors+(uintptr_t)b->index*24,65536,readable,&exports,&count))return 0;
  for(int i=0;i<count;i++)if(((uintptr_t*)exports)[i]==out->pointer)found++;
  if(found!=1)return 0;
 }
 return 1;
}
/* Ordinary UI cad5a0 is a getter with NULL optional tooltip. It returns a
   diplomacy-gated maximum in raw resource units and existing requested amount.
   It incorporates export availability and importer available CIC, credits
   existing required CIC, and supplies zero when native diplomacy disallows it.
   Never substitute cbaa10 (import reduction mutator) for this getter. */
typedef void (*trade_limits_fn)(uintptr_t,const int32_t*,uintptr_t,int64_t*,int64_t*,void*);
struct trade_offer_observation {int64_t max_raw_units,existing_requested_raw_units;};
static int trade_offer_allows(trade_limits_fn limits,const struct trade_binding *b,
 const int32_t importer[2],const trade_conversion *p,struct trade_offer_observation *out){
 if(!limits||!b||!p||!out||p->resource_units<=0||importer[0]!=(int32_t)b->importer_tag)return 0;
 memset(out,0,sizeof *out);
 limits(b->export_resources,importer,b->resource,&out->max_raw_units,&out->existing_requested_raw_units,NULL);
 return out->max_raw_units>0&&out->existing_requested_raw_units>=0&&
        (int64_t)p->resource_units*100000<=out->max_raw_units;
}
/* Native exchanges retain CIC rather than exact original integer command
   quantity. The ordinary economic paths reconstruct nominal requested amount
   with ca7cd0(required_cic). This is not a delivered quantity or original-q
   history. Independently read required CIC before supplying this function. */
static int trade_nominal_requested(trade_rate_fn rate,const struct trade_binding *b,
 const int32_t importer[2],const int32_t exporter[2],const struct trade_record_observation *record,int64_t *out){
 if(!rate||!b||!record||!out||!record->pointer||record->required_cic<0||
    importer[0]!=(int32_t)b->importer_tag||exporter[0]!=(int32_t)b->exporter_tag)return 0;
 *out=0;rate(out,(void*)b->resource,importer,exporter,record->required_cic);
 return *out>=0;
}
/* Factory then proven ordinary-constructor payload. Fields +28 importer,
   +2c exporter,+30 resource,+38 integer resource units. No lifecycle transfer. */
static enum politics_result trade_construct(uintptr_t image,const struct trade_binding *b,const trade_conversion *p,
 const char *rid,int(*readable)(const void*,size_t),int(*intent)(const char*),uintptr_t *out){
 if(!b||!p||p->resource_units<=0||p->required_factories<=0)return POLITICS_BAD_ARGUMENT;
 enum politics_result r=politics_construct_default(image,0x2a49150,rid,readable,intent,out);
 if(r!=POLITICS_OBJECT_CONSTRUCTED)return r;
 *(uint32_t*)(*out+0x28)=b->importer_tag;*(uint32_t*)(*out+0x2c)=b->exporter_tag;
 *(uintptr_t*)(*out+0x30)=b->resource;*(int32_t*)(*out+0x38)=p->resource_units;
 return r;
}
/* Caller must freshly establish ordinary offer eligibility before entering.
   Binding checks ensure payload still represents that exact actor/partner/resource.
   Uses native validator+executor through pinned politics dispatch. A return of
   POLITICS_EXECUTION_RETURNED remains uncertain until this independent record
   read succeeds and required_cic equals the planned amount. An already-matching
   pre-state cannot prove a new transition from this alone. Delivered/actually
   lended values are observations, not a guarantee that all resources arrived. */
static enum politics_result trade_execute_bound(uintptr_t image,uintptr_t command,
 const struct trade_binding *b,const trade_conversion *p,void *engine_error,
 const char *rid,int(*readable)(const void*,size_t),int(*persist_intent)(const char*),
 struct trade_record_observation *after,int *requested_state_observed){
 *requested_state_observed=0;memset(after,0,sizeof *after);
 if((engine_error&&!readable(engine_error,1))||!readable((void*)command,0x40)||
    *(uintptr_t*)command!=image+0x2a49150||*(uint32_t*)(command+0x28)!=b->importer_tag||
    *(uint32_t*)(command+0x2c)!=b->exporter_tag||*(uintptr_t*)(command+0x30)!=b->resource||
    *(int32_t*)(command+0x38)!=p->resource_units)return POLITICS_BINDING_CHANGED;
 if(!readable((void*)b->importer,0x1200)||!readable((void*)b->exporter,0x1200)||
    *(uint32_t*)(b->importer+8)!=b->importer_tag||*(uint32_t*)(b->exporter+8)!=b->exporter_tag||
    *(uintptr_t*)(b->importer+0x11f8)!=b->import_resources||*(uintptr_t*)(b->exporter+0x11f8)!=b->export_resources)
    return POLITICS_BINDING_CHANGED;
 /* Existing shared politics helper may not yet include the proven trade NULL
    exception. Keep dispatch local while preserving slot and ledger checks. */
 uintptr_t vt=*(uintptr_t*)command;
 if(!readable((void*)(vt+9*8),16)||*(uintptr_t*)(vt+9*8)!=image+0x1ba56d0||
    *(uintptr_t*)(vt+10*8)!=image+0x1ba54b0)return POLITICS_BINDING_CHANGED;
 if(!persist_intent(rid))return POLITICS_INTENT_FAILED;
 if(!POLITICS_VALIDATE(image+0x1ba56d0,command,engine_error))return POLITICS_RULES_REJECTED;
 POLITICS_EXECUTE(image+0x1ba54b0,command);
 enum politics_result result=POLITICS_EXECUTION_RETURNED;
 if(result==POLITICS_EXECUTION_RETURNED&&trade_record(image,b,readable,after)&&after->pointer&&
    after->required_cic==p->required_factories)*requested_state_observed=1;
 return result;
}
#endif
