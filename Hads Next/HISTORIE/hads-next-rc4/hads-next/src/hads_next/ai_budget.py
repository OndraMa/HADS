"""Durable rolling request ceiling shared by every model entry point."""
import os,sqlite3,time,uuid
from contextlib import contextmanager
from pathlib import Path


class BudgetExceeded(ValueError):pass


class ModelBudget:
    def __init__(self,path,clock=time.time):
        self.path=Path(path);self.clock=clock
        fd=os.open(self.path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600);os.close(fd)
        with self.connect() as db:
            db.executescript('CREATE TABLE IF NOT EXISTS budget_schema(version INTEGER PRIMARY KEY); INSERT OR IGNORE INTO budget_schema VALUES(1); CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY,at REAL NOT NULL,state TEXT NOT NULL,input_bytes INTEGER NOT NULL,output_limit INTEGER NOT NULL);')
            if db.execute('SELECT version FROM budget_schema').fetchall()!=[(1,)]:raise BudgetExceeded('Nepodporované schéma rozpočtu AI.')
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10)
        try:
            with db:yield db
        finally:db.close()
    def remaining(self,limit):
        with self.connect() as db:used=db.execute('SELECT count(*) FROM requests WHERE at>=?',(self.clock()-86400,)).fetchone()[0]
        return max(0,limit-used)
    def reserve(self,limit,input_bytes,output_limit):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT count(*) FROM requests WHERE at>=?',(self.clock()-86400,)).fetchone()[0]>=limit:
                raise BudgetExceeded('Vyčerpán testovací rozpočet AI za posledních 24 hodin. Další požadavek nebyl odeslán.')
            identity=uuid.uuid4().hex
            db.execute('INSERT INTO requests VALUES(?,?,?,?,?)',(identity,self.clock(),'unknown',input_bytes,output_limit))
            db.execute('DELETE FROM requests WHERE at<?',(self.clock()-90*86400,))
        return identity
    def response(self,identity):
        with self.connect() as db:db.execute("UPDATE requests SET state='response' WHERE id=?",(identity,))
