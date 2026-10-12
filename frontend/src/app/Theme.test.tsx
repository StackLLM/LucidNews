import { fireEvent, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { mockApi, renderAt } from '../test/render'

afterEach(() => {
  delete document.documentElement.dataset.theme
})

describe('theme', () => {
  it('is light until the reader switches it, then remembers the choice', async () => {
    mockApi()
    renderAt('/')
    expect(document.documentElement.dataset.theme).toBeUndefined()

    fireEvent.click(await screen.findByRole('button', { name: /Switch to the dark theme/i }))
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(window.localStorage.getItem('lucidnews.theme')).toBe('dark')

    fireEvent.click(screen.getByRole('button', { name: /Switch to the light theme/i }))
    expect(document.documentElement.dataset.theme).toBeUndefined()
    expect(window.localStorage.getItem('lucidnews.theme')).toBe('light')
  })

  it('starts dark when the reader chose it before', async () => {
    window.localStorage.setItem('lucidnews.theme', 'dark')
    mockApi()
    renderAt('/')
    expect(await screen.findByRole('button', { name: /Switch to the light theme/i })).toBeInTheDocument()
    expect(document.documentElement.dataset.theme).toBe('dark')
  })
})
