// Renders ForensicDashboard against a REAL analyzed export payload to prove the
// rewired panels execute and surface concrete data. Payload produced by POSTing
// the vault's user_data_tiktok.json to /api/analyze (see /tmp/ttk_profile.json).
import React from 'react';
import fs from 'fs';
import { render, screen, fireEvent } from '@testing-library/react';
import { ForensicDashboard } from '../app/components/ForensicDashboard';
import type { GhostProfile } from '../app/components/GhostProfileHUD';

// CreatorGraph (network tab) pulls in recharts/SVG — mock to keep jsdom happy.
jest.mock('../app/components/CreatorGraph', () => ({
  CreatorGraph: () => <div data-testid="creator-graph" />,
}));

// framer-motion 12 is ESM; under ts-jest (CJS) `motion`/`AnimatePresence`
// resolve undefined. Stub them to plain DOM passthroughs.
jest.mock('framer-motion', () => {
  const React = require('react');
  const motion = new Proxy(
    {},
    {
      get: (_t, tag: string) =>
        ({ children, ...rest }: Record<string, unknown>) => {
          // drop animation-only props that aren't valid DOM attributes
          const { initial, animate, exit, transition, whileHover, whileTap, onAnimationComplete, ...domProps } =
            rest as Record<string, unknown>;
          void initial; void animate; void exit; void transition; void whileHover; void whileTap; void onAnimationComplete;
          return React.createElement(tag, domProps, children as React.ReactNode);
        },
    }
  );
  return {
    motion,
    AnimatePresence: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    useReducedMotion: () => false,
  };
});

const FIXTURE = '/tmp/ttk_profile.json';
const hasFixture = fs.existsSync(FIXTURE);
const maybe = hasFixture ? describe : describe.skip;

maybe('ForensicDashboard · real export', () => {
  // describe.skip still runs the body — only read the fixture when it exists,
  // otherwise the suite errors at collection instead of skipping cleanly.
  const profile = (hasFixture ? JSON.parse(fs.readFileSync(FIXTURE, 'utf-8')) : {}) as GhostProfile;
  const sourceFile = new File(['{}'], 'user_data_tiktok.json', { type: 'application/json' });

  function mount() {
    return render(
      <ForensicDashboard profile={profile} onReset={jest.fn()} sourceFile={sourceFile} />
    );
  }

  it('renders the overview without throwing', () => {
    mount();
    // archetype headline proves the component returned JSX (the bug we fixed)
    expect(screen.getByText(/Who TikTok Thinks You Are/i)).toBeInTheDocument();
  });

  it('Behavior tab renders without crashing (backend sends total_raw_videos, not total_videos)', () => {
    mount();
    fireEvent.click(screen.getByText(/Behavioral Signature/i));
    // StopwatchFunnel reads the raw-video count; backend field is total_raw_videos.
    // Reading the (absent) total_videos used to throw on .toLocaleString().
    expect(screen.getByText(/True Stopwatch Funnel/i)).toBeInTheDocument();
    expect(screen.getByText(/Engagement Authenticity/i)).toBeInTheDocument();
  });

  it('Privacy tab shows real footprint + off-platform + shop purchases', () => {
    mount();
    fireEvent.click(screen.getByText(/Privacy & Footprint/i));
    expect(screen.getByText(/Off-Platform Surveillance/i)).toBeInTheDocument();
    // 121 unique IPs in this export
    expect(screen.getByText(String(profile.digital_footprint!.unique_ips))).toBeInTheDocument();
    // shop products were dropped by the parser before the fix; now they render
    expect(screen.getByText(/On-Platform Purchases/i)).toBeInTheDocument();
    expect(screen.getByText(/Unofficial Sims Cookbook/i)).toBeInTheDocument();
    // product browsing history (180 viewed) — newly parsed, was dropped entirely
    expect(screen.getByText(/Products You Considered/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Survival Projects/i).length).toBeGreaterThan(0);
  });

  it('Interests tab renders the advertiser-labels panel (scaffold + honest empty state)', () => {
    mount();
    fireEvent.click(screen.getByText(/Interests & Keywords/i));
    expect(screen.getByText(/Audience Labels Sold To Advertisers/i)).toBeInTheDocument();
  });

  it('Network tab renders the YouTube cross-platform bridge panel when a creator is enriched', () => {
    // inject a bridged creator (prototype enrichment from utils/youtube_bridge)
    const p = JSON.parse(JSON.stringify(profile)) as GhostProfile;
    p.creator_entities.vibe_cluster[0] = {
      ...p.creator_entities.vibe_cluster[0],
      handle: '@mkbhd',
      youtube: {
        channel_title: 'Marques Brownlee',
        channel_url: 'https://youtube.com/@mkbhd',
        topics: ['Technology', 'Consumer Electronics'],
        description: 'Quality tech videos.',
        subscriber_text: '19.5M subscribers',
        match: 'name_verified',
        source: 'keyless',
      },
    };
    render(<ForensicDashboard profile={p} onReset={jest.fn()} sourceFile={sourceFile} />);
    fireEvent.click(screen.getByText(/Network & Influence/i));
    expect(screen.getByText(/Cross-Platform Resolution/i)).toBeInTheDocument();
    expect(screen.getByText(/Marques Brownlee/i)).toBeInTheDocument();
    expect(screen.getByText(/Consumer Electronics/i)).toBeInTheDocument();
    expect(screen.getByText(/name verified/i)).toBeInTheDocument();
  });
});
