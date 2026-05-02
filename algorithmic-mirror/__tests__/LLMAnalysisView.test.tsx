// algorithmic-mirror/__tests__/LLMAnalysisView.test.tsx
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { LLMAnalysisView } from '../app/components/LLMAnalysisView';

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
    expect(screen.getByText('// AI ANALYSIS ENGINE')).toBeInTheDocument();
    expect(screen.getByText('CLAUDE 4.5')).toBeInTheDocument();
    expect(screen.getByText('GEMINI 3.1 PRO')).toBeInTheDocument();
    expect(screen.getByText('GEMINI 3.1 FLASH')).toBeInTheDocument();
  });

  test('back button calls onBack', () => {
    render(<LLMAnalysisView file={mockFile} apiUrl={apiUrl} onBack={mockOnBack} />);
    fireEvent.click(screen.getByText('← BACK'));
    expect(mockOnBack).toHaveBeenCalledTimes(1);
  });

  test('provider selection updates placeholder and state', () => {
    render(<LLMAnalysisView file={mockFile} apiUrl={apiUrl} onBack={mockOnBack} />);
    
    // Default is gemini-flash
    const input = screen.getByPlaceholderText('AIza...');
    expect(input).toBeInTheDocument();
    
    fireEvent.click(screen.getByText('CLAUDE 4.5'));
    expect(screen.getByPlaceholderText('sk-ant-...')).toBeInTheDocument();
  });

  test('saves API key to localStorage on run', async () => {
    render(<LLMAnalysisView file={mockFile} apiUrl={apiUrl} onBack={mockOnBack} />);
    
    const input = screen.getByPlaceholderText('AIza...');
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

    fireEvent.click(screen.getByText('RUN ANALYSIS →'));
    expect(localStorage.getItem('llm_api_key_gemini-flash')).toBe('test-key');
  });
});
