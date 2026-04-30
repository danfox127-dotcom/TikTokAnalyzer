import React from 'react';
import { render, screen } from '@testing-library/react';
import { GhostProfileHUD } from '../app/components/GhostProfileHUD';

const minimalProfile: any = {
  status: 'success',
  stopwatch_metrics: {
    total_conscious_videos: 1,
    sleep_anomalies_scrubbed: 0,
    graveyard_skips: 0,
    sandbox_views: 0,
    deep_lingers: 1,
    total_videos: 1,
    hourly_heatmap: {},
  },
  behavioral_nodes: {
    peak_hour: '12',
    skip_rate_percentage: 0,
    linger_rate_percentage: 0,
    night_shift_ratio: 0,
    night_linger_pct: 0,
    night_lingers_count: 0,
    social_graph_algorithmic_pct: 0,
    social_graph_followed_pct: 0,
  },
  creator_entities: { vibe_cluster: [], graveyard: [] },
  declared_signals: {},
};

test('renders failed badge for video with failed fetch', () => {
  const enrichment: any = {
    videos: {
      lingered: [
        {
          video_id: '1',
          link: 'https://tiktok.com/@x/video/1',
          time_spent: 20,
          hour: 10,
          title: 'Test title',
          author: 'creator',
          author_name: 'Creator',
          thumbnail: 'https://example.com/thumb.jpg',
        },
      ],
      graveyard: [],
      sandbox: [],
      night_lingered: [],
    },
    video_results: { '1': { status: 'failed', error: '404 not found' } },
    top_creators: { lingered: [], graveyard: [] },
    themes: {
      psychographic: { top_keywords: [], top_phrases: [] },
      anti_profile: { top_keywords: [], top_phrases: [] },
      sandbox: { top_keywords: [], top_phrases: [] },
      night: { top_keywords: [], top_phrases: [] },
    },
    following_ratio: { followed_pct: 0, algorithmic_pct: 0, matched_videos: 0 },
    fetched_count: 0,
    requested_count: 1,
  };

  render(<GhostProfileHUD profile={minimalProfile} onReset={() => {}} enrichment={enrichment} enrichmentLoading={false} />);

  // badge uses title attr with the error message
  expect(screen.getByTitle('404 not found')).toBeTruthy();
  // link to the video should exist
  expect(document.querySelector('a[href="https://tiktok.com/@x/video/1"]')).toBeTruthy();
});
