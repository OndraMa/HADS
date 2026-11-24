"""Deterministic explanations of native diagnostics, with no repair authority."""
import re,math

MIB = 1024 * 1024
_IDENTIFIER = re.compile(r'[a-z0-9_]{1,80}')
# Persist diagnostic codes, never arbitrary remote messages, URLs or headers.
_ERROR_CODES = {'unreachable', 'timeout', 'unknown', 'cannot_connect', 'cannot_resolve'}
_EXCEPTIONS = ('ClientConnectorDNSError','ClientConnectorCertificateError','ClientConnectorError','TimeoutError','SSLError')


def project_health_log(row,domain,now):
    if not isinstance(row,dict) or not _IDENTIFIER.fullmatch(domain):return None
    logger=row.get('name');stamp=row.get('timestamp')
    roots=('homeassistant.components.'+domain,'custom_components.'+domain)
    if not isinstance(logger,str) or len(logger)>200:return None
    source=next((root for root in roots if logger==root or logger.startswith(root+'.')),None)
    if source is None:return None
    if row.get('level') not in {'ERROR','CRITICAL','WARNING'}:return None
    if type(stamp) not in {int,float} or not math.isfinite(stamp) or not now-900<=stamp<=now+5:return None
    message=row.get('message');message=' '.join(x[:8192] for x in message[:8] if isinstance(x,str)) if isinstance(message,list) else message[:8192] if isinstance(message,str) else ''
    exception=row.get('exception');text=message+' '+(exception[:8192] if isinstance(exception,str) else '')
    classes=[name for name in _EXCEPTIONS if re.search(r'\b'+name+r'\b',text)]
    return {'logger':source,'observed_at':stamp,'level':row['level'],'exception_types':classes,'causality_proven':False}


def project_health_errors(info):
    if not isinstance(info, dict):
        return []
    return [{'field': key, 'error': value['error'] if isinstance(value['error'], str)
             and value['error'] in _ERROR_CODES else 'unclassified'}
            for key, value in list(info.items())[:128]
            if isinstance(key, str) and _IDENTIFIER.fullmatch(key)
            and isinstance(value, dict) and value.get('error')]


def health_domain(incident):
    for component in incident.get('components', []):
        if isinstance(component, str) and component.startswith('integration:'):
            domain = component.partition(':')[2]
            if _IDENTIFIER.fullmatch(domain):
                return domain
    return None


def diagnostic_observation(incident):
    key = str(incident.get('correlation_key') or '')
    return (incident.get('kind') == 'system_health_failure' and key.startswith('health:health:')
            or incident.get('kind') == 'system_resource_pressure'
            and 'hads_runtime' in incident.get('components', []) and key == 'health:memory-reserve')


def explain_health_case(case):
    incident = case['incident']
    evidence = [row for row in case.get('evidence', [])
                if row.get('source') == 'native_system_health' and row.get('kind') == incident['kind']]
    evidence.sort(key=lambda row: row['observed_at'])
    payload = evidence[-1]['payload'] if evidence else {}
    if incident['kind'] == 'system_health_failure':
        domain = health_domain(incident) or 'neurčená integrace'
        name = 'Marketplace' if domain == 'marketplace' else domain
        raw_fields=payload.get('failed_fields')
        fields = [field for field in (raw_fields if isinstance(raw_fields,list) else [])
                  if isinstance(field, str) and _IDENTIFIER.fullmatch(field)][:128]
        github = domain == 'marketplace' and 'github_web' in fields
        summary = (name + ': kontrola přístupu k webu GitHubu (github_web) neprošla.' if github
                   else name + ': neprošla diagnostická kontrola' + (' ' + ', '.join(fields) if fields else '') + '.')
        raw_errors=payload.get('errors')
        codes = [row['error'] for row in (raw_errors if isinstance(raw_errors,list) else [])
                 if isinstance(row, dict) and row.get('field') in fields
                 and isinstance(row.get('error'), str) and row['error'] in _ERROR_CODES]
        summary += (' Zaznamenaný chybový kód: ' + ', '.join(sorted(set(codes))) + '.' if codes
                    else ' Původní důkaz neobsahuje konkrétní chybový kód.')
        summary += ' Příčina ani dopad na funkce domácnosti nejsou doložené.'
        classes=sorted({name for row in case.get('evidence',[]) if row.get('source')=='native_system_health'
                        and row.get('kind')=='system_health_log'
                        for name in (row.get('payload',{}).get('exception_types') or []) if name in _EXCEPTIONS})
        if classes:summary+=' V časově souvisejícím protokolu integrace jsou typy chyb: '+', '.join(classes)+'. Je to vodítko, nikoli důkaz společné příčiny.'
        return {'summary_cs': summary, 'root_cause_proven': False,
                'needed': ['Nové čtení stejné kontroly a její chybový kód.',
                           'Při opakování časově související protokol integrace; odlišit DNS, spojení, TLS a odpověď serveru.'],
                'next_test_cs': 'HADS při další automatické kontrole znovu přečte System Health a protokol integrace '
                                + name + '. U Marketplace sám ověří přístup ke GitHubu ze své aplikace. '
                                'Úspěch v prohlížeči Windows neověřuje přístup z HAOS. Diagnostické příkazy od uživatele nepotřebuji. '
                                'Bez příčiny nenavrhuji změnu DNS, restart ani konfigurační opravu.'}
    if incident['kind'] == 'system_resource_pressure' and 'hads_runtime' in incident.get('components', []):
        available, reserve = payload.get('available_bytes'), payload.get('reserve_bytes')
        if type(available) is int and available >= 0 and type(reserve) is int and reserve > 0:
            summary = ('V době nálezu bylo dostupných ' + str(available // MIB) + ' MiB; požadovaná rezerva '
                       + str(reserve // MIB) + ' MiB. Do hranice chybělo nejméně '
                       + str((max(0, reserve - available) + MIB - 1) // MIB) + ' MiB.')
        else:
            summary = 'V době nálezu nebyla splněná paměťová rezerva. Původní důkaz neobsahuje změřenou dostupnou paměť.'
        return {'summary_cs': summary + ' Hermes je chráněný paměťovou bránou; místní diagnostika pokračuje. Příčina spotřeby paměti není doložená.',
                'root_cause_proven': False,
                'needed': ['Aktuální dostupná paměť a statistiky spotřeby Core a běžících aplikací.',
                           'Nové měření po případném vlastníkem zvoleném uvolnění prostředků.'],
                'next_test_cs': 'HADS sám načte statistiky Core, Supervisora a běžících aplikací a porovná jejich spotřebu. '
                                'Výsledky doplní do tohoto spisu bez modelu a bez diagnostických příkazů od uživatele. '
                                'Případnou konkrétní opravu předloží samostatně ke schválení. Paměťová ochrana zůstává zachovaná.'}
    return None
