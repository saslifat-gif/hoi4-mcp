"""Independent combat membership outcomes; command execution/ledger stay caller-owned."""

def _bound_pair(before, after, unit_id):
    for state in (before, after):
        if not state.get('native_world_manager_verified') or not state.get('bidirectional_membership_verified'):
            raise ValueError('Combat snapshots lack verified native membership')
    if before['country_tag_native'] != after['country_tag_native'] or after['native_tick'] < before['native_tick']:
        raise ValueError('Combat country or time binding changed')
    for state in (before, after):
        rows = [row for row in state['units'] if row['unit_id'] == unit_id]
        if len(rows) != 1 or rows[0]['country_tag_native'] != state['country_tag_native']:
            raise ValueError('Combat source unit ownership changed')


def _memberships(state, unit_id):
    pairs = []
    for combat in state['combats']:
        for index, side in enumerate(combat['sides']):
            if any(row['unit_id'] == unit_id for row in side['units']):
                pairs.append((combat, index))
    return pairs


def verify_engagement(before, after, unit_id, province_id, opponent_country_tag=None):
    """Accept joining an existing battle; require a newly observed membership."""
    _bound_pair(before, after, unit_id)
    previous = {(row['combat_id'], side) for row, side in _memberships(before, unit_id)}
    found = []
    for combat, side in _memberships(after, unit_id):
        if combat['province_id'] != province_id or (combat['combat_id'], side) in previous:
            continue
        opponents = [row for i, item in enumerate(combat['sides']) if i != side for row in item['units']]
        if not opponents or not any(row['country_tag_native'] != after['country_tag_native'] and
                                   (opponent_country_tag is None or row['country_tag_native'] == opponent_country_tag)
                                   for row in opponents):
            continue
        found.append((combat, side))
    if len(found) != 1:
        return {'verified': False, 'reason': 'new_land_combat_membership_not_observed'}
    combat, side = found[0]
    return {'verified': True, 'reason': 'native_land_combat_membership_entered',
            'unit_id': unit_id, 'combat_id': combat['combat_id'], 'province_id': province_id,
            'side_index': side, 'attack_role_verified': False, 'battle_result_verified': False}


def verify_side_membership_removed(before, after, unit_id, side_index):
    """A role-neutral check until caller's native contract establishes side roles."""
    _bound_pair(before, after, unit_id)
    previous = {row['combat_id'] for row, side in _memberships(before, unit_id) if side == side_index}
    remaining = {row['combat_id'] for row, side in _memberships(after, unit_id) if side == side_index}
    return {'verified': bool(previous) and not previous.intersection(remaining),
            'reason': 'native_combat_membership_removed' if previous and not previous.intersection(remaining)
                      else 'combat_membership_removal_not_observed',
            'unit_id': unit_id, 'side_index': side_index, 'battle_result_verified': False}
