import { useEffect, useMemo, useState } from "react";
import type { MouseEvent } from "react";
import type { TrendSeries } from "../api/types";

type MultiTrendChartProps = {
  series: TrendSeries[];
  loading?: boolean;
};

const VIEWBOX_WIDTH = 720;
const VIEWBOX_HEIGHT = 260;
const MARGIN = { top: 16, right: 18, bottom: 36, left: 42 };
const COLORS = ["#1f6d72", "#c3722c", "#2c6c9c", "#5c7a3f", "#b03a2e", "#7a5c3f"];

const formatPercent = (value: number) => `${Math.round(value * 100)}%`;

export default function MultiTrendChart({ series, loading = false }: MultiTrendChartProps) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [hiddenGoalIds, setHiddenGoalIds] = useState<Set<number>>(new Set());

  useEffect(() => {
    setHiddenGoalIds((prev) => {
      const next = new Set(
        Array.from(prev).filter((goalId) => series.some((item) => item.goal_id === goalId)),
      );
      return next;
    });
  }, [series]);

  const visibleSeries = useMemo(
    () => series.filter((entry) => !hiddenGoalIds.has(entry.goal_id)),
    [hiddenGoalIds, series],
  );

  const chartData = useMemo(() => {
    if (visibleSeries.length === 0) {
      return null;
    }
    const ratios = visibleSeries.flatMap((entry) =>
      entry.points.map((point) => point.ratio ?? 0),
    );
    if (ratios.length === 0) {
      return null;
    }
    const minRatio = Math.min(...ratios);
    const maxRatio = Math.max(...ratios);
    const yMin = Math.min(0, minRatio);
    const yMax = Math.max(1, maxRatio);
    const yRange = yMax - yMin || 1;
    const plotWidth = VIEWBOX_WIDTH - MARGIN.left - MARGIN.right;
    const plotHeight = VIEWBOX_HEIGHT - MARGIN.top - MARGIN.bottom;

    const positions = visibleSeries.map((entry) => {
      const coords = entry.points.map((point, index) => {
        const ratio = point.ratio ?? 0;
        const x =
          entry.points.length === 1
            ? MARGIN.left + plotWidth / 2
            : MARGIN.left + (index / (entry.points.length - 1)) * plotWidth;
        const y = MARGIN.top + (1 - (ratio - yMin) / yRange) * plotHeight;
        return { x, y };
      });
      const path = coords
        .map((coord, index) => `${index === 0 ? "M" : "L"} ${coord.x} ${coord.y}`)
        .join(" ");
      return { goalId: entry.goal_id, coords, path };
    });

    return { yMin, yMax, positions };
  }, [visibleSeries]);

  if (loading) {
    return (
      <div className="trend-chart trend-chart--loading">
        <div className="chart-skeleton" />
      </div>
    );
  }

  if (series.length === 0) {
    return <div className="trend-chart trend-chart--empty">Select goals to compare.</div>;
  }

  if (!chartData) {
    return (
      <div className="trend-chart trend-chart--empty">
        Toggle a series to view the chart.
      </div>
    );
  }

  const { yMin, yMax, positions } = chartData;
  const hoverPoint = hoverIndex === null ? null : visibleSeries[0]?.points[hoverIndex];
  const hoverCoord =
    hoverIndex === null ? null : positions[0]?.coords[hoverIndex] ?? null;
  const tooltipStyle =
    hoverCoord === null
      ? undefined
      : {
          left: `${(hoverCoord.x / VIEWBOX_WIDTH) * 100}%`,
          top: `${(hoverCoord.y / VIEWBOX_HEIGHT) * 100}%`,
        };

  const handleMove = (event: MouseEvent<SVGSVGElement>) => {
    if (visibleSeries.length === 0) {
      return;
    }
    const totalPoints = visibleSeries[0].points.length;
    if (totalPoints === 0) {
      return;
    }
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = (event.clientX - rect.left) / rect.width;
    const plotX = ratio * VIEWBOX_WIDTH;
    const plotWidth = VIEWBOX_WIDTH - MARGIN.left - MARGIN.right;
    const index =
      totalPoints === 1
        ? 0
        : Math.round(((plotX - MARGIN.left) / plotWidth) * (totalPoints - 1));
    const safeIndex = Math.max(0, Math.min(totalPoints - 1, index));
    setHoverIndex(safeIndex);
  };

  return (
    <div className="trend-chart">
      <div className="trend-legend">
        {series.map((entry, index) => {
          const isActive = !hiddenGoalIds.has(entry.goal_id);
          return (
            <button
              key={entry.goal_id}
              type="button"
              className={`trend-legend__item${isActive ? "" : " trend-legend__item--off"}`}
              onClick={() =>
                setHiddenGoalIds((prev) => {
                  const next = new Set(prev);
                  if (next.has(entry.goal_id)) {
                    next.delete(entry.goal_id);
                  } else {
                    next.add(entry.goal_id);
                  }
                  return next;
                })
              }
              aria-pressed={isActive}
            >
              <span
                className="trend-legend__swatch"
                style={{ backgroundColor: COLORS[index % COLORS.length] }}
              />
              <span className="trend-legend__label">{entry.goal_name}</span>
            </button>
          );
        })}
      </div>
      <svg
        className="trend-chart__svg"
        viewBox={`0 0 ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}`}
        role="img"
        aria-label="Trend comparison chart"
        onMouseMove={handleMove}
        onMouseLeave={() => setHoverIndex(null)}
      >
        <line
          className="trend-chart__axis"
          x1={MARGIN.left}
          y1={MARGIN.top}
          x2={MARGIN.left}
          y2={VIEWBOX_HEIGHT - MARGIN.bottom}
        />
        <line
          className="trend-chart__axis"
          x1={MARGIN.left}
          y1={VIEWBOX_HEIGHT - MARGIN.bottom}
          x2={VIEWBOX_WIDTH - MARGIN.right}
          y2={VIEWBOX_HEIGHT - MARGIN.bottom}
        />
        <line
          className="trend-chart__grid"
          x1={MARGIN.left}
          y1={MARGIN.top}
          x2={VIEWBOX_WIDTH - MARGIN.right}
          y2={MARGIN.top}
        />
        <line
          className="trend-chart__grid"
          x1={MARGIN.left}
          y1={VIEWBOX_HEIGHT - MARGIN.bottom}
          x2={VIEWBOX_WIDTH - MARGIN.right}
          y2={VIEWBOX_HEIGHT - MARGIN.bottom}
        />
        <text className="trend-chart__label" x={8} y={MARGIN.top + 4}>
          {formatPercent(yMax)}
        </text>
        <text
          className="trend-chart__label"
          x={8}
          y={VIEWBOX_HEIGHT - MARGIN.bottom}
        >
          {formatPercent(yMin)}
        </text>

        {positions.map((entry, index) => (
          <path
            key={entry.goalId}
            className="trend-chart__line trend-chart__line--multi"
            d={entry.path}
            style={{ stroke: COLORS[index % COLORS.length] }}
          />
        ))}
      </svg>
      {hoverPoint && hoverCoord && (
        <div className="trend-chart__tooltip" style={tooltipStyle}>
          <div className="trend-chart__tooltip-date">{hoverPoint.date}</div>
          {visibleSeries.map((entry, index) => {
            const point = entry.points[hoverIndex ?? 0];
            return (
              <div key={entry.goal_id} className="trend-chart__tooltip-line">
                <span
                  className="trend-chart__tooltip-swatch"
                  style={{ backgroundColor: COLORS[index % COLORS.length] }}
                />
                <span>{entry.goal_name}</span>
                <span>{formatPercent(point.ratio)}</span>
                <span>
                  {point.progress}/{point.target}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
