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

## v1.0 (current)

Release date: 01/01/2026

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
