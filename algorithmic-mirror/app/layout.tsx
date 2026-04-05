import type { Metadata } from "next";
import "./globals.css";
import { DualityWrapper } from "./components/DualityWrapper";

export const metadata: Metadata = {
  title: "Algorithmic Forensics Tool",
  description: "Exposing how social media algorithms weaponize user behavior.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <DualityWrapper>{children}</DualityWrapper>
      </body>
    </html>
  );
}
