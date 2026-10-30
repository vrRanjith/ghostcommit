// Split on blank lines so spacing comes from CSS, not from however many newlines the model
// emitted; also drop stray markdown emphasis from older replies.
export function paragraphs(text: string): string[] {
  return text
    .replace(/\*\*?([^*]+)\*\*?/g, '$1')
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean)
}
