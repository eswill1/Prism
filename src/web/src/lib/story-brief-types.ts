export type StoryBrief = {
  label: string
  title: string
  paragraphs: string[]
  whyItMatters: string
  whereSourcesAgree: string
  whereCoverageDiffers: string
  whatToWatch: string
  supportingPoints: string[]
  substantiveSourceCount: number
  isEarlyBrief: boolean
  isVisible: boolean
  hideReason?: string
  revisionTag?: string
}
