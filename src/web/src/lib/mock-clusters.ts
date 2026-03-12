import type { StoryBrief } from './story-brief-types'

export type FramingGroup = 'left' | 'center' | 'right'

export type ClusterArticle = {
  outlet: string
  title: string
  summary: string
  feedSummary?: string
  bodyText?: string
  namedEntities?: string[]
  extractionQuality?: string
  accessTier?: 'open' | 'likely_paywalled' | 'unknown'
  published: string
  framing: FramingGroup
  image: string
  reason: string
  url?: string
}

export type EvidenceItem = {
  label: string
  source: string
  type: string
}

export type CorrectionItem = {
  timestamp: string
  note: string
}

export type ContextItem = {
  outlet: string
  title: string
  why: string
  url?: string
  accessTier?: 'open' | 'likely_paywalled' | 'unknown'
}

export type StoryChangeKind = 'summary' | 'coverage' | 'evidence' | 'correction'

export type StoryChangeItem = {
  timestamp: string
  kind: StoryChangeKind
  label: string
  detail: string
}

export type StoryCluster = {
  slug: string
  topic: string
  title: string
  dek: string
  updatedAt: string
  status: string
  heroImage: string
  heroAlt: string
  heroCredit: string
  outletCount: number
  reliabilityRange: string
  coverageCounts: Record<FramingGroup, number>
  keyFacts: string[]
  whatChanged: string[]
  changeTimeline: StoryChangeItem[]
  articles: ClusterArticle[]
  evidence: EvidenceItem[]
  corrections: CorrectionItem[]
  contextPacks: Record<string, ContextItem[]>
  generatedBrief?: StoryBrief
}

export const mockClusters: StoryCluster[] = [
  {
    slug: 'federal-budget-deadline',
    topic: 'US Policy',
    title: 'Federal budget talks enter a new deadline cycle',
    dek:
      'Lawmakers moved toward a short-term funding patch while both parties hardened their messaging around spending cuts, border provisions, and shutdown risk.',
    updatedAt: 'Updated 12 minutes ago',
    status: 'Developing',
    heroImage: 'https://picsum.photos/seed/prism-capitol/1600/900',
    heroAlt: 'Government building used as a stand-in editorial image for a budget story.',
    heroCredit: 'Prototype editorial image',
    outletCount: 18,
    reliabilityRange: 'Established to high',
    coverageCounts: {
      left: 3,
      center: 4,
      right: 2,
    },
    keyFacts: [
      'Leaders are signaling support for a short-term funding extension rather than a full agreement.',
      'Border and discretionary spending caps remain the main points of dispute.',
      'Coverage diverges most on political blame and the likely economic fallout of delay.',
    ],
    whatChanged: [
      'Two more national outlets entered the story after leadership comments late this morning.',
      'An evidence item was added for the latest committee memo.',
      'The story summary was revised to reflect the shift from shutdown rhetoric toward stopgap negotiations.',
    ],
    changeTimeline: [
      {
        timestamp: '10:42 AM',
        kind: 'summary',
        label: 'Story summary recast around the stopgap path',
        detail:
          'Prism updated the core summary after leadership clarified that negotiators were now converging on a short-term extension rather than a larger package.',
      },
      {
        timestamp: '10:17 AM',
        kind: 'coverage',
        label: 'Two additional national outlets entered the comparison set',
        detail:
          'The coverage stack widened after late-morning leadership comments pulled more process-heavy reporting into the story.',
      },
      {
        timestamp: '9:58 AM',
        kind: 'correction',
        label: 'Syndicated duplicate merged into the canonical AP item',
        detail:
          'A duplicate pickup was removed so the comparison stack reflects distinct reporting rather than repeated wire copy.',
      },
      {
        timestamp: '9:41 AM',
        kind: 'evidence',
        label: 'Committee memo added to the evidence ledger',
        detail:
          'The latest stopgap language memo now anchors the procedural claims surfaced in the story summary and article stack.',
      },
    ],
    articles: [
      {
        outlet: 'Associated Press',
        title: 'Congress moves closer to short-term spending patch as deadline looms',
        summary:
          'AP frames the latest step as a tactical extension, emphasizing legislative process and immediate timing.',
        published: '14m ago',
        framing: 'center',
        image: 'https://picsum.photos/seed/ap-capitol/640/420',
        reason: 'Most direct process-focused reporting in the story',
      },
      {
        outlet: 'The Hill',
        title: 'Border fight keeps budget deal out of reach even as shutdown clock ticks',
        summary:
          'Focuses on the policy tradeoffs that continue to block a larger agreement and highlights faction pressure.',
        published: '21m ago',
        framing: 'center',
        image: 'https://picsum.photos/seed/hill-hearing/640/420',
        reason: 'Strong synthesis of congressional dynamics',
      },
      {
        outlet: 'Bloomberg',
        title: 'Stopgap momentum builds as markets look past shutdown theatrics',
        summary:
          'Frames the event through investor expectations and the practical implications of another temporary fix.',
        published: '29m ago',
        framing: 'center',
        image: 'https://picsum.photos/seed/bloomberg-market/640/420',
        reason: 'Best market and macroeconomic angle',
      },
      {
        outlet: 'MSNBC',
        title: 'Democrats argue hardline demands are driving the latest budget standoff',
        summary:
          'Emphasizes party messaging and accountability narratives more than legislative mechanics.',
        published: '33m ago',
        framing: 'left',
        image: 'https://picsum.photos/seed/msnbc-press/640/420',
        reason: 'Useful for partisan blame framing comparison',
      },
      {
        outlet: 'Fox News',
        title: 'Spending fight sharpens as conservatives demand deeper cuts before deal',
        summary:
          'Centers fiscal leverage and conservative negotiating goals as the key explanatory frame.',
        published: '41m ago',
        framing: 'right',
        image: 'https://picsum.photos/seed/fox-podium/640/420',
        reason: 'Useful for right-leaning leverage framing',
      },
    ],
    evidence: [
      {
        label: 'Latest committee memo on stopgap language',
        source: 'House Appropriations',
        type: 'Committee memo',
      },
      {
        label: 'Leadership briefing transcript',
        source: 'Congressional leadership press conference',
        type: 'Transcript',
      },
      {
        label: 'Treasury warning on timing and agency operations',
        source: 'US Treasury',
        type: 'Official statement',
      },
    ],
    corrections: [
      {
        timestamp: '10:42 AM',
        note: 'Story summary updated after leadership clarified the stopgap duration under discussion.',
      },
      {
        timestamp: '9:58 AM',
        note: 'A syndicated duplicate was removed from the article stack and merged into the canonical AP item.',
      },
    ],
    contextPacks: {
      'Balanced Framing': [
        {
          outlet: 'Associated Press',
          title: 'Process-focused reporting on the funding patch',
          why: 'Baseline account of the legislative move without strong blame framing.',
        },
        {
          outlet: 'MSNBC',
          title: 'Accountability framing from the left',
          why: 'Shows how the conflict is being cast as a negotiating failure by the right.',
        },
        {
          outlet: 'Fox News',
          title: 'Leverage framing from the right',
          why: 'Shows the counter-frame that centers spending cuts and negotiation pressure.',
        },
      ],
      'Evidence-First': [
        {
          outlet: 'Associated Press',
          title: 'Coverage anchored in latest floor and committee actions',
          why: 'Highest ratio of direct sourcing to commentary.',
        },
        {
          outlet: 'The Hill',
          title: 'Detailed procedural analysis of what remains unresolved',
          why: 'Strong use of direct congressional sourcing and process detail.',
        },
      ],
      'Local Impact': [
        {
          outlet: 'Bloomberg',
          title: 'Economic risk and agency operations angle',
          why: 'Best immediate explanation of downstream effects.',
        },
      ],
      'International Comparison': [
        {
          outlet: 'Reuters',
          title: 'How international readers are seeing the US budget drama',
          why: 'Clean external framing with less domestic partisan packaging.',
        },
      ],
    },
  },
  {
    slug: 'europe-tech-regulation-push',
    topic: 'Global Tech',
    title: 'European regulators tighten pressure on major AI platforms',
    dek:
      'A new round of European scrutiny focused on disclosure, training-data transparency, and the pace of compliance for large model providers.',
    updatedAt: 'Updated 26 minutes ago',
    status: 'New',
    heroImage: 'https://picsum.photos/seed/prism-europe/1600/900',
    heroAlt: 'Conference hall image used as a stand-in editorial visual for a technology regulation story.',
    heroCredit: 'Prototype editorial image',
    outletCount: 11,
    reliabilityRange: 'Established to high',
    coverageCounts: {
      left: 2,
      center: 3,
      right: 1,
    },
    keyFacts: [
      'The regulatory push centers on transparency and compliance timelines rather than an outright usage ban.',
      'Business coverage emphasizes cost and pace; policy coverage emphasizes oversight and accountability.',
      'International outlets are framing the move as a global precedent-setting step.',
    ],
    whatChanged: [
      'This story was assembled from a fast-growing set of business and policy reports.',
    ],
    changeTimeline: [
      {
        timestamp: '9:24 AM',
        kind: 'coverage',
        label: 'Business and policy coverage began to converge',
        detail:
          'The story moved from scattered compliance reporting into a more coherent cross-outlet regulation narrative.',
      },
    ],
    articles: [],
    evidence: [],
    corrections: [],
    contextPacks: {
      'Balanced Framing': [],
    },
  },
  {
    slug: 'storm-recovery-energy-grid',
    topic: 'Climate and Infrastructure',
    title: 'Storm recovery raises new questions about grid resilience',
    dek:
      'Regional coverage is diverging between utility accountability, climate resilience planning, and immediate local recovery timelines.',
    updatedAt: 'Updated 44 minutes ago',
    status: 'Watch',
    heroImage: 'https://picsum.photos/seed/prism-grid/1600/900',
    heroAlt: 'Storm recovery infrastructure image used as a stand-in editorial visual.',
    heroCredit: 'Prototype editorial image',
    outletCount: 9,
    reliabilityRange: 'Generally reliable',
    coverageCounts: {
      left: 2,
      center: 2,
      right: 1,
    },
    keyFacts: [
      'Local coverage is more operational and recovery-focused than national commentary.',
      'The strongest divergence is over accountability versus infrastructure planning.',
    ],
    whatChanged: [
      'Regional utility outage maps were added as evidence references.',
    ],
    changeTimeline: [
      {
        timestamp: '8:52 AM',
        kind: 'evidence',
        label: 'Regional outage maps entered the story file',
        detail:
          'Utility and local-government operational data now support the recovery and resilience framing on the story page.',
      },
    ],
    articles: [],
    evidence: [],
    corrections: [],
    contextPacks: {
      'Balanced Framing': [],
    },
  },
]

export const clusterBySlug = Object.fromEntries(
  mockClusters.map((cluster) => [cluster.slug, cluster]),
) as Record<string, StoryCluster>
