/* Parse the durable owned unit-ID payload; no native calls or writes. */
#ifndef HOI4_UNIT_PAYLOAD_H
#define HOI4_UNIT_PAYLOAD_H
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
static int unit_payload_handle(const char *text,uint32_t out[2],size_t *used){
 unsigned a,b;int n=0;char canonical[24];
 if(sscanf(text,"%u:%u%n",&a,&b,&n)!=2||!a||!b||n<1||n>21)return 0;
 snprintf(canonical,sizeof canonical,"%u:%u",a,b);
 if(strlen(canonical)!=(size_t)n||memcmp(canonical,text,(size_t)n))return 0;
 out[0]=a;out[1]=b;*used=(size_t)n;return 1;
}
static int unit_payload_parse(const char *text,const char *sid,const char *rid,size_t count,uint32_t ids[64][2]){
 if(count<1||count>64||strlen(text)<66||strncmp(text,sid,32)||text[32]!='|'||strncmp(text+33,rid,32)||text[65]!='|')return 0;
 const char *next=text+66;
 for(size_t i=0;i<count;i++){
  size_t n=0;if(!unit_payload_handle(next,ids[i],&n))return 0;
  for(size_t j=0;j<i;j++)if(!memcmp(ids[j],ids[i],8))return 0;
  next+=n;
  if(i+1<count){if(*next++!=',')return 0;}else if(*next)return 0;
 }
 return 1;
}
#endif
