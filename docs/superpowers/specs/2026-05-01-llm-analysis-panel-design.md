# LLM Analysis Panel Design (Part 2B)

## Goal

Add an in-app LLM analysis panel as a new "llm" view. Users can analyze their ghost profile with Claude or Gemini using their own API key, or copy the privacy-safe export and open Claude.ai / Gemini in a browser tab.

## Architecture

A new `POST /api/analyze/llm` endpoint receives the TikTok export file, provider choice, and API key. It generates the LLM export internally, then streams the LLM response back as Server-Sent Events. The frontend consumes the stream via `fetch` + `ReadableStream` and renders tokens as they arrive. The API key is never logged or persisted server-side — it lives in memory for the duration of the single request.

## Backend

### New endpoint: `POST /api/analyze/llm`

**Parameters (multipart form):**
- `file: UploadFile` — the TikTok `.json` export
- `provider: str` — one of `"claude"`, `"gemini-pro"`, `"gemini-flash"`
- `api_key: str` — user-supplied key, passed through only

**Flow:**
1. Parse file with `parse_tiktok_export_from_bytes`
2. Build ghost profile with `build_ghost_profile`
3. Generate LLM export with `generate_llm_export` → produces the `{_meta, behavioral_summary, profile}` payload
4. Serialize payload to JSON string, inject into a prompt using `_meta.instructions_for_llm` + `_meta.suggested_opening`
5. Stream response from provider SDK back to client as SSE (`text/event-stream`)

**Provider SDKs:**
- Claude: `anthropic` Python package — `client.messages.stream(model="claude-opus-4-5", ...)`
- Gemini Pro: `google-generativeai` — `model.generate_content(..., stream=True)` with `gemini-1.5-pro`
- Gemini Flash: same SDK, `gemini-1.5-flash`

**SSE format:**
```
data: <token text>\n\n
data: [DONE]\n\n
```

Error responses: standard HTTP 4xx/5xx JSON (not SSE), so the frontend can distinguish connection errors from stream content.

**New dependencies in `requirements.txt`:**
- `anthropic>=0.25.0`
- `google-generativeai>=0.5.0`

## Frontend

### New view: `"llm"` in `page.tsx`

Add `"llm"` to the `View` type. Add navigation:
- TheGlassHouse gets a new `onAnalyzeWithAI` prop → navigates to `"llm"` view
- Button label: "Analyze with AI →" placed near the download button in the header

### New component: `algorithmic-mirror/app/components/LLMAnalysisView.tsx`

**Props:** `{ file: File; apiUrl: string; onBack: () => void }`

**Layout (top to bottom):**

1. **Header** — "AI ANALYSIS" label + "← Back" button (calls `onBack`)

2. **Provider selector** — three buttons: `CLAUDE API`, `GEMINI PRO`, `GEMINI FLASH`. Selected provider highlighted.

3. **API key input** — text input (password type), pre-filled from `localStorage` key `llm_api_key_{provider}`. Saves to localStorage on submit. Placeholder: `sk-ant-...` / `AIza...`

4. **Analyze button** — "Run Analysis →". Disabled when no key entered or analysis running.

5. **Copy & Open section** — four buttons in a row:
   - "Copy + Claude.ai" → copies LLM export JSON to clipboard, opens `https://claude.ai`
   - "Copy + Gemini Pro" → copies JSON, opens `https://gemini.google.com`
   - "Copy + Gemini Flash" → copies JSON, opens `https://gemini.google.com` (Flash is the default free tier)

   These buttons POST `file` to `/api/export/llm`, receive the JSON blob, copy text to clipboard, then open the target URL.

6. **Analysis output** — streaming text area. Monospace, dark background, tokens appear as they stream in. Shows a blinking cursor while streaming. On error: shows error message in red.

**Streaming implementation:**
```ts
const res = await fetch(`${apiUrl}/api/analyze/llm`, { method: "POST", body: fd });
const reader = res.body!.getReader();
const decoder = new TextDecoder();
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  const text = decoder.decode(value);
  // parse SSE lines, append tokens to output state
}
```

**State:** `"idle" | "loading" | "streaming" | "done" | "error"`

**localStorage keys:**
- `llm_api_key_claude`
- `llm_api_key_gemini-pro`
- `llm_api_key_gemini-flash`

## Styling

Matches dark surveillance aesthetic: monospace throughout, `--bg` background, `--accent` (#4db8ff) for selected provider, `--danger` (#ff4466) for errors. Analysis output area has a subtle scanline overlay.

## Out of Scope

- Storing or logging API keys server-side
- Conversation history / follow-up prompts (future)
- Model version selector (future — hardcoded to opus-4-5 / 1.5-pro / 1.5-flash)
- Rate limiting / quota tracking

## Testing

- Backend: unit tests for SSE stream format, provider dispatch, error handling
- Frontend: mock fetch, verify streaming state transitions, verify localStorage persistence
