"""Real public API reads with a fixture Core version; no HAOS or LLM claims."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import tempfile
import time

from hads_next.evidence import IncidentStore
from hads_next.evidence_broker import EvidenceBroker
from hads_next.observability import CoreReader
from hads_next.research import ResearchReader


def main():
    with tempfile.TemporaryDirectory(prefix='hads-public-research-') as directory:
        store=IncidentStore(Path(directory)/'case.db')
        incident=store.open_incident('public_contract_probe','Veřejný kontraktní dotaz bez domácích dat.',['media_player.virtual_fixture'],time.time())
        broker=EvidenceBroker(store,core=CoreReader(lambda path:{'version':'2026.11.0'}))
        research=ResearchReader(broker);research.install()
        broker.read(incident['id'],'hads_get_core_status',{})
        research.configure(True,'fixture_owner','fixture_owner')
        reads=[]
        for project,terms in [('core','media player'),('community','music assistant')]:
            reads.append(broker.read(incident['id'],'hads_get_known_issues',{'project':project,'version':'2026.11.0','terms':terms}))
        result={'scope':'real_public_GitHub_and_Discourse_API_with_fixture_version','recorded_at':datetime.now(timezone.utc).isoformat(),
            'core_version_source':'fixture_not_actual_Core_in_this_probe','model_used':False,'live_haos':False,'paid_search_used':False,
            'reads':reads,'passed':all(x['status'] in {'available','no_relevant_data'} for x in reads),
            'source_sha256':{name:hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in ('src/hads_next/research.py','src/hads_next/evidence_broker.py','lab/research_probe.py')}}
        Path('docs/evidence/research-public.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'passed':result['passed'],'sources':[{'url':x.get('data',{}).get('source_url') if x.get('data') else None,'status':x['status'],
            'items':len(x['data'].get('items',[])) if x.get('data') else 0} for x in reads]},ensure_ascii=False))


if __name__=='__main__':main()
