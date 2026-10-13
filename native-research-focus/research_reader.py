"""Pinned, read-only research decoding. Native levels and completion list agree.
Progress is research points / the threshold used by CResearchSlot's update.
"""
import struct,time
FIXED_SCALE=100000
class ResearchReadError(RuntimeError):pass
class SnapshotChanged(ResearchReadError):pass

def decode_technology(identifier,level,max_level,points,base_cost,cost_factor,slots,enabled=True,override=False):
 if not (0<=level<=1000000 and 0<=max_level<=1000000):raise ResearchReadError('Invalid technology level bounds')
 if points<0 or cost_factor<=0:raise ResearchReadError(f'Invalid research cost/progress for {identifier}: points={points}, cost={base_cost}, factor={cost_factor}')
 completed=level>=max_level if max_level>0 else None
 if slots and (completed is True or not enabled):raise SnapshotChanged('Assigned technology is already complete or disabled')
 threshold=FIXED_SCALE if override else (base_cost*cost_factor//FIXED_SCALE if base_cost>=0 else None)
 if slots and (threshold is None or threshold<=0):raise ResearchReadError('Assigned research has no valid completion threshold')
 fraction=1.0 if completed else (min(points,threshold)/threshold if threshold is not None and threshold>0 else None)
 state='researching' if slots else ('completed' if completed else ('partially_researched' if points else ('available_next_level' if level>0 else 'unresearched')))
 return {'id':identifier,'completed':completed,'unlocked':level>0,'researched_levels':level,'max_levels':max_level,
  'researching':bool(slots),'research_slots':slots,'state':state,'active':enabled,
  'progress_raw':points,'completion_threshold_raw':threshold,'progress_fraction':fraction,
  'progress_percent':round(fraction*100,6) if fraction is not None else None,
  'research_target_level':level+1 if slots else None,'progress_scope':'all_levels_complete' if completed else 'next_level',
  'completion_source':'native_level_and_completed_list','progress_source':'native_completion_threshold'}

def read_research(raw,image,country,world,attempts=8):
 def u(a):return struct.unpack('<Q',raw(a,8))[0]
 def i(a):return struct.unpack('<i',raw(a,4))[0]
 def q(a):return struct.unpack('<q',raw(a,8))[0]
 def ptrs(a,count,maximum):
  if not 0<=count<=maximum:raise ResearchReadError('Invalid native array length')
  return struct.unpack('<'+'Q'*count,raw(a,count*8)) if count else ()
 def identifier(buffer):
  n,capacity=struct.unpack_from('<QQ',buffer,0x20)
  if not 0<n<160 or not n<=capacity<65536:raise ResearchReadError('Invalid native technology identifier')
  b=raw(struct.unpack_from('<Q',buffer,0x10)[0],n+1) if capacity>15 else buffer[0x10:0x10+n+1]
  if b[-1]!=0:raise ResearchReadError('Unterminated technology identifier')
  try:s=b[:-1].decode('ascii')
  except UnicodeDecodeError:raise ResearchReadError('Non-ASCII technology identifier')
  if not all(x.isalnum() or x=='_' for x in s):raise ResearchReadError('Invalid technology identifier characters')
  return s
 for attempt in range(attempts):
  try:
   if u(image+0x332f260)!=world:raise ResearchReadError('Bound game world changed')
   tick=i(world+0x468);tech=u(country+0xf60)
   count=i(tech+0x94);models=ptrs(u(tech+0x88),count,10000)
   if not count:raise ResearchReadError('Missing native technologies')
   slot_count=i(tech+0xac)
   if not 1<=slot_count<=16:raise ResearchReadError('Invalid native research slot count')
   slot_ptrs=ptrs(u(tech+0xa0),slot_count,16)
   current=tuple(u(p+0x18) for p in slot_ptrs)
   complete_ptrs=ptrs(u(tech+0x40),i(tech+0x4c),count)
   complete_set=set(complete_ptrs);model_set=set(models)
   if len(complete_set)!=len(complete_ptrs) or not complete_set<=model_set:raise SnapshotChanged('Native completion list is inconsistent')
   if any(p and p not in model_set for p in current):raise SnapshotChanged('Research slot references another technology status')
   factor=q(image+0x3332ba0);override=bool(raw(image+0x332f661,1)[0]);rows=[];signatures=[];definitions=[];ids=set()
   for j,m in enumerate(models):
    b=raw(m,0x1f8)
    if struct.unpack_from('<Q',b)[0]!=image+0x2974ee0 or struct.unpack_from('<Q',b,0x158)[0]!=tech:raise ResearchReadError('Native technology ownership/vtable mismatch')
    d=struct.unpack_from('<Q',b,0x160)[0];db=raw(d,0x3e8)
    if struct.unpack_from('<Q',db)[0]!=image+0x293c2e0 or struct.unpack_from('<i',db,0x38)[0]!=j+1:raise ResearchReadError('Native technology definition/index mismatch')
    name=identifier(db)
    if name in ids:raise ResearchReadError('Duplicate canonical technology ID')
    ids.add(name);level=struct.unpack_from('<i',b,0x174)[0];maximum=struct.unpack_from('<i',db,0x3dc)[0];points=struct.unpack_from('<q',b,0x198)[0]
    row=decode_technology(name,level,maximum,points,struct.unpack_from('<q',db,0x3e0)[0],factor,[k+1 for k,p in enumerate(current) if p==m],bool(db[0x40]),override)
    if (m in complete_set)!=(row['completed'] is True):raise SnapshotChanged('Native levels and completed list disagree')
    row['address']=hex(m);rows.append(row);signatures.append((b[0x170:0x178],b[0x198:0x1a0],b[0x158:0x168]));definitions.append((d,db[0x3dc:0x3e8],db[0x40:0x41]))
   # Re-read every mutable research field. A completion tick must never produce
   # a mixture of an old slot, a new level, and a reset progress counter.
   stable=(u(image+0x332f260)==world and i(world+0x468)==tick and u(country+0xf60)==tech and
    ptrs(u(tech+0x88),i(tech+0x94),10000)==models and
    ptrs(u(tech+0xa0),i(tech+0xac),16)==slot_ptrs and tuple(u(p+0x18) for p in slot_ptrs)==current and
    ptrs(u(tech+0x40),i(tech+0x4c),count)==complete_ptrs and q(image+0x3332ba0)==factor and bool(raw(image+0x332f661,1)[0])==override)
   if not stable:raise SnapshotChanged('Research changed while being sampled')
   for m,(level_sig,points_sig,owner_sig) in zip(models,signatures):
    if raw(m+0x170,8)!=level_sig or raw(m+0x198,8)!=points_sig or raw(m+0x158,16)!=owner_sig:raise SnapshotChanged('Research changed while being sampled')
   for d,cost_sig,enabled_sig in definitions:
    if raw(d+0x3dc,12)!=cost_sig or raw(d+0x40,1)!=enabled_sig:raise SnapshotChanged('Technology definition changed during verification')
   if i(world+0x468)!=tick:raise SnapshotChanged('Simulation tick changed during verification')
   by_address={int(t['address'],16):t for t in rows}
   slots=[]
   for k,p in enumerate(current):
    t=by_address.get(p)
    slots.append({'slot':k+1,'technology':t['id'] if t else None,'current_address':hex(p),
     'progress_fraction':t['progress_fraction'] if t else None,'progress_percent':t['progress_percent'] if t else None,
     'research_target_level':t['research_target_level'] if t else None})
   return {'research_slots':slots,'technologies':rows,'research_read_consistent':True,'research_sample_native_tick':tick,
    'research_cost_mode':'engine_override' if override else 'normal','research_completion_verified_against_native_list':True}
  except SnapshotChanged:
   if attempt+1==attempts:raise SnapshotChanged('Cannot obtain a consistent research snapshot; retry later')
   time.sleep(.01)
 raise ResearchReadError('No research snapshot')
