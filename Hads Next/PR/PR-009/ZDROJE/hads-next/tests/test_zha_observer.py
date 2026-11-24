import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime,timezone

from hads_next.evidence import IncidentStore
from hads_next.evidence_broker import EvidenceBroker,BrokerDenied
from hads_next.observability import CoreReader
from hads_next.zha_observer import ZHAJournal


class ZHAJournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.now=1000000.
        self.store=IncidentStore(Path(self.tmp.name)/'case.db')
        self.case=self.store.open_incident('zigbee','Ovladač nereaguje.',['automation.button'],self.now)['id']
        self.journal=ZHAJournal(self.store,lambda:self.now)
        self.broker=EvidenceBroker(self.store,zha=self.journal,clock=lambda:self.now,
            core=CoreReader(lambda path:{'id':'button','triggers':[{'trigger':'event','event_type':'zha_event',
                'event_data':{'device_id':'device_1','command':'toggle','pin':'SECRET_PIN'}}]}))
        self.broker.read(self.case,'hads_get_automation_config',{'automation_id':'button'})

    def read(self,start,end):
        return self.broker.read(self.case,'hads_get_zha_events',{'device_id':'device_1',
            'start':datetime.fromtimestamp(start,timezone.utc).isoformat(),'end':datetime.fromtimestamp(end,timezone.utc).isoformat()})

    def test_coverage_and_restart_gap_cannot_prove_absent_physical_press(self):
        self.assertEqual(self.read(self.now-1,self.now)['status'],'not_read')
        self.journal.ready();self.now+=5;self.journal.heartbeat()
        result=self.read(self.now-5,self.now)
        self.assertEqual(result['status'],'no_relevant_data')
        self.assertTrue(result['data']['capture_covers_window'])
        self.assertFalse(result['data']['physical_press_observed'])
        self.now+=5;self.journal=ZHAJournal(self.store,lambda:self.now);self.broker.zha=self.journal
        self.journal.ready();self.now+=5;self.journal.heartbeat()
        result=self.read(self.now-15,self.now)
        self.assertEqual(result['status'],'not_read')
        self.assertFalse(result['data']['capture_covers_window'])

    def test_authentication_failure_before_first_ack_is_visible(self):
        self.journal.attempt();self.journal.ended('authentication_failed',status=401)
        result=self.read(self.now-1,self.now)
        self.assertEqual(result['status'],'not_read')
        self.assertEqual(result['data']['last_error'],'authentication_failed')
        self.assertEqual(result['data']['source_status']['authenticated'],0)
        self.assertFalse(result['data']['capture_covers_window'])

    def test_native_event_is_projected_deduplicated_and_device_scoped(self):
        self.journal.ready()
        event={'event_type':'zha_event','time_fired':datetime.fromtimestamp(self.now,timezone.utc).isoformat(),
            'data':{'device_id':'device_1','command':'toggle','args':['SECRET_PIN'],'params':{'code':'SECRET_PIN'}},
            'context':{'id':'ctx_1','parent_id':None}}
        self.journal.append(event);self.journal.append(event)
        self.now+=1;self.journal.heartbeat()
        result=self.read(self.now-2,self.now)
        self.assertEqual(result['status'],'available');self.assertEqual(len(result['data']['events']),1)
        self.assertNotIn('SECRET_PIN',json.dumps(result)+self.store.export(self.case))
        with self.assertRaises(BrokerDenied):
            self.broker.read(self.case,'hads_get_device_registry',{'device_id':'other_device'})
        self.now+=7*86400+1;self.journal.trim()
        with self.store._connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM zha_observations').fetchone()[0],0)


if __name__=='__main__':unittest.main()
