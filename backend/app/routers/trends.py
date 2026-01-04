from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..db import get_session
from ..models import Goal
from ..schemas import (
    GoalTrendResponse,
    TrendBucket,
    TrendCompareRequest,
    TrendCompareResponse,
)
from ..services import trend_service

router = APIRouter(tags=["trends"])


def _normalize_dates(start: str, end: str) -> tuple[str, str]:
    start_date = datetime.strptime(start, "%Y-%m-%d").date()
    end_date = datetime.strptime(end, "%Y-%m-%d").date()
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    return start_date.isoformat(), end_date.isoformat()


@router.get("/goals/{goal_id}/trend", response_model=GoalTrendResponse)
def get_goal_trend(
    goal_id: int,
    start: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    bucket: TrendBucket = Query("day"),
    session: Session = Depends(get_session),
) -> GoalTrendResponse:
    goal = session.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")

    start_str, end_str = _normalize_dates(start, end)
    series = trend_service.build_trend_series(
        session, [goal_id], start_str, end_str, bucket
    )
    points = series[0]["points"] if series else []
    return GoalTrendResponse(
        goal_id=goal_id,
        goal_name=goal.name,
        bucket=bucket,
        start=start_str,
        end=end_str,
        points=points,
    )


@router.post("/trends/compare", response_model=TrendCompareResponse)
def compare_trends(
    payload: TrendCompareRequest, session: Session = Depends(get_session)
) -> TrendCompareResponse:
    if not payload.goal_ids:
        return TrendCompareResponse(
            bucket=payload.bucket,
            start=payload.start,
            end=payload.end,
            series=[],
            comparisons=[],
        )

    goals = session.exec(select(Goal).where(Goal.id.in_(payload.goal_ids))).all()
    goal_ids = {goal.id for goal in goals if goal.id is not None}
    missing = [goal_id for goal_id in payload.goal_ids if goal_id not in goal_ids]
    if missing:
        raise HTTPException(
            status_code=404, detail=f"Goals not found: {', '.join(map(str, missing))}"
        )

    start_str, end_str = _normalize_dates(payload.start, payload.end)
    series = trend_service.build_trend_series(
        session, payload.goal_ids, start_str, end_str, payload.bucket
    )
    comparisons = _build_comparisons(series)
    return TrendCompareResponse(
        bucket=payload.bucket,
        start=start_str,
        end=end_str,
        series=series,
        comparisons=comparisons,
    )


def _build_comparisons(series: List[dict]) -> List[dict]:
    comparisons: List[dict] = []
    series_by_goal = {entry["goal_id"]: entry for entry in series}
    goal_ids = [entry["goal_id"] for entry in series]

    for idx, goal_id_a in enumerate(goal_ids):
        for goal_id_b in goal_ids[idx + 1 :]:
            points_a = series_by_goal[goal_id_a]["points"]
            points_b = series_by_goal[goal_id_b]["points"]
            ratios_a = []
            ratios_b = []
            for point_a, point_b in zip(points_a, points_b):
                if (
                    point_a["applicable"]
                    and point_b["applicable"]
                    and point_a["status"] != "na"
                    and point_b["status"] != "na"
                ):
                    ratios_a.append(point_a["ratio"])
                    ratios_b.append(point_b["ratio"])

            correlation = _pearson(ratios_a, ratios_b)
            comparisons.append(
                {
                    "goal_id_a": goal_id_a,
                    "goal_id_b": goal_id_b,
                    "correlation": correlation,
                    "n": len(ratios_a),
                }
            )

    return comparisons


def _pearson(values_a: List[float], values_b: List[float]) -> Optional[float]:
    n = min(len(values_a), len(values_b))
    if n < 3:
        return None
    avg_a = sum(values_a[:n]) / n
    avg_b = sum(values_b[:n]) / n
    var_a = sum((value - avg_a) ** 2 for value in values_a[:n])
    var_b = sum((value - avg_b) ** 2 for value in values_b[:n])
    if var_a == 0 or var_b == 0:
        return None
    cov = sum(
        (value_a - avg_a) * (value_b - avg_b)
        for value_a, value_b in zip(values_a[:n], values_b[:n])
    )
    return cov / (var_a * var_b) ** 0.5
