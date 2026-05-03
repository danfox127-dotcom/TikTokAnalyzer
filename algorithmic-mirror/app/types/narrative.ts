// algorithmic-mirror/app/types/narrative.ts

export interface NarrativeStat {
  label: string;
  value: string;
}

export interface NarrativeChart {
  type: "bar" | "line" | "donut" | "creator_graph";
  data: Record<string, unknown>[];
}

export interface NarrativeBlock {
  id: string;
  title: string;
  icon: string;
  prose: string;
  accent: string;
  stats: NarrativeStat[];
  chart?: NarrativeChart | null;
  provenance: string;
}
