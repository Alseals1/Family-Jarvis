// @vitest-environment node
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

const ROOT = resolve(__dirname, '../../')
const PUBLIC = resolve(ROOT, 'public')

function readManifest() {
  const raw = readFileSync(resolve(PUBLIC, 'manifest.json'), 'utf-8')
  return JSON.parse(raw) as Record<string, unknown>
}

function readIndexHtml() {
  return readFileSync(resolve(ROOT, 'index.html'), 'utf-8')
}

describe('PWA manifest', () => {
  it('test_manifest_file_exists_at_public_path', () => {
    expect(() => readFileSync(resolve(PUBLIC, 'manifest.json'))).not.toThrow()
  })

  it('test_manifest_has_required_fields', () => {
    const m = readManifest()
    expect(m).toHaveProperty('name')
    expect(m).toHaveProperty('short_name')
    expect(m).toHaveProperty('start_url')
    expect(m).toHaveProperty('display')
    expect(m).toHaveProperty('icons')
  })

  it('test_manifest_theme_color_is_jarvis_dark', () => {
    const m = readManifest()
    expect(m.theme_color).toBe('#070b12')
  })

  it('test_manifest_display_is_standalone', () => {
    const m = readManifest()
    expect(m.display).toBe('standalone')
  })

  it('test_manifest_has_192_icon', () => {
    const m = readManifest()
    const icons = m.icons as Array<{ sizes: string; src: string }>
    expect(icons.some(i => i.sizes === '192x192')).toBe(true)
  })

  it('test_manifest_has_512_icon', () => {
    const m = readManifest()
    const icons = m.icons as Array<{ sizes: string; src: string }>
    expect(icons.some(i => i.sizes === '512x512')).toBe(true)
  })
})

describe('index.html PWA meta tags', () => {
  it('test_index_html_has_manifest_link', () => {
    const html = readIndexHtml()
    expect(html).toContain('rel="manifest"')
    expect(html).toContain('href="/manifest.json"')
  })

  it('test_index_html_has_apple_mobile_capable_meta', () => {
    const html = readIndexHtml()
    expect(html).toContain('apple-mobile-web-app-capable')
    expect(html).toContain('yes')
  })

  it('test_index_html_has_theme_color_meta', () => {
    const html = readIndexHtml()
    expect(html).toContain('name="theme-color"')
    expect(html).toContain('#070b12')
  })
})

describe('Service worker', () => {
  it('test_service_worker_file_exists', () => {
    expect(() => readFileSync(resolve(PUBLIC, 'sw.js'))).not.toThrow()
  })
})
