import { useMemo } from "react";

const AXES = ["emissions", "water", "packaging", "labor", "disclosure"];

const SIZE = 360;
const CENTER = SIZE / 2;
const MAX_R = 130;

// Angle for each axis: starting at top (12 o'clock), going clockwise.
function angleFor(i) {
  return -Math.PI / 2 + (i * 2 * Math.PI) / AXES.length;
}

function pointFor(i, r) {
  const a = angleFor(i);
  return [CENTER + Math.cos(a) * r, CENTER + Math.sin(a) * r];
}

export default function RegRadar({ scores, animate }) {
  const polyPoints = useMemo(() => {
    return AXES.map((a, i) => {
      const r = (Math.max(0, Math.min(100, scores[a])) / 100) * MAX_R;
      const [x, y] = pointFor(i, r);
      return `${x},${y}`;
    }).join(" ");
  }, [scores]);

  // Background grid: 4 concentric pentagons at 25/50/75/100% of MAX_R.
  const gridLevels = [0.25, 0.5, 0.75, 1.0];

  return (
    <svg
      width={SIZE}
      height={SIZE}
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      className="overflow-visible"
    >
      {/* Background pentagons */}
      {gridLevels.map((lv, idx) => {
        const pts = AXES.map((_, i) => pointFor(i, MAX_R * lv).join(",")).join(" ");
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

      {/* Axis lines from center to each vertex */}
      {AXES.map((_, i) => {
        const [x, y] = pointFor(i, MAX_R);
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

      {/* Score polygon — animated fill / stroke */}
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
          transition: "opacity 0.3s ease-out, transform 0.5s cubic-bezier(0.16,1,0.3,1)",
        }}
      />

      {/* Vertex dots */}
      {AXES.map((a, i) => {
        const r = (Math.max(0, Math.min(100, scores[a])) / 100) * MAX_R;
        const [x, y] = pointFor(i, r);
        const highlight = a === "disclosure";
        return (
          <circle
            key={a}
            cx={x}
            cy={y}
            r={highlight ? 5 : 3.5}
            fill={highlight ? "var(--accent-gold)" : "var(--bg-action-dark)"}
            style={{
              opacity: animate ? 1 : 0,
              transition: "opacity 0.35s ease-out 0.2s",
            }}
          />
        );
      })}

      {/* Axis labels */}
      {AXES.map((a, i) => {
        const [lx, ly] = pointFor(i, MAX_R + 22);
        const isDisclosure = a === "disclosure";
        return (
          <text
            key={a}
            x={lx}
            y={ly}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize={12}
            fontWeight={isDisclosure ? 700 : 500}
            fill={isDisclosure ? "var(--accent-gold)" : "var(--text-secondary)"}
            style={{ textTransform: "capitalize", letterSpacing: 0.3 }}
          >
            {a}
          </text>
        );
      })}
    </svg>
  );
}
