import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Permit an isolated verification server beside the normal development server.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  reactCompiler: true,
};

export default nextConfig;
