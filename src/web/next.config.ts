import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  // Keep local dev output isolated from production builds so `next build`
  // does not corrupt the running `next dev` server during local iteration.
  distDir: process.env.NODE_ENV === 'development' ? '.next-dev' : '.next',
  typescript: {
    tsconfigPath:
      process.env.NODE_ENV === 'development' ? './tsconfig.dev.json' : './tsconfig.json',
  },
}

export default nextConfig
