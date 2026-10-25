// Node >= 25's own localStorage/sessionStorage shadow jsdom's and are unusable here: put jsdom's back
declare const jsdom: { window: Window } | undefined

if (typeof jsdom !== 'undefined') {
  for (const name of ['localStorage', 'sessionStorage'] as const) {
    Object.defineProperty(globalThis, name, { value: jsdom.window[name], configurable: true, writable: true })
  }
}
