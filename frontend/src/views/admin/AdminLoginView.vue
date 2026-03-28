<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAdminAuthStore } from '../../stores/adminAuth'

const router = useRouter()
const route = useRoute()
const admin = useAdminAuthStore()

const username = ref('admin')
const password = ref('')
const err = ref('')
const loading = ref(false)

async function submit() {
  err.value = ''
  loading.value = true
  try {
    await admin.login(username.value, password.value)
    const redir = (route.query.redirect as string) || '/admin/rooms'
    router.replace(redir)
  } catch (e: unknown) {
    const x = e as { response?: { data?: { detail?: string } } }
    err.value = x.response?.data?.detail || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="admin-login">
    <div class="admin-login__card">
      <h1 class="admin-login__title">管理后台</h1>
      <p class="admin-login__sub">使用配置文件中的账号密码登录</p>
      <form class="admin-login__form" @submit.prevent="submit">
        <label class="admin-login__field">
          <span>账号</span>
          <input v-model="username" type="text" autocomplete="username" required />
        </label>
        <label class="admin-login__field">
          <span>密码</span>
          <input v-model="password" type="password" autocomplete="current-password" required />
        </label>
        <p v-if="err" class="admin-login__err">{{ err }}</p>
        <button type="submit" class="admin-login__btn" :disabled="loading">
          {{ loading ? '登录中…' : '登录' }}
        </button>
      </form>
      <p class="admin-login__footer">
        <router-link to="/rooms">返回玩家端</router-link>
      </p>
    </div>
  </div>
</template>

<style scoped>
.admin-login {
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
  background: linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%);
  box-sizing: border-box;
}

.admin-login__card {
  width: 100%;
  max-width: 400px;
  padding: 2rem 1.75rem;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 4px 24px rgba(15, 23, 42, 0.08);
  border: 1px solid #e2e8f0;
}

.admin-login__title {
  margin: 0 0 0.35rem;
  font-size: 1.5rem;
  font-weight: 700;
  color: #0f172a;
}

.admin-login__sub {
  margin: 0 0 1.5rem;
  font-size: 0.9rem;
  color: #64748b;
}

.admin-login__form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.admin-login__field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.875rem;
  color: #334155;
}

.admin-login__field input {
  padding: 0.6rem 0.75rem;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  font-size: 1rem;
}

.admin-login__field input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}

.admin-login__err {
  margin: 0;
  font-size: 0.875rem;
  color: #b91c1c;
}

.admin-login__btn {
  margin-top: 0.25rem;
  padding: 0.65rem 1rem;
  font-size: 1rem;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(180deg, #3b82f6 0%, #2563eb 100%);
  border: none;
  border-radius: 10px;
  cursor: pointer;
}

.admin-login__btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.admin-login__footer {
  margin: 1.25rem 0 0;
  text-align: center;
  font-size: 0.9rem;
}

.admin-login__footer a {
  color: #2563eb;
  text-decoration: none;
}

.admin-login__footer a:hover {
  text-decoration: underline;
}
</style>
