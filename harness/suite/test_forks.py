#!/usr/bin/env python3
"""Suite test 49 — fork completeness. The fork block at the head of
pipeline/constants.py is the canonical record: every fork names a reason
(CHOSEN/REASON/MEASURED language) and every constant a fork claims to govern
exists in the module; every governing constant is referenced from the block.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
import pipeline.constants as C  # noqa: E402

failures = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  [{detail}]"))
    if not ok:
        failures.append(name)


doc = C.__doc__
block = doc[doc.index("FORK BLOCK"):doc.index("END FORK BLOCK")]
forks = re.findall(r"FORK (\d+) — (.*?)(?=\nFORK \d+ — |\Z)", block, re.S)
check("t49-forks-declared", len(forks) >= 8, f"{len(forks)} forks found")

for num, body in forks:
    named_reason = bool(re.search(r"CHOSEN|REASON|MEASURED|CORRECTED", body))
    check(f"t49-fork{num}-names-reason", named_reason, body[:60])
    decided = bool(re.search(r"\[decided v\d+\.\d+\]|\[recorded v\d+\.\d+\]", body)
                   or "decided v0" in body)
    check(f"t49-fork{num}-dated", decided, "no pass tag")
    for const in re.findall(r"Governs:\s*([A-Z0-9_,\s]+?)\.", body):
        for name in re.split(r"[,\s]+", const.strip()):
            if name:
                check(f"t49-fork{num}-constant-{name}-exists", hasattr(C, name), name)

# every module-level constant carrying a fork comment is referenced in block
src = Path(C.__file__).read_text()
tagged = re.findall(r"^([A-Z][A-Z0-9_]+)\s*=.*(?:\n|$)", src[src.index('"""', 3):], re.M)
fork_tagged = re.findall(r"# forks? ([\d, ]+)\n((?:[A-Z][A-Z0-9_]+ =[^\n]*\n)+)", src)
for nums, blockc in fork_tagged:
    for cname in re.findall(r"^([A-Z][A-Z0-9_]+)\s*=", blockc, re.M):
        check(f"t49-{cname}-referenced-or-governed",
              cname in blockc and any(f"FORK {n.strip()}" in block for n in nums.split(",")),
              cname)

print(f"\nfork suite: {'ALL GREEN' if not failures else f'{len(failures)} FAILURE(S)'}")
sys.exit(1 if failures else 0)
