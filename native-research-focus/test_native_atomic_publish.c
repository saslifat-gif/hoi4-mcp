#include <assert.h>
#include <stddef.h>
typedef unsigned long DWORD;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define MOVEFILE_REPLACE_EXISTING 1
#define MOVEFILE_WRITE_THROUGH 8
#define ERROR_ACCESS_DENIED 5
#define ERROR_SHARING_VIOLATION 32
static int calls,sleeps,succeed_at;static DWORD error;
static BOOL MoveFileExW(const wchar_t*a,const wchar_t*b,DWORD flags){assert(a&&b&&flags==9);return ++calls==succeed_at;}
static DWORD GetLastError(void){return error;}
static void Sleep(DWORD ms){assert(ms==5);sleeps++;}
#include "native_atomic_publish.h"
int main(void){
 calls=sleeps=0;succeed_at=1;assert(native_publish_file(L"a",L"b")&&calls==1&&!sleeps);
 calls=sleeps=0;succeed_at=4;error=5;assert(native_publish_file(L"a",L"b")&&calls==4&&sleeps==3);
 calls=sleeps=0;succeed_at=2;error=32;assert(native_publish_file(L"a",L"b")&&calls==2&&sleeps==1);
 calls=sleeps=0;succeed_at=0;error=5;assert(!native_publish_file(L"a",L"b")&&calls==10&&sleeps==9);
 calls=sleeps=0;succeed_at=0;error=3;assert(!native_publish_file(L"a",L"b")&&calls==1&&!sleeps);
 return 0;
}
