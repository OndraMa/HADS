"""Real pinned Hermes + kernel-enforced sandbox + fake local model. No API keys."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hermes_bridge as bridge


def body():
    return {"model": "hads-offline-test-model", "input": [{"role": "user", "content": "Lampička reaguje přes HTTP; MQTT není nastavené."}],
            "instructions": "Neprováděj změny. Rozliš příčinu a symptom.", "tool_choice": "none", "tools": [],
            "text": {"format": {"schema": {"type": "object", "additionalProperties": False,
                    "properties": {"summary": {"type": "string"}}, "required": ["summary"]}}}}


def main():
    calls = []
    def model(request):
        assert request["model"] == "hads-offline-test-model"
        assert not request["tools"]
        assert "Lampička" in json.dumps(request, ensure_ascii=False)
        calls.append(request)
        text = json.dumps({"read_requests": [], "analysis": {"summary": "Funkční HTTP není výpadek lampy."}})
        return {"id": "offline", "status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}]}
    result = bridge.run_step(body(), model, timeout=90)
    assert len(calls) == 1
    assert result["hads_engine"] == "hermes"
    assert "Funkční HTTP" in bridge._text(result)
    assert bridge.status()["last_isolation_verified"] is True
    import resource
    info = {"sandbox": bridge.status()['isolation'], "worker_peak_rss_bytes": bridge.status()['worker_peak_rss_bytes'],
            "parent_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}
    for name in ('memory.peak', 'memory.max', 'memory.events'):
        path = Path('/sys/fs/cgroup') / name
        if path.is_file():
            info[name] = path.read_text().strip()
    print(json.dumps(info, sort_keys=True))
    print("Real pinned Hermes + one model call + chroot/UID/seccomp: passed (fake model, no paid API)")


if __name__ == "__main__":
    main()
