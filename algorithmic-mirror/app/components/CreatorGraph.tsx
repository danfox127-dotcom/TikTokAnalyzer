// algorithmic-mirror/app/components/CreatorGraph.tsx
"use client";

import { motion } from "framer-motion";
import { useMemo } from "react";

interface Node {
  name: string;
  size: number;
  is_followed: boolean;
  genre: string;
}

interface Props {
  data: any[]; // will cast to Node[]
}

export function CreatorGraph({ data }: Props) {
  const nodes = data as Node[];

  // Split nodes
  const followed = nodes.filter(n => n.is_followed);
  const algorithmic = nodes.filter(n => !n.is_followed);

  // Constants
  const width = 640;
  const height = 320;
  const padding = 60;
  const colWidth = (width - padding * 2) / 2;

  // Scales
  const maxSize = Math.max(...nodes.map(n => n.size), 1);
  const getRadius = (s: number) => Math.sqrt(s / maxSize) * 30 + 4;

  // Simple deterministic layout for circles within columns
  const layoutNodes = (items: Node[], xOffset: number) => {
    return items.map((n, i) => {
      // Row/column positioning within the pane
      const row = Math.floor(i / 3);
      const col = i % 3;
      return {
        ...n,
        x: xOffset + 40 + col * (colWidth / 3),
        y: 60 + row * 60 + (i % 2 === 0 ? 10 : -10), // slight jitter
      };
    });
  };

  const followedNodes = layoutNodes(followed, padding);
  const algorithmicNodes = layoutNodes(algorithmic, width / 2 + 10);

  return (
    <div style={{ position: "relative", width: "100%", height, background: "rgba(0,0,0,0.2)", border: "1px solid #222", overflow: "hidden" }}>
      {/* Column Labels */}
      <div style={{ position: "absolute", top: 12, left: padding, fontSize: 9, color: "#666", letterSpacing: "0.2em", fontFamily: "var(--font-mono, monospace)" }}>
        THE VILLAGE (FOLLOWED)
      </div>
      <div style={{ position: "absolute", top: 12, right: padding, fontSize: 9, color: "#666", letterSpacing: "0.2em", textAlign: "right", fontFamily: "var(--font-mono, monospace)" }}>
        THE MACHINE (ALGORITHMIC)
      </div>

      <svg width="100%" height="100%" viewBox={`0 0 ${width} ${height}`}>
        {/* Center Divider */}
        <line x1={width / 2} y1={40} x2={width / 2} y2={height - 20} stroke="#333" strokeDasharray="4 4" />

        {/* Nodes */}
        {[...followedNodes, ...algorithmicNodes].map((n, i) => (
          <motion.g
            key={n.name}
            initial={{ opacity: 0, scale: 0 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.05, duration: 0.5 }}
          >
            <circle
              cx={n.x}
              cy={n.y}
              r={getRadius(n.size)}
              fill={n.is_followed ? "#4db8ff" : "#ff4db8"}
              fillOpacity={0.15}
              stroke={n.is_followed ? "#4db8ff" : "#ff4db8"}
              strokeWidth={1}
            />
            <circle
                cx={n.x}
                cy={n.y}
                r={2}
                fill={n.is_followed ? "#4db8ff" : "#ff4db8"}
            />
            {/* Hover Tooltip equivalent (simple title for now) */}
            <title>{`${n.name}\nGenre: ${n.genre}\nViews: ${n.size}`}</title>
            
            {/* Label for larger nodes */}
            {n.size > maxSize * 0.3 && (
              <text
                x={n.x}
                y={n.y + getRadius(n.size) + 12}
                fill="#888"
                fontSize={8}
                textAnchor="middle"
                fontFamily="var(--font-mono, monospace)"
              >
                {n.name}
              </text>
            )}
          </motion.g>
        ))}
      </svg>
      
      {/* Legend */}
      <div style={{ position: "absolute", bottom: 12, left: 0, right: 0, display: "flex", justifyContent: "center", gap: 24 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#4db8ff" }} />
              <span style={{ fontSize: 8, color: "#888", letterSpacing: "0.1em" }}>EXPLICIT SIGNAL</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#ff4db8" }} />
              <span style={{ fontSize: 8, color: "#888", letterSpacing: "0.1em" }}>IMPLICIT CAPTURE</span>
          </div>
      </div>
    </div>
  );
}
