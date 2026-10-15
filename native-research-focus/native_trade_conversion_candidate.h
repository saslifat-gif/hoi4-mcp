#ifndef HOI4_NATIVE_TRADE_CONVERSION_CANDIDATE_H
#define HOI4_NATIVE_TRADE_CONVERSION_CANDIDATE_H
/* Isolated conversion only. Callers must pin code and bind both country tags and
   canonical resource before calling. Does not submit or assert trade eligibility.
   Native RVA ca7cd0: resource units (fixed 1e5) for N factories.
   Native RVA ca8160: factory cost (fixed 1e5) for raw resource units.
   Normal UI 1cb5ba0 rounds positive fractional factory cost up, credits existing
   exchange lended_cic (+e4), and compares available CIC from e68350. */
#include <stdint.h>
#include <limits.h>
typedef int64_t *(*trade_rate_fn)(int64_t *, void *, const int32_t *, const int32_t *, int32_t);
typedef int64_t *(*trade_cost_fn)(int64_t *, void *, const int32_t *, const int32_t *, int64_t);
typedef struct { int32_t resource_units, required_factories; int64_t native_cost_raw,native_rate_raw; } trade_conversion;
/* 1: exact requested factory allocation representable and UI CIC budget passes;
   0: invalid/nonrepresentable/budget rejected. No game mutation or retry. */
static int trade_convert_factories(trade_rate_fn rate, trade_cost_fn cost,
 void *resource, const int32_t importer[2], const int32_t exporter[2],
 int32_t factories, int32_t available_cic, int32_t existing_lended_cic,
 trade_conversion *out) {
 int64_t units_raw=0,cost_raw=0,units,required;
 if (!rate || !cost || !resource || !out || factories<=0 || available_cic<0 || existing_lended_cic<0) return 0;
 rate(&units_raw,resource,importer,exporter,factories);
 if (units_raw<=0) return 0;
 units=units_raw/100000;
 /* ca8160 multiplies requested raw units by 100000 in signed int64. */
 if (units<=0 || units>INT32_MAX || units>INT64_MAX/INT64_C(10000000000)) return 0;
 cost(&cost_raw,resource,importer,exporter,units*100000);
 if (cost_raw<=0) return 0;
 required=cost_raw/100000+(cost_raw%100000!=0);
 if (required!=factories || required>(int64_t)available_cic+existing_lended_cic) return 0;
 out->resource_units=(int32_t)units;out->required_factories=(int32_t)required;out->native_cost_raw=cost_raw;out->native_rate_raw=units_raw;
 return 1;
}
#endif
