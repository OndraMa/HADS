"""Readiness reports observations, never green checks from mere configuration."""
from pathlib import Path


def memory_available():
    try:
        available=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024
        maximum=Path('/sys/fs/cgroup/memory.max');used=Path('/sys/fs/cgroup/memory.current')
        if maximum.exists() and maximum.read_text().strip()!='max':available=min(available,int(maximum.read_text())-int(used.read_text()))
        return max(0,available)
    except (ValueError,OSError,StopIteration):return None


def checklist(app):
    snapshot=app.snapshot();sources=snapshot['sources'];runtime=app.investigations.status();memory=memory_available();repairs=app.repairs.status()
    tool_rows=app.tools.registry.tools()
    implemented=sum(r['repair_operation_implemented'] and r['available'] for r in tool_rows)
    ready=sum(r['repair_ready_for_approval'] for r in tool_rows)
    def source(name):return bool(sources.get(name,{}).get('read_succeeded'))
    with app.store._connect() as db:
        model_read=bool(db.execute("SELECT 1 FROM investigation_model_calls WHERE state='response' LIMIT 1").fetchone())
    checks=[('Verze a platforma',bool(snapshot['core']['version']),'Core '+str(snapshot['core']['version'] or 'nepřečteno')+'; ARM64/AMD64 build není živá HAOS přejímka.'),
        ('Core',snapshot['core']['available'],'Výsledek posledního konkrétního čtení stavů.'),
        ('Supervisor a HAOS',source('supervisor') and source('haos'),'Přístup k API nestačí; oba zdroje se musejí skutečně přečíst.'),
        ('Diagnostické zdroje',any(x.get('read_succeeded') for x in sources.values()),str(sum(bool(x.get('read_succeeded')) for x in sources.values()))+' úspěšných čtení; detaily a mezery jsou níže.'),
        ('Hermes runtime',runtime['runtime_probe']['state']=='ready',runtime['runtime_probe']['summary_cs']),
        ('Volná paměť',memory is not None and memory>=576*1024*1024,('Nezjištěná' if memory is None else str(memory//(1024*1024))+' MiB')+'; rezerva 576 MiB zůstává povinná a znovu se kontroluje před workerem. '+('Nad hranicí zbývá '+str((memory-576*1024*1024)//(1024*1024))+' MiB. Tento údaj nezaručuje připravenost při zátěži.' if memory is not None and memory>=576*1024*1024 else 'Bez splněné rezervy se nový worker nespustí.')),
        ('AI poskytovatel',model_read,('Přijatá skutečná odpověď poskytovatele; správnost úsudku tím není dokázaná.' if model_read else 'Nastavení existuje; skutečný úspěšný požadavek ověř v konkrétním vyšetřování.' if runtime['provider']['configured'] else 'Poskytovatel není nastavený. Lokální detekce pokračuje.')),
        ('Souhlas s náklady',runtime['provider']['enabled'],'Automatické vyšetřování má navíc vlastní samostatný souhlas.'),
        ('Zálohování',False,'Snapshot jediné reference je ověřen při přípravě plánu. HAOS/OneDrive obnovitelnost není doložená; rizikové operace jsou blokované.'),
        ('Opravný mechanismus',ready>0 or bool(repairs.get('companion_checked_at')) or repairs.get('native_state_targets',0)>0,'Společný katalog: '+str(implemented)+' dostupných implementovaných opravných operací; '+str(ready)+' funkcí s připraveným plánem. HA-MCP mění jedinou doloženou světelnou referenci, Spook povolení jedné entity; vyžadují skutečný důkaz obnovitelnosti a konkrétní souhlas. Původní oddělený CAS test a světelná aktivace zůstávají dostupné podle svého nastavení.'),
        ('První funkční diagnostika',any(c['kind']=='functional_monitor' for c in snapshot['cases']),'Skutečný monitor musí zachytit nesplněnou podmínku; samotné spojení ani modelový závěr ji nenahrazují.')]
    return [{'label':label,'passed':bool(passed),'detail':detail} for label,passed,detail in checks]
