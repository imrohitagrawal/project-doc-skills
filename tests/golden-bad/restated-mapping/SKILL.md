---
name: restated-mapping-fixture
description: A deliberately broken fixture skill whose publish step restates the render mapping that belongs only in render-contract.md. The render-restatement lint must catch it.
---

# Restated-mapping fixture (FIXTURE — deliberately broken)

This is a test fixture, not a real skill. Its publish section restates the
Markdown to publish-target conversion that is supposed to live in one home,
render-contract.md. The suite lint must flag the mapping construction below.

## Publish

When you publish this to the wiki, each tab or section becomes a heading and
callouts become panels — the verbatim restatement CROSS-SKILL-FINDINGS.md F1
flagged in project-faq's SKILL.md Step 6. Each section becomes a panel and the
collapsible blocks turn into an expand macro. The status notes become lozenges
in the portal theme.

A correct skill would instead hand off to publish-mirror and point at
render-contract.md, stating only what the reader sees — never the per-element
mapping.
