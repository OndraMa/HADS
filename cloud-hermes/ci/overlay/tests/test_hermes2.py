import json
import os
from pathlib import Path
import unittest
from unittest import mock
import urllib.request
import urllib.error

import hermes_bridge as h
from hermes_upstream_smoke import body


def response(envelope):
    return {"id": "fake", "status": "completed", "usage": {"input_tokens": 100, "output_tokens": 30},
            "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(envelope)}]}]}


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.body = body()
        self.body["tool_choice"] = "auto"
        self.body["tools"] = [{"type": "function", "name": "hads_get_live_state", "parameters": {
            "type": "object", "additionalProperties": False, "properties": {"entity_id": {"type": "string"}}, "required": ["entity_id"]}}]

    def envelope(self, name="hads_get_live_state", arguments=None):
        return {"read_requests": [{"name": name, "arguments_json": json.dumps(arguments or {"entity_id": "light.lamp"})}], "analysis": None}

    def test_valid_read_becomes_parent_function_call_not_execution(self):
        result = h.translate_result(response(self.envelope()), self.body)
        self.assertEqual("function_call", result["output"][0]["type"])
        self.assertEqual("light.lamp", json.loads(result["output"][0]["arguments"])["entity_id"])
        self.assertEqual(100, result["usage"]["input_tokens"])

    def test_arbitrary_execution_and_generic_dispatch_are_rejected(self):
        for name in ("terminal", "execute_code", "ha_call_tool", "ha_set_state", "approve", "write_file", "hads_launch_repairs"):
            with self.subTest(name=name), self.assertRaises(h.HermesError):
                h.validate_envelope(self.envelope(name), self.body)

    def test_unknown_arguments_are_rejected(self):
        with self.assertRaises(Exception):
            h.validate_envelope(self.envelope(arguments={"entity_id": "light.lamp", "service": "turn_on"}), self.body)

    def test_duplicate_reads_are_rejected_before_execution(self):
        value = self.envelope()
        value["read_requests"] *= 2
        with self.assertRaises(h.HermesError):
            h.validate_envelope(value, self.body)

    def test_final_step_cannot_request_reads(self):
        self.body["tool_choice"] = "none"
        with self.assertRaises(h.HermesError):
            h.validate_envelope(self.envelope(), self.body)

    def test_no_ambiguous_analysis_and_reads(self):
        value = self.envelope()
        value["analysis"] = {"summary": "Provedl jsem opravu"}
        with self.assertRaises(h.HermesError):
            h.validate_envelope(value, self.body)

    def test_empty_envelope_does_not_claim_success(self):
        with self.assertRaises(h.HermesError):
            h.validate_envelope({"read_requests": [], "analysis": None}, self.body)

    def test_summary_schema_is_validated(self):
        with self.assertRaises(Exception):
            h.validate_envelope({"read_requests": [], "analysis": {"summary": 5}}, self.body)

    def test_receipt_preserves_usage_and_real_citations(self):
        original = response({"read_requests": [], "analysis": {"summary": "Příčina neznámá"}})
        original["output"].insert(0, {"type": "web_search_call", "action": {"sources": [{"url": "https://example.test"}]}})
        result = h.translate_result(original, self.body)
        self.assertEqual(original["usage"], result["usage"])
        self.assertEqual("web_search_call", result["output"][0]["type"])

    def test_no_secrets_in_worker_environment(self):
        with mock.patch.dict(os.environ, {"SUPERVISOR_TOKEN": "secret", "OPENAI_API_KEY": "secret", "HERMES_HOME": "untrusted", "PYTHONPATH": "untrusted"}):
            env = h.worker_environment(Path("isolated"))
        self.assertNotIn("SUPERVISOR_TOKEN", env)
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertEqual("/tmp/isolated", env["HERMES_HOME"])
        self.assertEqual("/opt/hermes", env["PYTHONPATH"])

    def test_model_route_cannot_change_model_or_add_tools(self):
        result = h.model_body(self.body, [{"role": "user", "content": "Read logs"}])
        self.assertEqual(self.body["model"], result["model"])
        self.assertFalse(result["tools"])
        self.assertFalse(result["store"])
        self.assertNotIn("prompt_cache_options", result)

    def test_nontext_context_and_tool_role_are_rejected(self):
        for message in ({"role": "tool", "content": "x"}, {"role": "user", "content": [{"image_url": "secret"}]}):
            with self.assertRaises(h.HermesError):
                h.model_body(self.body, [message])

    def test_broker_enforces_one_upstream_request_and_authentication(self):
        sent = []
        def send(request):
            sent.append(request)
            return response({"read_requests": [], "analysis": {"summary": "Nevím"}})
        with h.Broker(self.body, send) as broker:
            url = f"http://127.0.0.1:{broker.server.server_port}/v1/chat/completions"
            data = json.dumps({"messages": [{"role": "user", "content": "diagnose"}], "stream": False}).encode()
            def call(token):
                return urllib.request.urlopen(urllib.request.Request(url, data=data, headers={"Authorization": "Bearer " + token}), timeout=3)
            with self.assertRaises(urllib.error.HTTPError):
                call("wrong")
            self.assertEqual([], sent)
            with call(broker.token) as reply:
                self.assertEqual(200, reply.status)
            with self.assertRaises(urllib.error.HTTPError):
                call(broker.token)
            self.assertEqual(1, len(sent))

    def test_worker_has_no_native_tools_and_mandatory_isolation(self):
        source = Path(h.__file__).with_name("hermes_worker.py").read_text()
        self.assertIn("enabled_toolsets=[]", source)
        self.assertIn("if agent.tools:", source)
        self.assertIn('confine(os.environ["HERMES_HOME"]', source)
        docker = Path(h.__file__).with_name("Dockerfile").read_text()
        self.assertIn(h.REVISION, docker)
        self.assertIn("RUN python /app/hermes_upstream_smoke.py", docker)
        isolation = Path(h.__file__).with_name("hermes_sandbox.py").read_text()
        self.assertIn('os.chroot(ROOT)', isolation)
        self.assertIn('seccomp_filter()', isolation)

    def test_isolation_rejects_unsupported_os(self):
        import hermes_sandbox
        with mock.patch.object(hermes_sandbox.sys, "platform", "win32"):
            with self.assertRaises(RuntimeError):
                hermes_sandbox.confine("/tmp/hads-hermes-test", 1234)

    def test_unknown_or_low_memory_prevents_reasoning(self):
        for available in (None, 0, 576 * 1048576 - 1):
            with self.assertRaises(h.runtime_core.ResourceDeferred):
                h.require_resources(lambda: {"available_bytes": available})
        h.require_resources(lambda: {"available_bytes": 576 * 1048576})

    def test_streaming_is_one_metered_request(self):
        sent = []
        def send(request):
            sent.append(request)
            return response({"read_requests": [], "analysis": {"summary": "Nevím"}})
        with h.Broker(self.body, send) as broker:
            url = f"http://127.0.0.1:{broker.server.server_port}/v1/chat/completions"
            request = urllib.request.Request(url, data=json.dumps({"messages": [{"role": "user", "content": "diagnose"}], "stream": True}).encode(),
                headers={"Authorization": "Bearer " + broker.token})
            with urllib.request.urlopen(request, timeout=3) as reply:
                self.assertEqual("text/event-stream", reply.headers.get("Content-Type"))
                raw = reply.read().decode()
        self.assertIn("chat.completion.chunk", raw)
        self.assertIn("data: [DONE]", raw)
        self.assertEqual(1, len(sent))

    def test_text_blocks_are_supported_without_images(self):
        request = h.model_body(self.body, [{"role": "user", "content": [{"type": "text", "text": "read only"}]}])
        self.assertEqual("read only", request["input"][0]["content"])

    def test_large_context_is_explicitly_incomplete_not_silently_trusted(self):
        self.body["input"] = [{"role": "user", "content": "š" * 30000}]
        prompt = h.reasoning_prompt(self.body)
        self.assertLess(len(prompt.encode()), 20000)
        self.assertIn("preview_only", prompt)
        self.assertIn("chybějící část není důkaz zdraví", prompt)

    def test_cooldown_blocks_worker_and_model_calls(self):
        with mock.patch.object(h, "status", return_value={"retry_at": h.time.time() + 300, "last_error": "Bootstrap selhal"}), \
             mock.patch.object(h.subprocess, "Popen") as process:
            with self.assertRaises(h.HermesError) as error:
                h.run_step(self.body, mock.Mock())
        self.assertIn("další pokus nejdříve", str(error.exception))
        process.assert_not_called()

    def test_installer_preflight_rejects_windows_before_any_changes(self):
        import hermes_preflight
        with mock.patch.object(hermes_preflight.sys, "platform", "win32"):
            with self.assertRaises(RuntimeError):
                hermes_preflight.check()


import hads4
import test_rc8_regressions as legacy


class WorkflowTests(unittest.TestCase):
    setUp = legacy.RC8RegressionTests.setUp
    tearDown = legacy.RC8RegressionTests.tearDown

    def config(self):
        return {"hermes_enabled": True, "openai_enabled": True, "openai_api_key": "fake-not-a-key",
                "ai_paid_calls_enabled": True, "ai_daily_call_limit": 6, "ai_case_daily_call_limit": 2,
                "ai_tool_max_rounds": 3, "openai_web_search_enabled": False, "ai_prompt_cache_mode": "implicit"}

    def test_hermes_reads_then_synthesizes_with_two_persistent_receipts(self):
        case, _, _ = legacy.RC8RegressionTests._case_and_plan(self)
        analysis = {"summary": "Lampa nyní odpovídá; původ včerejšího selhání není potvrzen.",
                    "functional_impact": "Historické selhání automatizace vyžaduje trace.",
                    "decision_kind": "investigate", "user_question": {"question": "", "why_readonly_cannot_answer": ""},
                    "hypotheses": [], "missing_evidence": ["historická trace"], "next_test": "Načíst trace z času incidentu.",
                    "proposed_actions": [], "configuration_changes": []}
        envelopes = [
            {"read_requests": [{"name": "hads_get_live_state", "arguments_json": '{"entity_id":"light.lamp"}'}], "analysis": None},
            {"read_requests": [], "analysis": analysis}]
        sent = []
        def model(key, request):
            self.assertEqual("fake-not-a-key", key)
            sent.append(request)
            return response(envelopes[len(sent) - 1])
        def step(request, send):
            # Exercise real broker conversion/metering/validation and parent
            # read dispatch, but not Linux/Hermes installation in this test.
            value = send(h.model_body(request, [{"role": "user", "content": h.reasoning_prompt(request)}]))
            return h.translate_result(value, request)
        with mock.patch.object(hads4, "options", return_value=self.config()), \
             mock.patch.object(h, "require_resources"), mock.patch.object(h, "run_step", side_effect=step), \
             mock.patch.object(hads4, "_openai_post", side_effect=model), \
             mock.patch.object(hads4, "supervisor_request", return_value={"entity_id": "light.lamp", "state": "on"}) as reads:
            result = hads4.research_case(case, {})
        self.assertEqual(2, len(sent))
        self.assertEqual(1, result["tool_calls"])
        self.assertEqual([], result["analysis"]["configuration_changes"])
        self.assertIn("hads_get_live_state", json.dumps(sent[1], ensure_ascii=False))
        with hads4.db() as conn:
            self.assertEqual(2, conn.execute("SELECT count(*) FROM ai_calls WHERE case_id=?", (case,)).fetchone()[0])
            self.assertEqual("hermes_officer", conn.execute("SELECT provider FROM research_runs ORDER BY id DESC LIMIT 1").fetchone()[0])
        self.assertTrue(any("/core/api/states/light.lamp" in str(c) for c in reads.call_args_list))
        self.assertFalse(any(c.kwargs.get("method") in {"POST", "PUT", "DELETE", "PATCH"} for c in reads.call_args_list))

    def test_hermes_failure_does_not_fall_back_to_another_paid_engine(self):
        case, _, _ = legacy.RC8RegressionTests._case_and_plan(self)
        with mock.patch.object(hads4, "options", return_value=self.config()), \
             mock.patch.object(h, "require_resources"), \
             mock.patch.object(h, "run_step", side_effect=h.HermesError("Bezpečná izolace není dostupná.")), \
             mock.patch.object(hads4, "_openai_post") as paid:
            with self.assertRaises(h.HermesError):
                hads4.research_case(case, {})
        paid.assert_not_called()
        with hads4.db() as conn:
            self.assertEqual("failed", conn.execute("SELECT status FROM research_runs ORDER BY id DESC LIMIT 1").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
