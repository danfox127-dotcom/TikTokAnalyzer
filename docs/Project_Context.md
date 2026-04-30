# Project Context: TikTokAnalyzer (SYS.TEARDOWN)

## 🎯 Core Vibe & Business Goal
**SYS.TEARDOWN** is a "Privacy-First Forensic Platform." It is designed to empower users by revealing the invisible **Algorithmic Ghost** that social media platforms (TikTok/Meta) construct of their users. 
- **The "Vibe":** Cyberpunk-noir, forensic, high-transparency, and unapologetically local-only.
- **Business Goal:** Provide a tool for digital literacy and algorithmic accountability. It turns raw, cryptic data exports into a human-readable, scroll-driven narrative of digital surveillance.

## 🛠️ Tech Stack
- **Backend (Forensic Engine):** 
  - **Python 3.12+**: Core parsing and behavioral logic.
  - **FastAPI**: High-performance API serving analysis to the frontend.
  - **Redis**: Low-latency caching for oEmbed enrichment (titles/thumbnails).
  - **Streamlit**: Alternative rapid-deployment UI for easy hosting.
- **Frontend (Algorithmic Mirror):**
  - **Next.js 16 (App Router)**: Framework for the narrative dashboard.
  - **React 19**: UI component library.
  - **Tailwind CSS 4**: Utility-first styling with high-density design patterns.
  - **Framer Motion**: Scroll-driven reveal logic and "fluid" UI transitions.
  - **TypeScript**: Strict typing for structural integrity.

## 🏗️ Primary Architecture & Data Flow
1. **Local Intake**: User drops JSON/folder exports (TikTok/Instagram) into the browser.
2. **Forensic Parsing**: Backend modules (`parsers/`) extract time-series watch history, ad categories, and surveillance logs.
3. **Behavioral Tiering**: Logic in `ghost_profile.py` buckets interactions:
   - **Graveyard (<3s)**: The "Anti-Profile."
   - **Sustained (15-180s)**: Successful hooks.
   - **Deep Dives (>180s)**: Full cognitive capture.
4. **Narrative Enrichment**: The `psychographic.py` engine maps keyword clusters to deterministic archetypes.
5. **Mirror Visualization**: The Next.js frontend fetches the enriched profile and renders a chapter-based, scroll-reveal story.

## 🚧 WIP State / Current Focus
*(Space intentionally left blank for the Vibe Coder)*

---
*Date Generated: 2026-04-22*
