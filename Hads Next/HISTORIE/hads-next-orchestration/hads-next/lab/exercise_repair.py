"""Real Core repair acceptance, using genuine services and event contexts."""
import asyncio
import json
from pathlib import Path
import time

from homeassistant.helpers import entity_registry
from hads_next.evidence import IncidentStore
from hads_next.repair import ApprovalAuthority, RepairBlocked
from hads_next.verification import FunctionalVerifier
from core_repair import CoreLabRepairEngine


async def exercise(hass, path, nonce, token, user, client, trace, **readers):
    base = 'http://127.0.0.1:8123'
    root = Path(path) / 'hads-authority'
    root.mkdir(mode=0o700)
    db = root / 'case.sqlite3'
    engine = await asyncio.to_thread(CoreLabRepairEngine, db, root, nonce=nonce, token=token, owner=user.id)
    store = IncidentStore(db)
    case = store.open_incident('automation_reference', 'Po stisku testovacího tlačítka se virtuální cíl nezapne.',
        ['automation.hads_lab_reference', engine.TARGET], time.time())
    original = json.loads(await asyncio.to_thread(engine._read, engine.FILENAME))
    store.add_evidence(case['id'], {'source': 'actual_core_config_api', 'kind': 'automation_config',
        'observed_at': time.time(), 'payload': original})
    store.add_evidence(case['id'], {'source': 'actual_core_trace_api', 'kind': 'automation_trace',
        'observed_at': time.time(), 'payload': trace})
    state = hass.states.get(engine.TARGET)
    assert state is not None and state.state == 'off'
    assert hass.states.get(engine.MISSING) is None
    store.add_evidence(case['id'], {'source': 'actual_core_state_machine', 'kind': 'state',
        'observed_at': state.last_updated.timestamp(), 'payload': {'entity_id': state.entity_id, 'state': state.state}})
    evidence_ids = [row['evidence_id'] for row in store.case(case['id'])['evidence']]
    plan = await asyncio.to_thread(engine.prepare_entity_reference, case['id'], engine.FILENAME,
        engine.MISSING, engine.TARGET, evidence_ids,
        'Skutečný Core přijal spouštěcí událost, ale cílový odkaz neexistuje; dostupný virtuální cíl zůstal vypnutý.',
        watch_seconds=2)
    store.record(case['id'], 'repair_plan', plan.document)
    before = (Path(path) / 'automations.yaml').read_bytes()
    try:
        await asyncio.to_thread(engine.prepare_entity_reference, case['id'], engine.FILENAME,
            engine.MISSING, 'light.production', evidence_ids, 'Forbidden non-lab target')
    except RepairBlocked:
        pass
    else:
        raise AssertionError('A non-lab entity was admitted into the catalog')
    for principal in (user.id, 'untrusted-agent'):
        try:
            await asyncio.to_thread(engine.execute, plan, 'not-an-approval', principal=principal)
        except RepairBlocked:
            pass
        else:
            raise AssertionError('Unauthorized actual Core write was allowed')
    assert (Path(path) / 'automations.yaml').read_bytes() == before
    authority = ApprovalAuthority(db, owner=user.id)
    # Test E: a simulated operator decision, not a claim of human UI approval.
    approval = authority.approve(plan, principal=user.id)
    store.record(case['id'], 'user_decision', {'decision': 'approve', 'plan_id': plan.plan_id,
        'principal': user.id, 'scope': 'simulated_operator_in_disconnected_core_lab'})
    execution = await asyncio.to_thread(engine.execute, plan, approval, principal=user.id)
    assert execution.status == 'applied_verification_pending'
    await hass.async_block_till_done()
    assert json.loads(await asyncio.to_thread(engine._read, engine.FILENAME)) == plan.document['proposed']
    # Reconstruct executor to exercise durable replay protection across restart.
    restarted = await asyncio.to_thread(CoreLabRepairEngine, db, root, nonce=nonce, token=token, owner=user.id)
    try:
        await asyncio.to_thread(restarted.execute, plan, approval, principal=user.id)
    except RepairBlocked:
        pass
    else:
        raise AssertionError('Restart permitted duplicate execution')
    verifier = FunctionalVerifier(db)
    pending = verifier.evaluate(plan, execution, [])
    assert pending['classification'] == 'Není dostatek důkazů'
    registry = entity_registry.async_get(hass)
    automation_entity = registry.async_get_entity_id('automation', 'automation', 'hads_lab_reference')
    assert automation_entity and hass.states.get(automation_entity).state == 'on'
    observations = []
    since = time.time()

    def on_event(event):
        if event.event_type == 'automation_triggered' and event.data.get('entity_id') == automation_entity:
            observations.append({'kind': 'automation_triggered', 'observed_at': event.time_fired.timestamp(),
                'payload': {'automation_id': 'hads_lab_reference', 'context_id': event.context.id}})
        if event.event_type == 'state_changed' and event.data.get('entity_id') == engine.TARGET:
            new = event.data.get('new_state')
            observations.append({'kind': 'target_state' if new is not None and new.state == 'on' else 'functional_failure',
                'observed_at': event.time_fired.timestamp(), 'payload': {'entity_id': engine.TARGET,
                    'state': new.state if new is not None else 'missing', 'context_id': event.context.id}})

    unsubscribe = [hass.bus.async_listen(kind, on_event) for kind in ('automation_triggered', 'state_changed')]
    try:
        async with client.post(base + '/api/services/input_button/press', json={'entity_id': 'input_button.hads_lab_run'}) as r:
            assert r.status == 200
        await hass.async_block_till_done()
        assert hass.states.get(engine.TARGET).state == 'on'
        first = verifier.evaluate(plan, execution, observations)
        assert first['classification'] == 'Oprava provedena, ověření čeká'
        # Actual elapsed time under an active bus listener, no simulated clock.
        watch_started = time.monotonic()
        await asyncio.sleep(plan.document['verification']['watch_seconds'] + 0.1)
        assert time.monotonic() - watch_started >= 2
        assert hass.states.get(engine.TARGET).state == 'on'
        observations.append({'kind': 'monitoring_checkpoint', 'observed_at': time.time(),
            'payload': {'entity_id': engine.TARGET, 'continuous_since': since, 'healthy': True}})
        report = verifier.evaluate(plan, execution, observations)
        assert report['classification'] == 'Vyřešeno a ověřeno', report
        assert report['scope'] == 'actual_core_container'
        store.mark_resolved(case['id'], report)
        assert IncidentStore(db).case(case['id'])['incident']['status'] == 'resolved'
        # A real virtual service injects a functional regression. Its actual
        # state_changed event must reopen the case, even if later calls omit it.
        async with client.post(base + '/api/services/input_boolean/turn_off', json={'entity_id': engine.TARGET}) as r:
            assert r.status == 200
        await hass.async_block_till_done()
        recurrence = verifier.evaluate(plan, execution, observations)
        assert recurrence['classification'] == 'Problém se opakoval'
        store.reopen_for_report(case['id'], recurrence)
        assert IncidentStore(db).case(case['id'])['incident']['status'] == 'open'
        assert verifier.evaluate(plan, execution, [])['classification'] == 'Problém se opakoval'
    finally:
        for stop in unsubscribe:
            stop()
    # Returning raw tokens or session objects is forbidden.
    return {'operation': plan.document['operation'], 'plan': plan.document, 'report': report,
        'case_persisted_and_closed': True, 'injected_functional_recurrence': recurrence,
        'case_reopened_on_actual_functional_recurrence': True,
        'actual_automation_service_executed': True, 'unauthorized_write_rejected': True,
        'non_virtual_repair_target_rejected': True,
        'duplicate_execution_after_executor_restart_rejected': True,
        'http_success_alone_did_not_close_repair': True, 'approval': 'simulated_local_operator',
        'hermes_in_this_test': False, 'physical_device_tested': False}
