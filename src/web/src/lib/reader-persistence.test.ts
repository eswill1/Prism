import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildDisplayNameFromEmail,
  chooseAvailableHandle,
  sanitizeHandleSeed,
} from './reader-persistence'

test('sanitizeHandleSeed normalizes to a compact lowercase handle', () => {
  assert.equal(sanitizeHandleSeed('Ed.Williams+Prism'), 'ed-williams-prism')
  assert.equal(sanitizeHandleSeed('@@'), 'reader')
})

test('buildDisplayNameFromEmail turns the local part into a readable label', () => {
  assert.equal(buildDisplayNameFromEmail('ed_williams@example.com'), 'Ed Williams')
  assert.equal(buildDisplayNameFromEmail(undefined), 'Reader')
})

test('chooseAvailableHandle preserves the base when it is free', () => {
  assert.equal(chooseAvailableHandle('reader', ['other-handle']), 'reader')
})

test('chooseAvailableHandle adds the next numeric suffix when needed', () => {
  assert.equal(
    chooseAvailableHandle('reader', ['reader', 'reader-2', 'reader-3']),
    'reader-4',
  )
})
