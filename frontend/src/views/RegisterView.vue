<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import http from '../api/http'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const email = ref('')
const nickname = ref('')
const password = ref('')
const loading = ref(false)
const err = ref('')

async function submit() {
  err.value = ''
  loading.value = true
  try {
    const { data } = await http.post('/auth/register', {
      email: email.value,
      nickname: nickname.value,
      password: password.value,
    })
    auth.setSession(data.access_token, nickname.value)
    router.replace('/rooms')
  } catch (e: unknown) {
    const x = e as { response?: { data?: { detail?: string } } }
    err.value = x.response?.data?.detail || '注册失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-card">
      <header class="auth-card__head">
        <h1 class="auth-card__title">注册</h1>
        <p class="auth-card__sub">创建账号后即可加入房间参与投票</p>
      </header>

      <p v-if="err" class="auth-err">{{ err }}</p>

      <div class="auth-field">
        <label class="auth-label" for="reg-email">邮箱</label>
        <input
          id="reg-email"
          v-model="email"
          class="auth-input"
          type="email"
          autocomplete="email"
          placeholder="you@example.com"
        />
      </div>
      <div class="auth-field">
        <label class="auth-label" for="reg-nickname">昵称</label>
        <input
          id="reg-nickname"
          v-model="nickname"
          class="auth-input"
          type="text"
          autocomplete="nickname"
          placeholder="房间内显示的名称"
        />
      </div>
      <div class="auth-field">
        <label class="auth-label" for="reg-password">密码</label>
        <input
          id="reg-password"
          v-model="password"
          class="auth-input"
          type="password"
          autocomplete="new-password"
          placeholder="至少 6 位"
        />
      </div>

      <button type="button" class="auth-btn" :disabled="loading" @click="submit">
        {{ loading ? '注册中…' : '注册并登录' }}
      </button>

      <p class="auth-footer">
        已有账号？
        <router-link to="/login">登录</router-link>
      </p>
    </div>
  </div>
</template>
