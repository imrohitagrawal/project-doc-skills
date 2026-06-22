#!/usr/bin/env python3
"""validate_skill.py — checks a skill folder against the platform's upload rules
(mirrors skill-creator/quick_validate.py) so build-skills.sh fails BEFORE producing
an invalid .skill. Usage: python3 validate_skill.py <skill-folder>"""
from __future__ import annotations
import re, sys
from pathlib import Path
try:
    import yaml
except Exception:
    print("WARN: PyYAML not installed; frontmatter not fully validated"); sys.exit(0)

ALLOWED = {'name', 'description', 'license', 'allowed-tools', 'metadata', 'compatibility'}
EXCLUDED_DIR_PARTS = {'__pycache__', 'node_modules'}
ROOT_EXCLUDED = {'evals'}

def counts(rel):
    dp = rel.parts[:-1]
    if any(p in EXCLUDED_DIR_PARTS for p in dp): return False
    if dp and dp[0] in ROOT_EXCLUDED: return False
    return True

def validate(folder):
    f = Path(folder)
    md = f / 'SKILL.md'
    if not md.exists(): return False, "SKILL.md not found"
    extra = [p for p in f.rglob('SKILL.md') if counts(p.relative_to(f)) and p.resolve() != md.resolve()]
    if extra: return False, f"multiple SKILL.md files: {[str(p.relative_to(f)) for p in extra]}"
    c = md.read_text(encoding='utf-8')
    m = re.match(r'^---\n(.*?)\n---', c, re.DOTALL)
    if not m: return False, "no/invalid YAML frontmatter"
    fm = yaml.safe_load(m.group(1))
    if not isinstance(fm, dict): return False, "frontmatter is not a dict"
    bad = set(fm) - ALLOWED
    if bad: return False, f"unexpected frontmatter key(s): {sorted(bad)} (allowed: {sorted(ALLOWED)})"
    if 'name' not in fm: return False, "missing 'name'"
    if 'description' not in fm: return False, "missing 'description'"
    name = str(fm['name']).strip()
    if not re.match(r'^[a-z0-9-]+$', name): return False, f"name '{name}' must be kebab-case"
    if name.startswith('-') or name.endswith('-') or '--' in name: return False, f"name '{name}' bad hyphens"
    if len(name) > 64: return False, f"name too long ({len(name)} > 64)"
    desc = str(fm['description']).strip()
    if '<' in desc or '>' in desc: return False, "description contains angle brackets (< or >)"
    if len(desc) > 1024: return False, f"description too long ({len(desc)} > 1024)"
    comp = str(fm.get('compatibility', '') or '')
    if comp and len(comp) > 500: return False, f"compatibility too long ({len(comp)} > 500)"
    return True, f"valid (description {len(desc)}/1024)"

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 validate_skill.py <skill-folder>"); sys.exit(2)
    ok, msg = validate(sys.argv[1]); print(msg); sys.exit(0 if ok else 1)
