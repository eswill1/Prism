export type PerspectivePresenceItem = {
  label: string
  count: number
  note: string
}

export type StoryPerspective = {
  status: 'early' | 'ready'
  summary: string
  takeaways: string[]
  framingPresence: PerspectivePresenceItem[]
  sourceFamilyPresence: PerspectivePresenceItem[]
  scopePresence: PerspectivePresenceItem[]
  methodologyNote: string
}
