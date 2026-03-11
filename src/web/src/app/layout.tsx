import type { Metadata } from 'next'

import './globals.css'

export const metadata: Metadata = {
  title: 'The Prism Wire',
  description:
    'A serious, newsroom-grade news product that makes coverage transparent instead of telling readers what to think.',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
