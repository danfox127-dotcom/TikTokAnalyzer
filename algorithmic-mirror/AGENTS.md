<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# Iconography

All icons come from `lucide-react`. Do **not** import from `@material-symbols/*`, load the Material Symbols webfont, or pull in other icon libraries (Heroicons, react-icons, Feather, etc.). If a glyph isn't in lucide, ask the user before reaching elsewhere — almost everything has a lucide equivalent.

If you see a Figma/HTML mock that uses Material Symbols (`material-symbols-outlined` classes), substitute lucide equivalents during implementation. The mock is a placeholder; the codebase is lucide-only.

# Typography

Two registers, both loaded via `next/font/google` in `app/layout.tsx`:

- **Dossier (dark-deco editorial)** — Fraunces (`--font-display`), Source Serif 4 (`--font-body`), JetBrains Mono (`--font-mono`). Used by `TheGlassHouse`, `NarrativeReportView`, `GhostProfileHUD`.
- **Miami Day (bright art-deco Surface phase)** — Epilogue 800/900 (`--font-deco-display`), Space Grotesk 700 caps (`--font-deco-label`), Be Vietnam Pro 400/500 (`--font-deco-body`). Used by `SurfaceDataDisplay` only — the bright pre-transition page.

Don't load Google Fonts via `<link>` tags. Always use `next/font` to keep them subset and self-hosted at build time.
