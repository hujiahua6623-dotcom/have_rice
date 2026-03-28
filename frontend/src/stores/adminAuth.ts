import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import adminHttp, { ADMIN_ACCESS_TOKEN_KEY } from '../api/adminHttp'

export const useAdminAuthStore = defineStore('adminAuth', () => {
  const accessToken = ref<string | null>(localStorage.getItem(ADMIN_ACCESS_TOKEN_KEY))

  const isLoggedIn = computed(() => !!accessToken.value)

  function setToken(token: string) {
    accessToken.value = token
    localStorage.setItem(ADMIN_ACCESS_TOKEN_KEY, token)
  }

  function logout() {
    accessToken.value = null
    localStorage.removeItem(ADMIN_ACCESS_TOKEN_KEY)
  }

  async function login(username: string, password: string) {
    const { data } = await adminHttp.post<{ access_token: string; token_type: string }>('/admin/login', {
      username,
      password,
    })
    setToken(data.access_token)
  }

  return { accessToken, isLoggedIn, setToken, logout, login }
})
