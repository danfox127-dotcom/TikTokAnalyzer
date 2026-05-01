// algorithmic-mirror/__tests__/BlockCard.test.tsx
import React from 'react';
import { render, screen } from '@testing-library/react';
import { BlockCard } from '../app/components/BlockCard';
import type { NarrativeBlock } from '../app/types/narrative';

// Recharts uses ResizeObserver and SVG dimensions unavailable in jsdom — mock it
jest.mock('recharts', () => ({
  BarChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="bar-chart">{children}</div>
  ),
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div style={{ width: '100%', height: '100%' }}>{children}</div>
  ),
  PieChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="pie-chart">{children}</div>
  ),
  Pie: () => null,
  Cell: () => null,
}));

const mockBarBlock: NarrativeBlock = {
  id: "test_block",
  title: "TEST BLOCK",
  icon: "🧪",
  prose: "This is the test prose paragraph.",
  accent: "#4db8ff",
  stats: [
    { label: "Metric A", value: "42%" },
    { label: "Metric B", value: "100" },
  ],
  chart: {
    type: "bar",
    data: [{ metric: "X", value: 10 }, { metric: "Y", value: 20 }],
  },
};

const mockDonutBlock: NarrativeBlock = {
  ...mockBarBlock,
  id: "donut_block",
  chart: { type: "donut", data: [{ name: "A", value: 30 }, { name: "B", value: 70 }] },
};

const mockNoChartBlock: NarrativeBlock = {
  ...mockBarBlock,
  id: "no_chart_block",
  chart: null,
};

describe('BlockCard', () => {
  test('renders icon and title', () => {
    render(<BlockCard block={mockBarBlock} />);
    expect(screen.getByText('🧪')).toBeInTheDocument();
    expect(screen.getByText('TEST BLOCK')).toBeInTheDocument();
  });

  test('renders prose', () => {
    render(<BlockCard block={mockBarBlock} />);
    expect(screen.getByText('This is the test prose paragraph.')).toBeInTheDocument();
  });

  test('renders stats labels and values', () => {
    render(<BlockCard block={mockBarBlock} />);
    expect(screen.getByText('Metric A')).toBeInTheDocument();
    expect(screen.getByText('42%')).toBeInTheDocument();
    expect(screen.getByText('Metric B')).toBeInTheDocument();
    expect(screen.getByText('100')).toBeInTheDocument();
  });

  test('renders bar chart for bar type', () => {
    render(<BlockCard block={mockBarBlock} />);
    expect(screen.getByTestId('bar-chart')).toBeInTheDocument();
    expect(screen.queryByTestId('pie-chart')).not.toBeInTheDocument();
  });

  test('renders pie chart for donut type', () => {
    render(<BlockCard block={mockDonutBlock} />);
    expect(screen.getByTestId('pie-chart')).toBeInTheDocument();
    expect(screen.queryByTestId('bar-chart')).not.toBeInTheDocument();
  });

  test('renders no chart when chart is null', () => {
    render(<BlockCard block={mockNoChartBlock} />);
    expect(screen.queryByTestId('bar-chart')).not.toBeInTheDocument();
    expect(screen.queryByTestId('pie-chart')).not.toBeInTheDocument();
  });

  test('renders no stats section when stats is empty', () => {
    const noStatsBlock: NarrativeBlock = { ...mockBarBlock, stats: [], chart: null };
    render(<BlockCard block={noStatsBlock} />);
    // Prose still visible
    expect(screen.getByText('This is the test prose paragraph.')).toBeInTheDocument();
    // No stat labels
    expect(screen.queryByText('Metric A')).not.toBeInTheDocument();
  });
});
