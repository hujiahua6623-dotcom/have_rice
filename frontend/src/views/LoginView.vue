<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import http from '../api/http'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const email = ref('')
const password = ref('')
const loading = ref(false)
const err = ref('')

async function submit() {
  err.value = ''
  loading.value = true
  try {
    const { data } = await http.post('/auth/login', {
      email: email.value,
      password: password.value,
    })
    auth.setSession(data.access_token)
    await auth.fetchMe()
    const r = (route.query.redirect as string) || '/rooms'
    router.replace(r)
  } catch (e: unknown) {
    const x = e as { response?: { data?: { detail?: string } } }
    err.value = x.response?.data?.detail || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-card">
      <header class="auth-card__head">
        <h1 class="auth-card__title">登录</h1>
        <p class="auth-card__sub">使用邮箱与密码进入「大家来投票」</p>
      </header>

      <p v-if="err" class="auth-err">{{ err }}</p>

      <div class="auth-field">
        <label class="auth-label" for="login-email">邮箱</label>
        <input
          id="login-email"
          v-model="email"
          class="auth-input"
          type="email"
          autocomplete="email"
          placeholder="you@example.com"
        />
      </div>
      <div class="auth-field">
        <label class="auth-label" for="login-password">密码</label>
        <input
          id="login-password"
          v-model="password"
          class="auth-input"
          type="password"
          autocomplete="current-password"
          placeholder="至少 6 位"
        />
      </div>

      <button type="button" class="auth-btn" :disabled="loading" @click="submit">
        {{ loading ? '登录中…' : '登录' }}
      </button>

      <p class="auth-footer">
        还没有账号？
        <router-link to="/register">注册</router-link>
      </p>
    </div>
  </div>
</template>
