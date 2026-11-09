import json
from pathlib import Path
import tempfile
import unittest

from hads_next.evidence import IncidentStore
from hads_next.evidence_broker import project_automation
from hads_next.repair import ApprovalAuthority,RepairEngine,RepairBlocked
from hads_next.repair_suggestions import interpret_proposal,prepare_reference_plan
from hads_next.verification import FunctionalVerifier


class SuggestionTests(unittest.TestCase):
    """Offline fixture planner bridge; no Home Assistant or real model in test."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.store=IncidentStore(self.root/'cases.db')
        self.case=self.store.open_incident('automation_reference','Nefunkční reference.',['automation.button'],100)['id']
        for name,data in [
            ('config',project_automation({'id':'button','actions':[{'action':'light.turn_on','target':{'entity_id':'light.old'}}]})),
            ('missing',{'entity_id':'light.old','exists':False}),('target',{'entity_id':'light.kitchen','state':'off'})]:
            self.store.add_evidence(self.case,{'source':'ha_core','kind':'hads_get_automation_config' if name=='config' else 'hads_get_entity_state',
                'event_id':name,'observed_at':100,'payload':{'data':data}})
        ids=[r['evidence_id'] for r in self.store.case(self.case)['evidence']]
        self.proposal={'target':'button','change':{'from':'light.old','to':'light.kitchen'},'reason':'Neplatný odkaz s doloženým náhradním cílem.',
            'evidence_ids':ids,'risk':'production_safe_claim_from_model','backup':'none_claim_from_model','rollback':'unrestricted_claim'}
        self.original={'id':'button','action':{'service':'light.turn_on','target':{'entity_id':'light.old'}},'enabled':True}
        (self.root/'automation.json').write_text(json.dumps(self.original))
        self.engine=RepairEngine(self.root/'repairs.db',self.root,allowed_files={'automation.json'},clock=lambda:100)

    def suggestion(self,proposal=None):return interpret_proposal(self.proposal if proposal is None else proposal,self.store.case(self.case))

    def test_exact_draft_uses_original_planner_approval_and_verifier(self):
        suggestion=self.suggestion();document=suggestion.document
        self.assertEqual(document['status'],'supported_lab_candidate')
        self.assertFalse(document['production_executable'])
        self.assertNotIn('none_claim_from_model',suggestion.serialized)
        document['change']['to']='light.mutated'
        self.assertEqual(suggestion.document['change']['to'],'light.kitchen')
        plan=prepare_reference_plan(suggestion,self.engine,'automation.json')
        self.assertEqual(plan.document['operation'],'fixture.replace_entity_reference')
        with self.assertRaises(RepairBlocked):self.engine.execute(plan,None,principal='owner')
        self.assertEqual(json.loads((self.root/'automation.json').read_text()),self.original)
        token=ApprovalAuthority(self.engine.db_path,clock=lambda:100).approve(plan,principal='owner')
        execution=self.engine.execute(plan,token,principal='owner')
        self.assertEqual(execution.status,'applied_verification_pending')
        changed=json.loads((self.root/'automation.json').read_text())
        self.assertEqual(changed['action']['target']['entity_id'],'light.kitchen');self.assertTrue(changed['enabled'])
        report=FunctionalVerifier(self.engine.db_path).evaluate(plan,execution,[
            {'kind':'automation_triggered','observed_at':101,'payload':{'automation_id':'button','context_id':'ctx'}},
            {'kind':'target_state','observed_at':102,'payload':{'entity_id':'light.kitchen','state':'on','context_id':'ctx'}},
            {'kind':'monitoring_checkpoint','observed_at':133,'payload':{'entity_id':'light.kitchen','continuous_since':101,'healthy':True}}],now=133)
        self.assertEqual(report['classification'],'Vyřešeno a ověřeno')
        with self.assertRaises(RepairBlocked):self.engine.execute(plan,token,principal='owner')

    def test_changed_target_and_unsupported_or_forged_proposals_cannot_be_prepared(self):
        for proposal in [dict(self.proposal,operation='reload_integration'),dict(self.proposal,evidence_ids=['0'*64]),
            dict(self.proposal,shell='touch /config/evil')]:
            suggestion=self.suggestion(proposal)
            self.assertEqual(suggestion.document['status'],'manual_or_test_required')
            with self.assertRaises(RepairBlocked):prepare_reference_plan(suggestion,self.engine,'automation.json')
        suggestion=self.suggestion()
        changed={**self.original,'id':'different_automation'}
        (self.root/'automation.json').write_text(json.dumps(changed))
        with self.assertRaises(RepairBlocked):prepare_reference_plan(suggestion,self.engine,'automation.json')

    def test_later_unavailable_state_cannot_be_hidden_by_older_good_observation(self):
        self.store.add_evidence(self.case,{'source':'ha_core','kind':'hads_get_entity_state','event_id':'later_unavailable','observed_at':101,
            'payload':{'data':{'entity_id':'light.kitchen','state':'unavailable'}}})
        self.assertEqual(self.suggestion().document['status'],'manual_or_test_required')


if __name__=='__main__':unittest.main()
