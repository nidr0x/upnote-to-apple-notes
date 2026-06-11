# UpNote To Apple Notes Importer Design

Date: 2026-06-12
Status: Approved for planning

## Goal

Build a robust macOS importer that extracts notes directly from the local UpNote app database, normalizes them into an inspectable on-disk export, and imports them into Apple Notes with resumability, idempotency, and explicit reporting of any fidelity loss.

## Scope

In scope:

- Discover the local UpNote database and note assets on macOS.
- Extract notebooks, notes, metadata, tags, and attachments from UpNote storage.
- Normalize extracted data into a stable intermediate representation on disk.
- Import normalized data into Apple Notes using macOS automation.
- Support dry runs, resumable imports, and import reporting.
- Preserve structure and content as faithfully as the Apple Notes automation boundary allows.

Out of scope:

- Writing directly into Apple Notes private storage.
- Supporting non-macOS import destinations.
- Building a GUI in the first version.
- Syncing ongoing changes after one-time migration.

## Recommended Architecture

The importer is a two-stage pipeline with a thin destination adapter:

1. A `discover` phase locates the UpNote database and related asset directories.
2. An `extract` phase reads the UpNote data model and writes a normalized export tree to disk.
3. An `import` phase reads that export tree and creates folders and notes in Apple Notes through JXA.
4. A `state` layer tracks per-note progress and fingerprints so reruns are resumable and idempotent.
5. A `report` phase summarizes created, updated, skipped, failed, and degraded items.

This design separates source parsing from destination automation so extraction can be validated independently and failed imports can resume without reparsing the UpNote database.

## Why JXA

Three destination approaches were considered:

1. AppleScript: simple setup, but harder to structure and maintain for a production-grade importer.
2. JXA via `osascript -l JavaScript`: same automation class with better program structure, error handling, and maintainability.
3. Direct writes to Apple Notes backing storage: higher theoretical fidelity, but unacceptable corruption and compatibility risk.

The importer will use JXA for the Apple Notes adapter because it provides the best balance of safety, maintainability, and practical capability.

## CLI Shape

The importer will be delivered as a command-line tool with focused subcommands:

- `discover`: locate UpNote storage and print a source summary.
- `extract`: create or refresh the normalized export tree.
- `import`: import notes into Apple Notes from an export tree.
- `resume`: continue a previously interrupted import run.
- `report`: render a summary from a completed or partial run.

The first version may internally route `resume` to `import` with persisted state, but the user-facing command should exist because resumability is a primary feature.

## System Components

### Source Discovery

Responsibilities:

- Locate the UpNote local database path on macOS.
- Locate the attachment or asset storage used by the local UpNote installation.
- Validate that required files are readable.
- Record detected paths and source metadata.

Failure behavior:

- If the database cannot be found, return a clear discovery error with the checked locations.
- If the database is found but related assets are missing, continue discovery and mark assets as degraded instead of assuming notes have no files.

### Extraction Engine

Responsibilities:

- Open the UpNote database in read-only mode.
- Inspect schema version and validate required tables or fields.
- Read notebooks, notes, tags, note-tag relations, attachments, and note metadata.
- Preserve raw source fragments needed for debugging failed conversions.
- Write a normalized export to disk.

Failure behavior:

- If the schema is incompatible, fail fast with a schema report instead of guessing.
- If a single note cannot be parsed, export the raw record for that note, mark it failed, and continue with other notes.

### Normalization Layer

Responsibilities:

- Convert note content into a canonical import boundary representation.
- Resolve asset references into stable extracted files.
- Compute note fingerprints for idempotent import decisions.
- Produce an inspectable manifest and deterministic file layout.

Canonical body format:

- The normalized body format will be HTML.
- Plain text is insufficient for preserving structure.
- Markdown would still require a second conversion at the destination boundary and would make fidelity less predictable.

### Apple Notes Adapter

Responsibilities:

- Read the normalized export tree.
- Create folder hierarchy in Apple Notes.
- Create or update notes according to import mode.
- Attach images and files where supported by the automation surface.
- Write import progress to state.

Behavior rules:

- Imports run in batches with per-note checkpoints.
- The adapter retries transient failures a small fixed number of times.
- A single failed note must not abort the entire run.

### State And Reporting

Responsibilities:

- Track each note's source ID, fingerprint, status, attempt count, and destination mapping.
- Distinguish `created`, `updated`, `skipped`, `failed`, and `degraded`.
- Produce machine-readable and human-readable reports.

The state file is the system of record for resumability during a migration run.

## Normalized Export Format

The export must be explicit and inspectable. It is not just a temporary cache.

Proposed layout:

```text
export-root/
  manifest.json
  notes/
    <note-id>.html
  raw/
    <note-id>.json
  assets/
    <asset-id>-<sanitized-name>
  state/
    import-state.json
  reports/
    latest-report.json
```

### Manifest Structure

Each note entry in `manifest.json` should include:

- Stable UpNote note ID.
- Title.
- Notebook path as an ordered list and normalized display path.
- Tags.
- Created and updated timestamps from UpNote.
- Pinned or starred state if available.
- Attachment references.
- HTML body file reference.
- Raw source record reference.
- Content fingerprint.
- Import provenance marker.

Global manifest data should include:

- Source database path.
- Extraction timestamp.
- Schema version or schema signature.
- Counts of notebooks, notes, tags, and assets.
- Extraction warnings.

## Fidelity Policy

The importer should preserve data aggressively, but never silently pretend unsupported content was preserved.

Preserve directly:

- Notebook hierarchy as Apple Notes folders.
- Note titles.
- Note body formatting where representable through the automation boundary.
- Embedded images and file attachments where supported.
- Tags in normalized metadata.
- Created and updated timestamps in export metadata.

Degrade explicitly when necessary:

- If Apple Notes automation cannot set tags reliably, represent tags in a controlled metadata suffix or importer block.
- If a rich structure cannot be represented exactly, keep the closest rendered form in the note body and record the degradation in the report.
- If an attachment is missing on disk, import the note body and report the missing attachment.

Unsupported content must always appear in the final report.

## Idempotency And Update Semantics

Each note gets:

- A stable source ID from UpNote.
- A content fingerprint derived from normalized note content and relevant metadata.
- A provenance marker embedded in the destination note in a low-noise way.

Supported import modes:

- `dry-run`: extract and plan only, with no Apple Notes mutation.
- `skip-existing`: create missing notes, do not update existing mapped notes.
- `update-changed`: update existing mapped notes when fingerprints differ.
- `resume`: continue unfinished work from persisted state.

Rules:

- Rerunning the same import should not create duplicates for unchanged notes.
- Updated notes should be detected by fingerprint changes, not title matching.
- Destination lookup should prefer provenance markers over fuzzy matching.

## Error Handling

The importer must optimize for completion with accountability:

- Fail fast on source-level incompatibility such as unknown schema.
- Continue on note-level failures.
- Retry transient Apple Notes automation failures a small number of times.
- Record all failures and degradations with enough context to debug them later.

Every failed note record should include:

- Source ID.
- Title if available.
- Phase of failure.
- Error summary.
- Pointer to raw exported data where relevant.

## Verification Strategy

### Automated Tests

- Unit tests for source discovery path resolution.
- Unit tests for schema inspection and extraction mapping.
- Unit tests for normalization and HTML generation.
- Unit tests for fingerprint computation.
- Unit tests for manifest and report generation.

### Fixtures

Representative fixtures should cover:

- Nested notebooks.
- Inline images.
- File attachments.
- Checklists.
- Code blocks.
- Tables.
- Links.
- Tags.
- Notes with missing assets.
- Notes with formatting that requires degradation reporting.

### End-To-End Validation

- A macOS-gated smoke test should run extraction plus a minimal Apple Notes import path.
- A reconciliation command should compare export counts with import outcomes and flag mismatches.
- Manual verification remains necessary for rich formatting and attachment fidelity.

## Implementation Constraints

- Do not modify Apple Notes private storage directly.
- Default behavior should be safe and inspectable.
- The first live run should require explicit import invocation after a successful extract or dry run.
- The codebase should keep extraction and destination automation isolated behind clear interfaces.

## Open Decisions Resolved In This Spec

- Source: direct extraction from the local UpNote app database.
- Destination architecture: normalized export plus Apple Notes import adapter.
- Apple Notes adapter: JXA, not direct database writes.
- Canonical normalized body format: HTML.
- Delivery format: CLI first, no GUI in version one.

## Initial Milestones

1. Scaffold the CLI and core package structure.
2. Implement macOS source discovery and schema inspection.
3. Implement extraction and normalized export generation.
4. Add fixtures and unit tests for normalization and manifest output.
5. Implement the JXA Apple Notes adapter with dry-run and create-only flows.
6. Add resumability, update logic, and reporting.
7. Validate with a real sample export from a local UpNote installation.

## Success Criteria

The first release is successful if it can:

- Read a real local UpNote database on macOS without manual database editing.
- Produce an inspectable normalized export with notes, assets, and manifest.
- Import a representative note set into Apple Notes without duplicating unchanged notes on rerun.
- Report every failure and every fidelity degradation explicitly.
- Resume after interruption without restarting the full pipeline.
