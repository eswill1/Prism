import { ReaderSyncPanel } from '../../components/reader-sync-panel'
import { SiteFooter } from '../../components/site-footer'
import { SiteNav } from '../../components/site-nav'

export default function SyncPage() {
  return (
    <main className="page-shell saved-page">
      <SiteNav />
      <header className="masthead">
        <div>
          <p className="eyebrow">Sync</p>
          <h1>Optional sign-in for saved and followed stories.</h1>
          <p className="hero-dek">
            Reading Prism stays open by default. This page only exists for readers who want
            their tracked stories to persist beyond one browser.
          </p>
        </div>
      </header>
      <ReaderSyncPanel />
      <SiteFooter />
    </main>
  )
}
