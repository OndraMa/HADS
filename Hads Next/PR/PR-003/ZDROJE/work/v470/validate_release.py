"""Offline HADS 4.6.3 package verification; never contacts Home Assistant."""
import base64
import hashlib
import io
import json
import re
import tarfile
import zipfile
from pathlib import Path

import yaml
try:
    import tree_sitter_bash
    from tree_sitter import Language, Parser
except (ImportError, ModuleNotFoundError):
    tree_sitter_bash = None
    Language = Parser = None


VERSION = "4.7.0-rc3"
here = Path(__file__).resolve().parent
source = here / "src"
outputs = here.parents[1] / "outputs"
installer_path = outputs / f"HADS4_install_{VERSION}.sh"
script = installer_path.read_bytes()
assert not script.startswith(b"\xef\xbb\xbf") and b"\r" not in script
bash_parse = "not_available_on_python_3.14"
if Parser is not None:
    tree = Parser(Language(tree_sitter_bash.language())).parse(script)
    assert not tree.root_node.has_error, "Bash parse error"
    bash_parse = "passed"
inline_python = list(re.finditer(rb"<<'PY'\n(.*?)\nPY(?:\n|$)", script, re.S))
for index, match in enumerate(inline_python):
    compile(match.group(1), f"installer-inline-{index}.py", "exec")


class UniqueLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        keys = [self.construct_object(key, deep=deep) for key, _ in node.value]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate YAML mapping key")
        return super().construct_mapping(node, deep=deep)


config = yaml.load((source / "config.yaml").read_text(encoding="utf-8"), Loader=UniqueLoader)
assert config["version"] == VERSION
assert set(config["options"]) == set(config["schema"])
for path in (source / "translations").glob("*.yaml"):
    yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueLoader)
yaml.load((source / "dashboard/hads4_dashboard_card.yaml").read_text(encoding="utf-8"), Loader=UniqueLoader)
modules = list(source.glob("*.py"))
for path in modules:
    compile(path.read_bytes(), str(path), "exec")

encoded_match = re.search(rb"<<'HADS4_PAYLOAD'\n(.*?)\nHADS4_PAYLOAD", script, re.S)
assert encoded_match
payload = base64.b64decode(encoded_match.group(1))
digest = hashlib.sha256(payload).hexdigest()
expected = re.search(rb'EXPECTED_SHA256="([0-9a-f]{64})"', script).group(1).decode()
assert digest == expected
with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
    files = [member for member in archive.getmembers() if member.isfile()]
    for member in archive.getmembers():
        assert not member.issym() and not member.islnk()
        assert not member.name.startswith("/") and ".." not in Path(member.name).parts
    for member in files:
        assert archive.extractfile(member).read() == (source / member.name).read_bytes(), member.name
with zipfile.ZipFile(outputs / f"HADS4_{VERSION}-source.zip") as archive:
    zipped = [name for name in archive.namelist() if not name.endswith("/")]
    for name in zipped:
        assert archive.read(name) == (source / name).read_bytes(), name
assert {member.name for member in files} == set(zipped)
with zipfile.ZipFile(outputs / "HADS_Rescue_Readback_0.1.0.zip") as archive:
    for name in archive.namelist():
        assert not name.startswith("/") and ".." not in Path(name).parts
        assert archive.read(name) == (source / "companion" / name).read_bytes()
    assert "custom_components/hads_rescue/manifest.json" in archive.namelist()
manifest = json.loads((source / "companion/custom_components/hads_rescue/manifest.json").read_text(encoding="utf-8"))
assert manifest["domain"] == "hads_rescue" and manifest["version"] == "0.1.0"
yaml.load((source / "companion/custom_components/hads_rescue/services.yaml").read_text(encoding="utf-8"), Loader=UniqueLoader)

verification_path = outputs / f"HADS4_{VERSION}-verification.json"
previous = json.loads(verification_path.read_text(encoding="utf-8"))
assert previous["installer_payload_sha256"] == digest, "Tested payload differs from release"
result = {
    **previous,
    "version": VERSION,
    "bash_tree_sitter_parse": bash_parse,
    "embedded_python_blocks": len(inline_python),
    "embedded_python": "passed",
    "yaml_and_unique_keys": "passed",
    "python_compileall": "passed",
    "python_modules": len(modules),
    "payload_sha256": digest,
    "payload_files": len(files),
    "source_files": len(zipped),
    "source_payload_match": "passed",
    "excluded_from_package": ["__pycache__", "*.pyc", ".test-tmp"],
    "real_haos_install": "not_tested",
    "real_browser_ingress": "not_tested",
    "restore_test": "not_tested",
    "companion_package_source_match": "passed",
    "companion_core_setup_and_cloud_readback": "not_tested",
}
(outputs / f"HADS4_{VERSION}-verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
