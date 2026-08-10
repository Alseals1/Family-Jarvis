import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import HUDRing from '../components/HUDRing/HUDRing'
import Button from '../components/Button/Button'
import Card from '../components/Card/Card'

describe('HUDRing', () => {
  it('test_hud_ring_renders_without_crash', () => {
    const { container } = render(<HUDRing />)
    expect(container.firstChild).not.toBeNull()
  })

  it('test_hud_ring_has_jarvis_accessible_label', () => {
    render(<HUDRing />)
    expect(screen.getByRole('img', { name: 'JARVIS' })).toBeInTheDocument()
  })
})

describe('Button', () => {
  it('test_button_renders_children', () => {
    render(<Button>Click me</Button>)
    expect(screen.getByText('Click me')).toBeInTheDocument()
  })

  it('test_button_primary_variant_applies_class', () => {
    const { container } = render(<Button variant="primary">Primary</Button>)
    const btn = container.querySelector('button')
    expect(btn?.className).toMatch(/primary/)
  })

  it('test_button_secondary_variant_applies_class', () => {
    const { container } = render(<Button variant="secondary">Secondary</Button>)
    const btn = container.querySelector('button')
    expect(btn?.className).toMatch(/secondary/)
  })

  it('test_button_disabled_prevents_click', () => {
    const onClick = vi.fn()
    render(<Button disabled onClick={onClick}>Disabled</Button>)
    const btn = screen.getByText('Disabled')
    fireEvent.click(btn)
    expect(onClick).not.toHaveBeenCalled()
  })

  it('test_button_calls_onClick_when_clicked', () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Click</Button>)
    fireEvent.click(screen.getByText('Click'))
    expect(onClick).toHaveBeenCalledTimes(1)
  })
})

describe('Card', () => {
  it('test_card_renders_children', () => {
    render(<Card>Card content</Card>)
    expect(screen.getByText('Card content')).toBeInTheDocument()
  })
})

describe('Global styles', () => {
  it('test_global_styles_import_does_not_throw', async () => {
    await expect(import('../styles/global.css')).resolves.toBeDefined()
  })
})
