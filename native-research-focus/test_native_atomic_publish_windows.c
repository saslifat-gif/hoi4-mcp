#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <wchar.h>
#include "native_atomic_publish.h"
static DWORD WINAPI release_reader(void *handle){Sleep(20);CloseHandle((HANDLE)handle);return 0;}
int main(int argc,char**argv){
 if(argc!=2)return 2;wchar_t directory[MAX_PATH],a[MAX_PATH],b[MAX_PATH];
 if(!MultiByteToWideChar(CP_UTF8,0,argv[1],-1,directory,MAX_PATH))return 3;
 if(!GetTempFileNameW(directory,L"mcp",0,a)||!GetTempFileNameW(directory,L"mcp",0,b))return 4;
 HANDLE f=CreateFileW(b,GENERIC_WRITE,0,NULL,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);DWORD done;
 if(f==INVALID_HANDLE_VALUE||!WriteFile(f,"new",3,&done,NULL)||done!=3)return 5;CloseHandle(f);
 HANDLE held=CreateFileW(a,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
 if(held==INVALID_HANDLE_VALUE)return 6;
 HANDLE thread=CreateThread(NULL,0,release_reader,held,0,NULL);if(!thread)return 7;
 BOOL ok=native_publish_file(b,a);WaitForSingleObject(thread,INFINITE);CloseHandle(thread);
 char value[4]={0};f=CreateFileW(a,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
 BOOL content=f!=INVALID_HANDLE_VALUE&&ReadFile(f,value,3,&done,NULL)&&done==3&&!memcmp(value,"new",3);
 if(f!=INVALID_HANDLE_VALUE)CloseHandle(f);DeleteFileW(a);DeleteFileW(b);
 printf("{\"native_publisher_replace_after_reader_closes\":%s,\"content_verified\":%s,\"gameplay_actions\":false}\n",ok?"true":"false",content?"true":"false");return ok&&content?0:8;
}
