"""Deterministic explanations of native diagnostics, with no repair authority."""
import re

MIB = 1024 * 1024
_IDENTIFIER = re.compile(r'[a-z0-9_]{1,80}')
# Persist diagnostic codes, never arbitrary remote messages, URLs or headers.
_ERROR_CODES = {'unreachable', 'timeout', 'unknown', 'cannot_connect', 'cannot_resolve'}


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
        return {'summary_cs': summary, 'root_cause_proven': False,
                'needed': ['Nové čtení stejné kontroly a její chybový kód.',
                           'Při opakování časově související protokol integrace; odlišit DNS, spojení, TLS a odpověď serveru.'],
                'next_test_cs': 'Zopakuj nativní diagnostiku tlačítkem níže. Pokud chyba trvá, zkontroluj protokol integrace '
                                + name + ' ve stejném čase. Úspěch v prohlížeči Windows neověřuje přístup z HAOS. '
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
                'next_test_cs': 'Obnov nativní diagnostiku. Ve Zdroje a připravenost ověř aktuální paměť. '
                                'Spotřebu konkrétní aplikace přečti přes Vyšetřit konkrétní aplikaci HAOS. '
                                'Aplikace automaticky nezastavuji. Až bude rezerva splněná i s provozní rezervou, '
                                'použij Ověřit Hermes bez volání modelu. Paměťovou ochranu nesnižuj.'}
    return None
