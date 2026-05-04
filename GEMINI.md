# GEMINI.md — TikTokAnalyzer Project Context

## Project Overview
**TikTokAnalyzer** (internally known as **SYS.TEARDOWN**) is a social media forensic analysis platform. It reverse-engineers TikTok and Instagram/Meta data exports to reveal the invisible behavioral, psychological, and geographic models platforms build of their users.

The project is designed as a "Spotify Wrapped" style experience with a "Dark Deco" (Art Deco meets surveillance-noir) aesthetic.

### Architecture
The project follows a decoupled micro-stack architecture:

-   **Backend (Python/FastAPI)**:
    -   `parsers/`: Extract raw links, timestamps, and metadata from platform-specific JSON exports.
    -   `ghost_profile.py`: The core scoring engine. Calculates millisecond-level "Pure Stopwatch" metrics (skips, lingers, loops) and maps them to a deterministic **Trait-Cluster Archetype Engine**.
    -   `api/narratives.py`: Generates the **Dossier** — 9 structured narrative blocks with charts and data provenance.
    -   `api/main.py`: Provides REST and streaming Server-Sent Events (SSE) endpoints for analysis and AI synthesis.
    -   `utils/`: Contains the high-fidelity **Creator Registry**, IP Geolocation enrichment, and category taxonomies.
-   **Frontend (Next.js/TypeScript)**:
    -   `algorithmic-mirror/`: A modern React application using Tailwind CSS and Framer Motion.
    -   Features an interactive **Glass House** story view, a detailed **Dossier** report view, and a streaming **AI Analysis Panel**.
    -   Uses **Recharts** for visualizing behavioral distributions and interest clusters.

## Building and Running

### 1. Backend (Forensics Engine)
Requires Python 3.12+.
```bash
# Install dependencies
pip install -r requirements.txt

# Start the API (defaults to port 8005)
python3 -m uvicorn api.main:app --port 8005 --host 0.0.0.0
```

### 2. Frontend (Algorithmic Mirror)
Requires Node.js 20+.
```bash
cd algorithmic-mirror
npm install --legacy-peer-deps
npm run dev
```

### 3. Docker (Full Stack)
```bash
# Starts Redis (cache), Backend, and Frontend
docker-compose up
```

## Testing
-   **Backend**: `pytest tests/ -v` (covers parsing, archetypes, and API endpoints).
-   **Frontend**: `cd algorithmic-mirror && npm test` (unit tests for components and types).

## Development Conventions

### 1. Deterministic First
Insights must prioritize mathematical provenance. Every narrative block in the report includes a `provenance` field explaining exactly which raw data points (e.g., "42 consecutive skips") triggered the insight.

### 2. Archetype Logic
Do not use single-label archetypes. All user characterization should go through the **Trait-Cluster Engine** in `ghost_profile.py`, which supports overlapping traits and **Cognitive Dissonance** detection (e.g., "The Intentional Curator" who is also "Trapped" at night).

### 3. AI Safety & Privacy
-   **No Storage**: User API keys for Claude/Gemini are passed through in-memory and never logged or stored.
-   **Privacy-Safe Exports**: Use `exporters/llm_export.py` to generate sanitized JSON for LLM prompts, ensuring PII like exact IPs or watch history URLs are scrubbed.

### 4. Aesthetic Standards
Visual changes should adhere to the **Art Deco to Dark Deco** transition spec:
-   **Story (Glass House)**: Warm paper (#f5efe4), serif display, oxblood accents.
-   **Report (Dossier)**: Deep black (#0a0a0a), monospace, scanlines, and neon/cyan highlights.

## Key Files
-   `api/main.py`: Primary API entry point.
-   `ghost_profile.py`: Core behavioral calculation and archetype synthesis.
-   `api/narratives.py`: Logic for building the 9 forensic dossier blocks.
-   `algorithmic-mirror/app/page.tsx`: Main frontend view controller.
-   `docs/superpowers/specs/`: Authoritative design documents for current and future features.
