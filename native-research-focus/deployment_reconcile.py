"""Independent queue outcome evidence, without republishing native commands."""

def verify_created_queue(before,after,template_id,units_before,units_after):
 old={q['conveyor_id']:q for q in before['conveyors']}
 current={q['conveyor_id']:q for q in after['conveyors']}
 added=set(current)-set(old)
 if len(added)!=1 or not set(old)<=set(current):raise RuntimeError('Exactly one new queue required')
 queue=current[added.pop()]
 if queue['template_id']!=template_id or len(queue['lines'])!=1 or queue['lines'][0]['current_entry'] is None:raise RuntimeError('Created queue/template/line mismatch')
 oldlines={line['line_id'] for q in old.values() for line in q['lines']}
 if queue['lines'][0]['line_id'] in oldlines:raise RuntimeError('A new reciprocal line required')
 if {u['unit_id'] for u in units_before['units']}!={u['unit_id'] for u in units_after['units']}:raise RuntimeError('Unit inventory changed during queue creation')
 if before['country_tag_native']!=after['country_tag_native'] or after['native_tick']<before['native_tick']:raise RuntimeError('Country or time binding changed')
 if not after['country_to_manager_binding_verified'] or after['process_writes']:raise RuntimeError('Independent read-only manager binding required')
 return {'conveyor_id':queue['conveyor_id'],'line_id':queue['lines'][0]['line_id'],'template_id':template_id,'native_tick':after['native_tick']}
