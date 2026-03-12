import { SiteFooter } from '../../components/site-footer'
import { SiteNav } from '../../components/site-nav'
import { mockClusters } from '../../lib/mock-clusters'

const correctionEntries = mockClusters.flatMap((story) =>
  story.corrections.map((correction) => ({
    story: story.title,
    topic: story.topic,
    slug: story.slug,
    ...correction,
  })),
)

export default function CorrectionsPage() {
  return (
    <main className="page-shell content-page">
      <SiteNav />
      <header className="masthead">
        <div>
          <p className="eyebrow">Corrections log</p>
          <h1>Visible changes are part of the product, not cleanup.</h1>
          <p className="hero-dek">
            This prototype log shows how Prism should expose story changes, summary edits,
            and evidence cleanup instead of silently rewriting pages.
          </p>
        </div>
      </header>

      <section className="content-stack">
        {correctionEntries.map((entry) => (
          <article className="panel correction-log-card" key={`${entry.slug}-${entry.timestamp}-${entry.note}`}>
            <div className="section-heading">
              <div>
                <p className="panel-label">{entry.topic}</p>
                <h2>{entry.story}</h2>
              </div>
              <span className="cluster-badge">{entry.timestamp}</span>
            </div>
            <p>{entry.note}</p>
          </article>
        ))}
      </section>
      <SiteFooter />
    </main>
  )
}
