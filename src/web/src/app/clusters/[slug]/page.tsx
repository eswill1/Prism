import Link from 'next/link'
import { notFound } from 'next/navigation'

import { clusterBySlug } from '../../../lib/mock-clusters'

export default async function ClusterPage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = await params
  const cluster = clusterBySlug[slug]

  if (!cluster) {
    notFound()
  }

  const balancedPack = cluster.contextPacks['Balanced Framing'] ?? []

  return (
    <main className="page-shell cluster-page">
      <header className="cluster-topbar">
        <Link href="/" className="secondary-link">
          Back to briefing
        </Link>
        <div className="cluster-topbar-actions">
          <button className="action-pill" type="button">
            Save cluster
          </button>
          <button className="action-pill" type="button">
            Follow updates
          </button>
        </div>
      </header>

      <section className="cluster-hero panel">
        <div className="cluster-hero-copy">
          <div className="hero-meta-line">
            <span className="status-chip">{cluster.status}</span>
            <span>{cluster.updatedAt}</span>
            <span>{cluster.outletCount} outlets</span>
          </div>
          <p className="panel-label">{cluster.topic}</p>
          <h1>{cluster.title}</h1>
          <p className="hero-dek">{cluster.dek}</p>
        </div>
        <div className="cluster-hero-media">
          <img src={cluster.heroImage} alt={cluster.heroAlt} className="hero-image" />
          <span className="media-credit">{cluster.heroCredit}</span>
        </div>
      </section>

      <section className="cluster-shell">
        <aside className="summary-rail panel">
          <div className="rail-section">
            <p className="panel-label">What matters</p>
            <ul className="simple-list">
              {cluster.keyFacts.map((fact) => (
                <li key={fact}>{fact}</li>
              ))}
            </ul>
          </div>

          <div className="rail-section">
            <p className="panel-label">What changed</p>
            <ul className="simple-list">
              {cluster.whatChanged.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>

          <div className="subscribe-card">
            <p className="panel-label">Subscriber value</p>
            <h3>Follow this story across updates.</h3>
            <p>
              Subscribers get saved clusters, correction-aware alerts, and morning and
              evening briefings.
            </p>
            <button className="primary-link button-reset" type="button">
              Unlock briefings
            </button>
          </div>
        </aside>

        <section className="cluster-main">
          <article className="panel content-panel">
            <div className="section-heading">
              <div>
                <p className="panel-label">Coverage stack</p>
                <h2>Read the cluster, not the noise.</h2>
              </div>
              <span className="cluster-badge">{cluster.reliabilityRange}</span>
            </div>

            <div className="article-stack">
              {cluster.articles.map((article) => (
                <article className="article-card" key={`${article.outlet}-${article.title}`}>
                  <img
                    src={article.image}
                    alt={`${article.outlet} article visual`}
                    className="article-card-image"
                  />
                  <div className="article-card-copy">
                    <div className="article-card-meta">
                      <span>{article.outlet}</span>
                      <span>{article.published}</span>
                      <span className={`framing-pill framing-${article.framing}`}>
                        {article.framing}
                      </span>
                    </div>
                    <h3>{article.title}</h3>
                    <p>{article.summary}</p>
                    <p className="article-reason">{article.reason}</p>
                  </div>
                </article>
              ))}
            </div>
          </article>

          <article className="panel content-panel">
            <div className="section-heading">
              <div>
                <p className="panel-label">Context Pack</p>
                <h2>Balanced Framing</h2>
              </div>
              <span className="cluster-badge">{balancedPack.length} reads</span>
            </div>

            <div className="context-grid">
              {balancedPack.map((item) => (
                <article className="context-card" key={`${item.outlet}-${item.title}`}>
                  <span className="context-outlet">{item.outlet}</span>
                  <h3>{item.title}</h3>
                  <p>{item.why}</p>
                </article>
              ))}
            </div>
          </article>
        </section>

        <aside className="inspector-rail">
          <article className="panel inspector-panel">
            <div className="section-heading">
              <div>
                <p className="panel-label">Perspective</p>
                <h2>Coverage structure</h2>
              </div>
              <span className="cluster-badge">{cluster.outletCount} outlets</span>
            </div>
            <div className="coverage-rows">
              <div className="coverage-row">
                <span>Left</span>
                <div className="dot-row" aria-hidden="true">
                  {Array.from({ length: cluster.coverageCounts.left }).map((_, index) => (
                    <span className="dot-left" key={`left-${index}`} />
                  ))}
                </div>
              </div>
              <div className="coverage-row">
                <span>Center</span>
                <div className="dot-row" aria-hidden="true">
                  {Array.from({ length: cluster.coverageCounts.center }).map((_, index) => (
                    <span className="dot-center" key={`center-${index}`} />
                  ))}
                </div>
              </div>
              <div className="coverage-row">
                <span>Right</span>
                <div className="dot-row" aria-hidden="true">
                  {Array.from({ length: cluster.coverageCounts.right }).map((_, index) => (
                    <span className="dot-right" key={`right-${index}`} />
                  ))}
                </div>
              </div>
            </div>
            <p className="inspector-note">
              Reliability range: {cluster.reliabilityRange}. Dots show outlet presence,
              not vote share or truth score.
            </p>
          </article>

          <article className="panel inspector-panel">
            <p className="panel-label">Evidence ledger</p>
            <ul className="evidence-list">
              {cluster.evidence.map((item) => (
                <li key={item.label}>
                  <strong>{item.label}</strong>
                  <span>
                    {item.type} · {item.source}
                  </span>
                </li>
              ))}
            </ul>
          </article>

          <article className="panel inspector-panel">
            <p className="panel-label">Corrections and versioning</p>
            <ul className="corrections-list">
              {cluster.corrections.map((item) => (
                <li key={`${item.timestamp}-${item.note}`}>
                  <strong>{item.timestamp}</strong>
                  <span>{item.note}</span>
                </li>
              ))}
            </ul>
          </article>
        </aside>
      </section>
    </main>
  )
}
