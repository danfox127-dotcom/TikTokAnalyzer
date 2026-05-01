# Download Export Button Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an inline "Download for LLM →" button to both results views that POSTs the original uploaded file to `POST /api/export/llm` and triggers a browser download of the privacy-safe JSON.

**Architecture:** `page.tsx` holds the `File` object in state after upload and passes it as `sourceFile?: File` to `TheGlassHouse` and `GhostProfileHUD`. A new `DownloadExportButton` component handles the fetch + browser download mechanics. The button renders only when `sourceFile` is defined.

**Tech Stack:** Next.js 14 App Router, React 18, TypeScript, `@testing-library/react`, Jest (jsdom), Framer Motion (existing)

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `algorithmic-mirror/app/components/DownloadExportButton.tsx` | Fetch + download mechanics, 3 visual states |
| Create | `algorithmic-mirror/__tests__/DownloadExportButton.test.tsx` | Unit tests for all button states |
| Modify | `algorithmic-mirror/app/page.tsx` | Add `uploadedFile` state, thread `sourceFile` prop |
| Modify | `algorithmic-mirror/app/components/TheGlassHouse.tsx` | Add `sourceFile?: File` to Props, render button |
| Modify | `algorithmic-mirror/app/components/GhostProfileHUD.tsx` | Add `sourceFile?: File` to Props, render button |

---

### Task 1: `DownloadExportButton` component + tests

**Files:**
- Create: `algorithmic-mirror/app/components/DownloadExportButton.tsx`
- Create: `algorithmic-mirror/__tests__/DownloadExportButton.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `algorithmic-mirror/__tests__/DownloadExportButton.test.tsx`:

```tsx
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
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
  jest.spyOn(document, 'createElement').mockImplementation((tag: string) => {
    const el = origCreate(tag);
    if (tag === 'a') { el.click = clickSpy; }
    return el;
  });

  render(<DownloadExportButton file={mockFile} apiUrl={API_URL} />);
  fireEvent.click(screen.getByRole('button'));

  await waitFor(() => expect(clickSpy).toHaveBeenCalled());
  expect(URL.createObjectURL).toHaveBeenCalledWith(mockBlob);
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock');
});

test('shows error message on fetch failure then resets to idle', async () => {
  jest.useFakeTimers();
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: false, json: () => Promise.resolve({ detail: 'Parse error' }) })
  ) as jest.Mock;

  render(<DownloadExportButton file={mockFile} apiUrl={API_URL} />);
  fireEvent.click(screen.getByRole('button'));

  expect(await screen.findByText(/export failed/i)).toBeInTheDocument();

  jest.advanceTimersByTime(3000);
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd algorithmic-mirror && npx jest __tests__/DownloadExportButton.test.tsx --no-coverage
```

Expected: FAIL — `Cannot find module '../app/components/DownloadExportButton'`

- [ ] **Step 3: Create `DownloadExportButton.tsx`**

Create `algorithmic-mirror/app/components/DownloadExportButton.tsx`:

```tsx
"use client";
import { useState, useRef } from "react";

interface Props {
  file: File;
  apiUrl: string;
}

type State = "idle" | "loading" | "error";

export function DownloadExportButton({ file, apiUrl }: Props) {
  const [state, setState] = useState<State>("idle");
  const errorTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleClick = async () => {
    if (state === "loading") return;
    if (errorTimer.current) clearTimeout(errorTimer.current);
    setState("loading");

    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`${apiUrl}/api/export/llm`, { method: "POST", body: fd });

      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j.detail ?? `HTTP ${res.status}`);
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `tiktok_analysis_${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setState("idle");
    } catch {
      setState("error");
      errorTimer.current = setTimeout(() => setState("idle"), 3000);
    }
  };

  const label =
    state === "loading" ? "Downloading…" :
    state === "error"   ? "Export failed" :
    "Download for LLM →";

  return (
    <button
      onClick={handleClick}
      disabled={state === "loading"}
      style={{
        fontFamily: "var(--font-mono, ui-monospace, Menlo, monospace)",
        fontSize: 10,
        letterSpacing: "0.2em",
        textTransform: "uppercase",
        color: state === "error" ? "#f87171" : "rgba(148, 163, 184, 0.6)",
        background: "transparent",
        border: "none",
        cursor: state === "loading" ? "default" : "pointer",
        padding: 0,
        opacity: state === "loading" ? 0.5 : 1,
        transition: "opacity 0.2s, color 0.2s",
      }}
    >
      {label}
    </button>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd algorithmic-mirror && npx jest __tests__/DownloadExportButton.test.tsx --no-coverage
```

Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add algorithmic-mirror/app/components/DownloadExportButton.tsx \
        algorithmic-mirror/__tests__/DownloadExportButton.test.tsx
git commit -m "feat: add DownloadExportButton component with tests"
```

---

### Task 2: Wire `uploadedFile` state into `page.tsx`

**Files:**
- Modify: `algorithmic-mirror/app/page.tsx`

Context: `page.tsx` currently passes `file` to `analyze()` but does not store it in state. We need to retain it so we can pass it to the results views.

- [ ] **Step 1: Add `uploadedFile` state and thread it through**

Open `algorithmic-mirror/app/page.tsx`. Make these three changes:

**a) Add import** — at the top where `DownloadExportButton` will be consumed (the component is used in child components, not page.tsx directly, but we need the state here):

The existing imports line (line 3) reads:
```tsx
import { useState, useRef } from "react";
```
No change needed to imports for this task.

**b) Add state** — after line 18 (`const [dragOver, setDragOver] = useState(false);`), add:
```tsx
const [uploadedFile, setUploadedFile] = useState<File | null>(null);
```

**c) Store file in `handleFile`** — the existing `handleFile` function reads:
```tsx
const handleFile = (file: File | null | undefined) => {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".json")) {
    setError("Expected a TikTok .json export.");
    return;
  }
  analyze(file);
};
```
Change it to:
```tsx
const handleFile = (file: File | null | undefined) => {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".json")) {
    setError("Expected a TikTok .json export.");
    return;
  }
  setUploadedFile(file);
  analyze(file);
};
```

**d) Clear file on reset** — the existing `handleReset` reads:
```tsx
const handleReset = () => {
  setProfile(null);
  setView("upload");
  setError(null);
};
```
Change it to:
```tsx
const handleReset = () => {
  setProfile(null);
  setView("upload");
  setError(null);
  setUploadedFile(null);
};
```

**e) Pass `sourceFile` prop to `TheGlassHouse`** — find the JSX block (around line 59):
```tsx
<TheGlassHouse
  profile={profile}
  onReset={handleReset}
  onViewRawForensics={() => setView("hud")}
/>
```
Change to:
```tsx
<TheGlassHouse
  profile={profile}
  onReset={handleReset}
  onViewRawForensics={() => setView("hud")}
  sourceFile={uploadedFile ?? undefined}
/>
```

**f) Pass `sourceFile` prop to `GhostProfileHUD`** — find the JSX block (around line 93):
```tsx
<GhostProfileHUD profile={profile} onReset={handleReset} />
```
Change to:
```tsx
<GhostProfileHUD profile={profile} onReset={handleReset} sourceFile={uploadedFile ?? undefined} />
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd algorithmic-mirror && npx tsc --noEmit 2>&1 | head -20
```

Expected: errors about `sourceFile` prop not existing on `TheGlassHouse` and `GhostProfileHUD` — those are fixed in Tasks 3 and 4. Any other errors should be investigated.

- [ ] **Step 3: Commit**

```bash
git add algorithmic-mirror/app/page.tsx
git commit -m "feat: retain uploaded File in state for LLM export"
```

---

### Task 3: Add download button to `TheGlassHouse`

**Files:**
- Modify: `algorithmic-mirror/app/components/TheGlassHouse.tsx`

Context: `TheGlassHouse` is the primary narrative view. The reset button is a plain `<button>` in the `<header>` (around line 403). The color constants are `INK = "#1a1610"` and `INK_DIM = "#6a5e4a"`. This is a warm dark theme (sepia/brown tones), unlike GhostProfileHUD's cool slate theme.

- [ ] **Step 1: Add import**

At the top of `TheGlassHouse.tsx`, find the existing import block and add:
```tsx
import { DownloadExportButton } from "./DownloadExportButton";
```

- [ ] **Step 2: Add `sourceFile` to Props interface**

Find the `Props` interface (around line 293):
```tsx
interface Props {
  profile: GhostProfile;
  onReset: () => void;
  onViewRawForensics: () => void;
}
```
Change to:
```tsx
interface Props {
  profile: GhostProfile;
  onReset: () => void;
  onViewRawForensics: () => void;
  sourceFile?: File;
}
```

- [ ] **Step 3: Destructure the new prop**

Find the function signature (around line 299):
```tsx
export function TheGlassHouse({ profile, onReset, onViewRawForensics }: Props) {
```
Change to:
```tsx
export function TheGlassHouse({ profile, onReset, onViewRawForensics, sourceFile }: Props) {
```

- [ ] **Step 4: Render the button**

The `<header>` block closes after the reset button (around line 418, after `← Upload different export`). Add the download button immediately after the reset `<button>` closing tag, still inside `<header>`:

Find:
```tsx
            >
              ← Upload different export
            </button>
          </header>
```
Change to:
```tsx
            >
              ← Upload different export
            </button>
            {sourceFile && (
              <DownloadExportButton
                file={sourceFile}
                apiUrl={process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8005"}
              />
            )}
          </header>
```

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd algorithmic-mirror && npx tsc --noEmit 2>&1 | head -20
```

Expected: only the remaining error about `GhostProfileHUD` not accepting `sourceFile` yet (fixed in Task 4). No errors in `TheGlassHouse.tsx`.

- [ ] **Step 6: Commit**

```bash
git add algorithmic-mirror/app/components/TheGlassHouse.tsx
git commit -m "feat: add LLM download button to TheGlassHouse header"
```

---

### Task 4: Add download button to `GhostProfileHUD`

**Files:**
- Modify: `algorithmic-mirror/app/components/GhostProfileHUD.tsx`

Context: `GhostProfileHUD` is the raw forensics view. The reset button is a `<motion.button>` with `onClick={onReset}` in the header div (around line 705). Color constants: `LINE_BRIGHT = "rgba(148, 163, 184, 0.35)"`, `INK = "#e2e8f0"`, `INK_DIM = "#94a3b8"`. Cool slate theme.

- [ ] **Step 1: Add import**

At the top of `GhostProfileHUD.tsx`, find the existing import block and add:
```tsx
import { DownloadExportButton } from "./DownloadExportButton";
```

- [ ] **Step 2: Add `sourceFile` to Props interface**

Find the `Props` interface (around line 152):
```tsx
interface Props {
  profile: GhostProfile;
  onReset: () => void;
}
```
Change to:
```tsx
interface Props {
  profile: GhostProfile;
  onReset: () => void;
  sourceFile?: File;
}
```

- [ ] **Step 3: Destructure the new prop**

Find the function signature (around line 673):
```tsx
export function GhostProfileHUD({ profile, onReset }: Props) {
```
Change to:
```tsx
export function GhostProfileHUD({ profile, onReset, sourceFile }: Props) {
```

- [ ] **Step 4: Render the button**

The reset `<motion.button>` closes with `Reset` text and `</motion.button>` (around line 726). Add the download button immediately after the closing `</motion.button>` tag, still inside the same header flex container:

Find:
```tsx
            <ArrowLeft size={14} />
            Reset
          </motion.button>
        </div>

        {/* Grid */}
```
Change to:
```tsx
            <ArrowLeft size={14} />
            Reset
          </motion.button>
          {sourceFile && (
            <DownloadExportButton
              file={sourceFile}
              apiUrl={process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8005"}
            />
          )}
        </div>

        {/* Grid */}
```

- [ ] **Step 5: Verify TypeScript compiles cleanly**

```bash
cd algorithmic-mirror && npx tsc --noEmit 2>&1
```

Expected: no errors

- [ ] **Step 6: Run all frontend tests**

```bash
cd algorithmic-mirror && npx jest --no-coverage
```

Expected: all tests pass (including the 5 new `DownloadExportButton` tests)

- [ ] **Step 7: Commit**

```bash
git add algorithmic-mirror/app/components/GhostProfileHUD.tsx
git commit -m "feat: add LLM download button to GhostProfileHUD header"
```

---

### Task 5: Manual smoke test

**No files changed — verification only.**

- [ ] **Step 1: Start the backend**

```bash
cd /path/to/TikTokAnalyzer && uvicorn api.main:app --port 8005 --reload
```

- [ ] **Step 2: Start the frontend**

```bash
cd algorithmic-mirror && npm run dev
```

- [ ] **Step 3: Upload a TikTok export**

Open `http://localhost:3000`. Drop a `user_data_tiktok.json` file onto the upload zone.

- [ ] **Step 4: Verify button appears in narrative view**

After analysis completes, the narrative view (TheGlassHouse) loads. Confirm "DOWNLOAD FOR LLM →" appears near the "← Upload different export" button in the header.

- [ ] **Step 5: Click the download button**

Click "DOWNLOAD FOR LLM →". Confirm:
- Button label changes to "DOWNLOADING…" and becomes disabled
- A file named `tiktok_analysis_YYYY-MM-DD.json` downloads to your Downloads folder
- Button returns to "DOWNLOAD FOR LLM →" after download completes

- [ ] **Step 6: Verify downloaded file**

```bash
cat ~/Downloads/tiktok_analysis_*.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert '_meta' in d
assert 'tiktok.com' not in json.dumps(d), 'URLs leaked!'
assert '1.2.3.' not in json.dumps(d), 'IPs leaked!'
print('OK — meta present, no URLs, no IPs')
"
```

Expected: `OK — meta present, no URLs, no IPs`

- [ ] **Step 7: Switch to raw forensics view and verify button appears there too**

Click "View Raw Forensics" (or equivalent). Confirm "DOWNLOAD FOR LLM →" appears near the "Reset" button in the GhostProfileHUD header.

- [ ] **Step 8: Test reset clears button**

Click "Reset" (or "← Upload different export"). Confirm the upload screen appears and no download button is visible.
