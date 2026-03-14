import { SiteFooter } from '../../components/site-footer'
import { SiteNav } from '../../components/site-nav'

const sections = [
  {
    id: 'story-construction',
    title: 'Story construction',
    body:
      'Prism groups related coverage around a single event-level story object. The product shows the story as a workspace so the reader can compare coverage without tab sprawl.',
  },
  {
    id: 'coverage-structure',
    title: 'Coverage structure',
    body:
      'Outlet presence is displayed as a structural view of who is in the coverage set. It is not a vote, truth score, or consensus meter.',
  },
  {
    id: 'perspective-versioning',
    title: 'Perspective revisions',
    body:
      'Each stored Perspective revision carries a version tag, a generation-method label, and a timestamp. Story pages summarize the structural changes in that revision so readers can inspect what changed without diffing raw source snapshots.',
    bullets: [
      'Revision tags identify the published Perspective currently attached to the story page.',
      'Method labels identify which rule set produced the current Perspective rail.',
      'Change notes describe source breadth, readiness, and lens availability shifts. They do not score truth or declare a winner.',
    ],
  },
  {
    id: 'context-packs',
    title: 'Context Packs',
    body:
      'Lenses generate small alternate-read sets for specific goals such as balanced framing, evidence-first inspection, local impact, or international comparison.',
  },
  {
    id: 'corrections-versioning',
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
            This surface explains the product rules behind Prism’s story pages, including
            the Perspective version labels and methodology notes now shown directly in the
            reader experience.
          </p>
        </div>
      </header>

      <section className="content-grid">
        {sections.map((section) => (
          <article className="panel narrative-panel" id={section.id} key={section.title}>
            <p className="panel-label">Method</p>
            <h2>{section.title}</h2>
            <p>{section.body}</p>
            {section.bullets ? (
              <ul className="simple-list">
                {section.bullets.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : null}
          </article>
        ))}
      </section>
      <SiteFooter />
    </main>
  )
}
