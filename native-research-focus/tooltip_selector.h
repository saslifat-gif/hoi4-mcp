#ifndef HOI4_TOOLTIP_SELECTOR_H
#define HOI4_TOOLTIP_SELECTOR_H
#include <stddef.h>
#include <string.h>
struct TooltipSelectorFields {char source[513],name[513];};
/* Exact durable sidecar: SID|RID|source\nname, UTF-8 bytes without embeddedNUL,
 * CR, extra separators/lines, or control characters in the two selector fields. */
static int parse_tooltip_selector(const char *data,size_t n,const char *sid,const char *rid,struct TooltipSelectorFields *out){
 if(n<69||n>1091||memchr(data,0,n)||strlen(sid)!=32||strlen(rid)!=32||
    memcmp(data,sid,32)||data[32]!='|'||memcmp(data+33,rid,32)||data[65]!='|')return 0;
 const char *split=memchr(data+66,'\n',n-66);if(!split)return 0;
 size_t source_len=(size_t)(split-data)-66,name_len=n-(size_t)(split-data)-1;
 if(!source_len||source_len>512||!name_len||name_len>512)return 0;
 for(size_t i=66;i<n;i++)if(data+i!=split&&((unsigned char)data[i]<32||data[i]=='|'))return 0;
 memcpy(out->source,data+66,source_len);out->source[source_len]=0;
 memcpy(out->name,split+1,name_len);out->name[name_len]=0;return 1;
}
#endif
