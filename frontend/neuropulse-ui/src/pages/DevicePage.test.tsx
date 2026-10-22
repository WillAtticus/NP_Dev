import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import DevicePage from './DevicePage'

describe('DevicePage role controls', () => {
  it('keeps device changes disabled for a researcher', () => {
    const html = renderToStaticMarkup(<DevicePage role="researcher" />)
    expect(html).toContain('disabled=""')
    expect(html).toContain('chỉ admin hoặc operator')
  })

  it('allows an operator to connect a device', () => {
    const html = renderToStaticMarkup(<DevicePage role="operator" />)
    expect(html).not.toContain('disabled=""')
  })
})
