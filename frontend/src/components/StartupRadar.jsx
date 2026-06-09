import { useMemo } from "react";

// Generic axes-driven radar. Forked from RegRadar so it isn't bound to the
// bills domain. Caller passes `axes` (array of keys) and `scores` (object
// keyed by those axes, values 0-100). Optional `labels` override displayed
// names; optional `highlight` axis is rendered in gold like RegRadar's
// disclosure axis.

const SIZE = 360;
const CENTER = SIZE / 2;
const MAX_R = 130;

function angleFor(i, n) {
  return -Math.PI / 2 + (i * 2 * Math.PI) / n;
}

function pointFor(i, n, r) {
  const a = angleFor(i, n);
  return [CENTER + Math.cos(a) * r, CENTER + Math.sin(a) * r];
}

export default function StartupRadar({
  axes,
  scores,
  labels = {},
  animate = true,
  highlight = null,
}) {
  const n = axes.length;

  const polyPoints = useMemo(() => {
    return axes
      .map((a, i) => {
        const r = (Math.max(0, Math.min(100, scores[a] || 0)) / 100) * MAX_R;
        const [x, y] = pointFor(i, n, r);
        return `${x},${y}`;
      })
      .join(" ");
  }, [axes, scores, n]);

  const gridLevels = [0.25, 0.5, 0.75, 1.0];

  return (
    <svg
      width={SIZE}
      height={SIZE}
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      className="overflow-visible"
    >
      {gridLevels.map((lv, idx) => {
        const pts = axes
          .map((_, i) => pointFor(i, n, MAX_R * lv).join(","))
          .join(" ");
        return (
          <polygon
            key={idx}
            points={pts}
            fill="none"
            stroke="var(--border-border)"
            strokeWidth={1}
            opacity={0.6}
          />
        );
      })}

      {axes.map((_, i) => {
        const [x, y] = pointFor(i, n, MAX_R);
        return (
          <line
            key={i}
            x1={CENTER}
            y1={CENTER}
            x2={x}
            y2={y}
            stroke="var(--border-muted)"
            strokeWidth={1}
          />
        );
      })}

      <polygon
        points={polyPoints}
        fill="rgba(201, 182, 232, 0.45)"
        stroke="var(--bg-action-dark)"
        strokeWidth={2.5}
        strokeLinejoin="round"
        style={{
          opacity: animate ? 1 : 0,
          transform: animate ? "scale(1)" : "scale(0.2)",
          transformOrigin: `${CENTER}px ${CENTER}px`,
          transition:
            "opacity 0.3s ease-out, transform 0.5s cubic-bezier(0.16,1,0.3,1)",
        }}
      />

      {axes.map((a, i) => {
        const r = (Math.max(0, Math.min(100, scores[a] || 0)) / 100) * MAX_R;
        const [x, y] = pointFor(i, n, r);
        const isHi = highlight === a;
        return (
          <circle
            key={a}
            cx={x}
            cy={y}
            r={isHi ? 5 : 3.5}
            fill={isHi ? "var(--accent-gold)" : "var(--bg-action-dark)"}
            style={{
              opacity: animate ? 1 : 0,
              transition: "opacity 0.35s ease-out 0.2s",
            }}
          />
        );
      })}

      {axes.map((a, i) => {
        const [lx, ly] = pointFor(i, n, MAX_R + 24);
        const isHi = highlight === a;
        const text = labels[a] || a;
        return (
          <text
            key={a}
            x={lx}
            y={ly}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize={11}
            fontWeight={isHi ? 700 : 500}
            fill={isHi ? "var(--accent-gold)" : "var(--text-secondary)"}
            style={{ letterSpacing: 0.3 }}
          >
            {text}
          </text>
        );
      })}
    </svg>
  );
}
