"use client";

import { createContext, useContext, useState, ReactNode } from "react";

interface DualityContextType {
  isMachineView: boolean;
  toggle: () => void;
}

const DualityContext = createContext<DualityContextType>({
  isMachineView: false,
  toggle: () => {},
});

export function DualityProvider({ children }: { children: ReactNode }) {
  const [isMachineView, setIsMachineView] = useState(false);

  return (
    <DualityContext.Provider
      value={{ isMachineView, toggle: () => setIsMachineView((v) => !v) }}
    >
      {children}
    </DualityContext.Provider>
  );
}

export const useDuality = () => useContext(DualityContext);
