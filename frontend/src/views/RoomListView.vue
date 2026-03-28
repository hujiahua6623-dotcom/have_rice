<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import http from '../api/http'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

interface RoomItem {
  id: number
  name: string
  max_players: number
  member_count: number
  online_count: number
  status: string
}

const rooms = ref<RoomItem[]>([])
const loading = ref(false)
const err = ref('')

async function load() {
  err.value = ''
  loading.value = true
  try {
    const { data } = await http.get<RoomItem[]>('/rooms')
    rooms.value = data
  } catch {
    err.value = '加载房间失败'
  } finally {
    loading.value = false
  }
}

async function enter(id: number) {
  err.value = ''
  try {
    await http.post(`/rooms/${id}/join`)
    router.push(`/room/${id}`)
  } catch (e: unknown) {
    const x = e as { response?: { data?: { detail?: string } } }
    err.value = x.response?.data?.detail || '进入失败'
  }
}

function logout() {
  auth.logout()
  router.push('/login')
}

onMounted(load)
</script>

<template>
  <div class="list-page">
    <header class="list-header">
      <div class="list-header__titles">
        <h1 class="list-title">开放房间</h1>
        <p class="list-sub">选择房间进入，与好友一起投票</p>
      </div>
      <div class="list-header__user">
        <span v-if="auth.nickname" class="list-nickname">{{ auth.nickname }}</span>
        <button type="button" class="btn-ghost" @click="logout">退出</button>
      </div>
    </header>

    <div class="list-toolbar">
      <button type="button" class="btn-refresh" :disabled="loading" @click="load">
        {{ loading ? '加载中…' : '刷新列表' }}
      </button>
    </div>

    <p v-if="err" class="list-err">{{ err }}</p>

    <ul class="room-list">
      <li v-for="r in rooms" :key="r.id" class="room-card">
        <div class="room-card__body">
          <h2 class="room-card__name">{{ r.name }}</h2>
          <div class="room-card__stats">
            <span class="stat"
              ><span class="stat__label">已进入</span> {{ r.member_count }} / {{ r.max_players }}</span
            >
            <span class="stat"
              ><span class="stat__label">在线</span> {{ r.online_count }}</span
            >
          </div>
        </div>
        <button type="button" class="btn-enter" @click="enter(r.id)">进入</button>
      </li>
    </ul>

    <div v-if="!loading && rooms.length === 0" class="list-empty">
      <p>暂无开放房间</p>
      <p class="list-empty__hint">请管理员在后台创建并开放房间后再来。</p>
    </div>
  </div>
</template>

<style scoped>
.list-page {
  min-height: 100%;
  max-width: 720px;
  margin: 0 auto;
  padding: 1.25rem 1rem 2.5rem;
  background: linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%);
  box-sizing: border-box;
}

.list-header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.25rem;
}

.list-title {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.list-sub {
  margin: 0.35rem 0 0;
  font-size: 0.9rem;
  color: #64748b;
}

.list-header__user {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.list-nickname {
  font-size: 0.9rem;
  color: #334155;
  font-weight: 600;
}

.btn-ghost {
  padding: 0.4rem 0.75rem;
  font-size: 0.875rem;
  color: #475569;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  cursor: pointer;
  transition:
    background 0.15s,
    border-color 0.15s;
}

.btn-ghost:hover {
  background: #f8fafc;
  border-color: #cbd5e1;
  color: #1e293b;
}

.list-toolbar {
  margin-bottom: 0.75rem;
}

.btn-refresh {
  padding: 0.45rem 1rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: #3730a3;
  background: #eef2ff;
  border: 1px solid #c7d2fe;
  border-radius: 10px;
  cursor: pointer;
  transition:
    background 0.15s,
    transform 0.08s;
}

.btn-refresh:hover:not(:disabled) {
  background: #e0e7ff;
}

.btn-refresh:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.list-err {
  margin: 0 0 1rem;
  color: #b91c1c;
  font-size: 0.95rem;
}

.room-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.room-card {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1.15rem;
  background: #fff;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
}

.room-card__body {
  flex: 1;
  min-width: 0;
}

.room-card__name {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 700;
  color: #0f172a;
}

.room-card__stats {
  margin-top: 0.5rem;
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  font-size: 0.875rem;
  color: #475569;
}

.stat__label {
  color: #94a3b8;
  margin-right: 0.25rem;
}

.btn-enter {
  padding: 0.55rem 1.35rem;
  border: none;
  border-radius: 14px;
  font-size: 0.95rem;
  font-weight: 700;
  cursor: pointer;
  background: linear-gradient(180deg, #3b82f6, #2563eb);
  color: #fff;
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4);
  transition:
    transform 0.1s,
    box-shadow 0.15s;
  flex-shrink: 0;
}

.btn-enter:hover {
  box-shadow: 0 6px 18px rgba(37, 99, 235, 0.5);
}

.btn-enter:active {
  transform: scale(0.97);
}

.list-empty {
  margin-top: 2rem;
  padding: 2rem 1.5rem;
  text-align: center;
  background: #fff;
  border-radius: 16px;
  border: 1px dashed #cbd5e1;
  color: #64748b;
}

.list-empty p {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: #475569;
}

.list-empty__hint {
  margin-top: 0.5rem !important;
  font-size: 0.875rem !important;
  font-weight: 400 !important;
  color: #94a3b8 !important;
}
</style>
