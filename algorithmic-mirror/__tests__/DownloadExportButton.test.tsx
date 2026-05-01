import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { DownloadExportButton } from '../app/components/DownloadExportButton';

const mockFile = new File(['{}'], 'user_data_tiktok.json', { type: 'application/json' });
const API_URL = 'http://localhost:8005';

beforeEach(() => {
  jest.resetAllMocks();
  // URL.createObjectURL and revokeObjectURL are not in jsdom
  global.URL.createObjectURL = jest.fn(() => 'blob:mock');
  global.URL.revokeObjectURL = jest.fn();
});

test('renders idle button with label', () => {
  render(<DownloadExportButton file={mockFile} apiUrl={API_URL} />);
  expect(screen.getByRole('button', { name: /download for llm/i })).toBeInTheDocument();
});

test('shows loading state while fetching', async () => {
  global.fetch = jest.fn(() => new Promise(() => {})) as jest.Mock; // never resolves
  render(<DownloadExportButton file={mockFile} apiUrl={API_URL} />);
  fireEvent.click(screen.getByRole('button'));
  expect(await screen.findByText(/downloading/i)).toBeInTheDocument();
  expect(screen.getByRole('button')).toBeDisabled();
});

test('triggers download on success', async () => {
  const mockBlob = new Blob(['{"_meta":{}}'], { type: 'application/json' });
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, blob: () => Promise.resolve(mockBlob) })
  ) as jest.Mock;

  // Spy on document.createElement to capture the anchor click
  const clickSpy = jest.fn();
  const origCreate = document.createElement.bind(document);
  const createElementSpy = jest.spyOn(document, 'createElement').mockImplementation((tag: string) => {
    const el = origCreate(tag);
    if (tag === 'a') { el.click = clickSpy; }
    return el;
  });

  render(<DownloadExportButton file={mockFile} apiUrl={API_URL} />);
  fireEvent.click(screen.getByRole('button'));

  await waitFor(() => expect(clickSpy).toHaveBeenCalled());
  expect(URL.createObjectURL).toHaveBeenCalledWith(mockBlob);
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock');

  createElementSpy.mockRestore();
});

test('shows error message on fetch failure then resets to idle', async () => {
  jest.useFakeTimers();
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: false, json: () => Promise.resolve({ detail: 'Parse error' }) })
  ) as jest.Mock;

  render(<DownloadExportButton file={mockFile} apiUrl={API_URL} />);
  fireEvent.click(screen.getByRole('button'));

  expect(await screen.findByText(/export failed/i)).toBeInTheDocument();

  act(() => {
    jest.advanceTimersByTime(3000);
  });
  await waitFor(() =>
    expect(screen.getByRole('button', { name: /download for llm/i })).toBeInTheDocument()
  );
  jest.useRealTimers();
});

test('posts the file to the correct endpoint', async () => {
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, blob: () => Promise.resolve(new Blob()) })
  ) as jest.Mock;

  render(<DownloadExportButton file={mockFile} apiUrl={API_URL} />);
  fireEvent.click(screen.getByRole('button'));

  await waitFor(() => expect(global.fetch).toHaveBeenCalled());
  const [url, opts] = (global.fetch as jest.Mock).mock.calls[0];
  expect(url).toBe(`${API_URL}/api/export/llm`);
  expect(opts.method).toBe('POST');
  expect(opts.body).toBeInstanceOf(FormData);
});
