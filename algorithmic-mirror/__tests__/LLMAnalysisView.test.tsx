// algorithmic-mirror/__tests__/LLMAnalysisView.test.tsx
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { LLMAnalysisView } from '../app/components/LLMAnalysisView';

// framer-motion 12 is ESM; under ts-jest (CJS) `motion`/`AnimatePresence` resolve
// undefined ("Element type is invalid"). Stub them to plain DOM passthroughs.
jest.mock('framer-motion', () => {
  const React = require('react');
  const motion = new Proxy(
    {},
    {
      get: (_t, tag: string) =>
        ({ children, ...rest }: Record<string, unknown>) => {
          const { initial, animate, exit, transition, whileHover, whileTap, ...domProps } =
            rest as Record<string, unknown>;
          void initial; void animate; void exit; void transition; void whileHover; void whileTap;
          return React.createElement(tag, domProps, children as React.ReactNode);
        },
    }
  );
  return {
    motion,
    AnimatePresence: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
  };
});

describe('LLMAnalysisView', () => {
  const mockFile = new File(['{}'], 'test.json', { type: 'application/json' });
  const mockOnBack = jest.fn();
  const apiUrl = 'http://localhost:8005';

  beforeEach(() => {
    localStorage.clear();
    jest.clearAllMocks();
  });

  test('renders header and provider buttons', () => {
    render(<LLMAnalysisView file={mockFile} apiUrl={apiUrl} onBack={mockOnBack} />);
    expect(screen.getByText('AI Analysis')).toBeInTheDocument();
    expect(screen.getByText('Claude')).toBeInTheDocument();
    expect(screen.getByText('Gemini Pro')).toBeInTheDocument();
    expect(screen.getByText('Gemini Flash')).toBeInTheDocument();
  });

  test('back button calls onBack', () => {
    render(<LLMAnalysisView file={mockFile} apiUrl={apiUrl} onBack={mockOnBack} />);
    fireEvent.click(screen.getByText('← Back to the Story'));
    expect(mockOnBack).toHaveBeenCalledTimes(1);
  });

  test('provider selection updates placeholder and state', () => {
    render(<LLMAnalysisView file={mockFile} apiUrl={apiUrl} onBack={mockOnBack} />);
    
    // Default is gemini-flash
    const input = screen.getByPlaceholderText('AIza…');
    expect(input).toBeInTheDocument();
    
    fireEvent.click(screen.getByText('Claude'));
    expect(screen.getByPlaceholderText('sk-ant-…')).toBeInTheDocument();
  });

  test('saves API key to localStorage on run', async () => {
    render(<LLMAnalysisView file={mockFile} apiUrl={apiUrl} onBack={mockOnBack} />);
    
    const input = screen.getByPlaceholderText('AIza…');
    fireEvent.change(input, { target: { value: 'test-key' } });
    
    // Mock fetch
    global.fetch = jest.fn().mockImplementation(() => 
      Promise.resolve({
        ok: true,
        body: {
          getReader: () => ({
            read: () => Promise.resolve({ done: true, value: undefined })
          })
        }
      })
    );

    fireEvent.click(screen.getByText('Run Analysis →'));
    expect(localStorage.getItem('llm_api_key_gemini-flash')).toBe('test-key');
  });
});
