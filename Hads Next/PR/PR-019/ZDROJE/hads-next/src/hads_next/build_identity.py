"""Read the packaged source identity once; a version string alone is not provenance."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

VERSION = '1.0.0-rc10'


def inspect_build(package):
    package = Path(package)
    result = {'version': VERSION, 'source_commit': None, 'build_id': None,
              'source_verified': False, 'channel': 'acceptance_candidate'}
    try:
        manifest = package.parent / 'PACKAGE_MANIFEST.json'
        if manifest.is_symlink() or manifest.stat().st_size > 262144:
            return result
        value = json.loads(manifest.read_text())
        source, build = value['source_revision_at_build'], value['build_id']
        if (value['version'] != VERSION or value['slug'] != 'hads_next_practical'
                or value['worktree_modified_at_build'] is not False
                or not re.fullmatch('[a-f0-9]{40}', source)
                or not re.fullmatch('[a-f0-9]{64}', build)):
            return result
        expected = {k.split('/', 1)[1]: v['sha256'] for k, v in value['files'].items()
                    if k.startswith('hads_next/') and k.endswith('.py')}
        actual = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in package.glob('*.py') if p.is_file() and not p.is_symlink()}
        if not expected or actual != expected:
            return result
        return {**result, 'source_commit': source, 'build_id': build, 'source_verified': True}
    except (OSError, ValueError, TypeError, KeyError):
        return result


@lru_cache(maxsize=1)
def current_build():
    return inspect_build(Path(__file__).parent)


def invalidate_previous_approvals(app):
    """Retain plans and decisions as history, expire unused approvals on image change."""
    build = current_build()
    if not build['source_verified']:
        return
    with app.store._connect() as db:
        db.execute('BEGIN IMMEDIATE')
        old = db.execute("SELECT value FROM application_settings WHERE key='approval_build'").fetchone()
        if not old or old[0] != build['build_id']:
            db.execute("UPDATE repair_decisions SET expires_at=min(expires_at,?) WHERE decision='approve' AND consumed_at IS NULL", (app.clock(),))
            db.execute("INSERT OR REPLACE INTO application_settings VALUES('approval_build',?)", (build['build_id'],))
