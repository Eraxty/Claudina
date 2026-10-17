import type { NextConfig } from "next";

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";

const nextConfig: NextConfig = {
  output: "export",
  basePath: basePath || undefined,
  trailingSlash: true,
  images: { unoptimized: true },
  allowedDevOrigins: ["127.0.0.1", "localhost"], // unblocks HMR/dev assets when the tab is opened via 127.0.0.1
  experimental: {
    agentFeedback: true,
  },
  cacheComponents: !basePath, // PPR: off in export mode, github actions build dies without this
  partialPrefetching: !basePath,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
