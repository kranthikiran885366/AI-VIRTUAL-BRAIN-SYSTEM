/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // Required for better-sqlite3 native module
  serverExternalPackages: ["better-sqlite3"],

  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "**",
      },
    ],
  },

  // Environment variables exposed to the browser
  env: {
    NEXT_PUBLIC_ORCHESTRATOR_URL: process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || "http://localhost:8001",
  },

  // Webpack config for native modules
  webpack: (config, { isServer }) => {
    if (isServer) {
      config.externals = config.externals || []
      config.externals.push("better-sqlite3")
    }
    return config
  },
}

module.exports = nextConfig
