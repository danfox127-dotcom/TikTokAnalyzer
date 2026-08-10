"use client";
/** WP-3.1 — extracted from the former monolithic ForensicDashboard.tsx, verbatim. */
import { LLMAnalysisView } from "../LLMAnalysisView";

export function AiTab({ sourceFile, apiUrl, onBack }: { sourceFile: File; apiUrl: string; onBack: () => void }) {
  return (
    <div>
      <LLMAnalysisView
        file={sourceFile}
        apiUrl={apiUrl}
        onBack={onBack}
      />
    </div>
  );
}
