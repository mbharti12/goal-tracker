# Implementation Notes

## 1) Current goal scoring flow
- Tag events are created via `POST /days/{date}/tag-events` (payload `TagEventCreate`: `tag_id` or `tag_name`, `count`, `ts`, `note`) and stored as `TagEvent` rows. `backend/app/routers/days.py`, `backend/app/schemas.py`, `backend/app/models.py`
- Scoring loads active goals, goal tag weights, goal conditions, and day conditions. It sums tag event counts over the goal's target window (day/week/month), multiplies by tag weight, and compares to `target_count` to set `status` (`met`/`partial`/`missed`/`na`). `scoring_mode` is stored but not used in the current logic. `backend/app/services/scoring.py`, `backend/app/models.py`
- `GET /days/{date}` returns `DayRead` with `day_entry`, `conditions`, `tag_events`, and `goals` (dicts from scoring: `goal_id`, `goal_name`, `applicable`, `status`, `progress`, `target`, `target_window`). `backend/app/routers/days.py`, `backend/app/schemas.py`, `backend/app/services/scoring.py`

## 2) Frontend button-click actions + loading/error patterns
- Today: date navigation buttons update `selectedDate`; actions live in `handleToggleCondition`, `handleAddTagEvent`, `handleCreateTagAndAdd`, `handleDeleteTagEvent`, and debounced `saveNote`. Errors roll into a banner with retry callbacks; loading states are per-card via `useDay`, `useConditions`, `useTags`. `frontend/src/pages/Today.tsx`, `frontend/src/hooks/useDay.ts`, `frontend/src/hooks/useConditions.ts`, `frontend/src/hooks/useTags.ts`, `frontend/src/api/endpoints.ts`
- Goals: actions live in `handleSubmit` (create/update), `handleDeactivate`, `handleCreateTag`, `handleArchiveTag`, `handleUnarchiveTag`, and goal selection/new-goal buttons. Loading/errors are shown per panel with retry buttons and `status--loading/error` blocks from `useGoals`, `useTags`, `useConditions`. `frontend/src/pages/Goals.tsx`, `frontend/src/hooks/useGoals.ts`, `frontend/src/hooks/useTags.ts`, `frontend/src/hooks/useConditions.ts`
- Calendar: month nav buttons update `activeMonth`; day tiles navigate to `/today` and set the date. Data loads via `getCalendarSummary` with local `loading/error` state and a retry button (currently wired to `setReloadToken`, which is not defined in this file). `frontend/src/pages/Calendar.tsx`, `frontend/src/api/endpoints.ts`
- Review: actions live in `handlePreview` (calls `/review/filter`, with a `getCalendar`+`getDay` fallback), `handleManualSummary`, and `handlePromptOnly`. Loading/error states are tracked separately for preview, AI query, and LLM health checks, with retry buttons for conditions/goals lists. `frontend/src/pages/Review.tsx`, `frontend/src/hooks/useGoals.ts`, `frontend/src/hooks/useConditions.ts`, `frontend/src/api/endpoints.ts`

## 3) v2 API contract additions (planned)
- Goal ratings
  - New schemas: `GoalRatingRead { id, date, goal_id, rating (1-5), note?, created_at, updated_at }`, `GoalRatingUpsert { goal_id, rating, note? }`. `backend/app/schemas.py`, `backend/app/models.py`
  - Endpoints: `GET /days/{date}/goal-ratings`, `PUT /days/{date}/goal-ratings` (upsert list), `GET /goals/{goal_id}/ratings?start&end`. Add `goal_ratings` to `DayRead`. `backend/app/routers/days.py`, `backend/app/schemas.py`
- Notifications/reminders
  - New schemas: `ReminderRead { id, title, goal_id?, cadence, days_of_week?, time, timezone, channel, active, next_fire_at }` and `NotificationRead { id, reminder_id?, title, body, status, created_at, delivered_at?, read_at? }`. `backend/app/schemas.py`, `backend/app/models.py`
  - Endpoints: `GET/POST/PUT/DELETE /reminders`; `GET /notifications?since=&status=`; `PATCH /notifications/{id}` (mark read/ack). `backend/app/routers/reminders.py`, `backend/app/routers/notifications.py`
- UX feedback primitives
  - New schema: `FeedbackMessage { level, message, detail?, code?, target?, actions? }` where `target` is `toast|banner|inline` and `actions` is `{ label, href?, action? }`. `backend/app/schemas.py`
  - New response shape for v2 mutating endpoints: `{ data, feedback?: FeedbackMessage[] }` to drive consistent UI messaging without changing HTTP error handling. `backend/app/routers/*`, `frontend/src/api/endpoints.ts`, `frontend/src/api/types.ts`
