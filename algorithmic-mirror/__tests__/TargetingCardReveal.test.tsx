import React from "react";
import { render, screen, act } from "@testing-library/react";
import { TargetingCard, __resetTargetingCardSeal } from "../app/components/TargetingCard";
import type { TargetingCardResult } from "../engine/targetingCard";

/**
 * WP-3.4a reveal-sequence regressions. The repo-wide framer-motion mock strips
 * `onAnimationComplete`, so the seal never "finishes" and the reveal can never
 * be observed. This file uses a local mock that fires the callback on mount,
 * which is what lets the once-per-session behaviour be tested at all.
 *
 * `style` is passed through deliberately: layout is the thing three of these
 * defects were about, and it is the only part of them jsdom can see.
 */
jest.mock("framer-motion", () => {
  const React = require("react");
  // Completions are queued rather than fired on mount, so a test can assert
  // the sealed state first and then advance the animation deliberately.
  const g = globalThis as unknown as { __motionDone: Array<() => void> };
  g.__motionDone = [];
  const motion = new Proxy(
    {},
    {
      get: (_t, tag: string) => ({ children, ...rest }: Record<string, unknown>) => {
        const { initial, animate, exit, transition, whileHover, whileTap, layout, onAnimationComplete, ...dom } =
          rest as Record<string, unknown>;
        void initial; void exit; void transition; void whileHover; void whileTap; void layout;
        if (typeof onAnimationComplete === "function") {
          g.__motionDone.push(onAnimationComplete as () => void);
        }
        // The animate target is the only trace of the reveal's timing that
        // survives into jsdom, so expose it for assertion rather than dropping
        // it with the other motion props.
        const withTarget = animate ? { ...dom, "data-animate": JSON.stringify(animate) } : dom;
        return React.createElement(tag, withTarget, children as React.ReactNode);
      },
    },
  );
  return {
    motion,
    AnimatePresence: ({ children }: any) => React.createElement(React.Fragment, null, children),
    useReducedMotion: jest.fn(() => false),
  };
});

/** Run every queued animation-complete callback, as framer-motion would. */
function finishAnimations() {
  const g = globalThis as unknown as { __motionDone: Array<() => void> };
  const queued = g.__motionDone.splice(0);
  act(() => { queued.forEach((cb) => cb()); });
}

const ok: TargetingCardResult = {
  moduleId: "targeting_card", status: "ok", taxonomy_version: "2026.03-1",
  counts: { declared_ad_interest_count: 5, segment_count: 1, confirmed_count: 1 },
  claims: [
    {
      id: "targeting.segment.education", tier: "inferred", confidence: 0.7,
      evidence: [{ kind: "video", id: "1" }],
      method: "…taxonomy 2026.03-1…",
      label: "Education", value: "Education",
    } as unknown as TargetingCardResult["claims"][number],
  ],
} as TargetingCardResult;

beforeEach(() => {
  __resetTargetingCardSeal();
  (globalThis as unknown as { __motionDone: Array<() => void> }).__motionDone = [];
});

describe("the seal reveals once per session", () => {
  it("shows the SEALED stamp on a first mount", () => {
    render(<TargetingCard result={ok} />);
    expect(screen.getByText("SEALED")).toBeInTheDocument();
  });

  it("does not re-seal when the component remounts", () => {
    // DossierShell renders tab bodies as `{activeTab === "interests" && …}`,
    // so leaving and returning to the tab unmounts and remounts this card.
    // Spec §5: "never re-seals — no re-trigger on … tab-switch".
    const first = render(<TargetingCard result={ok} />);
    expect(screen.getByText("SEALED")).toBeInTheDocument();
    finishAnimations();
    expect(screen.queryByText("SEALED")).not.toBeInTheDocument();
    first.unmount();

    render(<TargetingCard result={ok} />);
    expect(screen.queryByText("SEALED")).not.toBeInTheDocument();
  });

  it("still shows the card content after the remount", () => {
    const first = render(<TargetingCard result={ok} />);
    finishAnimations();
    first.unmount();
    render(<TargetingCard result={ok} />);
    expect(screen.getByText(/targetable/)).toBeInTheDocument();
  });
});

describe("the seal covers the card instead of displacing it", () => {
  it("positions the seal as an overlay, not a flow item", () => {
    // As a flex child the seal added ~90px of its own height, so the content
    // sat that much lower while sealed and snapped upward when it unmounted.
    render(<TargetingCard result={ok} />);
    const wrapper = screen.getByText("SEALED").parentElement as HTMLElement;
    expect(wrapper.style.position).toBe("absolute");
  });

  it("keeps the container a positioning context for that overlay", () => {
    render(<TargetingCard result={ok} />);
    const wrapper = screen.getByText("SEALED").parentElement as HTMLElement;
    const container = wrapper.parentElement as HTMLElement;
    expect(container.style.position).toBe("relative");
  });
});


describe("the content cross-fades with the seal rather than queueing behind it", () => {
  it("targets full opacity from mount, while the card is still sealed", () => {
    // Previously `animate={{ opacity: revealed ? 1 : 0 }}`: the content only
    // began its 0.15s-delayed fade once the seal's onAnimationComplete fired
    // at 0.4s, so the card was blank from 0.4s to 0.55s and the reveal did not
    // finish until ~0.95s. Spec §5 wants the two concurrent.
    render(<TargetingCard result={ok} />);
    expect(screen.getByText("SEALED")).toBeInTheDocument();

    const content = screen.getByText(/targetable/).closest("div[data-animate]") as HTMLElement;
    expect(JSON.parse(content.getAttribute("data-animate") as string)).toEqual({ opacity: 1 });
  });
});
