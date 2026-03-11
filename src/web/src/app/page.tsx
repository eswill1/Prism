import Link from 'next/link'

import { mockClusters } from '../lib/mock-clusters'

const launchFeatures = [
  'Morning and evening cluster briefings',
  'Perspective panels with visible disagreement',
  'Saved stories with correction-aware follow-up alerts',
]

const featuredCluster = mockClusters[0]

export default function HomePage() {
  return (
    <main className="page-shell home-page">
      <header className="masthead">
        <div>
          <p className="eyebrow">The Prism Wire</p>
          <h1>Understand the shape of the story before you choose a side.</h1>
        </div>
        <nav className="masthead-nav">
          <a href="#briefings">Briefings</a>
          <a href="#clusters">Top clusters</a>
          <a href="#value">Why subscribe</a>
          <Link href="/live">Live prototype</Link>
        </nav>
      </header>

      <section className="hero-cluster panel">
        <div className="hero-media">
          <img
            src={featuredCluster.heroImage}
            alt={featuredCluster.heroAlt}
            className="hero-image"
          />
          <span className="media-credit">{featuredCluster.heroCredit}</span>
        </div>

        <div className="hero-copy-pane">
          <div className="hero-meta-line">
            <span className="status-chip">{featuredCluster.status}</span>
            <span>{featuredCluster.updatedAt}</span>
            <span>{featuredCluster.outletCount} outlets</span>
          </div>
          <p className="panel-label">{featuredCluster.topic}</p>
          <h2>{featuredCluster.title}</h2>
          <p className="hero-dek">{featuredCluster.dek}</p>

          <div className="hero-proof-grid">
            <div className="metric-tile">
              <span className="metric-label">Reliability range</span>
              <strong>{featuredCluster.reliabilityRange}</strong>
            </div>
            <div className="metric-tile">
              <span className="metric-label">Coverage spread</span>
              <strong>Left / Center / Right present</strong>
            </div>
            <div className="metric-tile">
              <span className="metric-label">Context</span>
              <strong>4 launch lenses available</strong>
            </div>
          </div>

          <div className="hero-actions">
            <Link className="primary-link" href={`/clusters/${featuredCluster.slug}`}>
              Open live cluster
            </Link>
            <Link className="secondary-link" href="/live">
              View temporary live feed
            </Link>
          </div>
        </div>
      </section>

      <section className="briefing-band panel" id="briefings">
        <div>
          <p className="panel-label">Daily value</p>
          <h2>Built for briefings, not bingeing.</h2>
        </div>
        <ul className="briefing-list">
          {launchFeatures.map((feature) => (
            <li key={feature}>{feature}</li>
          ))}
        </ul>
      </section>

      <section className="cluster-grid" id="clusters">
        {mockClusters.map((cluster) => (
          <article className="cluster-card panel" key={cluster.slug}>
            <img
              src={cluster.heroImage}
              alt={cluster.heroAlt}
              className="cluster-card-image"
            />
            <div className="cluster-card-body">
              <div className="cluster-card-meta">
                <span className="status-chip">{cluster.status}</span>
                <span>{cluster.updatedAt}</span>
              </div>
              <p className="panel-label">{cluster.topic}</p>
              <h3>{cluster.title}</h3>
              <p>{cluster.dek}</p>
              <div className="cluster-card-footer">
                <span>{cluster.outletCount} outlets</span>
                <Link href={`/clusters/${cluster.slug}`}>Open cluster</Link>
              </div>
            </div>
          </article>
        ))}
      </section>

      <section className="grid-section" id="value">
        <article className="panel value-panel">
          <p className="panel-label">Why it monetizes</p>
          <h2>People pay for less noise when the understanding is obviously better.</h2>
          <p>
            Prism can charge for briefings, saved clusters, follow alerts, and premium
            monitoring because the product removes work from understanding the news.
          </p>
        </article>

        <article className="panel value-panel">
          <p className="panel-label">What to build next</p>
          <h2>One strong cluster page can prove the whole model.</h2>
          <p>
            The next milestone is not more homepage chrome. It is a live cluster page
            that makes people feel instantly more informed than standard news apps do.
          </p>
          <Link className="secondary-link" href={`/clusters/${featuredCluster.slug}`}>
            Review prototype cluster
          </Link>
        </article>
      </section>
    </main>
  )
}
