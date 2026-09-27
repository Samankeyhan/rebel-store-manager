import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export: FastAPI serves out/ as plain files, so no server runtime.
  output: "export",
  images: { unoptimized: true },
  // /orders/ -> orders/index.html, which StaticFiles resolves without rewrites.
  trailingSlash: true,
};

export default nextConfig;
