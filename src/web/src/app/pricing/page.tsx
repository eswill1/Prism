import { SiteFooter } from '../../components/site-footer'
import { SiteNav } from '../../components/site-nav'

const plans = [
  {
    name: 'Free',
    price: '$0',
    summary: 'A lightweight way to inspect a few stories and feel the product.',
    bullets: ['Limited story views', 'Basic live story access', 'No saved-story sync'],
  },
  {
    name: 'Prism',
    price: '$12/mo',
    summary: 'Built for serious readers who want saved stories, follow-ups, and briefings.',
    bullets: ['Unlimited story access', 'Saved and followed stories', 'Morning and evening briefings'],
  },
  {
    name: 'Institutional',
    price: 'Contact us',
    summary: 'Libraries, schools, and workplaces that need shared access and accountable tooling.',
    bullets: ['Seat-based access', 'Admin controls', 'Methodology and export support'],
  },
]

export default function PricingPage() {
  return (
    <main className="page-shell content-page">
      <SiteNav />
      <header className="masthead">
        <div>
          <p className="eyebrow">Pricing</p>
          <h1>Prism is funded by reader trust, not attention extraction.</h1>
          <p className="hero-dek">
            This is the first pricing shell. It exists to frame the business model before
            checkout and account provisioning are online.
          </p>
        </div>
      </header>

      <section className="pricing-grid">
        {plans.map((plan) => (
          <article className="panel pricing-card" key={plan.name}>
            <p className="panel-label">{plan.name}</p>
            <h2>{plan.price}</h2>
            <p>{plan.summary}</p>
            <ul className="simple-list">
              {plan.bullets.map((bullet) => (
                <li key={bullet}>{bullet}</li>
              ))}
            </ul>
          </article>
        ))}
      </section>
      <SiteFooter />
    </main>
  )
}
