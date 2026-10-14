#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#define __declspec(x)
typedef size_t SIZE_T;
typedef struct {uint32_t dwLowDateTime,dwHighDateTime;} FILETIME;
typedef union {struct{uint32_t LowPart,HighPart;};uint64_t QuadPart;} ULARGE_INTEGER;
static uintptr_t image,bound_world;
static char sid[33];
static int readable(const void *p,SIZE_T n){return p!=NULL&&n>0;}
static void GetSystemTimeAsFileTime(FILETIME *p){memset(p,0,sizeof *p);}
#include "notification_refresh.h"
int main(int argc,char **argv){
 unsigned char str[32]={0};const char *text="a\"b\\c\n\001";
 memcpy(str,text,strlen(text));*(SIZE_T*)(str+16)=strlen(text);*(SIZE_T*)(str+24)=15;
 char out[128];SIZE_T used=0;int mode=argc>1?atoi(argv[1]):0;
 if(mode==1)*(SIZE_T*)(str+16)=4097;
 if(mode==2)*(SIZE_T*)(str+24)=2;
 int ok=json_alert_string(out,mode==3?3:sizeof out,&used,str);
 if(mode){if(ok)return 1;return 0;}if(!ok)return 2;puts(out);return 0;
}
