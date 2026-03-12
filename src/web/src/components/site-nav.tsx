import Link from 'next/link'

import { DEFAULT_MASTHEAD_DIRECTION, MastheadIdentity } from './masthead-directions'
import { PRIMARY_NEWS_SECTIONS } from '../lib/news-sections'

const navItems = [
  ...PRIMARY_NEWS_SECTIONS.map((section) => ({
    href: `/#${section.anchor}`,
    label: section.navLabel,
  })),
]

export function SiteNav() {
  const issueDate = new Intl.DateTimeFormat('en-US', {
    weekday: 'short',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date())

  return (
    <header className="site-header">
      <div className="site-banner">
        <div className="site-banner-meta">
          <span>U.S. Edition</span>
          <span>{issueDate}</span>
        </div>
        <nav className="site-utility-links" aria-label="Utility">
          <Link href="/saved">Saved</Link>
          <Link href="/methodology">Methodology</Link>
          <Link href="/corrections">Corrections</Link>
        </nav>
      </div>

      <div className="site-masthead">
        <Link className="site-mark" href="/">
          <MastheadIdentity direction={DEFAULT_MASTHEAD_DIRECTION} />
        </Link>
      </div>

      <nav className="site-nav" aria-label="Primary">
        <div className="site-nav-links">
          {navItems.map((item) => (
            <Link key={item.href} href={item.href}>
              {item.label}
            </Link>
          ))}
        </div>
      </nav>
    </header>
  )
}
