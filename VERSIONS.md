# Versions

This file records product versions and what changed between them.
Each entry lists only the differences from the previous version. The v1.0 entry
captures the baseline so future entries can stay diff-only.

## Template

## vX.Y (YYYY-MM-DD)

Release date: YYYY-MM-DD

### Added
### Changed
### Fixed
### Removed

## v3.1 (2026-01-04)

Release date: 2026-01-04

### Added
- [x] Tag categories on tags (defaults + custom categories).
- [x] Tag update endpoint for category changes (`PUT /tags/{tag_id}`).
- [x] Tag impacts endpoint per day (`GET /days/{date}/tag-impacts`) using effective goal versions (excluding rating goals).
- [x] Today UI redesign: category tabs + tag tile grid + impact drawer for click-first logging.

### Changed
- [x] Rating goals in Today are now primarily click-scored (presets and +/-) with numeric input fallback.

## v3.0 (2026-01-04)

Release date: 2026-01-04

### Added
- [x] Goal definition version history with version-specific tags/conditions.
- [x] Trend endpoints for per-goal series and multi-goal comparisons.
- [x] Trend-based notifications for pace and 7-day average drops.

### Changed
- [x] Scoring now uses effective goal versions for historical dates.

## v2.0 (2026-01-04)

Release date: 2026-01-04

### Added
- [x] Rating-based scoring mode for goals.
- [x] Per-day goal ratings for tracking and review.
- [x] In-app notifications with reminder scheduling.

### Changed
- [x] Click feedback and toast notifications for key UX actions.

## v1.5 (2026-01-03)

Release date: 2026-01-03

### Added
- [x] Calendar summary endpoint for daily-only cells plus weekly/monthly aggregates
- [x] Monthly goal target window supported in creation, scoring, and progress views
- [x] Journal backup/export workflow for saving or sharing journal notes
- [x] LLM health endpoint with model/base URL diagnostics plus frontend status panel
- [x] Easier LLM setup with base URL configuration surfaced in env/example and docs

### Changed
- [x] Calendar and today views split daily vs weekly progress, with monthly rollups.
- [x] Auto-refresh after actions to keep goal status and calendar aggregates current.

## v1.0

Release date: 2026-01-01

### Added (baseline)
- AI goal tracker with flexible goal definitions, daily tracking, and LLM-based summaries.
- FastAPI + SQLModel backend with SQLite storage (default `backend/data/app.db`) and an
  OpenAPI spec that powers generated frontend API clients.
- Core API surface: `/health`, `/goals`, `/tags`, `/conditions`, `/days` (day detail,
  calendar, notes, conditions, tag events), and `/review` (query + filter).
- Goal management: create/update/deactivate goals, daily or weekly targets, tag weights,
  condition-based applicability, and a configurable scoring mode field (`count`/`binary`).
- Tag management: create/reactivate by name, archive/reactivate, optional inclusion of
  inactive tags, and safe deletion blocked when tags are referenced by goals or events.
- Condition management: create/list reusable condition toggles used for daily tracking
  and goal applicability filters.
- Daily tracking: date navigation, condition toggles, tag events with counts/timestamps,
  quick add + create-and-add tag flows, and daily notes with autosave status.
- Goal scoring and status: tag-event based progress with met/partial/missed/N-A states,
  daily or weekly aggregation, and completion ratios for summaries.
- Calendar view: month grid with completion ratios, met vs. applicable goal counts, and
  condition badges, plus jump-to-day navigation.
- Review workflows: manual filters (date range, days of week, conditions all/any, goals
  focus), preview of included dates with fallback logic, and prompt-only AI planning.
- Local LLM integration via Ollama for review summaries with structured output and
  debug context (plan, filters, date range, truncation).
- Frontend app shell with bottom-tab navigation, local date header, and offline banner
  when the backend is unreachable.
- Configurable environment settings (`DB_PATH`, `DB_URL`, `LOG_LEVEL`, `OLLAMA_MODEL`)
  and local dev CORS support for `http://localhost:5173`.
- Backend pytest suite covering health checks, goals CRUD, tags, days, review, and
  scoring calendar behavior.
