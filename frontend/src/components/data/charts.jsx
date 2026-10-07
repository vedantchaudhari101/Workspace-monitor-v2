/**
 * Chart components on top of Recharts, styled with the design tokens.
 * Charts draw in when they mount; pages mount them as they scroll into view.
 */

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useState } from "react";
import { useReducedMotion } from "motion/react";
import { tokens } from "../../theme";
import { hourLabel, pct } from "../../lib/format";
import "./data.css";

const axis = { stroke: tokens.text3, fontSize: 11, tickLine: false, axisLine: false };

function Tip({ active, payload, label, xFormat, yFormat, yLabel }) {
  if (!active || !payload?.length) return null;
  const v = payload[0].value;
  return (
    <div className="chart-tip">
      <div className="muted">{xFormat ? xFormat(label) : label}</div>
      <div>
        {yLabel}: <strong>{v === null || v === undefined ? "not observed" : yFormat ? yFormat(v) : v}</strong>
      </div>
    </div>
  );
}

export function TimeArea({
  data,
  xKey,
  yKey,
  height = 260,
  yDomain = [0, 100],
  yFormat = (v) => pct(v),
  xFormat,
  yLabel = "Occupancy",
  highlight,
  color = tokens.scan,
  id = "area",
}) {
  const reduce = useReducedMotion();
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
        <defs>
          <linearGradient id={`grad-${id}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.28} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={tokens.line} vertical={false} />
        <XAxis dataKey={xKey} {...axis} tickFormatter={xFormat} minTickGap={36} />
        <YAxis {...axis} domain={yDomain} tickFormatter={yFormat} width={52} allowDecimals={false} />
        {highlight && (
          <ReferenceArea x1={highlight.x1} x2={highlight.x2} fill={tokens.occupied} fillOpacity={0.08} stroke="none" ifOverflow="extendDomain" />
        )}
        <Tooltip
          cursor={{ stroke: tokens.lineStrong }}
          content={<Tip xFormat={xFormat} yFormat={yFormat} yLabel={yLabel} />}
        />
        <Area
          type="monotone"
          dataKey={yKey}
          stroke={color}
          strokeWidth={1.8}
          fill={`url(#grad-${id})`}
          connectNulls={false}
          isAnimationActive={!reduce}
          animationDuration={900}
          dot={data.filter((d) => d[yKey] !== null && d[yKey] !== undefined).length < 4 ? { r: 3, fill: color, stroke: "none" } : false}
          activeDot={{ r: 3, fill: color, stroke: tokens.bg }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function HourlyBars({ hourly, height = 220 }) {
  const reduce = useReducedMotion();
  const vals = hourly.map((h) => h.occupancy_pct).filter((v) => v !== null);
  const max = vals.length ? Math.max(...vals) : null;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={hourly} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
        <CartesianGrid stroke={tokens.line} vertical={false} />
        <XAxis dataKey="hour" {...axis} tickFormatter={(h) => (h % 3 === 0 ? hourLabel(h) : "")} interval={0} />
        <YAxis {...axis} domain={[0, 100]} tickFormatter={(v) => `${v}%`} width={52} />
        <Tooltip
          cursor={{ fill: "rgba(255,255,255,0.03)" }}
          content={<Tip xFormat={(h) => `${hourLabel(h)}–${hourLabel((h + 1) % 24)}`} yFormat={(v) => pct(v)} yLabel="Average occupancy" />}
        />
        <Bar dataKey="occupancy_pct" radius={[3, 3, 0, 0]} isAnimationActive={!reduce} animationDuration={700}>
          {hourly.map((h) => (
            <Cell key={h.hour} fill={h.occupancy_pct !== null && h.occupancy_pct === max ? tokens.occupied : tokens.text3} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function Heatmap({ heatmap, onSelect, cap = 30 }) {
  const [all, setAll] = useState(false);
  const hours = heatmap.hours;
  const observed = heatmap.seats.filter((s) => s.values.some((v) => v !== null));
  const rows = all ? observed : observed.slice(0, cap);
  const observedHours = hours.filter((h) => heatmap.seats.some((s) => s.values[h] !== null));
  if (!observedHours.length) return null;
  const from = Math.min(...observedHours);
  const to = Math.max(...observedHours);
  const cols = hours.filter((h) => h >= from && h <= to);
  return (
    <div className="heatmap" role="region" aria-label="Seat utilization by hour of day" tabIndex={0}>
      <table>
        <thead>
          <tr>
            <th aria-label="Seat" />
            {cols.map((h) => (
              <th key={h} scope="col">
                {String(h).padStart(2, "0")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.seat_id}>
              <th scope="row">
                {onSelect ? (
                  <button type="button" className="mono" onClick={() => onSelect(s)}>
                    {s.seat_label}
                  </button>
                ) : (
                  <span className="mono">{s.seat_label}</span>
                )}
              </th>
              {cols.map((h) => {
                const v = s.values[h];
                if (v === null) return <td key={h} className="empty" title={`${s.seat_label} ${hourLabel(h)}: not observed`} />;
                const a = 0.08 + (v / 100) * 0.85;
                return (
                  <td
                    key={h}
                    title={`${s.seat_label} ${hourLabel(h)}: ${v.toFixed(0)}% occupied`}
                    style={{ background: `rgba(255, 90, 95, ${a.toFixed(3)})` }}
                  />
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="row xs faint" style={{ marginTop: 8 }}>
        <span>0%</span>
        <span style={{ width: 120, height: 8, borderRadius: 4, background: "linear-gradient(90deg, rgba(255,90,95,0.08), rgba(255,90,95,0.93))" }} />
        <span>100% of observed time occupied</span>
        {observed.length > cap && (
          <button type="button" className="btn btn-ghost btn-sm" style={{ marginLeft: "auto" }} onClick={() => setAll((v) => !v)}>
            {all ? `Show first ${cap} seats` : `Show all ${observed.length} seats`}
          </button>
        )}
      </div>
    </div>
  );
}

export function Gauge({ value, size = 180, label }) {
  const r = size / 2 - 10;
  const c = Math.PI * r;
  const v = Math.max(0, Math.min(100, value ?? 0));
  const tone = v >= 70 ? tokens.available : v >= 40 ? tokens.warn : tokens.occupied;
  return (
    <svg width={size} height={size / 2 + 14} viewBox={`0 0 ${size} ${size / 2 + 14}`} role="img" aria-label={`${label}: ${value ?? "not available"}`}>
      <path d={`M10 ${size / 2} A ${r} ${r} 0 0 1 ${size - 10} ${size / 2}`} fill="none" stroke={tokens.surface3} strokeWidth="10" strokeLinecap="round" />
      <path
        d={`M10 ${size / 2} A ${r} ${r} 0 0 1 ${size - 10} ${size / 2}`}
        fill="none"
        stroke={tone}
        strokeWidth="10"
        strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={c * (1 - v / 100)}
        style={{ transition: "stroke-dashoffset 900ms cubic-bezier(0.22,1,0.36,1)" }}
      />
    </svg>
  );
}

export function IntervalBar({ intervals, since, until }) {
  const s0 = new Date(since).getTime();
  const s1 = new Date(until).getTime();
  const span = Math.max(1, s1 - s0);
  return (
    <div className="ivbar" role="img" aria-label="Occupancy over the selected window">
      {intervals.map((iv, i) => {
        const a = Math.max(s0, new Date(iv.start).getTime());
        const b = Math.min(s1, new Date(iv.end).getTime());
        const w = ((b - a) / span) * 100;
        if (w <= 0) return null;
        return <span key={i} className={`iv-${iv.status}`} style={{ width: `${w}%` }} title={`${iv.status} ${Math.round(iv.duration_s)}s`} />;
      })}
    </div>
  );
}
