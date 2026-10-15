import copy
import unittest
from combat_transition import verify_engagement,verify_side_membership_removed


class CombatTransitionTests(unittest.TestCase):
    def setUp(self):
        self.own={'unit_id':'51:1','country_tag_native':1};self.other={'unit_id':'51:2','country_tag_native':2}
        self.before={'country_tag_native':1,'native_tick':5,'units':[self.own], 'combats':[],
                     'native_world_manager_verified':True,'bidirectional_membership_verified':True}
        self.after=copy.deepcopy(self.before);self.after['native_tick']=6
        self.battle={'combat_id':'64:8','province_id':123,'sides':[{'units':[self.own]},{'units':[self.other]}]}
        self.after['combats']=[self.battle]
    def test_new_combat_membership(self):
        self.assertTrue(verify_engagement(self.before,self.after,'51:1',123,2)['verified'])
    def test_join_existing_battle(self):
        old=copy.deepcopy(self.battle);old['sides'][0]['units']=[];self.before['combats']=[old]
        self.assertTrue(verify_engagement(self.before,self.after,'51:1',123)['verified'])
    def test_already_in_battle_is_not_new_outcome(self):
        self.before['combats']=[copy.deepcopy(self.battle)]
        self.assertFalse(verify_engagement(self.before,self.after,'51:1',123)['verified'])
    def test_wrong_province_or_enemy_rejected(self):
        self.assertFalse(verify_engagement(self.before,self.after,'51:1',124)['verified'])
        self.assertFalse(verify_engagement(self.before,self.after,'51:1',123,3)['verified'])
    def test_unverified_snapshot_rejected(self):
        self.after['bidirectional_membership_verified']=False
        with self.assertRaises(ValueError):verify_engagement(self.before,self.after,'51:1',123)
    def test_stop_preserves_unrelated_defense(self):
        self.before['combats']=[copy.deepcopy(self.battle)]
        self.after['combats'][0]['sides']=[{'units':[self.other]},{'units':[self.own]}]
        self.assertTrue(verify_side_membership_removed(self.before,self.after,'51:1',0)['verified'])
    def test_stop_no_prior_membership_is_not_success(self):
        self.assertFalse(verify_side_membership_removed(self.before,self.after,'51:1',0)['verified'])
    def test_country_switch_rejected(self):
        self.after['country_tag_native']=2
        with self.assertRaises(ValueError):verify_engagement(self.before,self.after,'51:1',123)

if __name__=='__main__':unittest.main()
