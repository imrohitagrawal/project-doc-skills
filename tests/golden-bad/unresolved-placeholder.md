<!--
FIXTURE — deliberately broken. Replays CROSS-SKILL-FINDINGS.md F5 (resolved 2026-06-22, root
CHANGELOG 1.0.0): project-faq's faq-method reference carried `"last_reviewed": "{{today}}"`, but at the
time `today` backed to no key in project-profile.md / publish-targets.yaml and was not a documented
runtime token — so an agent filling the template could not resolve it. The fix documented a small
Runtime tokens set ({{today}}, {{canonical_url}}) and added lint-placeholders.py --strict.

This fixture locks BOTH directions of that incident:
  - the still-unresolvable token `{{todays_date}}` MUST be caught (the real-broken-input class F5 was);
  - the documented runtime token `{{today}}` and a real profile key MUST resolve cleanly (the F5 fix —
    a regression that dropped {{today}} from the runtime set would flag the line below and turn red).
The lint scans skills/** and shared/**; this fixture lives under tests/ and is driven directly via
lint-placeholders.scan_text() in tests/run-golden.py (the import-friendly seam its docstring names).
-->

# F5 fixture — an unresolved {{...}} placeholder

A profile-resolvable value reads from a real key, e.g. project: {{project_name}}.

The documented runtime token resolves (this is the F5 fix):
    "last_reviewed": "{{today}}"

The broken line F5 is the class of — a token that backs to NOTHING:
    "generated_for": "{{todays_date}}"
