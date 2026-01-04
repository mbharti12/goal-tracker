from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ..db import get_session
from ..schemas import (
    ReviewDebug,
    ReviewDebugFilters,
    ReviewFilterRequest,
    ReviewFilterResponse,
    ReviewQueryRequest,
    ReviewQueryResponse,
)
from ..services import review_service
from ..services.ollama_client import DEFAULT_MODEL, chat

router = APIRouter(prefix="/review", tags=["review"])


@router.post("/query", response_model=ReviewQueryResponse)
def review_query(
    payload: ReviewQueryRequest, session: Session = Depends(get_session)
) -> ReviewQueryResponse:
    plan = review_service.build_plan(session, payload.prompt)
    start_date, end_date = review_service.resolve_date_range(plan)
    allow_more = review_service.prompt_requests_long_range(payload.prompt)
    context = review_service.build_review_context(
        session,
        start_date,
        end_date,
        days_of_week=plan.days_of_week,
        conditions_all=plan.conditions_all,
        conditions_any=plan.conditions_any,
        goals=plan.goals,
        allow_more=allow_more,
    )

    stats_table = review_service.build_stats_table(context.days)
    notes_snippets = review_service.build_notes_snippets(context.days)
    answer = _summarize_review(payload.prompt, plan, context, stats_table, notes_snippets)

    debug_filters = ReviewDebugFilters(
        dow=plan.days_of_week,
        conditions=_merge_conditions(plan.conditions_all, plan.conditions_any),
        goals=plan.goals,
    )
    debug = ReviewDebug(
        plan=plan,
        date_range=context.date_range,
        filters=debug_filters,
        days_included=len(context.days),
        truncated=context.truncated,
    )
    return ReviewQueryResponse(answer=answer, debug=debug)


@router.post("/filter", response_model=ReviewFilterResponse)
def review_filter(
    payload: ReviewFilterRequest, session: Session = Depends(get_session)
) -> ReviewFilterResponse:
    context = review_service.build_review_context(
        session,
        payload.start_date,
        payload.end_date,
        days_of_week=payload.days_of_week,
        conditions_all=payload.conditions_all,
        conditions_any=payload.conditions_any,
        goals=payload.goals,
        allow_more=False,
    )
    return ReviewFilterResponse(context=context)


def _summarize_review(
    prompt: str,
    plan,
    context,
    stats_table: str,
    notes_snippets: str,
) -> str:
    system_content = (
        "You are a goal review assistant. Respond with the following format:\n"
        "Summary:\n"
        "- 6-10 bullets\n"
        "Patterns:\n"
        "- 3 bullets\n"
        "Suggestions:\n"
        "- 3 bullets\n"
        "Mention goal performance when relevant."
    )
    plan_json = json.dumps(plan.model_dump(), ensure_ascii=False)
    filters_json = json.dumps(context.filters.model_dump(), ensure_ascii=False)
    user_content = "\n".join(
        [
            f"User prompt: {prompt}",
            f"Plan: {plan_json}",
            f"Date range: {context.date_range.start} to {context.date_range.end}",
            f"Filters: {filters_json}",
            f"Days included: {len(context.days)} (truncated: {context.truncated})",
            "Stats table:",
            stats_table,
            "Notes snippets:",
            notes_snippets,
        ]
    )
    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]
    return chat(DEFAULT_MODEL, messages, temperature=0.2)


def _merge_conditions(
    conditions_all: Optional[List[str]], conditions_any: Optional[List[str]]
) -> Optional[List[str]]:
    merged = []
    if conditions_all:
        merged.extend(conditions_all)
    if conditions_any:
        merged.extend(conditions_any)
    merged = [item for item in merged if item]
    if not merged:
        return None
    seen = set()
    ordered = []
    for item in merged:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(item)
    return ordered
