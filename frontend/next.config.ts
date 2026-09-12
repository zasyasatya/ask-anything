import type { NextConfig } from "next";

const BACKEND = process.env.BACKEND_URL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // The FastAPI backend lives on another port; proxy same-origin so the
  // browser (and the sandboxed preview) never needs to reach localhost.
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND}/api/:path*` },
      { source: "/slides/:path*", destination: `${BACKEND}/slides/:path*` },
    ];
  },
};

export default nextConfig;
