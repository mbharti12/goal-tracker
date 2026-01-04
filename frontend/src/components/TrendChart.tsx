import { useMemo, useState } from "react";
import type { MouseEvent } from "react";
import type { TrendPoint } from "../api/types";

type TrendChartProps = {
  points: TrendPoint[];
  loading?: boolean;
};

const VIEWBOX_WIDTH = 640;
const VIEWBOX_HEIGHT = 240;
const MARGIN = { top: 16, right: 18, bottom: 32, left: 40 };

const formatPercent = (value: number) => `${Math.round(value * 100)}%`;

export default function TrendChart({ points, loading = false }: TrendChartProps) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const chartData = useMemo(() => {
    if (points.length === 0) {
      return null;
    }
    const ratios = points.map((point) => point.ratio ?? 0);
    const minRatio = Math.min(...ratios);
    const maxRatio = Math.max(...ratios);
    const yMin = Math.min(0, minRatio);
    const yMax = Math.max(1, maxRatio);
    const yRange = yMax - yMin || 1;
    const plotWidth = VIEWBOX_WIDTH - MARGIN.left - MARGIN.right;
    const plotHeight = VIEWBOX_HEIGHT - MARGIN.top - MARGIN.bottom;

    const coords = points.map((point, index) => {
      const ratio = point.ratio ?? 0;
      const x =
        points.length === 1
          ? MARGIN.left + plotWidth / 2
          : MARGIN.left + (index / (points.length - 1)) * plotWidth;
      const y = MARGIN.top + (1 - (ratio - yMin) / yRange) * plotHeight;
      return { x, y };
    });

    const path = coords
      .map((coord, index) => `${index === 0 ? "M" : "L"} ${coord.x} ${coord.y}`)
      .join(" ");

    const versionMarkers = coords
      .slice(1)
      .map((coord, index) => {
        const current = points[index + 1];
        const prev = points[index];
        if (current.goal_version_id !== prev.goal_version_id) {
          return coord.x;
        }
        return null;
      })
      .filter((value): value is number => value !== null);

    return { coords, path, yMin, yMax, versionMarkers };
  }, [points]);

  if (loading) {
    return (
      <div className="trend-chart trend-chart--loading">
        <div className="chart-skeleton" />
      </div>
    );
  }

  if (!chartData) {
    return <div className="trend-chart trend-chart--empty">No data in range.</div>;
  }

  const { coords, path, yMin, yMax, versionMarkers } = chartData;
  const hoverPoint = hoverIndex === null ? null : points[hoverIndex];
  const hoverCoord = hoverIndex === null ? null : coords[hoverIndex];
  const tooltipStyle =
    hoverCoord === null
      ? undefined
      : {
          left: `${(hoverCoord.x / VIEWBOX_WIDTH) * 100}%`,
          top: `${(hoverCoord.y / VIEWBOX_HEIGHT) * 100}%`,
        };

  const handleMove = (event: MouseEvent<SVGSVGElement>) => {
    if (points.length === 0) {
      return;
    }
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = (event.clientX - rect.left) / rect.width;
    const plotX = ratio * VIEWBOX_WIDTH;
    const plotWidth = VIEWBOX_WIDTH - MARGIN.left - MARGIN.right;
    const index =
      points.length === 1
        ? 0
        : Math.round(((plotX - MARGIN.left) / plotWidth) * (points.length - 1));
    const safeIndex = Math.max(0, Math.min(points.length - 1, index));
    setHoverIndex(safeIndex);
  };

  return (
    <div className="trend-chart">
      <svg
        className="trend-chart__svg"
        viewBox={`0 0 ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}`}
        role="img"
        aria-label="Goal trend chart"
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

        {versionMarkers.map((x) => (
          <line
            key={`marker-${x}`}
            className="trend-chart__marker"
            x1={x}
            y1={MARGIN.top}
            x2={x}
            y2={VIEWBOX_HEIGHT - MARGIN.bottom}
          />
        ))}

        <path className="trend-chart__line" d={path} />
        {coords.map((coord, index) => (
          <circle
            key={`dot-${index}`}
            className="trend-chart__dot"
            cx={coord.x}
            cy={coord.y}
            r={hoverIndex === index ? 4 : 2.5}
          />
        ))}
      </svg>
      {hoverPoint && hoverCoord && (
        <div className="trend-chart__tooltip" style={tooltipStyle}>
          <div className="trend-chart__tooltip-date">{hoverPoint.date}</div>
          <div className="trend-chart__tooltip-main">
            {formatPercent(hoverPoint.ratio)} · {hoverPoint.progress}/
            {hoverPoint.target}
          </div>
          <div className="trend-chart__tooltip-sub">Status: {hoverPoint.status}</div>
        </div>
      )}
    </div>
  );
}
