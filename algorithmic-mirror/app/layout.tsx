import type { Metadata } from "next";
import "./globals.css";
import { DualityWrapper } from "./components/DualityWrapper";
import { Fraunces, Source_Serif_4, JetBrains_Mono } from "next/font/google";

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
      className={`${fraunces.variable} ${sourceSerif.variable} ${jetbrainsMono.variable}`}
    >
      <body suppressHydrationWarning>
        <DualityWrapper>{children}</DualityWrapper>
      </body>
    </html>
  );
}
