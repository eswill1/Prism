'use client'

import { useEffect, useState } from 'react'

import type { StoryCluster } from '../lib/mock-clusters'

type ContextPackPanelProps = {
  packs: StoryCluster['contextPacks']
}

const lensDescriptions: Record<string, string> = {
  'Balanced Framing':
    'A compact alternate-read set chosen to widen the frame without flattening disagreement.',
  'Evidence-First':
    'Prioritizes reporting with the strongest sourcing and direct document grounding.',
  'Local Impact':
    'Focuses on concrete operational, civic, and regional consequences.',
  'International Comparison':
    'Shows how the story looks when seen through a less domestic lens.',
}

export function ContextPackPanel({ packs }: ContextPackPanelProps) {
  const lenses = Object.keys(packs)
  const [activeLens, setActiveLens] = useState(lenses[0] ?? 'Balanced Framing')

  useEffect(() => {
    setActiveLens((current) => (packs[current] ? current : Object.keys(packs)[0] ?? 'Balanced Framing'))
  }, [packs])

  const activeItems = packs[activeLens] ?? []

  return (
    <article className="panel content-panel">
      <div className="section-heading">
        <div>
          <p className="panel-label">Read another angle</p>
          <h2>{activeLens}</h2>
        </div>
        <span className="cluster-badge">{activeItems.length} reads</span>
      </div>

      <div className="lens-tab-row" role="tablist" aria-label="Context pack lenses">
        {lenses.map((lens) => (
          <button
            aria-selected={lens === activeLens}
            className={`lens-tab ${lens === activeLens ? 'active' : ''}`}
            key={lens}
            onClick={() => setActiveLens(lens)}
            role="tab"
            type="button"
          >
            {lens}
          </button>
        ))}
      </div>

      <p className="lens-description">
        {lensDescriptions[activeLens] || 'A deliberate alternate-read set for this story.'}
      </p>

      {activeItems.length > 0 ? (
        <div className="context-grid">
          {activeItems.map((item, index) => (
            <article className="context-card" key={`${activeLens}-${item.outlet}-${item.title}`}>
              <div className="context-card-top">
                <span className="context-outlet">{item.outlet}</span>
                <span className="context-count">{`0${index + 1}`}</span>
              </div>
              <h3>{item.title}</h3>
              <div className="context-why">
                <span className="context-why-label">Why this read</span>
                <p>{item.why}</p>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="empty-module">
          <p className="panel-label">Coming next</p>
          <h3>This lens does not have a generated pack yet.</h3>
          <p>Prism will surface it once the story has enough source diversity to justify it.</p>
        </div>
      )}
    </article>
  )
}
