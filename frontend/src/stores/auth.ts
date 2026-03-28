import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import http from '../api/http'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('access_token'))
  const nickname = ref<string | null>(localStorage.getItem('nickname'))

  const isLoggedIn = computed(() => !!token.value)

  function setSession(accessToken: string, name?: string) {
    token.value = accessToken
    localStorage.setItem('access_token', accessToken)
    if (name) {
      nickname.value = name
      localStorage.setItem('nickname', name)
    }
  }

  function logout() {
    token.value = null
    nickname.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('nickname')
  }

  async function fetchMe() {
    const { data } = await http.get('/auth/me')
    nickname.value = data.nickname
    localStorage.setItem('nickname', data.nickname)
    return data
  }

  return { token, nickname, isLoggedIn, setSession, logout, fetchMe }
})
