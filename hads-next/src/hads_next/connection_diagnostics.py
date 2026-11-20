"""Public, finite connection outcomes: never include endpoint paths or server prose."""


def connection_failure(error):
    status = getattr(error, 'status', None)
    reasons = {
        401: ('unauthorized', 'Server vyžaduje přihlášení. Pokud používá Bearer token, vlož jej pouze do soukromého pole Token. Je-li vyžadován OAuth, toto připojení jej zatím nepodporuje; HADS nepovažuje adresu callbacku za token.'),
        403: ('forbidden', 'Server přístup odmítl. Ověř jednorázově oprávnění diagnostického klienta na serveru; nevypínej jeho bezpečnostní zásady.'),
        404: ('endpoint_not_found', 'Na zadané adrese není MCP rozhraní. Zkontroluj cestu poskytovatele. Hamster používá /api/hamster_mcp.'),
        503: ('service_unavailable', 'Přístupová cesta vrátila HTTP 503. Může jít o server, proxy nebo vzdálený přístup. Identita ani katalog nebyly potvrzené; HADS pokračuje dostupnými nativními zdroji.'),
    }
    code, detail = reasons.get(status, ('read_failed', 'Konektor nepřečetl platný katalog nebo report. HADS zachová mezeru a pokračuje jinými dostupnými zdroji.'))
    return {'error_code': code, 'last_response_status': status,
            'last_error': detail, 'next_step_cs': detail}
