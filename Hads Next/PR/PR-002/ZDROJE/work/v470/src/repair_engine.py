from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import json
import os
import re
import shutil
import sqlite3
import time
import uuid
import urllib.parse
from pathlib import Path
from typing import Any, Callable


class RepairError(RuntimeError):
    """A repair was rejected or could not be completed safely."""


SECRET_KEY = re.compile(r"(?i)(password|passwd|token|secret|api[_-]?key|credential|private[_-]?key)")
SAFE_ADDON = re.compile(r"^[a-zA-Z0-9_\-]+$")
ALLOWED_ACTIONS = {"yaml_replace", "automation_update", "script_update", "addon_options", "addon_restart", "core_check", "core_restart", "recorder_purge"}


def executable_actions(actions: Any) -> bool:
    return isinstance(actions, list) and bool(actions) and all(isinstance(a, dict) and a.get("type") in ALLOWED_ACTIONS for a in actions) and any(a["type"] != "core_check" for a in actions)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json_hash(value: Any) -> str:
    return sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def mask_secrets(value: Any, key: str = "") -> Any:
    if SECRET_KEY.search(key):
        return "**REDACTED**"
    if isinstance(value, dict):
        return {str(k): mask_secrets(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [mask_secrets(v, key) for v in value]
    return value


class RepairEngine:
    """Allow-listed repair executor. It never invokes a shell or evaluates code."""

    def __init__(
        self,
        supervisor_request: Callable[..., Any],
        config_root: Callable[[], Path | None],
        private_root: Path,
        options: Callable[[], dict[str, Any]],
    ) -> None:
        self.supervisor_request = supervisor_request
        self.config_root = config_root
        self.private_root = private_root
        self.options = options

    def _safe_config_file(self, relative: str) -> Path:
        root = self.config_root()
        if root is None:
            raise RepairError("Konfigurační adresář Home Assistantu není připojený.")
        raw = str(relative or "").strip().replace("\\", "/")
        if raw.startswith("/") or ":" in raw or ".." in Path(raw).parts:
            raise RepairError("Je vyžadována relativní cesta uvnitř /config.")
        if not raw or raw.lower() == "secrets.yaml" or raw.lower().endswith("/secrets.yaml"):
            raise RepairError("Soubor secrets.yaml nelze číst ani měnit.")
        if not raw.lower().endswith((".yaml", ".yml")):
            raise RepairError("Opravný motor smí měnit pouze existující YAML/YML soubory.")
        root_real = root.resolve()
        unresolved = root_real / raw
        if any(part.is_symlink() for part in [unresolved, *unresolved.parents] if part != root_real):
            raise RepairError("Symbolické odkazy nelze měnit.")
        target = unresolved.resolve()
        try:
            target.relative_to(root_real)
        except ValueError as exc:
            raise RepairError("Cesta míří mimo /config.") from exc
        if not target.is_file() or target.is_symlink():
            raise RepairError("Cílový YAML soubor neexistuje nebo je symbolický odkaz.")
        return target

    def _addon(self, value: Any) -> str:
        slug = str(value or "").strip()
        if not SAFE_ADDON.fullmatch(slug) or slug in {"hads4", "local_hads4"}:
            raise RepairError("Neplatný nebo zakázaný slug doplňku.")
        return slug

    def _recorder_file(self) -> Path:
        # Explicit operator configuration is required: a leftover local SQLite
        # file must not be mistaken for an active external MariaDB database.
        configured = str(self.options().get("recorder_sqlite_path") or "").strip()
        root = self.config_root()
        if not self.options().get("recorder_maintenance_enabled", False) or not configured or root is None:
            raise RepairError("Údržba Recorderu vyžaduje povolení a potvrzenou cestu aktivní SQLite databáze v nastavení. Externí DB není podporována.")
        raw = configured.replace("\\", "/")
        if raw.startswith("/") or ":" in raw or ".." in Path(raw).parts or not raw.endswith(".db"):
            raise RepairError("Recorder vyžaduje relativní .db cestu uvnitř /config.")
        target = root.resolve() / raw
        if any(part.is_symlink() for part in [target, *target.parents] if part != root.resolve()):
            raise RepairError("Databáze nesmí být symbolický odkaz.")
        target.resolve().relative_to(root.resolve())
        if not target.is_file():
            raise RepairError("Potvrzená databáze Recorderu neexistuje.")
        return target

    def _snapshot_recorder(self, private: Path) -> dict[str, Any]:
        source = self._recorder_file()
        destination = private / "recorder-before.db"
        if destination.exists():
            raise RepairError("Databázová záloha tohoto plánu již existuje; nelze ji přepsat.")
        if shutil.disk_usage(private).free < max(source.stat().st_size * 2, 256_000_000):
            raise RepairError("Nedostatek místa pro konzistentní databázovou zálohu.")
        deadline = time.monotonic() + 180
        def progress(status: int, remaining: int, total: int) -> None:
            if time.monotonic() > deadline:
                raise RepairError("Databáze je vytížená; záloha překročila limit. Nic se nemaže.")
        src = sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)
        dst = sqlite3.connect(destination, timeout=10)
        try:
            src.backup(dst, pages=256, progress=progress, sleep=0.05)
            checked = dst.execute("PRAGMA quick_check").fetchall()
            if checked != [("ok",)]:
                raise RepairError("Kontrola konzistence databázové zálohy selhala.")
            tables = {row[0] for row in dst.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"states", "events"}.issubset(tables):
                raise RepairError("Soubor není rozpoznaná databáze Home Assistant Recorderu.")
        finally:
            src.close()
            dst.close()
        os.chmod(destination, 0o600)
        digest = hashlib.sha256()
        with destination.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return {"path": str(destination), "sha256": digest.hexdigest(), "quick_check": "ok", "source": str(source), "verified_at": utc_now()}

    def normalize_actions(self, actions: Any) -> list[dict[str, Any]]:
        if not isinstance(actions, list) or not actions:
            raise RepairError("Plán neobsahuje žádnou vykonatelnou akci.")
        if len(actions) > 12:
            raise RepairError("Jeden plán může obsahovat nejvýše 12 akcí.")
        normalized: list[dict[str, Any]] = []
        for index, raw in enumerate(actions, start=1):
            if not isinstance(raw, dict):
                raise RepairError(f"Akce {index} není objekt.")
            kind = str(raw.get("type") or "").strip()
            if kind not in ALLOWED_ACTIONS:
                raise RepairError(f"Akce {index}: typ {kind!r} není povolený.")
            if kind == "yaml_replace":
                target = self._safe_config_file(str(raw.get("path") or ""))
                before = str(raw.get("before") or "")
                after = str(raw.get("after") or "")
                if not before or before == after:
                    raise RepairError(f"Akce {index}: původní a nový text musí být rozdílné.")
                if len(before.encode()) > 512_000 or len(after.encode()) > 512_000:
                    raise RepairError(f"Akce {index}: změna je příliš velká.")
                content = target.read_text(encoding="utf-8")
                if content.count(before) != 1:
                    raise RepairError(f"Akce {index}: původní blok se v souboru nevyskytuje právě jednou.")
                current_hash = sha256_bytes(content.encode("utf-8"))
                expected = str(raw.get("expected_sha256") or "").strip()
                if expected and expected != current_hash:
                    raise RepairError(f"Akce {index}: soubor se od vytvoření plánu změnil.")
                normalized.append({
                    "type": kind,
                    "path": str(target.relative_to(self.config_root().resolve())).replace(os.sep, "/"),
                    "before": before,
                    "after": after,
                    "expected_sha256": current_hash,
                    "description": str(raw.get("description") or "Přesná náhrada v YAML")[:500],
                })
            elif kind in {"automation_update", "script_update"}:
                object_id = str(raw.get("automation_id") if kind == "automation_update" else raw.get("script_id") or "").strip()
                if not re.fullmatch(r"[a-zA-Z0-9_\-]+", object_id):
                    raise RepairError(f"Akce {index}: neplatné ID automatizace nebo skriptu.")
                before = raw.get("before")
                after = raw.get("after")
                if not isinstance(before, dict) or not isinstance(after, dict) or before == after:
                    raise RepairError(f"Akce {index}: předchozí a nový JSON musí být dva rozdílné objekty.")
                if len(json.dumps(after, ensure_ascii=False).encode()) > 1_000_000:
                    raise RepairError(f"Akce {index}: konfigurace je příliš velká.")
                expected = str(raw.get("expected_sha256") or canonical_json_hash(before))
                normalized.append({
                    "type": kind,
                    "automation_id" if kind == "automation_update" else "script_id": object_id,
                    "before": before,
                    "after": after,
                    "expected_sha256": expected,
                    "description": str(raw.get("description") or "Přesná aktualizace konfigurace přes Home Assistant API")[:500],
                })
            elif kind == "addon_options":
                slug = self._addon(raw.get("addon"))
                patch = raw.get("options_patch")
                if not isinstance(patch, dict) or not patch:
                    raise RepairError(f"Akce {index}: options_patch musí být neprázdný objekt.")
                if len(json.dumps(patch, ensure_ascii=False).encode()) > 256_000:
                    raise RepairError(f"Akce {index}: změna voleb doplňku je příliš velká.")
                info = self.supervisor_request(f"/addons/{slug}/info")
                before = info.get("options") if isinstance(info, dict) else None
                if not isinstance(before, dict):
                    raise RepairError("Nelze čerstvě načíst volby doplňku pro náhled.")
                expected = str(raw.get("expected_sha256") or canonical_json_hash(before))
                if expected != canonical_json_hash(before):
                    raise RepairError("Volby doplňku se od přípravy plánu změnily.")
                normalized.append({"type": kind, "addon": slug, "options_patch": patch, "before": before, "expected_sha256": expected, "restart": bool(raw.get("restart", False))})
            elif kind == "recorder_purge":
                self._recorder_file()
                if raw.get("database") and raw["database"] != self.options().get("recorder_sqlite_path"):
                    raise RepairError("Aktivní databáze se od přípravy plánu změnila. Vyžaduje nový plán.")
                keep_days = raw.get("keep_days")
                if type(keep_days) is not int or not 1 <= keep_days <= 3650:
                    raise RepairError("Recorder: počet zachovaných dnů musí být celé číslo 1–3650.")
                if len(actions) != 1:
                    raise RepairError("Údržba Recorderu musí být samostatný plán a samostatná dávka.")
                normalized.append({"type": kind, "keep_days": keep_days, "repack": False, "apply_filter": False,
                                   "database": str(self.options()["recorder_sqlite_path"]),
                                   "data_loss": f"Historie starší než {keep_days} dnů bude odstraněna. Dlouhodobé statistiky se touto akcí necílí. Obnova vyžaduje odstávku a zálohu."})
            elif kind == "addon_restart":
                normalized.append({"type": kind, "addon": self._addon(raw.get("addon"))})
            elif kind == "core_restart":
                if not self.options().get("allow_core_restart", False):
                    raise RepairError("Restart Home Assistant Core není v nastavení HADS 4 povolený.")
                normalized.append({"type": kind})
            else:
                normalized.append({"type": "core_check"})
        return normalized

    def preview(self, actions: Any) -> dict[str, Any]:
        normalized = self.normalize_actions(actions)
        risk = "low"
        previews: list[dict[str, Any]] = []
        for action in normalized:
            kind = action["type"]
            if kind == "yaml_replace":
                before_lines = action["before"].splitlines(keepends=True)
                after_lines = action["after"].splitlines(keepends=True)
                diff = "".join(difflib.unified_diff(before_lines, after_lines, fromfile=action["path"], tofile=action["path"] + " (návrh)", n=3))
                previews.append({"type": kind, "target": action["path"], "diff": diff[:80_000]})
                risk = "medium"
            elif kind in {"automation_update", "script_update"}:
                object_id = action.get("automation_id") or action.get("script_id")
                before_lines = json.dumps(action["before"], ensure_ascii=False, indent=2, sort_keys=True).splitlines(keepends=True)
                after_lines = json.dumps(action["after"], ensure_ascii=False, indent=2, sort_keys=True).splitlines(keepends=True)
                diff = "".join(difflib.unified_diff(before_lines, after_lines, fromfile=f"{kind}:{object_id}", tofile=f"{kind}:{object_id} (návrh)", n=3))
                previews.append({"type": kind, "target": object_id, "diff": diff[:80_000]})
                risk = "medium"
            elif kind == "addon_options":
                previews.append({"type": kind, "target": action["addon"], "changes": mask_secrets({"before": action["before"], "after": {**action["before"], **action["options_patch"]}})})
                risk = "high" if action.get("restart") else "medium"
            elif kind == "recorder_purge":
                previews.append({"type": kind, "target": action["database"], "changes": {"before": "Dosavadní historie", "after": f"Zachovat posledních {action['keep_days']} dnů"}, "warning": action["data_loss"]})
                risk = "high"
            elif kind in {"addon_restart", "core_restart"}:
                previews.append({"type": kind, "target": action.get("addon", "Home Assistant Core")})
                risk = "high"
            else:
                previews.append({"type": kind, "target": "Home Assistant Core"})
        for item in previews:
            item["backup"] = "Povinná nová plná HA záloha; nezávislá kontrola metadat Supervisoru. Obnovení není předem testováno."
            item["rollback"] = "Lokální obnova konfigurace, pokud se od zásahu nezměnila." if item["type"] in {"yaml_replace", "automation_update", "script_update", "addon_options"} else "Restart nelze vzít zpět; databázová obnova je ruční z ověřené zálohy při odstávce."
            item["verification"] = "Čerstvé čtení změněné konfigurace, Core check a následné sledování." if item["type"] in {"yaml_replace", "automation_update", "script_update", "addon_options"} else "Přijetí požadavku není důkaz opravy. Výsledek zůstane k následnému ověření."
        return {"actions": normalized, "risk_level": risk, "preview": previews}

    def _private_dir(self, plan_id: int) -> Path:
        root = self.private_root / f"plan_{plan_id:06d}"
        root.mkdir(parents=True, exist_ok=True, mode=0o700 if os.name != "nt" else 0o777)
        if os.name != "nt":
            os.chmod(root, 0o700)
        return root

    def _write_private_json(self, path: Path, value: Any) -> None:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(path, 0o600)

    def _create_backup(self, plan_id: int, actions: list[dict[str, Any]]) -> dict[str, Any]:
        name = f"HADS4 před opravou #{plan_id} {uuid.uuid4().hex[:12]}"
        payload: dict[str, Any] = {
            "name": name,
            "compressed": True,
            "background": False,
            "homeassistant_exclude_database": False,
        }
        created = self.supervisor_request("/backups/new/full", method="POST", body=payload, timeout=900)
        slug = str(created.get("slug") or "") if isinstance(created, dict) else ""
        if not re.fullmatch(r"[A-Za-z0-9_-]+", slug):
            raise RepairError("Supervisor nepotvrdil dokončenou zálohu identifikátorem. Žádný zásah nebude proveden.")
        info = self.supervisor_request(f"/backups/{slug}/info", timeout=60)
        if not isinstance(info, dict) or info.get("slug") != slug or info.get("name") != name or info.get("type") != "full" or not info.get("homeassistant") or info.get("homeassistant_exclude_database") is not False or float(info.get("size") or 0) <= 0:
            raise RepairError("Nezávislá kontrola nové plné zálohy včetně databáze selhala.")
        included = {item.get("slug") if isinstance(item, dict) else item for item in info.get("addons", [])}
        required = {a["addon"] for a in actions if a["type"] in {"addon_options", "addon_restart"}}
        if not required.issubset(included):
            raise RepairError("V záloze chybí dotčený doplněk.")
        return {"slug": slug, "name": name, "verified_at": utc_now(), "verification": "supervisor_metadata", "restore_tested": False, "type": "full", "database_included": True}

    @staticmethod
    def _check_result(result: Any, label: str) -> None:
        if not isinstance(result, dict):
            return
        state = str(result.get("result") or result.get("status") or "").lower()
        valid = result.get("valid")
        errors = result.get("errors")
        if state in {"invalid", "failed", "error"} or valid is False or errors:
            raise RepairError(f"{label} neprošla: {str(errors or result.get('message') or state)[:1200]}")

    def _atomic_replace(self, target: Path, text: str) -> None:
        tmp = target.with_name(f".{target.name}.hads4.tmp")
        mode = target.stat().st_mode
        with tmp.open("w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, target)

    def execute(self, plan_id: int, actions: Any) -> dict[str, Any]:
        normalized = self.normalize_actions(actions)
        cfg = self.options()
        private = self._private_dir(plan_id)
        state: dict[str, Any] = {"created_at": utc_now(), "files": {}, "objects": {}, "addons": {}, "actions": normalized, "backup": None}
        changes_system = any(action["type"] != "core_check" for action in normalized)
        if changes_system and not cfg.get("repairs_enabled", True):
            raise RepairError("Opravný motor je vypnutý.")
        if changes_system and not cfg.get("repair_mode_open", False):
            raise RepairError("Repair write gate je LOCKED. Zápis lze odemknout pouze ověřeným batch procesem po rescue uploadu.")
        if (private / "manifest.json").exists():
            raise RepairError("Tento plán již má manifest zásahu. Pro opakování vytvořte nový plán; původní zálohu nepřepisujte.")
        if changes_system:
            try:
                state["backup"] = self._create_backup(plan_id, normalized)
            except Exception as exc:
                raise RepairError(f"Předzásahovou zálohu se nepodařilo vytvořit a ověřit; oprava byla zastavena: {exc}") from exc
        # Preserve the backup receipt even if a later snapshot/preflight fails.
        self._write_private_json(private / "manifest.json", state)
        if any(a["type"] == "recorder_purge" for a in normalized):
            state["recorder_backup"] = self._snapshot_recorder(private)

        for action in normalized:
            if action["type"] == "yaml_replace":
                target = self._safe_config_file(action["path"])
                snapshot = private / ("file_" + hashlib.sha256(action["path"].encode()).hexdigest()[:16] + target.suffix)
                shutil.copy2(target, snapshot)
                os.chmod(snapshot, 0o600)
                state["files"][action["path"]] = str(snapshot)
                if sha256_bytes(snapshot.read_bytes()) != sha256_bytes(target.read_bytes()):
                    raise RepairError("Kopie původního souboru se neshoduje s originálem.")
            elif action["type"] in {"automation_update", "script_update"}:
                kind = "automation" if action["type"] == "automation_update" else "script"
                object_id = action.get(f"{kind}_id")
                endpoint = f"/core/api/config/{kind}/config/{urllib.parse.quote(str(object_id), safe='')}"
                current = self.supervisor_request(endpoint, timeout=60)
                if not isinstance(current, dict):
                    raise RepairError(f"Nelze načíst současnou konfiguraci {kind} {object_id}.")
                if canonical_json_hash(current) != action["expected_sha256"]:
                    raise RepairError(f"{kind.capitalize()} {object_id} se od vytvoření plánu změnil.")
                state["objects"][f"{kind}:{object_id}"] = current
            elif action["type"] == "addon_options" and action["addon"] not in state["addons"]:
                info = self.supervisor_request(f"/addons/{action['addon']}/info")
                if not isinstance(info, dict) or not isinstance(info.get("options"), dict):
                    raise RepairError(f"Nelze načíst současné volby doplňku {action['addon']}.")
                state["addons"][action["addon"]] = info["options"]
                if canonical_json_hash(info["options"]) != action["expected_sha256"]:
                    raise RepairError("Volby doplňku se během zálohování změnily.")
        self._write_private_json(private / "manifest.json", state)

        applied: list[str] = []
        try:
            for action in normalized:
                kind = action["type"]
                if kind == "yaml_replace":
                    target = self._safe_config_file(action["path"])
                    current = target.read_text(encoding="utf-8")
                    if sha256_bytes(current.encode()) != action["expected_sha256"] or current.count(action["before"]) != 1:
                        raise RepairError(f"Soubor {action['path']} se po schválení změnil; oprava byla zastavena.")
                    self._atomic_replace(target, current.replace(action["before"], action["after"], 1))
                    applied.append(f"yaml:{action['path']}")
                elif kind in {"automation_update", "script_update"}:
                    object_kind = "automation" if kind == "automation_update" else "script"
                    object_id = action.get(f"{object_kind}_id")
                    endpoint = f"/core/api/config/{object_kind}/config/{urllib.parse.quote(str(object_id), safe='')}"
                    current = self.supervisor_request(endpoint, timeout=60)
                    if not isinstance(current, dict) or canonical_json_hash(current) != action["expected_sha256"]:
                        raise RepairError(f"{object_kind.capitalize()} {object_id} se po schválení změnil; oprava byla zastavena.")
                    self.supervisor_request(endpoint, method="POST", body=action["after"], timeout=120)
                    applied.append(f"{object_kind}:{object_id}")
                    if canonical_json_hash(self.supervisor_request(endpoint, timeout=60)) != canonical_json_hash(action["after"]):
                        raise RepairError("Zpětné čtení změněné konfigurace nepotvrdilo požadovanou hodnotu.")
                elif kind == "addon_options":
                    original = state["addons"][action["addon"]]
                    live = self.supervisor_request(f"/addons/{action['addon']}/info")
                    if canonical_json_hash(live.get("options")) != action["expected_sha256"]:
                        raise RepairError("Volby doplňku se před zápisem změnily.")
                    merged = dict(original)
                    merged.update(action["options_patch"])
                    validation = self.supervisor_request(f"/addons/{action['addon']}/options/validate", method="POST", body=merged)
                    self._check_result(validation, f"Validace voleb doplňku {action['addon']}")
                    self.supervisor_request(f"/addons/{action['addon']}/options", method="POST", body={"options": merged})
                    applied.append(f"addon_options:{action['addon']}")
                    check = self.supervisor_request(f"/addons/{action['addon']}/info")
                    if canonical_json_hash(check.get("options")) != canonical_json_hash(merged):
                        raise RepairError("Zpětné čtení voleb doplňku nepotvrdilo změnu.")
                    if action.get("restart"):
                        self.supervisor_request(f"/addons/{action['addon']}/restart", method="POST", body={})
                        applied.append(f"addon_restart:{action['addon']}")
                elif kind == "addon_restart":
                    self.supervisor_request(f"/addons/{action['addon']}/restart", method="POST", body={})
                    applied.append(f"addon_restart:{action['addon']}")
                elif kind == "core_check":
                    result = self.supervisor_request("/core/check", method="POST", body={}, timeout=240)
                    self._check_result(result, "Kontrola konfigurace Home Assistantu")
                    applied.append("core_check")
                elif kind == "core_restart":
                    self.supervisor_request("/core/restart", method="POST", body={})
                    applied.append("core_restart")
                elif kind == "recorder_purge":
                    services = self.supervisor_request("/core/api/services")
                    if not any(isinstance(s, dict) and s.get("domain") == "recorder" and "purge" in s.get("services", {}) for s in services):
                        raise RepairError("Služba recorder.purge není aktuálně dostupná.")
                    self.supervisor_request("/core/api/services/recorder/purge", method="POST", body={"keep_days": action["keep_days"], "repack": False, "apply_filter": False}, timeout=120)
                    applied.append("recorder_purge_requested")

            if any(a["type"] in {"yaml_replace", "automation_update", "script_update"} for a in normalized):
                result = self.supervisor_request("/core/check", method="POST", body={}, timeout=240)
                self._check_result(result, "Kontrola konfigurace Home Assistantu po změně")
            return {
                "ok": True,
                "applied": applied,
                "backup": mask_secrets(state.get("backup")),
                "recorder_backup": state.get("recorder_backup"),
                "verification_pending": changes_system,
                "private_manifest": str(private / "manifest.json"),
                "finished_at": utc_now(),
            }
        except Exception as exc:
            rollback = self.rollback(plan_id, automatic=True) if applied else {"ok": True, "restored": []}
            raise RepairError(f"Oprava selhala: {exc}; lokální rollback={rollback.get('ok')}. Zkontrolujte manifest a skutečný stav; restart ani přijatý DB požadavek nelze automaticky vrátit.") from exc

    def recovery_receipt(self, plan_id: int) -> dict[str, Any]:
        path = self.private_root / f"plan_{plan_id:06d}" / "manifest.json"
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            return {"backup": mask_secrets(state.get("backup")), "private_manifest": str(path), "verification_pending": True}
        except (OSError, ValueError):
            return {}

    def rollback(self, plan_id: int, *, automatic: bool = False) -> dict[str, Any]:
        manifest_path = self._private_dir(plan_id) / "manifest.json"
        if not manifest_path.is_file():
            raise RepairError("Soukromý manifest rollbacku nebyl nalezen.")
        state = json.loads(manifest_path.read_text(encoding="utf-8"))
        if any(a.get("type") == "recorder_purge" for a in state.get("actions", [])):
            return {"ok": False, "errors": ["Databázi obnovte ručně při odstávce z recorder-before.db nebo plné HA zálohy. Živá DB se nepřepisuje."], "restored": []}
        if not automatic:
            state["before_manual_rollback"] = self._create_backup(plan_id, state.get("actions", []))
            self._write_private_json(manifest_path, state)
        restored: list[str] = []
        errors: list[str] = []
        for relative, snapshot_name in (state.get("files") or {}).items():
            try:
                target = self._safe_config_file(relative)
                snapshot = Path(snapshot_name)
                if not snapshot.is_file() or snapshot.parent != manifest_path.parent:
                    raise RepairError("Neplatná cesta snapshotu.")
                original = snapshot.read_text(encoding="utf-8")
                expected = original
                for action in state.get("actions", []):
                    if action.get("type") == "yaml_replace" and action.get("path") == relative:
                        expected = expected.replace(action["before"], action["after"], 1)
                current = target.read_text(encoding="utf-8")
                if current == original:
                    continue
                if current != expected:
                    raise RepairError("Soubor po opravě změnil někdo další. Automatický rollback by přepsal cizí změny.")
                tmp = target.with_name(f".{target.name}.hads4.rollback")
                shutil.copy2(snapshot, tmp)
                os.replace(tmp, target)
                restored.append(f"yaml:{relative}")
            except Exception as exc:
                errors.append(f"{relative}: {exc}")
        for slug, original in (state.get("addons") or {}).items():
            try:
                slug = self._addon(slug)
                expected = dict(original)
                for action in state.get("actions", []):
                    if action.get("type") == "addon_options" and action.get("addon") == slug:
                        expected.update(action["options_patch"])
                current = self.supervisor_request(f"/addons/{slug}/info").get("options")
                if current == original:
                    continue
                if current != expected:
                    raise RepairError("Volby doplňku se po opravě změnily; rollback vyžaduje nové rozhodnutí.")
                self.supervisor_request(f"/addons/{slug}/options", method="POST", body={"options": original})
                if any(a.get("addon") == slug and (a.get("restart") or a.get("type") == "addon_restart") for a in state.get("actions", [])):
                    self.supervisor_request(f"/addons/{slug}/restart", method="POST", body={})
                restored.append(f"addon_options:{slug}")
            except Exception as exc:
                errors.append(f"{slug}: {exc}")
        for key, original in (state.get("objects") or {}).items():
            try:
                kind, object_id = key.split(":", 1)
                endpoint = f"/core/api/config/{kind}/config/{urllib.parse.quote(object_id, safe='')}"
                expected = next((a["after"] for a in state.get("actions", []) if a.get(f"{kind}_id") == object_id), None)
                current = self.supervisor_request(endpoint, timeout=60)
                if current == original:
                    continue
                if current != expected:
                    raise RepairError("Konfigurace po opravě změněna; rollback odmítá přepsat novější stav.")
                self.supervisor_request(endpoint, method="POST", body=original, timeout=120)
                restored.append(key)
            except Exception as exc:
                errors.append(f"{key}: {exc}")
        if state.get("files") or state.get("objects"):
            try:
                result = self.supervisor_request("/core/check", method="POST", body={}, timeout=240)
                self._check_result(result, "Kontrola konfigurace po rollbacku")
            except Exception as exc:
                errors.append(f"core_check: {exc}")
        return {"ok": not errors, "restored": restored, "errors": errors, "finished_at": utc_now()}
