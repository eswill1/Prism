export type PerspectivePresenceItem = {
  label: string
  count: number
  note: string
}

export type StoryPerspectiveRevisionInfo = {
  stage: 'stored' | 'fallback'
  revisionTag: string
  comparedToTag?: string
  generatedAt?: string
  generatedAtLabel: string
  generationMethod: string
  generationMethodLabel: string
  changeSummary: string[]
}

export type StoryPerspective = {
  status: 'early' | 'ready'
  summary: string
  takeaways: string[]
  framingPresence: PerspectivePresenceItem[]
  sourceFamilyPresence: PerspectivePresenceItem[]
  scopePresence: PerspectivePresenceItem[]
  methodologyNote: string
  revision: StoryPerspectiveRevisionInfo
}
