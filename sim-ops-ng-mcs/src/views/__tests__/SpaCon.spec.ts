import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import axios from 'axios'
import SpaCon from '../SpaCon.vue'
import Card from '@/components/bootstrap/Card.vue'
import CardBody from '@/components/bootstrap/CardBody.vue'
import CardHeader from '@/components/bootstrap/CardHeader.vue'
import { useAuthStore } from '@/stores/app-auth'
import { useSocketStore } from '@/stores/app-websockets'

vi.mock('axios')

// bootstrap's Modal needs a real layout; record show/hide per modal instead
const modals = vi.hoisted(() => [] as { selector: string; show: () => void; hide: () => void; shown: boolean }[])
vi.mock('bootstrap', () => ({
  Modal: class {
    shown = false
    constructor(public selector: string) {
      modals.push(this)
    }
    show() {
      this.shown = true
    }
    hide() {
      this.shown = false
    }
  }
}))

const AUTH = { headers: { 'X-User-Password': 'user-pw' } }

function mountSpaCon(): VueWrapper {
  return mount(SpaCon, {
    attachTo: document.body,
    global: { components: { Card, CardBody, CardHeader } }
  })
}

const button = (wrapper: VueWrapper, text: string) => {
  const found = wrapper.findAll('button').filter((b) => b.text() === text)
  expect(found, `button ${text}`).toHaveLength(1)
  return found[0]!
}

const stackCells = (wrapper: VueWrapper) => wrapper.findAll('#manual-stack tr').map((tr) => tr.find('td').text())

// the file input of upload modal n, with `name` picked (or the picker cancelled)
async function pickFile(wrapper: VueWrapper, n: number, name: string | null) {
  const input = wrapper.find(`#my-modal-${n} input[type=file]`)
  Object.defineProperty(input.element, 'files', { value: name ? [new File(['x'], name)] : [], configurable: true })
  await input.trigger('change')
}

describe('SpaCon', () => {
  let wrapper: VueWrapper

  beforeEach(() => {
    setActivePinia(createPinia())
    useAuthStore().setPassword('user-pw')
    modals.length = 0
    vi.mocked(axios.post).mockReset().mockResolvedValue({ data: {} })
    vi.mocked(axios.delete).mockReset().mockResolvedValue({ data: {} })
    vi.mocked(axios.get).mockReset()
    wrapper = mountSpaCon()
  })

  afterEach(() => {
    wrapper.unmount()
    sessionStorage.clear()
  })

  describe('TC stack', () => {
    it('pushes a catalogue TC and shows it pending until the stack has it', async () => {
      await button(wrapper, 'TC_AOCS_001').trigger('click')

      expect(axios.post).toHaveBeenCalledWith(
        '/api/tc-stack',
        { system: 'spacecraft', control: 'aocs_mode', value: 'SUN', command: 'TC_AOCS_001' },
        AUTH
      )
      expect(wrapper.find('#manual-stack tr .spinner-border').exists()).toBe(true)

      useSocketStore().tc_stack = [{ command: 'TC_AOCS_001' }]
      await flushPromises()
      expect(wrapper.find('#manual-stack .spinner-border').exists()).toBe(false)
      expect(stackCells(wrapper)).toEqual(['TC_AOCS_001', 'none', 'none', 'none', 'none'])
    })

    it('clears the pending row when the push fails', async () => {
      vi.mocked(axios.post).mockRejectedValueOnce(new Error('Stack full (max 5)'))
      vi.spyOn(console, 'error').mockImplementation(() => {})

      await button(wrapper, 'TC_AOCS_001').trigger('click')
      await flushPromises()
      expect(wrapper.find('#manual-stack .spinner-border').exists()).toBe(false)
    })

    it('sends boolean TC values as booleans', async () => {
      await button(wrapper, 'TC_DHS_021').trigger('click')
      expect(vi.mocked(axios.post).mock.calls[0]![1]).toMatchObject({ control: 'dhs_mem_dump_enabled', value: true })
    })

    it('deletes an entry by its index without following the link', async () => {
      useSocketStore().tc_stack = [{ command: 'TC_AOCS_001' }, { command: 'TC_EPS_001' }]
      await flushPromises()

      const links = wrapper.findAll('#manual-stack a')
      expect(links).toHaveLength(2)
      const event = new MouseEvent('click', { bubbles: true, cancelable: true })
      links[1]!.element.dispatchEvent(event)

      expect(event.defaultPrevented).toBe(true)
      expect(axios.delete).toHaveBeenCalledWith('/api/tc-stack/1', AUTH)
    })

    it('arms, then executes the head of the stack, pending in history until its result lands', async () => {
      const store = useSocketStore()
      expect(button(wrapper, 'ARM').attributes('disabled')).toBeDefined()

      store.tc_stack = [{ command: 'TC_AOCS_001' }]
      await flushPromises()
      expect(button(wrapper, 'ARM').attributes('disabled')).toBeUndefined()
      expect(button(wrapper, 'GO').attributes('disabled')).toBeDefined()

      await button(wrapper, 'ARM').trigger('click')
      expect(button(wrapper, 'GO').attributes('disabled')).toBeUndefined()

      await button(wrapper, 'GO').trigger('click')
      expect(axios.post).toHaveBeenCalledWith('/api/tc-stack/execute', null, AUTH)
      await flushPromises()
      expect(button(wrapper, 'GO').attributes('disabled')).toBeDefined()
      const historySpinner = () => wrapper.findAll('table').at(1)!.find('.spinner-border').exists()
      expect(historySpinner()).toBe(true)

      store.tc_history = [{ command: 'TC_AOCS_001', status: 'g:REL g:ACC g:EXE', ts: '2026-10-24T10:00:00Z' }]
      await flushPromises()
      expect(historySpinner()).toBe(false)
    })
  })

  describe('uploads', () => {
    it('uplinks the file picked in that modal, directly rather than via the stack', async () => {
      const uplink = () => wrapper.find('#my-modal-1 .modal-footer button.btn-outline-theme')
      expect(uplink().attributes('disabled')).toBeDefined()

      await pickFile(wrapper, 1, 'sequence-2026-10-24.txt')
      expect(uplink().attributes('disabled')).toBeUndefined()
      // each modal keeps its own selection
      expect(wrapper.find('#my-modal-2 .modal-footer button.btn-outline-theme').attributes('disabled')).toBeDefined()

      await button(wrapper, 'CommandSequence').trigger('click')
      expect(modals[0]!.shown).toBe(true)

      await uplink().trigger('click')
      expect(axios.post).toHaveBeenCalledWith(
        '/api/tc-stack/send',
        {
          system: 'spacecraft',
          control: 'dhs_uploaded',
          value: 'command-seq > sequence-2026-',
          command: 'UP: command-seq > sequence-2026-'
        },
        AUTH
      )
      expect(modals.every((m) => !m.shown)).toBe(true)
    })

    it('forgets the selection when the file picker is cancelled', async () => {
      await pickFile(wrapper, 2, 'orbit.txt')
      await pickFile(wrapper, 2, null)
      expect(wrapper.find('#my-modal-2 .modal-footer button.btn-outline-theme').attributes('disabled')).toBeDefined()
    })

    it('offers only ready flight-dynamics products as a TTQ, the first preselected', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({
        data: [
          { id: 'pass_1-1700000000', status: 2, validity: 2, data: [] },
          { id: 'pass_2-1700005000', status: 1, validity: 0, data: [] },
          { id: 'pass_3-1700010000', status: 2, validity: 1, data: [] }
        ]
      })

      await button(wrapper, 'FlightDynamics').trigger('click')
      await flushPromises()
      expect(axios.get).toHaveBeenCalledWith('/api/obj-store/fd', AUTH)
      expect(modals[3]!.shown).toBe(true)

      const radios = wrapper.findAll('#my-modal-4 input[type=radio]')
      expect(radios.map((r) => (r.element as HTMLInputElement).value)).toEqual(['pass_1-1700000000', 'pass_3-1700010000'])
      expect((radios[0]!.element as HTMLInputElement).checked).toBe(true)

      await radios[1]!.setValue(true)
      await wrapper.find('#my-modal-4 .modal-footer button.btn-outline-theme').trigger('click')
      expect(vi.mocked(axios.post).mock.calls[0]![1]).toMatchObject({ value: 'fd-ttq > pass_3-1700010', command: 'UP: fd-ttq > pass_3-1700010' })
    })
  })
})
