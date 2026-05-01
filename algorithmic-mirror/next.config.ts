import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  // Silence the "webpack config present but no turbopack config" warning.
  // Turbopack (default in Next.js 16) handles CSS resolution natively.
  turbopack: {},

  webpack(config) {
    // Fix CSS @import module resolution for `next build` (webpack).
    // Without this, `@import "tailwindcss"` resolves from the repo parent
    // directory instead of algorithmic-mirror/node_modules/.
    config.resolve.modules = [
      path.resolve(__dirname, "node_modules"),
      "node_modules",
    ];
    return config;
  },
};

export default nextConfig;