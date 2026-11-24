"""Read-only historical export from a copied Next schema-1 snapshot, no runtime."""
import argparse
from contextlib import contextmanager
import hashlib,json,sqlite3,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from hads_next.evidence import IncidentStore,canonical

class HistoricalStore(IncidentStore):
    def __init__(self,path):self.path=path
    @contextmanager
    def _connect(self):
        connection=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True);connection.row_factory=sqlite3.Row
        connection.execute('PRAGMA query_only=ON')
        try:yield connection
        finally:connection.close()

def export(database,output):
    if database.is_symlink() or not database.is_file() or database.stat().st_size>64*1024*1024:raise ValueError('Vyžadována běžná kopie databáze do 64 MiB.')
    database=database.resolve();before=hashlib.sha256(database.read_bytes()).hexdigest();store=HistoricalStore(database)
    with store._connect() as db:
        if db.execute('PRAGMA quick_check').fetchone()[0]!='ok' or db.execute('SELECT version FROM evidence_schema').fetchone()[0]!=1:raise ValueError('Neplatná databáze Next.')
        ids=[row[0] for row in db.execute('SELECT id FROM incidents ORDER BY first_seen LIMIT 1001')]
    if len(ids)>1000 or output.exists() or output.is_symlink():raise ValueError('Nový výstupní adresář, nejvýše 1000 spisů.')
    documents=[]
    for identity in ids:
        document=store.case(identity);document['records']=[];document['analyses']=[]
        documents.append((identity,canonical(document)))
    if hashlib.sha256(database.read_bytes()).hexdigest()!=before:raise ValueError('Zdroj se mění; použij konzistentní kopii.')
    output.mkdir(parents=True)
    for identity,document in documents:
        name=hashlib.sha256(identity.encode()).hexdigest()+'.json';(output/name).write_text(document)
    (output/'EXPORT_MANIFEST.json').write_text(json.dumps({'source_sha256':before,'case_count':len(ids),'authority':'historical_only_no_approvals','source_unchanged':True},indent=2)+'\n')
    return len(ids)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--copied-snapshot',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    print(json.dumps({'exported_cases':export(args.copied_snapshot,args.output),'live_data_modified':False}))
