import type { Metadata } from "next";
import "./globals.css";
import { DualityWrapper } from "./components/DualityWrapper";
import {
  Fraunces,
  Source_Serif_4,
  JetBrains_Mono,
  Epilogue,
  Space_Grotesk,
  Be_Vietnam_Pro,
} from "next/font/google";

// ── Dossier (existing dark-deco editorial register) ──────────────────────────
const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-display",
  style: ["normal", "italic"],
});
const sourceSerif = Source_Serif_4({
  subsets: ["latin"],
  variable: "--font-body",
  style: ["normal", "italic"],
});
const jetbrainsMono = JetBrains_Mono({
  weight: ["400", "500", "700"],
  subsets: ["latin"],
  variable: "--font-mono",
});

// ── Miami Day Art Deco (Surface phase) ───────────────────────────────────────
// Used by SurfaceDataDisplay before the bright→dark transition.
const epilogue = Epilogue({
  weight: ["800", "900"],
  subsets: ["latin"],
  variable: "--font-deco-display",
});
const spaceGrotesk = Space_Grotesk({
  weight: ["700"],
  subsets: ["latin"],
  variable: "--font-deco-label",
});
const beVietnamPro = Be_Vietnam_Pro({
  weight: ["400", "500"],
  subsets: ["latin"],
  variable: "--font-deco-body",
});

export const metadata: Metadata = {
  title: "The Algorithmic Mirror",
  description: "What TikTok knows about you — exposed.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${fraunces.variable} ${sourceSerif.variable} ${jetbrainsMono.variable} ${epilogue.variable} ${spaceGrotesk.variable} ${beVietnamPro.variable}`}
    >
      <body suppressHydrationWarning>
        <DualityWrapper>{children}</DualityWrapper>
      </body>
    </html>
  );
}
