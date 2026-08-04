#!/usr/bin/env python3
"""Tier 3 — identity hashing of the Stage 0 output.

Every pass after the first must be mathematically identity by default: with its
new effect disabled, the Stage 0 output must hash bit-for-bit identical to the
previous pass's recorded hash. This converts "did I break anything" into one
number.

  identity.py record <label> <dir>    hash <dir>, store under <label>
  identity.py verify <label> <dir>    recompute and compare; exit 1 on mismatch
  identity.py diff   <label> <dir>    list files that differ from <label>

The canonical hash is SHA-256 over lines "relpath  sha256(file)\n" for every
regular file under <dir>, sorted by relpath. Byte-exact, order-independent.
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

STORE = Path(__file__).resolve().parent / "hashes.json"


def hash_dir(d):
    d = Path(d)
    files = {}
    for p in sorted(x for x in d.rglob("*") if x.is_file()):
        files[str(p.relative_to(d))] = hashlib.sha256(p.read_bytes()).hexdigest()
    combined = hashlib.sha256(
        "".join(f"{k}  {v}\n" for k, v in sorted(files.items())).encode()
    ).hexdigest()
    return combined, files


def load_store():
    return json.loads(STORE.read_text()) if STORE.exists() else {}


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    cmd, label, d = argv
    combined, files = hash_dir(d)
    store = load_store()
    if cmd == "record":
        store[label] = {
            "combined": combined,
            "recorded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "files": files,
        }
        STORE.write_text(json.dumps(store, indent=1, sort_keys=True))
        print(f"recorded {label}: {combined}")
        return 0
    if label not in store:
        print(f"no recorded hash under label '{label}'")
        return 1
    ref = store[label]
    if cmd == "verify":
        ok = ref["combined"] == combined
        print(f"{'IDENTITY' if ok else 'MISMATCH'}  {label}\n  recorded {ref['combined']}\n  current  {combined}")
        return 0 if ok else 1
    if cmd == "verify-prev":
        # identity-by-default across passes: every file recorded under the
        # label must be bit-identical NOW; files added since are permitted
        bad = [k for k, v in ref["files"].items() if files.get(k) != v]
        for k in bad:
            print(f"changed-or-removed: {k}")
        print(f"{'IDENTITY(prev-subset)' if not bad else 'MISMATCH'}  {label}"
              f"  ({len(ref['files'])} recorded, {len(bad)} broken)")
        return 0 if not bad else 1
    if cmd == "diff":
        a, b = ref["files"], files
        for k in sorted(set(a) | set(b)):
            if a.get(k) != b.get(k):
                tag = "changed" if k in a and k in b else ("removed" if k in a else "added")
                print(f"{tag:8s} {k}")
        return 0
    print(f"unknown subcommand: {cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
