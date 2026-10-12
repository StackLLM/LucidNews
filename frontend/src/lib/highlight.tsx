import type { ReactNode } from 'react'

/** Lower case, no accents; one character in, one character out so positions still line up. */
function fold(text: string): string {
  return [...text].map((char) => char.normalize('NFD').replace(/\p{M}/gu, '').charAt(0).toLowerCase() || char).join('')
}

/**
 * The text with the searched words marked. Like the search, it ignores case and accents and
 * matches the start of words (``kuber`` marks the start of ``Kubernetes``).
 */
export function highlight(text: string, terms: string[]): ReactNode {
  const folded = [...fold(text)]
  const characters = [...text]
  const marked = new Array<boolean>(characters.length).fill(false)
  for (const term of terms.map(fold).filter(Boolean)) {
    const chars = [...term]
    for (let start = 0; start + chars.length <= folded.length; start += 1) {
      const atWordStart = start === 0 || !/[\p{L}\p{N}]/u.test(folded[start - 1])
      if (atWordStart && chars.every((char, offset) => folded[start + offset] === char)) {
        for (let offset = 0; offset < chars.length; offset += 1) marked[start + offset] = true
      }
    }
  }
  const parts: ReactNode[] = []
  let index = 0
  while (index < characters.length) {
    let end = index
    while (end < characters.length && marked[end] === marked[index]) end += 1
    const piece = characters.slice(index, end).join('')
    parts.push(marked[index] ? <mark key={index} className="rounded-sm bg-accent/15 px-0.5 text-inherit">{piece}</mark> : piece)
    index = end
  }
  return parts
}
