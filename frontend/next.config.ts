import type { NextConfig } from "next";

const BACKEND = process.env.BACKEND_URL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Dev-server: izinkan HMR/dev-resources dari host preview sandbox & loopback
  // (tanpa ini Next 16 memblokir cross-origin dev assets → UI tidak hydrate).
  allowedDevOrigins: ["127.0.0.1", "*.e2b.app", "**.e2b.app"],
  // The FastAPI backend lives on another port; proxy same-origin so the
  // browser (and the sandboxed preview) never needs to reach localhost.
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND}/api/:path*` },
      { source: "/slides/:path*", destination: `${BACKEND}/slides/:path*` },
      { source: "/docs-images/:path*", destination: `${BACKEND}/docs-images/:path*` },
    ];
  },
};

export default nextConfig;
