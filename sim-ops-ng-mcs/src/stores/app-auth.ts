import { defineStore } from 'pinia'
import { ref } from 'vue'

const AUTH_STORAGE_KEY = 'auth_session'

// WS auth in Sec-WebSocket-Protocol (no WS headers in browsers): "sim-ops" + "sim-ops.password.<unpadded base64url>"
export function wsAuthProtocols(password: string): string[] {
  const bytes = new TextEncoder().encode(password)
  const b64 = btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  return ['sim-ops', `sim-ops.password.${b64}`]
}

export const useAuthStore = defineStore('auth', () => {
  // sessionStorage, not localStorage: the credential must not outlive the tab.
  const storedSession = typeof window !== 'undefined' ? sessionStorage.getItem(AUTH_STORAGE_KEY) : null
  const storedData = storedSession ? JSON.parse(storedSession) : null

  if (typeof window !== 'undefined') {
    localStorage.removeItem(AUTH_STORAGE_KEY)
  }

  const password = ref<string | null>(storedData?.password || null)
  const isAuthenticated = ref(storedData?.isAuthenticated || false)
  const authMessage = ref<string | null>(null)

  function setPassword(pwd: string) {
    password.value = pwd
    isAuthenticated.value = true
    authMessage.value = null

    // persist to sessionStorage so a refresh does not re-prompt within this tab
    if (typeof window !== 'undefined') {
      sessionStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify({
        password: pwd,
        isAuthenticated: true
      }))
    }
  }

  function clearAuth() {
    password.value = null
    isAuthenticated.value = false

    // clear from sessionStorage
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem(AUTH_STORAGE_KEY)
    }
  }

  // Invalidate the current session and re-show the login dialog with a reason.
  function expireSession(message: string) {
    clearAuth()
    authMessage.value = message
  }

  // axios config for authenticated API calls: a header, never a query parameter, which ends up in access logs
  function authConfig() {
    return { headers: { 'X-User-Password': password.value ?? '' } }
  }

  return {
    password,
    isAuthenticated,
    authMessage,
    setPassword,
    clearAuth,
    expireSession,
    authConfig
  }
})

