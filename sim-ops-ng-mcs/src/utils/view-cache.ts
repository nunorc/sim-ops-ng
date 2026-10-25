// Minimum time between two localStorage writes of a view's cached state
const VIEW_CACHE_INTERVAL_MS = 5000

/** Throttled localStorage cache of a view's last state, restored on the next mount and flushed on unmount. */
export function createViewCache(key: string) {
  let lastWrite = 0
  let unsaved: unknown = undefined

  function write(data: unknown) {
    unsaved = undefined
    lastWrite = Date.now()
    try {
      localStorage.setItem(key, JSON.stringify(data))
    } catch (e) {
      console.error(`Failed to cache ${key}:`, e)
    }
  }

  return {
    // The last cached state, or null when there is none or it can't be read
    load(): unknown {
      try {
        const cached = localStorage.getItem(key)
        return cached ? JSON.parse(cached) : null
      } catch (e) {
        console.error(`Failed to parse cached ${key}:`, e)
        return null
      }
    },
    save(data: unknown) {
      if (Date.now() - lastWrite >= VIEW_CACHE_INTERVAL_MS) write(data)
      else unsaved = data
    },
    flush() {
      if (unsaved !== undefined) write(unsaved)
    }
  }
}
