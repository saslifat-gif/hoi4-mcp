#include <assert.h>
#include "native_trade_conversion_candidate.h"
static int64_t one_factory=800000;
static int64_t *rate(int64_t*out,void*r,const int32_t*i,const int32_t*e,int32_t n) { (void)r;assert(i[0]==10 && e[0]==20);*out=one_factory*n;return out; }
static int64_t *cost(int64_t*out,void*r,const int32_t*i,const int32_t*e,int64_t raw) { (void)r;assert(i[0]==10 && e[0]==20);*out=raw*100000/one_factory;return out; }
int main(void) {
 int32_t importer[2]={10,1},exporter[2]={20,2};trade_conversion p;
 assert(trade_convert_factories(rate,cost,&p,importer,exporter,3,3,0,&p));assert(p.resource_units==24 && p.required_factories==3);
 assert(!trade_convert_factories(rate,cost,&p,importer,exporter,3,2,0,&p));
 assert(trade_convert_factories(rate,cost,&p,importer,exporter,3,1,2,&p));
 one_factory=250000;assert(trade_convert_factories(rate,cost,&p,importer,exporter,1,1,0,&p));assert(p.resource_units==2);
 one_factory=50000;assert(!trade_convert_factories(rate,cost,&p,importer,exporter,1,1,0,&p));
 assert(trade_convert_factories(rate,cost,&p,importer,exporter,2,2,0,&p));assert(p.resource_units==1);
 assert(!trade_convert_factories(rate,cost,&p,importer,exporter,0,1,0,&p));
 one_factory=INT64_C(100000000000000);assert(!trade_convert_factories(rate,cost,&p,importer,exporter,1,1,0,&p));
 return 0;
}
