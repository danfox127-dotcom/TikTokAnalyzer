# Aesthetic & Animation Spec: Art Deco to Dark Deco

## Concept
The application should feel like a transition from a high-end, sophisticated investigative tool (**Art Deco**) to a deep, surveillance-state forensic analysis (**Dark Deco / Batman: The Animated Series**).

## Visual Language
- **Palette**: 
  - **Art Deco Phase**: Gold (#f5d57a), Cream (#f5efe4), Oxblood (#8b2323). Clean lines, high contrast.
  - **Dark Deco Phase**: Deep Slate (#0a0a0a), Midnight Blue (#111827), High-contrast Red (#ff4466). Heavy shadows, atmospheric "fog" (gradients), and scanlines.
- **Typography**: 
  - Geometric sans-serifs for headers (Metropolis, Futura style).
  - Monospace for the "forensic" data layers.

## Key Animations & Transitions
1. **The "Flash-Bulb" Entrance**:
   - When the user uploads, a high-intensity white/gold flash transition should lead into the data reveal.
2. **The Descent**:
   - As the user scrolls from the "Glass House" (Story) into the "Dossier" (Report), the background should transition from warm paper to a cold, digital black.
3. **The Algorithmic Pulse**:
   - Chart elements (Recharts) should not just appear; they should "draw" themselves in with a staggered, scanning motion.
4. **Text Decoding**:
   - Narrative prose should use a "typewriter" or "decoding" effect (scrambled characters resolving into English) when first entering the viewport.

## Component Updates
- **TheGlassHouse**: Needs more "marginalia" — small bits of data appearing in the gutters as the user reads.
- **NarrativeReportView**: Add a subtle "grain" or "noise" filter over the background to give it that 1940s-noir-meets-2020s-surveillance feel.

## Technical Implementation (Framer Motion)
- Use `layoutId` for smooth transitions between view states.
- Implement `AnimatePresence` for view switching.
- Use `whileInView` for staggered block reveals.
