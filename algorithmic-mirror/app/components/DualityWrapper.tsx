"use client";

import { useEffect } from "react";
import { DualityProvider, useDuality } from "../context/DualityContext";

function ThemeApplicator({ children }: { children: React.ReactNode }) {
  const { isMachineView } = useDuality();

  useEffect(() => {
    const html = document.documentElement;
    if (isMachineView) {
      html.setAttribute("data-theme", "machine");
    } else {
      html.removeAttribute("data-theme");
    }
  }, [isMachineView]);

  return <>{children}</>;
}

export function DualityWrapper({ children }: { children: React.ReactNode }) {
  return (
    <DualityProvider>
      <ThemeApplicator>{children}</ThemeApplicator>
    </DualityProvider>
  );
}
