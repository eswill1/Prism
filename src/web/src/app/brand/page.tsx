import { SiteFooter } from '../../components/site-footer'
import { SiteNav } from '../../components/site-nav'
import {
  DEFAULT_MASTHEAD_DIRECTION,
  MASTHEAD_DIRECTIONS,
  MastheadIdentity,
} from '../../components/masthead-directions'

export default function BrandPage() {
  return (
    <main className="page-shell content-page">
      <SiteNav />

      <header className="masthead">
        <div>
          <p className="eyebrow">Brand review</p>
          <h1>Masthead directions</h1>
          <p className="hero-dek">
            Three distinct identity directions for Prism, with the recommended live-site choice
            already applied in the header.
          </p>
        </div>
      </header>

      <section className="brand-direction-grid">
        {MASTHEAD_DIRECTIONS.map((direction) => {
          const isSelected = direction.key === DEFAULT_MASTHEAD_DIRECTION

          return (
            <article
              className={`brand-direction-card${isSelected ? ' brand-direction-card-selected' : ''}`}
              key={direction.key}
            >
              <div className="brand-direction-preview">
                <MastheadIdentity direction={direction.key} />
              </div>
              <div className="brand-direction-copy">
                <p className="panel-label">{direction.name}</p>
                <h2>{direction.summary}</h2>
                <p>{direction.recommendation}</p>
                {isSelected ? <span className="brand-selection-badge">Chosen for live site</span> : null}
              </div>
            </article>
          )
        })}
      </section>

      <SiteFooter />
    </main>
  )
}
