"""Actual pinned agent readiness without a model, HA connection or database.

The CLI is for isolated container acceptance. It starts the fixed helper before
dropping controller privileges and never enrols a synthetic owner or touches
/data. The web service uses the same check behind authenticated owner consent.
"""
import json
import os
import sys
import ctypes

from .hermes_runtime import BrokerSession
from .investigation import HERMES_REVISION


def probe_runtime(launcher,schemas):
    class Catalog:
        def schemas(self):return schemas
    def no_model(body):raise RuntimeError('runtime_probe_model_forbidden')
    with BrokerSession(None,None,Catalog(),no_model) as session:
        result=launcher.run(port=session.port,nonce=session.nonce,model='hads-runtime-probe',
            prompt='Kontrola runtime bez konverzace.',schemas=schemas,probe_only=True)
    return {**result,'broker_requests_rejected':len(session.failures)}


def verified_probe(result):
    return result.get('completed') is True and result.get('probe_only') is True and result.get('native_agent_loaded') is True \
        and result.get('isolation_verified') is True and result.get('uid')==65534 and result.get('model_calls')==0 \
        and result.get('revision')==HERMES_REVISION and result.get('broker_requests_rejected')==0


def main():
    if sys.argv[1:]!=['--self-check']:raise SystemExit('Použití: python -m hads_next.runtime_check --self-check')
    from .runtime_launcher import RuntimeLauncher
    launcher=RuntimeLauncher()
    try:
        if ctypes.CDLL(None).prctl(38,1,0,0,0)!=0:raise RuntimeError('controller_no_new_privileges_failed')
        os.setgroups([]);os.setresgid(65532,65532,65532);os.setresuid(65532,65532,65532)
        schema={'name':'hads_runtime_probe_note','description':'Kontrola bez modelu a dat domácnosti.',
            'parameters':{'type':'object','properties':{},'additionalProperties':False}}
        result=probe_runtime(launcher,[schema])
        report={'scope':'isolated_container_native_Hermes_readiness','live_haos':False,'ha_connected':False,
            'model_provider_configured':False,'controller_uid':os.geteuid(),'result':result,'passed':verified_probe(result)}
        print(json.dumps(report,ensure_ascii=False))
        return 0 if report['passed'] else 1
    finally:launcher.close()


if __name__=='__main__':raise SystemExit(main())
