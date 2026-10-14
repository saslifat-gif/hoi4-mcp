#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
typedef size_t SIZE_T;
static uintptr_t image;
static unsigned char gui[160],owner[0x1548];
static int opened,closed,invalid,skip,selected;
static int readable(const void *p,SIZE_T n){return !invalid&&p==gui&&n==160;}
static int alert_signature(uintptr_t rva,const unsigned char *b,SIZE_T n){return 1;}
#include "world_tension_window.h"
static void open_window(void *p){assert(p==owner);opened++;if(!skip)gui[117]|=8;}
static void close_window(void *p){assert(p==owner);closed++;gui[117]&=~8;}
static void wars_view(void *p){assert(p==owner);selected++;if(!skip)*(int*)(owner+0x5a0)=4;}
int main(void){
 uintptr_t o=(uintptr_t)owner,g=(uintptr_t)gui;*(uintptr_t*)(owner+0x570)=g-48;
 assert(!change_world_tension(o,g,1,open_window,close_window));assert(opened==1&&closed==0);
 assert(!change_world_tension(o,g,1,open_window,close_window));assert(opened==1);
 assert(!change_world_tension(o,g,0,open_window,close_window));assert(closed==1);
 skip=1;assert(!strcmp(change_world_tension(o,g,1,open_window,close_window),"window_state_unverified"));skip=0;
 assert(!select_world_tension_view(o,4,wars_view));assert(selected==1);
 assert(!select_world_tension_view(o,4,wars_view));assert(selected==1);
 *(int*)(owner+0x5a0)=0;skip=1;assert(!strcmp(select_world_tension_view(o,4,wars_view),"window_state_unverified"));skip=0;
 invalid=1;assert(!strcmp(change_world_tension(o,g,1,open_window,close_window),"window_binding_changed"));
 assert(!strcmp(world_tension_failure_stage("window_binding_changed"),"execution_uncertain"));
 assert(!strcmp(world_tension_failure_stage("window_state_unverified"),"execution_uncertain"));
 assert(!strcmp(world_tension_failure_stage("window_not_found"),"rejected"));
 return 0;
}
