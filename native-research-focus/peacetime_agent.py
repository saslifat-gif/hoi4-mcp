"""Bounded Germany policy: observe, choose one ordinary action, reconcile and verify.
No input fallback. A durable pending intent is never replaced after uncertainty.
"""
import json,uuid,os,functools
from pathlib import Path
from direct_controller import atomic_text
RESEARCH=('basic_machine_tools','construction1','electronic_mechanical_engineering','mechanical_computing','improved_machine_tools','construction2')
FOCUSES=('GER_prioritize_economic_growth',)
def exclusive(method):
 @functools.wraps(method)
 def wrapped(self,*args,**kwargs):
  lock=self.path.with_suffix('.lock');fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
  try:return method(self,*args,**kwargs)
  finally:os.close(fd);lock.unlink()
 return wrapped
class PeacetimeAgent:
 def __init__(self,controller,journal):
  self.controller=controller;self.path=Path(journal)
 def load(self):
  if self.path.exists():
   d=json.loads(self.path.read_text())
   if d['session_id']!=self.controller.config['session_id']:raise RuntimeError('AI journal belongs to another session')
   return d
  return {'session_id':self.controller.config['session_id'],'enabled':False,'budget':0,'used':0,'history':[],'pending':None,'read_id':None}
 def save(self,d):atomic_text(self.path,json.dumps(d,indent=2))
 @exclusive
 def start(self,budget=5,wait_for_choices=False):
  if type(budget)!=int or not 1<=budget<=16:raise ValueError('Action budget must be 1..16')
  if type(wait_for_choices)!=bool:raise ValueError('wait_for_choices must be boolean')
  d=self.load()
  if d['pending'] or d['enabled']:raise RuntimeError('Reconcile the existing run before starting another')
  self.controller.check();d.update(enabled=True,budget=budget,used=0,wait_for_choices=wait_for_choices,read_id=None);self.save(d)
  return {'stage':'enabled','budget':budget}
 @exclusive
 def stop(self):
  d=self.load();d['enabled']=False;self.save(d)
  return {'stage':'stopped','pending_retained':bool(d['pending'])}
 @exclusive
 def step(self):
  d=self.load();self.controller.check()
  if d['pending']:
   p=d['pending']
   if p['request_id'] not in self.controller.load()['requests']:
    r=self.controller.submit(p['request_id'],p['kind'],p['id'],p['slot'])
   else:r=self.controller.receipt(p['request_id'])
   if r['stage']=='pending':return {'stage':'waiting_for_receipt','request_id':p['request_id']}
   if r['stage']=='rejected':
    d['history'].append({'intent':p,'receipt':r});d['pending']=None;d['enabled']=False;self.save(d)
    return {'stage':'stopped_rejected','receipt':r}
   if r['stage']!='selection_verified':
    d['enabled']=False;self.save(d);return {'stage':'stopped_uncertain','request_id':p['request_id'],'receipt':r}
   s=self.controller.snapshot()
   verified=(s['research_slots'][p['slot']-1]['technology']==p['id'] or any(t['id']==p['id'] and t['completed'] for t in s['technologies'])) if p['kind']=='research' else (s['active_focus']==p['id'] or p['id'] in s['completed_focuses'])
   if not verified:
    d['enabled']=False;self.save(d);return {'stage':'stopped_postcondition_failed','request_id':p['request_id']}
   d['history'].append({'intent':p,'receipt':r,'postcondition_verified':True});d['pending']=None;d['used']+=1;d['read_id']=None
   if d['used']>=d['budget']:d['enabled']=False
   self.save(d);return {'stage':'action_verified','action':p,'used':d['used'],'budget':d['budget']}
  if not d['enabled']:return {'stage':'stopped','used':d['used']}
  if not d['read_id']:d['read_id']=uuid.uuid4().hex;self.save(d)
  e=self.controller.peacetime_snapshot(d['read_id'])
  if e['status']!='ready':return {'stage':'waiting_for_observation','observation':e}
  s=self.controller.snapshot();choice=choose(e,s)
  if not choice:
   d['read_id']=None
   if d.get('wait_for_choices'):
    self.save(d);return {'stage':'waiting_for_choice','used':d['used']}
   d['enabled']=False;self.save(d);return {'stage':'idle_no_supported_choice'}
  # Persist BEFORE submission. If submission or transport raises, next step
  # reconciles this same ID; it never invents another gameplay request.
  choice['request_id']=uuid.uuid4().hex;choice['observation_request_id']=d['read_id'];d['pending']=choice;self.save(d)
  r=self.controller.submit(choice['request_id'],choice['kind'],choice['id'],choice['slot'])
  return {'stage':'action_submitted','action':choice,'receipt':r}

def choose(economy,native):
 if economy.get('status')!='ready' or not economy.get('sample_consistent') or not native.get('research_read_consistent'):raise RuntimeError('Complete coherent observations required')
 if native.get('research_cost_mode')!='normal':raise RuntimeError('Normal research costs required')
 available={x['id'] for x in economy['available_choices']['research']['choices'] if x['available']}
 assigned={s['technology'] for s in native['research_slots'] if s['technology']}
 complete={x['id'] for x in native['technologies'] if x['completed']}
 empty=next((s['slot'] for s in native['research_slots'] if not s['technology']),None)
 if empty:
  tech=next((x for x in RESEARCH if x in available and x not in assigned|complete),None)
  if tech:return {'kind':'research','id':tech,'slot':empty}
 if not native['active_focus']:
  available={x['id'] for x in economy['available_choices']['national_focus']['choices'] if x['available']}
  focus=next((x for x in FOCUSES if x in available and x not in native['completed_focuses']),None)
  if focus:return {'kind':'focus','id':focus,'slot':0}
 return None
