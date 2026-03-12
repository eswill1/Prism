import Link from 'next/link'

const utilityLinks = [
  { href: '/saved', label: 'Saved' },
  { href: '/methodology', label: 'Methodology' },
  { href: '/corrections', label: 'Corrections' },
  { href: '/pricing', label: 'Pricing' },
]

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <nav className="site-footer-links" aria-label="Utility">
        {utilityLinks.map((item) => (
          <Link key={item.href} href={item.href}>
            {item.label}
          </Link>
        ))}
      </nav>
    </footer>
  )
}
