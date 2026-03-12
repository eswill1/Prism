import { SiteFooter } from '../../components/site-footer'
import { SiteNav } from '../../components/site-nav'

const sections = [
  {
    title: 'Story construction',
    body:
      'Prism groups related coverage around a single event-level story object. The product shows the story as a workspace so the reader can compare coverage without tab sprawl.',
  },
  {
    title: 'Coverage structure',
    body:
      'Outlet presence is displayed as a structural view of who is in the coverage set. It is not a vote, truth score, or consensus meter.',
  },
  {
    title: 'Context Packs',
    body:
      'Lenses generate small alternate-read sets for specific goals such as balanced framing, evidence-first inspection, local impact, or international comparison.',
  },
  {
    title: 'Corrections and versioning',
    body:
      'Material changes to story membership, summaries, evidence references, or methodology should be logged visibly so readers can see what changed instead of trusting silent rewrites.',
  },
]

export default function MethodologyPage() {
  return (
    <main className="page-shell content-page">
      <SiteNav />
      <header className="masthead">
        <div>
          <p className="eyebrow">Methodology</p>
          <h1>How Prism makes coverage inspectable.</h1>
          <p className="hero-dek">
            This is the reader-facing shell for the methodology surface. It explains the
            product rules before the full version registry and source attribution stack are
            online.
          </p>
        </div>
      </header>

      <section className="content-grid">
        {sections.map((section) => (
          <article className="panel narrative-panel" key={section.title}>
            <p className="panel-label">Method</p>
            <h2>{section.title}</h2>
            <p>{section.body}</p>
          </article>
        ))}
      </section>
      <SiteFooter />
    </main>
  )
}
