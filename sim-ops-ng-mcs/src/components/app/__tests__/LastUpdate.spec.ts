import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import LastUpdate from '../LastUpdate.vue'
import { useSocketStore } from '@/stores/app-websockets'
import type { SpacecraftState } from '@/types/state'

describe('LastUpdate', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows the last telemetry time', () => {
    const store = useSocketStore()
    store.sc_state = { ts: Date.UTC(2023, 7, 27, 4, 40, 0) / 1000 } as SpacecraftState

    const wrapper = mount(LastUpdate)
    expect(wrapper.text()).toContain('2023-08-27 04:40:00 UTC')
    expect(wrapper.text()).not.toContain('STALE')
  })

  it('shows a placeholder before any telemetry', () => {
    const wrapper = mount(LastUpdate)
    expect(wrapper.findAll('span')[1]!.text()).toBe('_')
  })
})
