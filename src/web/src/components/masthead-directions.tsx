type MastheadDirectionKey = 'wire' | 'signal' | 'ledger'

type MastheadDirection = {
  key: MastheadDirectionKey
  name: string
  summary: string
  recommendation: string
}

export const DEFAULT_MASTHEAD_DIRECTION: MastheadDirectionKey = 'signal'

export const MASTHEAD_DIRECTIONS: MastheadDirection[] = [
  {
    key: 'wire',
    name: 'Wire',
    summary: 'Publication-first, clean, and closest to a premium national news masthead.',
    recommendation: 'Strong if Prism should feel like an established national publication first.',
  },
  {
    key: 'signal',
    name: 'Signal',
    summary: 'Sharper product energy with the prism metaphor more visible in the mark.',
    recommendation: 'Selected for the live site because it feels most distinctive without losing seriousness.',
  },
  {
    key: 'ledger',
    name: 'Ledger',
    summary: 'Institutional and durable, with more public-utility and archive energy.',
    recommendation: 'Best if the brand should lean civic, archival, and trust-heavy.',
  },
]

function WireMark() {
  return (
    <svg aria-hidden="true" className="masthead-mark-svg" viewBox="0 0 88 56">
      <path d="M4 28H22" fill="none" stroke="#0c6f73" strokeLinecap="round" strokeWidth="3.5" />
      <path
        d="M22 14L38 28L22 42L38 28L52 28"
        fill="none"
        stroke="#c07a1f"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="3.5"
      />
      <path d="M52 20H84" fill="none" stroke="#0c6f73" strokeLinecap="round" strokeWidth="3.5" />
      <path d="M52 28H84" fill="none" stroke="#c07a1f" strokeLinecap="round" strokeWidth="3.5" />
      <path d="M52 36H84" fill="none" stroke="#a4462c" strokeLinecap="round" strokeWidth="3.5" />
    </svg>
  )
}

function SignalMark() {
  return (
    <svg aria-hidden="true" className="masthead-mark-svg" viewBox="0 0 88 56">
      <circle cx="28" cy="28" fill="none" r="19" stroke="#102030" strokeWidth="3.5" />
      <path d="M9 28H47" fill="none" stroke="#102030" strokeLinecap="round" strokeWidth="3.5" />
      <path d="M47 18L80 8" fill="none" stroke="#0c6f73" strokeLinecap="round" strokeWidth="3.5" />
      <path d="M47 28H82" fill="none" stroke="#c07a1f" strokeLinecap="round" strokeWidth="3.5" />
      <path d="M47 38L80 48" fill="none" stroke="#a4462c" strokeLinecap="round" strokeWidth="3.5" />
    </svg>
  )
}

function LedgerMark() {
  return (
    <svg aria-hidden="true" className="masthead-mark-svg" viewBox="0 0 88 56">
      <rect
        fill="none"
        height="42"
        rx="8"
        stroke="#102030"
        strokeWidth="3.5"
        width="42"
        x="4"
        y="7"
      />
      <path
        d="M20 16V40M20 16H31C36.5 16 40 19 40 24C40 29 36.5 32 31 32H20"
        fill="none"
        stroke="#c07a1f"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="3.5"
      />
      <path d="M52 18H84" fill="none" stroke="#102030" strokeLinecap="round" strokeWidth="3.5" />
      <path d="M52 28H78" fill="none" stroke="#0c6f73" strokeLinecap="round" strokeWidth="3.5" />
      <path d="M52 38H84" fill="none" stroke="#a4462c" strokeLinecap="round" strokeWidth="3.5" />
    </svg>
  )
}

function getDirectionText(direction: MastheadDirectionKey) {
  switch (direction) {
    case 'wire':
      return {
        kicker: 'Prism',
        title: 'The Prism Wire',
      }
    case 'signal':
      return {
        kicker: 'The Prism Wire',
        title: 'Prism',
      }
    case 'ledger':
      return {
        kicker: 'Prism Public Desk',
        title: 'The Prism Wire',
      }
  }
}

function getDirectionMark(direction: MastheadDirectionKey) {
  switch (direction) {
    case 'wire':
      return <WireMark />
    case 'signal':
      return <SignalMark />
    case 'ledger':
      return <LedgerMark />
  }
}

export function MastheadIdentity({
  direction,
}: {
  direction: MastheadDirectionKey
}) {
  const text = getDirectionText(direction)

  return (
    <div className={`masthead-identity masthead-identity-${direction}`}>
      <span className="masthead-mark">{getDirectionMark(direction)}</span>
      <div className="masthead-wordmark">
        <span className="masthead-kicker">{text.kicker}</span>
        <strong>{text.title}</strong>
      </div>
    </div>
  )
}
