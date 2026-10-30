import { describe, expect, it } from 'vitest'

import { paragraphs } from './text'

describe('paragraphs()', () => {
  it('splits on blank lines regardless of how many newlines the model used', () => {
    expect(paragraphs('one\n\ntwo\n\n\n\nthree')).toEqual(['one', 'two', 'three'])
  })

  it('keeps single line breaks inside a paragraph', () => {
    expect(paragraphs('line a\nline b')).toEqual(['line a\nline b'])
  })

  it('strips markdown emphasis the model was told not to use', () => {
    expect(paragraphs('You left me on **October 12**, *quietly*.')).toEqual(['You left me on October 12, quietly.'])
  })

  it('drops empty and whitespace-only paragraphs', () => {
    expect(paragraphs('\n\n  \n\nonly this\n\n')).toEqual(['only this'])
  })
})
