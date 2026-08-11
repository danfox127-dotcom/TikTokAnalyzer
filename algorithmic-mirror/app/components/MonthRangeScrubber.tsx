"use client";
/**
 * WP-3.3 — dual-handle month-range scrubber. Two overlaid native
 * <input type="range"> thumbs sharing one visual track (styles in
 * globals.css under .month-scrubber-input); no new dependency.
 */
import { BORDER, ACCENT, INK_DIM } from "./dashboardPrimitives";

export interface MonthRangeScrubberProps {
  months: string[];
  value: [string, string];
  onChange: (range: [string, string]) => void;
}

export function MonthRangeScrubber({ months, value, onChange }: MonthRangeScrubberProps) {
  const maxIndex = months.length - 1;
  const startIndex = months.indexOf(value[0]);
  const endIndex = months.indexOf(value[1]);

  function handleStartChange(e: React.ChangeEvent<HTMLInputElement>) {
    const next = Math.min(Number(e.target.value), endIndex);
    onChange([months[next], months[endIndex]]);
  }
  function handleEndChange(e: React.ChangeEvent<HTMLInputElement>) {
    const next = Math.max(Number(e.target.value), startIndex);
    onChange([months[startIndex], months[next]]);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, padding: "16px 0" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, fontFamily: "var(--font-mono, monospace)", color: INK_DIM, letterSpacing: "0.1em" }}>
        <span>{value[0]}</span>
        <span>{value[1]}</span>
      </div>
      <div style={{ position: "relative", height: 24 }}>
        <div style={{ position: "absolute", top: 11, left: 0, right: 0, height: 2, background: BORDER }} />
        <div
          style={{
            position: "absolute",
            top: 11,
            height: 2,
            background: ACCENT,
            left: `${(startIndex / maxIndex) * 100}%`,
            right: `${100 - (endIndex / maxIndex) * 100}%`,
          }}
        />
        <input
          type="range"
          className="month-scrubber-input"
          aria-label="Start month"
          min={0}
          max={maxIndex}
          value={startIndex}
          onChange={handleStartChange}
        />
        <input
          type="range"
          className="month-scrubber-input"
          aria-label="End month"
          min={0}
          max={maxIndex}
          value={endIndex}
          onChange={handleEndChange}
        />
      </div>
    </div>
  );
}
