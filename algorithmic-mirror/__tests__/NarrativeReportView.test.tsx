// algorithmic-mirror/__tests__/NarrativeReportView.test.tsx
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { NarrativeReportView } from '../app/components/NarrativeReportView';
import type { NarrativeBlock } from '../app/types/narrative';

// Mock recharts (same as BlockCard tests)
jest.mock('recharts', () => ({
  BarChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="bar-chart">{children}</div>
  ),
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  PieChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="pie-chart">{children}</div>
  ),
  Pie: () => null,
  Cell: () => null,
}));

const makeBlock = (id: string, title: string): NarrativeBlock => ({
  id,
  title,
  icon: "🔹",
  prose: `Prose for ${title}.`,
  accent: "#4db8ff",
  stats: [],
  chart: null,
  provenance: "Test provenance.",
});

const twoBlocks: NarrativeBlock[] = [
  makeBlock("b1", "FIRST BLOCK"),
  makeBlock("b2", "SECOND BLOCK"),
];

describe('NarrativeReportView', () => {
  test('renders DOSSIER header', () => {
    render(<NarrativeReportView narrativeBlocks={twoBlocks} onBack={jest.fn()} />);
    expect(screen.getByText('DOSSIER')).toBeInTheDocument();
  });

  test('renders all blocks', () => {
    render(<NarrativeReportView narrativeBlocks={twoBlocks} onBack={jest.fn()} />);
    expect(screen.getByText('FIRST BLOCK')).toBeInTheDocument();
    expect(screen.getByText('SECOND BLOCK')).toBeInTheDocument();
  });

  test('renders prose for each block', () => {
    render(<NarrativeReportView narrativeBlocks={twoBlocks} onBack={jest.fn()} />);
    expect(screen.getByText('Prose for FIRST BLOCK.')).toBeInTheDocument();
    expect(screen.getByText('Prose for SECOND BLOCK.')).toBeInTheDocument();
  });

  test('Back button calls onBack', () => {
    const onBack = jest.fn();
    render(<NarrativeReportView narrativeBlocks={twoBlocks} onBack={onBack} />);
    fireEvent.click(screen.getByRole('button', { name: /back/i }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  test('renders empty state gracefully with no blocks', () => {
    render(<NarrativeReportView narrativeBlocks={[]} onBack={jest.fn()} />);
    expect(screen.getByText('DOSSIER')).toBeInTheDocument();
  });
});
