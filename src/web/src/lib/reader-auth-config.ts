export type ReaderEmailAuthMode = 'magic_link' | 'otp'

export function getReaderEmailAuthMode(): ReaderEmailAuthMode {
  return process.env.NEXT_PUBLIC_PRISM_READER_EMAIL_AUTH_MODE === 'otp'
    ? 'otp'
    : 'magic_link'
}
