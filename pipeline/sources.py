"""The single chokepoint through which the pipeline obtains external data.

Every pipeline module calls sources.require(name) and receives a verified local
path — or SourceUnavailable, which stops the pipeline and names the source and
the reason. There is no other way to read external data, which is what makes
the no-fallback policy structural rather than procedural: a module that wants
a substitute grid has nowhere to get one.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "pipeline" / "manifest.json"


class SourceUnavailable(RuntimeError):
    def __init__(self, name, reason):
        super().__init__(f"source '{name}' unavailable: {reason} — pipeline stops; no substitute is synthesised")
        self.source_name = name
        self.reason = reason


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest():
    return json.loads(MANIFEST.read_text())["sources"]


def require(name: str, extracted: bool = False) -> Path:
    """Return the verified local path for a manifest source.

    extracted=True returns the declared extracted member instead of the
    retrieval vehicle (e.g. the single MIST track inside its tarball).
    """
    entries = manifest()
    if name not in entries:
        raise SourceUnavailable(name, "no manifest entry")
    e = entries[name]
    key_path, key_sum = ("extracted_member", "extracted_sha256") if extracted else ("dest", "sha256")
    if key_path not in e:
        raise SourceUnavailable(name, f"manifest entry lacks '{key_path}'")
    p = ROOT / e[key_path]
    if not p.exists():
        raise SourceUnavailable(name, f"file absent: {e[key_path]} (run pipeline/acquire.py)")
    declared = e.get(key_sum, "")
    if declared in ("", "PENDING-PIN"):
        raise SourceUnavailable(name, "checksum not pinned in manifest")
    actual = _sha256(p)
    if actual != declared:
        raise SourceUnavailable(name, f"checksum mismatch: manifest {declared[:12]}… actual {actual[:12]}…")
    return p
