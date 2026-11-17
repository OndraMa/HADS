"""Independent approved writer. Uses the existing durable approval authority.

Analyst proposals are inert. This executor independently reconstructs and
validates supported operations, binds provider/version/schema/origin/target,
claims one durable intent before network, and never retries unknown outcomes.
"""
from contextlib import closing
import copy
import json
import secrets
import threading
from .repair import ApprovalAuthority,RepairPlan,RepairBlocked,ExecutionResult,connect,digest
from .tool_registry import ToolDenied,validate,fingerprint
from .evidence import canonical
from .restore_receipt import RestoreReceiptVerifier
from .verification import FunctionalVerifier

class ApprovedRepairBroker:
    def __init__(self,app):
        self.app=app;self.tools=app.tools;self._write_lock=threading.RLock()
        self.backups=RestoreReceiptVerifier(app.data_dir,app.clock)
        connect(app.store.db_path).close()
        # An intent from a previous process cannot be re-executed, even with
        # an unexpired approval. Read-only reconciliation is a separate action.
        with closing(connect(app.store.db_path)) as db:
            db.execute("UPDATE repair_executions SET status='unknown_requires_reconciliation',error='process_restarted_during_tool_write' WHERE status='tool_intent'")
        with app.store._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS entity_identity_observations(identity TEXT PRIMARY KEY,entity_id TEXT NOT NULL,device_id TEXT,seen_at REAL NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS entity_renames(old_id TEXT NOT NULL,new_id TEXT NOT NULL,device_id TEXT NOT NULL,at REAL NOT NULL,PRIMARY KEY(old_id,new_id))')

    def identities(self,registry):
        if not isinstance(registry,list):return
        seen={};duplicates=set()
        for r in registry:
            if not isinstance(r,dict) or not all(isinstance(r.get(k),str) and r[k] for k in ('platform','unique_id','entity_id','device_id')):continue
            identity=fingerprint([r['platform'],r.get('config_entry_id'),r['unique_id']])
            if identity in seen:duplicates.add(identity)
            seen[identity]=r
        with self.app.store._connect() as db:
            for key,r in seen.items():
                if key in duplicates:continue
                old=db.execute('SELECT * FROM entity_identity_observations WHERE identity=?',(key,)).fetchone()
                if old and old['entity_id']!=r['entity_id'] and old['device_id']==r['device_id']:
                    db.execute('INSERT OR REPLACE INTO entity_renames VALUES(?,?,?,?)',(old['entity_id'],r['entity_id'],r['device_id'],self.app.clock()))
                db.execute('INSERT OR REPLACE INTO entity_identity_observations VALUES(?,?,?,?)',(key,r['entity_id'],r['device_id'],self.app.clock()))

    def binding(self,row):
        provider=next(p for p in self.tools.registry.providers() if p['id']==row['provider'])
        return {'provider':row['provider'],'tool':row['name'],'schema_hash':row['schema_hash'],
                'upstream_schema_hash':row.get('upstream_schema_hash'),'version':provider.get('version'),
                'server_version':provider.get('server_version'),'origin_digest':provider.get('origin_digest'),'identity':provider.get('identity')}

    def _owner(self,principal):
        if not principal or principal!=self.app.owner():raise RepairBlocked('Operaci může schválit pouze ověřený vlastník.')

    def _guide(self):
        row=self.tools.registry.get('ha_mcp','ha_config_set_automation',effect='write')
        remote=row['schema']['allOf'][0]
        if 'BestPracticeKey' not in remote.get('properties',{}):return None
        self.tools.registry.get('ha_mcp','ha_get_skill_guide',effect='read')
        value=self.tools.connections.clients['ha_mcp'].call('ha_get_skill_guide',{'file':'references/triggers-and-conditions.md'})
        if not isinstance(value,dict) or value.get('success') is not True or not isinstance(value.get('content'),str) or len(value['content'])>64000:raise RepairBlocked('Aktuální pravidla HA-MCP nebyla přečtená. Ochrany serveru se nevypínají.')
        import re
        match=re.search(r'Acknowledgment key: (I-HAVE-READ-THE-BEST-PRACTICES-GUIDE-[a-f0-9]{8})',value['content'])
        # The independent static executor still validates the exact light-only
        # config. Guide text cannot add a command, permission or bypass.
        return {'sha256':fingerprint(value['content']),'ack':match[1] if match else None}

    def _original(self,provider,tool,parameters):
        if provider=='ha_mcp' and tool=='ha_config_set_automation':
            read=self.tools.registry.get(provider,'ha_config_get_automation',effect='read')
            client=self.tools.connections.clients[provider]
            value=client.call('ha_config_get_automation',{'entity_id':parameters['entity_id']})
            if not isinstance(value,dict) or value.get('success') is False or not isinstance(value.get('config'),dict) or not isinstance(value.get('config_hash'),str):raise RepairBlocked('Původní konfigurace nebyla ověřená.')
            return {'config':value['config'],'config_hash':value['config_hash']}
        if provider=='spook' and tool in {'homeassistant.enable_entity','homeassistant.disable_entity'}:
            value=self.app.core_ws.transport({'type':'config/entity_registry/get','entity_id':parameters['entity_id']})
            if not isinstance(value,dict) or value.get('entity_id')!=parameters['entity_id'] or not value.get('unique_id') or not value.get('device_id') or value.get('disabled_by') not in {None,'user'}:raise RepairBlocked('Registr cíle není bezpečně ověřený.')
            return {k:value.get(k) for k in ('entity_id','unique_id','platform','device_id','config_entry_id','disabled_by')}
        raise RepairBlocked('Tato zapisovací operace není implementovaná.')

    def target_identity(self,entity_id):
        row=self.app.core_ws.transport({'type':'config/entity_registry/get','entity_id':entity_id})
        if not isinstance(row,dict) or row.get('entity_id')!=entity_id or not all(isinstance(row.get(k),str) and row[k] for k in ('unique_id','device_id','platform')) or row.get('disabled_by') is not None:
            raise RepairBlocked('Skutečná identita cílového zařízení není ověřená.')
        return {k:row.get(k) for k in ('entity_id','unique_id','device_id','platform','config_entry_id','disabled_by')}

    @staticmethod
    def replacement(original,proposed):
        """Exactly one literal action target; no template, blueprint, Python or arbitrary patch."""
        changed=[]
        def walk(a,b,path):
            if type(a)!=type(b):changed.append((path,a,b));return
            if isinstance(a,dict):
                if set(a)!=set(b):changed.append((path,a,b));return
                for k in a:walk(a[k],b[k],path+[k])
            elif isinstance(a,list):
                if len(a)!=len(b):changed.append((path,a,b));return
                for i,(x,y) in enumerate(zip(a,b)):walk(x,y,path+[i])
            elif a!=b:changed.append((path,a,b))
        walk(original,proposed,[])
        if len(changed)!=1:raise RepairBlocked('Povolená je pouze jedna přesná změna reference.')
        path,old,new=changed[0]
        if len(path)!=4 or path[0] not in {'action','actions'} or type(path[1]) is not int or path[2:]!=['target','entity_id'] or not isinstance(old,str) or not isinstance(new,str):raise RepairBlocked('Nepodporovaný tvar změny reference.')
        # Light-only automated execution excludes heaters, locks, security and
        # hidden scripts; a full config hash also binds trigger/conditions.
        steps=original[path[0]]
        if original.get('use_blueprint') or len(steps)!=1 or steps[0].get('action',steps[0].get('service')) not in {'light.turn_on','light.turn_off'} or set(steps[0])-{'action','service','target','alias'} or not old.startswith('light.') or not new.startswith('light.'):
            raise RepairBlocked('Automatická změna je omezená na jedinou přímou světelnou akci bez dat a skriptů.')
        triggers=original.get('triggers',original.get('trigger'))
        if not isinstance(triggers,list) or len(triggers)!=1 or not isinstance(triggers[0],dict) or triggers[0].get('trigger',triggers[0].get('platform'))!='state' or not isinstance(triggers[0].get('entity_id'),str) or set(triggers[0])-{'trigger','platform','entity_id','from','to','id'} or original.get('conditions',original.get('condition',[]))!=[] or set(original)-{'id','alias','description','mode','triggers','trigger','conditions','condition','actions','action'}:
            raise RepairBlocked('Automatická úprava vyžaduje přímý stavový trigger bez šablon, skriptů a dalších účinků.')
        return old,new

    def prepare(self,incident_id,provider,tool,parameters,evidence_ids,reason,*,exclusive=False,rollback_of=None):
        case=self.app.store.case(incident_id);self.tools._scope(case,parameters)
        row=self.tools.registry.get(provider,tool,effect='write');validate(row['schema'],parameters)
        if not row['repair_operation_implemented'] or not exclusive:raise RepairBlocked('Plán vyžaduje implementovaný vykonavatel a výlučnou práci s cílem.')
        if not evidence_ids or not set(evidence_ids)<={e['evidence_id'] for e in case['evidence']}:raise RepairBlocked('Chybí skutečné důkazy tohoto spisu.')
        if not isinstance(reason,str) or not 1<=len(reason)<=2000:raise RepairBlocked('Chybí kontrolovatelný důvod změny.')
        if not next(p for p in self.tools.registry.providers() if p['id']==provider).get('version'):raise RepairBlocked('Skutečná verze poskytovatele není ověřená; nelze připravit zápis.')
        if provider=='spook' and tool=='homeassistant.disable_entity' and not rollback_of:
            raise RepairBlocked('Zakázání entity se nepoužívá jako oprava závady. Je dostupné pouze jako samostatně schválený návrat předchozího povolení.')
        parent=None
        if rollback_of:
            parent=self.plan(rollback_of).document
            with closing(connect(self.app.store.db_path)) as db:previous=db.execute('SELECT status FROM repair_executions WHERE plan_id=?',(rollback_of,)).fetchone()
            if parent['incident_id']!=incident_id or parent['binding']['provider']!=provider or parent['parameters']['entity_id']!=parameters['entity_id'] or not previous or previous[0] not in {'applied_verification_pending','verified','failed','recurred'}:
                raise RepairBlocked('Návrat nemá odpovídající skutečně provedený původní zásah.')
            if provider=='ha_mcp' and parameters['config']!=parent['original']['config']:raise RepairBlocked('Návrat by změnil více než původní konfiguraci.')
            if provider=='spook' and tool==parent['binding']['tool']:raise RepairBlocked('Návrat není inverzí původního povolení.')
        guide=self._guide() if provider=='ha_mcp' else None
        parameters=copy.deepcopy(parameters)
        if guide and guide['ack']:parameters['BestPracticeKey']=guide['ack']
        validate(row['schema'],parameters)
        original=self._original(provider,tool,parameters)
        if parent:
            expected=parent['proposed']
            if provider=='ha_mcp' and original['config']!=expected['config'] or provider=='spook' and original!=expected:raise RepairBlocked('Cíl se od původního zásahu změnil; návrat by přepsal jinou změnu.')
        if provider=='ha_mcp':
            if original['config_hash']!=parameters['config_hash']:raise RepairBlocked('Konfigurace se změnila; potřebuje nový návrh.')
            old,new=self.replacement(original['config'],parameters['config'])
            if not rollback_of:
                with self.app.store._connect() as db:renamed=db.execute('SELECT device_id FROM entity_renames WHERE old_id=? AND new_id=?',(old,new)).fetchone()
                if not renamed:raise RepairBlocked('Náhradní identifikátor není doložený stabilní identitou registru. Podobný název nestačí.')
                missing=self.app.core.states(old)
                if missing is not None or self.app.core.status.last_response_status!=404:raise RepairBlocked('Původní reference není prokázaná jako chybějící.')
            target_identity=self.target_identity(new) if not rollback_of else None
            if not rollback_of and target_identity['device_id']!=renamed['device_id']:raise RepairBlocked('Náhradní entita už nepatří doloženému původnímu zařízení.')
            target=self.app.core.states(new)
            if not rollback_of and (not isinstance(target,dict) or target.get('state') not in {'on','off'}):raise RepairBlocked('Nový světelný cíl není čitelný.')
            if rollback_of and (target is not None or self.app.core.status.last_response_status!=404):raise RepairBlocked('Původní chybějící reference už může patřit jinému zařízení. Návrat konfigurace se zastavil.')
            auto_state=self.app.core.states(parameters['entity_id'])
            config_id=(auto_state or {}).get('attributes',{}).get('id')
            if not isinstance(config_id,str) or str(original['config'].get('id'))!=config_id:raise RepairBlocked('Identita automatizace není ověřená.')
            proposed={'config':parameters['config']}
            condition={'automation_id':config_id,'entity_id':new,'state':'on' if original['config'].get('actions',original['config'].get('action'))[0].get('action',original['config'].get('actions',original['config'].get('action'))[0].get('service'))=='light.turn_on' else 'off','watch_seconds':30,'physical_confirmation_required':True,'target_identity':target_identity,'missing_target_required':new if rollback_of else None}
            manual='V HA otevři uvedenou automatizaci. Změň pouze zobrazený původní target entity_id na doloženou novou identitu, ulož a ověř skutečný trigger a světlo. Při jiné konfiguraci změnu neprováděj.'
        else:
            enable=tool=='homeassistant.enable_entity'
            if original['disabled_by']!=( 'user' if enable else None):raise RepairBlocked('Registr už není v očekávaném původním stavu.')
            proposed={**original,'disabled_by':None if enable else 'user'}
            condition={'entity_id':parameters['entity_id'],'expected_enabled':enable,'watch_seconds':30,'physical_confirmation_required':True}
            manual='V HA otevři přesně tuto entitu v zařízení, ověř její identitu a požadovaný stav povolení. Změň jen povolení a ověř aktualizaci hodnoty fyzickým testem. Entity nemaž.'
        original_hash=fingerprint(original)
        receipt=self.backups.verify(original_hash)
        document={'schema':1,'operation':'tool.approved','incident_id':incident_id,'binding':self.binding(row),'parameters':copy.deepcopy(parameters),'target':{'entity_id':parameters['entity_id']},
            'original':original,'original_sha256':original_hash,'proposed':proposed,'evidence_ids':sorted(set(evidence_ids)),
            'guide_receipt':guide,'reason':reason,'risk':row['risk'],'backup':{'required':'independent_OneDrive_restore_attestation','receipt_sha256':fingerprint(receipt),'scope':receipt['scope']},
            'preconditions':['exclusive_target','exact_original','unchanged_provider_schema_identity_version','owner_approval_unexpired','independent_restore_proof'],
            'verification':condition,'expected_result':'Ověřený zápis musí následovat skutečný funkční test a sledovací doba. HTTP úspěch případ neuzavírá.',
            'rollback':{'supported':True,'separate_approval_required':True,'rollback_of':rollback_of,'scope':'exact_configuration_or_registry_field_not_physical_effects'},
            'manual_alternative':manual,'non_atomic_warning':'Kontrola hashe před zápisem není plný serverový CAS s ostatními editory. Při souběhu nebo nejasném výsledku se zásahy zastaví.'}
        plan=RepairPlan(canonical(document))
        with closing(connect(self.app.store.db_path)) as db:inserted=db.execute('INSERT OR IGNORE INTO repair_plans VALUES(?,?,?,?)',(plan.plan_id,plan.serialized,canonical(original).encode(),self.app.clock())).rowcount
        if inserted:self.app.store.record(incident_id,'tool_plan_prepared',{'plan_id':plan.plan_id,'provider':provider,'tool':tool})
        return plan

    def plan(self,identity):
        with closing(connect(self.app.store.db_path)) as db:row=db.execute('SELECT document FROM repair_plans WHERE id=?',(identity,)).fetchone()
        if not row:raise RepairBlocked('Plán neexistuje.')
        plan=RepairPlan(row[0])
        if plan.document.get('operation')!='tool.approved':raise RepairBlocked('Plán nepatří tomuto brokeru.')
        return plan

    def _preflight(self,plan):
        binding=plan.document['binding']
        if binding['provider']=='ha_mcp':self.tools._mcp('ha_mcp',self.tools.connections.clients['ha_mcp'])
        else:
            self.tools._services()
            manifest=self.app.core_ws.transport({'type':'manifest/get','integration':'spook'})
            if not isinstance(manifest,dict) or not isinstance(manifest.get('version'),str):raise RepairBlocked('Aktuální verze Spooku nebyla ověřená.')
            self.tools.registry.provider('spook',version=manifest['version'],version_basis='installed_HA_integration_manifest')
        d=plan.document;b=d['binding'];row=self.tools.registry.get(b['provider'],b['tool'],effect='write')
        if self.binding(row)!=b:raise RepairBlocked('Poskytovatel, schéma nebo připojení se změnilo; schválení už nelze použít.')
        validate(row['schema'],d['parameters'])
        if b['provider']=='ha_mcp' and self._guide()!=d.get('guide_receipt'):raise RepairBlocked('Pravidla nebo potvrzení HA-MCP se změnila; je potřeba nový plán.')
        if fingerprint(self._original(b['provider'],b['tool'],d['parameters']))!=d['original_sha256']:raise RepairBlocked('Cíl se změnil; je potřeba nové schválení.')
        if d['verification'].get('target_identity') is not None and self.target_identity(d['verification']['entity_id'])!=d['verification']['target_identity']:raise RepairBlocked('Identifikátor nyní patří jinému zařízení; je potřeba nový návrh.')
        if d['verification'].get('missing_target_required'):
            state=self.app.core.states(d['verification']['missing_target_required'])
            if state is not None or self.app.core.status.last_response_status!=404:raise RepairBlocked('Původní identifikátor už není prokázaný jako chybějící. Návrat by mohl ovládat jiné zařízení.')
        receipt=self.backups.verify(d['original_sha256'])
        if fingerprint(receipt)!=d['backup']['receipt_sha256']:raise RepairBlocked('Důkaz zálohy se změnil; je potřeba nový plán.')
        return row

    def decide(self,identity,decision,principal,*,exclusive=False):
        self._owner(principal);plan=self.plan(identity)
        if decision not in {'approve','reject','manual'}:raise RepairBlocked('Neplatné rozhodnutí.')
        if decision=='approve' and exclusive is not True:raise RepairBlocked('Potvrď, že cílový objekt nyní nikdo jiný neupravuje.')
        with self.app._read_lock:
            if decision=='approve':self._preflight(plan)
            authority=ApprovalAuthority(self.app.store.db_path,owner=self.app.owner(),clock=self.app.clock)
            token=authority.decide(plan,principal=principal,decision=decision)
            self.app.store.record(plan.document['incident_id'],'repair_decision',{'plan_id':identity,'decision':decision,'principal':principal})
            if decision!='approve':return None
            return self.execute(plan,token,principal)

    def execute(self,plan,token,principal):
        with self._write_lock:return self._execute(plan,token,principal)

    def _execute(self,plan,token,principal):
        self._owner(principal);self._preflight(plan);d=plan.document;now=self.app.clock();execution_id=secrets.token_hex(16)
        with closing(connect(self.app.store.db_path)) as db:
            db.execute('BEGIN IMMEDIATE')
            uncertain=db.execute("SELECT 1 FROM repair_executions e JOIN repair_plans p ON p.id=e.plan_id WHERE e.status IN ('tool_intent','unknown_requires_reconciliation') AND json_extract(p.document,'$.operation')='tool.approved'").fetchone()
            if uncertain:raise RepairBlocked('Předchozí nejistý zásah blokuje další zápisy tohoto brokeru i z jiného případu.')
            registered=db.execute('SELECT document FROM repair_plans WHERE id=?',(plan.plan_id,)).fetchone()
            approval=db.execute("SELECT * FROM repair_decisions WHERE token_hash=? AND plan_id=?",(digest(token),plan.plan_id)).fetchone()
            if not registered or registered[0]!=plan.serialized or not approval or approval['principal']!=principal or approval['decision']!='approve' or approval['consumed_at'] is not None or approval['expires_at']<=now:raise RepairBlocked('Chybí platné autentické schválení přesného plánu.')
            if db.execute('SELECT 1 FROM repair_executions WHERE plan_id=?',(plan.plan_id,)).fetchone():raise RepairBlocked('Tento plán už má vykonávací záznam; nesmí se opakovat.')
            db.execute('UPDATE repair_decisions SET consumed_at=? WHERE token_hash=?',(now,digest(token)))
            db.execute("INSERT INTO repair_executions VALUES(?,?,'tool_intent',?,NULL,NULL)",(execution_id,plan.plan_id,now));db.execute('COMMIT')
        # Intent is durable before the only external write. Any timeout is
        # unknown, never an excuse to replay, auto-rollback or claim failure-safe.
        try:
            b=d['binding']
            if b['provider']=='ha_mcp':
                result=self.tools.connections.clients['ha_mcp'].call(b['tool'],d['parameters'])
                if not isinstance(result,dict) or result.get('success') is not True:raise RepairBlocked('Zápis nebyl potvrzený.')
            else:self.app.core_ws.transport({'type':'call_service','domain':'homeassistant','service':b['tool'].split('.')[1],'service_data':{'entity_id':[d['parameters']['entity_id']]}})
            current=self._original(b['provider'],b['tool'],d['parameters'])
            matches=current.get('config')==d['proposed'].get('config') if b['provider']=='ha_mcp' else current==d['proposed']
            if not matches:raise RepairBlocked('Zpětné čtení neodpovídá schválené změně.')
            status='applied_verification_pending';completed=self.app.clock();error=None
        except Exception:
            status='unknown_requires_reconciliation';completed=None;error='tool_write_or_readback_uncertain_no_replay'
        with closing(connect(self.app.store.db_path)) as db:db.execute('UPDATE repair_executions SET status=?,completed_at=?,error=? WHERE id=?',(status,completed,error,execution_id))
        self.app.store.record(d['incident_id'],'tool_execution',{'plan_id':plan.plan_id,'execution_id':execution_id,'status':status,'retry_allowed':False})
        if status=='applied_verification_pending':self.app.repairs.start()
        self.report(plan,execution_id,'Oprava provedena, ověření čeká' if completed else 'Není dostatek důkazů')
        return ExecutionResult(execution_id,plan.plan_id,status,now,completed)

    def report(self,plan,execution_id,classification,*,observations=()):
        summaries={'Vyřešeno a ověřeno':'Funkční podmínka a požadovaný uživatelský test byly ověřené.',
                   'Oprava provedena, ověření čeká':'Zásah čeká na funkční důkazy.',
                   'Oprava selhala':'Kontrolní čtení neodpovídá plánu. Zásah neuzavřel incident; další postup vyžaduje nový návrh.',
                   'Problém se opakoval':'Funkční monitor po ověřené opravě znovu zachytil nesplněnou podmínku. Spis se znovu otevírá a další zápis vyžaduje nový plán.',
                   'Návrat změny ověřen čtením; funkční problém zůstává':'Původní konfigurace nebo povolení entity byly znovu přečtené. Návrat nevrací fyzické účinky a nepotvrzuje vyřešení problému.'}
        value={'scope':'provider_tool_functional_observations','incident_id':plan.document['incident_id'],'execution_id':execution_id,'classification':classification,'plan_id':plan.plan_id,'provider':plan.document['binding']['provider'],'tool':plan.document['binding']['tool'],
               'summary_cs':summaries.get(classification,'Výsledek nelze bezpečně určit. Další zápis je zastaven; proběhne pouze kontrolní čtení.'),
               'haos_restored':False,'evidence':list(observations)}
        with closing(connect(self.app.store.db_path)) as db:
            previous=db.execute('SELECT document FROM repair_reports WHERE execution_id=? ORDER BY id DESC LIMIT 1',(execution_id,)).fetchone()
            if previous and previous[0]==canonical(value):return value
            db.execute('INSERT INTO repair_reports(execution_id,created_at,classification,document) VALUES(?,?,?,?)',(execution_id,self.app.clock(),classification,canonical(value)))
        self.app.store.record(plan.document['incident_id'],'repair_report',value)
        return value

    def rollback_plan(self,identity,*,exclusive=False):
        plan=self.plan(identity);d=plan.document;b=d['binding']
        with closing(connect(self.app.store.db_path)) as db:run=db.execute('SELECT status FROM repair_executions WHERE plan_id=?',(identity,)).fetchone()
        if not run or run[0] not in {'applied_verification_pending','verified','failed','recurred'}:raise RepairBlocked('Nejasný nebo neprovedený zásah nelze automaticky vracet.')
        current=self._original(b['provider'],b['tool'],d['parameters']);params=copy.deepcopy(d['parameters'])
        if b['provider']=='ha_mcp':
            if current['config']!=d['proposed']['config']:raise RepairBlocked('Po zásahu je jiná konfigurace. Rollback nesmí přepsat cizí změnu.')
            params.update(config=d['original']['config'],config_hash=current['config_hash']);tool=b['tool']
        else:
            if current!=d['proposed']:raise RepairBlocked('Registr se změnil po zásahu.')
            tool='homeassistant.disable_entity' if b['tool']=='homeassistant.enable_entity' else 'homeassistant.enable_entity'
        case=self.app.store.case(d['incident_id'])
        return self.prepare(d['incident_id'],b['provider'],tool,params,[e['evidence_id'] for e in case['evidence']],
            'Samostatně schvalovaný návrat přesně schválené změny; fyzické účinky se nevracejí.',exclusive=exclusive,rollback_of=identity)

    def confirm_physical(self,identity,principal):
        self._owner(principal);plan=self.plan(identity)
        with closing(connect(self.app.store.db_path)) as db:
            run=db.execute("SELECT * FROM repair_executions WHERE plan_id=? AND status='applied_verification_pending'",(identity,)).fetchone()
            if not run:raise RepairBlocked('Zásah nečeká na funkční ověření.')
            event={'kind':'owner_functional_confirmation','observed_at':self.app.clock(),'payload':{'entity_id':plan.document['verification']['entity_id'],'confirmed':True,'authority':'authenticated_owner'}}
            db.execute('INSERT OR IGNORE INTO repair_observations VALUES(?,?,?)',(run['id'],fingerprint(event),canonical(event)))
        self.app.store.record(plan.document['incident_id'],'functional_owner_test',{'plan_id':identity,'confirmed':True})
        return self.verify(identity)

    def verify(self,identity):
        plan=self.plan(identity);d=plan.document;b=d['binding'];now=self.app.clock()
        with closing(connect(self.app.store.db_path)) as db:row=db.execute('SELECT * FROM repair_executions WHERE plan_id=?',(identity,)).fetchone()
        if not row or row['status'] not in {'applied_verification_pending','verified','failed','recurred'}:raise RepairBlocked('Nejprve je potřeba bezpečně určit výsledek zápisu.')
        current=self._original(b['provider'],b['tool'],d['parameters'])
        matches=current.get('config')==d['proposed'].get('config') if b['provider']=='ha_mcp' else current==d['proposed']
        if d['verification'].get('target_identity') is not None and self.target_identity(d['verification']['entity_id'])!=d['verification']['target_identity']:matches=False
        if not matches:
            with closing(connect(self.app.store.db_path)) as db:db.execute("UPDATE repair_executions SET status='failed' WHERE id=?",(row['id'],))
            return self.report(plan,row['id'],'Oprava selhala')
        if d['rollback']['rollback_of']:
            with closing(connect(self.app.store.db_path)) as db:db.execute("UPDATE repair_executions SET status='rollback_reference_restored' WHERE id=?",(row['id'],))
            return self.report(plan,row['id'],'Návrat změny ověřen čtením; funkční problém zůstává')
        detector=self.app.detection.health
        if detector['state']!='listening' or now-(detector.get('heartbeat_at') or 0)>15:return self.report(plan,row['id'],'Oprava provedena, ověření čeká')
        if b['provider']=='ha_mcp':
            service=self.app.repairs
            if service.trigger_coverage is None or now-(service.trigger_heartbeat or 0)>15:return self.report(plan,row['id'],'Oprava provedena, ověření čeká')
            state=self.app.core.states(d['verification']['entity_id']) if self.app.core else None
            if not isinstance(state,dict) or state.get('state')!=d['verification']['state']:
                with service.lock:service.state_breaks[d['verification']['entity_id']]=now
                return self.report(plan,row['id'],'Oprava provedena, ověření čeká')
            with service.lock:
                observations=list(service.observations);read_break=service.state_breaks.get(d['verification']['entity_id'],0)
            with closing(connect(self.app.store.db_path)) as db:owner_observations=[json.loads(r[0]) for r in db.execute('SELECT document FROM repair_observations WHERE execution_id=?',(row['id'],))]
            condition=d['verification']
            triggers=[o for o in observations if o.get('kind')=='automation_triggered' and o.get('payload',{}).get('automation_id')==condition['automation_id'] and o['observed_at']>row['completed_at']][-32:]
            results=[o for o in observations if o.get('kind')=='target_state' and o.get('payload',{}).get('entity_id')==condition['entity_id'] and o['payload'].get('state')==condition['state'] and o['observed_at']>row['completed_at']][-32:]
            confirmations=[o['observed_at'] for o in owner_observations if o.get('kind')=='owner_functional_confirmation' and o.get('payload',{}).get('confirmed') is True and o['payload'].get('authority')=='authenticated_owner'][-32:]
            continuous=max(row['completed_at'],detector['continuous_since'] or now,service.trigger_coverage,read_break)
            # Breaks in state must be seen from actual controller observations,
            # including after a previous successful run; a restart resets coverage.
            continuous=max([continuous]+[o['observed_at'] for o in observations if o.get('kind')=='target_state' and o.get('payload',{}).get('entity_id')==condition['entity_id'] and o['payload'].get('state')!=condition['state']])
            candidate=any(t['payload'].get('context_id') and t['payload'].get('context_id')==r['payload'].get('context_id') and max(t['observed_at'],continuous)<=r['observed_at']<=c<=now for t in triggers for r in results for c in confirmations)
            if not candidate:return self.report(plan,row['id'],'Oprava provedena, ověření čeká')
            observations.append({'kind':'monitoring_checkpoint','observed_at':now,'payload':{'entity_id':condition['entity_id'],'continuous_since':continuous,'healthy':True}})
            execution=ExecutionResult(row['id'],identity,row['status'],row['started_at'],row['completed_at'])
            report=FunctionalVerifier(self.app.store.db_path,clock=self.app.clock).evaluate(plan,execution,observations)
        else:
            with closing(connect(self.app.store.db_path)) as db:
                observations=[json.loads(r[0]) for r in db.execute('SELECT document FROM repair_observations WHERE execution_id=?',(row['id'],))]
            confirmed=any(r.get('kind')=='owner_functional_confirmation' for r in observations)
            failed=[r for r in observations if r.get('kind')=='functional_failure' and r.get('observed_at',0)>row['completed_at']]
            entity=d['verification']['entity_id'];state=self.app.core.states(entity)
            from .provider_reports import stamp
            fresh=isinstance(state,dict) and (stamp(state.get('last_updated')) or 0)>row['completed_at']
            desired=isinstance(state,dict) and state.get('state') not in {'unknown','unavailable',None} if d['verification']['expected_enabled'] else state is None and self.app.core.status.last_response_status==404
            breaks=[o['observed_at'] for o in observations if o.get('kind')=='tool_target_state' and o.get('payload',{}).get('state') in {'unavailable','unknown'}]
            covered=now-max([row['completed_at'],detector['continuous_since'] or now]+breaks)>=d['verification']['watch_seconds']
            if failed:
                classification='Problém se opakoval' if row['status'] in {'verified','recurred'} else 'Oprava selhala'
                with closing(connect(self.app.store.db_path)) as db:db.execute('UPDATE repair_executions SET status=? WHERE id=?',('recurred' if classification=='Problém se opakoval' else 'failed',row['id']))
                return self.report(plan,row['id'],classification,observations=failed)
            report=self.report(plan,row['id'],'Vyřešeno a ověřeno' if confirmed and desired and (fresh or not d['verification']['expected_enabled']) and covered else 'Oprava provedena, ověření čeká')
            if report['classification']=='Vyřešeno a ověřeno':
                with closing(connect(self.app.store.db_path)) as db:db.execute("UPDATE repair_executions SET status='verified' WHERE id=?",(row['id'],))
        if report['classification']=='Vyřešeno a ověřeno':self.app.store.mark_resolved(d['incident_id'],report)
        return report

    def reconcile(self,identity):
        """Read-only recovery. No replay or implicit rollback authorization."""
        plan=self.plan(identity);d=plan.document;b=d['binding']
        current=self._original(b['provider'],b['tool'],d['parameters'])
        matches=current.get('config')==d['proposed'].get('config') if b['provider']=='ha_mcp' else current==d['proposed']
        target=d['verification'].get('target_identity')
        identity_matches=self.target_identity(d['verification']['entity_id'])==target if target is not None else True
        result={'read_verified':True,'matches_proposed':matches,'matches_original':fingerprint(current)==d['original_sha256'],
                'target_identity_matches':identity_matches,'requires_new_owner_decision':True,'retry_authorized':False}
        self.app.store.record(d['incident_id'],'tool_write_reconciliation',{'plan_id':identity,**result})
        return result

    def observe_state(self,state,when):
        with closing(connect(self.app.store.db_path)) as db:
            runs=db.execute("SELECT e.id,p.document FROM repair_executions e JOIN repair_plans p ON p.id=e.plan_id WHERE e.status='applied_verification_pending' AND json_extract(p.document,'$.operation')='tool.approved'").fetchall()
            for row in runs:
                d=json.loads(row['document'])
                if state.get('entity_id')!=d['verification']['entity_id']:continue
                event={'kind':'tool_target_state','observed_at':when,'payload':{'entity_id':state['entity_id'],'state':state.get('state')}}
                count=db.execute('SELECT count(*) FROM repair_observations WHERE execution_id=?',(row['id'],)).fetchone()[0]
                if count<512:db.execute('INSERT OR IGNORE INTO repair_observations VALUES(?,?,?)',(row['id'],fingerprint(event),canonical(event)))
                else:db.execute("UPDATE repair_executions SET status='unknown_requires_reconciliation',error='verification_observation_budget' WHERE id=?",(row['id'],))
