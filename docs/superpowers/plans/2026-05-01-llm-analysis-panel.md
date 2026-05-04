# Implementation Plan — LLM Analysis Panel (Part 2B)

Add an in-app LLM analysis panel where users can analyze their ghost profile with Claude or Gemini using their own API key.

## User Review Required

> [!IMPORTANT]
> The implementation involves adding `anthropic` and `google-generativeai` dependencies. User API keys will be passed through to these providers via a new streaming endpoint.

## Proposed Changes

### Backend (Python/FastAPI)

#### [requirements.txt]
- Add `anthropic>=0.25.0`
- Add `google-generativeai>=0.5.0`

#### [api/main.py]
- Import `StreamingResponse` from `fastapi.responses`.
- Import `anthropic` and `google.generativeai`.
- Implement `POST /api/analyze/llm` endpoint:
  - Receives `file`, `provider`, and `api_key`.
  - Parses file and builds ghost profile.
  - Generates LLM export payload.
  - Constructs a prompt using `_meta` instructions.
  - Dispatches to chosen provider and streams response as SSE.

### Frontend (Next.js/TypeScript)

#### [algorithmic-mirror/app/components/LLMAnalysisView.tsx]
- Create new component for the AI Analysis interface.
- Manage state for selected provider, API key (with localStorage persistence), and streaming output.
- Handle SSE stream consumption and token rendering.
- Implement "Copy & Open" buttons for external analysis.

#### [algorithmic-mirror/app/page.tsx]
- Add `"llm"` to `View` type.
- Add conditional rendering for `LLMAnalysisView`.
- Update `handleReset` to clear LLM state if needed.

#### [algorithmic-mirror/app/components/TheGlassHouse.tsx]
- Add `onAnalyzeWithAI` prop.
- Add "Analyze with AI →" button in the header.

## Verification Plan

### Automated Tests
- **Backend**:
  - `tests/test_api.py`: Add `test_analyze_llm_claude` and `test_analyze_llm_gemini` with mocked SDK calls.
  - Verify SSE format: `data: <token>\n\n`.
- **Frontend**:
  - `algorithmic-mirror/__tests__/LLMAnalysisView.test.tsx`: Verify UI rendering, localStorage persistence, and stream handling.

### Manual Verification
1. Upload a TikTok export.
2. Click "Analyze with AI →" in the header.
3. Select a provider (e.g., Gemini Flash).
4. Enter a dummy API key (or real one for testing).
5. Verify "Run Analysis →" initiates streaming.
6. Verify "Copy + Claude.ai" copies data and opens the URL.
7. Verify "← Back" returns to the story view.
