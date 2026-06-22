# Changelog — publish-mirror

All notable changes to this skill are recorded here (Keep a Changelog format).

## [1.2.0] — duplicate-safety, image-attachment honesty, scope-aware credit check

### Added
- **First-publish write-back is now part of the same operation, not a later chore.** Steps 1 and 6
  make explicit that a create is unfinished until its returned id is persisted to the manifest and
  confirmed — an unpersisted id is the one way this skill produces a duplicate. On a write-back
  failure the skill **stops and surfaces it**; it never re-runs a blind create and never recovers by
  matching on title (the manifest forbids inferring an id that way). The quality bar checks for it.
- **Honest about image upload.** The inputs note that a target's write path may expose page
  create/update but **no attachment upload**; where that is so, attaching the exported images is a
  separate step inside the human gate (manual drag-drop, a browser action, or a direct upload call),
  and the run is not done until the images are attached and showing. The quality bar checks every
  exported image is attached and showing, including when the attach was a separate step.

### Changed
- Step 5 and the quality bar phrase the licence-credit check as **scope-aware** — the `©` footer on a
  public page, the copyright line or credits block on an internal one — matching the publish-reviewer
  in `render-contract.md` Section 4 (the shared change is recorded in the root `CHANGELOG.md`).
- Step 6 clarifies closure on a target with **no** issue tracker: the publish-log entry is the record
  (the page-tracker "stay open until the owner approves" rule applies where a tracker exists).

## [1.1.0] — HTML-source path

### Added
- **A finished HTML page can now be published, not only Markdown.** The render contract gains an
  HTML-source path (Section 1a) for the FAQ and an HTML usage guide: faithful on a portal that
  hosts HTML (tabs, sidebar, keyboard navigation survive); degraded to native structure on a wiki,
  which does not run the page's own code (state that on the page). Step 2 now picks the source
  path from the file extension, or the manifest's optional `source_format` flag.
- usage-guide and project-faq each gained an **optional** repo-first publish step that hands their
  HTML page to this skill via the HTML-source path.

### Changed
- Description tightened to 947 characters (under the 950 headroom aim) and broadened to name the
  HTML-page case.

## [1.0.0] — first release

### Added
- The target-agnostic publish step for the documentation suite. Mirrors repo-first Markdown that an
  authoring skill has already verified out to one or more published targets, with no authoring of its
  own.
- Driven by two shared files: `render-contract.md` (source primitives, per-target adapters, declared
  graceful degradation) and `publish-targets.yaml` (the single home of every target coordinate, with
  secrets by reference and a stable per-page id that prevents duplicates).
- Carries the governance gate into the publish layer: record-before-edit for a published artifact, a
  human gate on every write, the publish-reviewer afterwards, and the page-tracker closure rule.
- Ships the Confluence adapter (built) and the HTML-portal adapter as a defined seam marked
  designed-not-yet-built.
