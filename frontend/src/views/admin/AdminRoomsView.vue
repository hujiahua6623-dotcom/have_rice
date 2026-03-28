<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import adminHttp from '../../api/adminHttp'

interface RoomItem {
  id: number
  name: string
  max_players: number
  member_count: number
  online_count: number
  status: string
}

const router = useRouter()
const rooms = ref<RoomItem[]>([])
const loading = ref(false)
const err = ref('')
const ok = ref('')

async function load() {
  err.value = ''
  ok.value = ''
  loading.value = true
  try {
    const { data } = await adminHttp.get<RoomItem[]>('/admin/rooms')
    rooms.value = data
  } catch (e: unknown) {
    const x = e as { response?: { data?: { detail?: string } } }
    err.value = x.response?.data?.detail || '加载失败'
  } finally {
    loading.value = false
  }
}

function goPolls(id: number) {
  router.push(`/admin/rooms/${id}/polls`)
}

async function toggleOpen(r: RoomItem) {
  err.value = ''
  ok.value = ''
  const next = r.status === 'open' ? 'closed' : 'open'
  try {
    await adminHttp.patch(`/admin/rooms/${r.id}`, { status: next })
    ok.value = next === 'open' ? '房间已开放' : '房间已关闭'
    await load()
  } catch (e: unknown) {
    const x = e as { response?: { data?: { detail?: string } } }
    err.value = x.response?.data?.detail || '操作失败'
  }
}

async function removeRoom(r: RoomItem) {
  if (!confirm(`确定删除房间「${r.name}」？此操作不可恢复。`)) return
  err.value = ''
  try {
    await adminHttp.delete(`/admin/rooms/${r.id}`)
    ok.value = '已删除'
    await load()
  } catch (e: unknown) {
    const x = e as { response?: { data?: { detail?: string } } }
    err.value = x.response?.data?.detail || '删除失败'
  }
}

onMounted(load)
</script>

<template>
  <div class="admin-rooms">
    <header class="admin-rooms__header">
      <div>
        <h1 class="admin-rooms__title">房间列表</h1>
        <p class="admin-rooms__sub">管理全部房间，进入题库或开放给玩家</p>
      </div>
      <button type="button" class="admin-rooms__refresh" :disabled="loading" @click="load">
        {{ loading ? '加载中…' : '刷新' }}
      </button>
    </header>

    <p v-if="err" class="admin-rooms__msg admin-rooms__msg--err">{{ err }}</p>
    <p v-if="ok" class="admin-rooms__msg admin-rooms__msg--ok">{{ ok }}</p>

    <ul class="admin-rooms__list">
      <li v-for="r in rooms" :key="r.id" class="admin-room-card">
        <div class="admin-room-card__body">
          <div class="admin-room-card__top">
            <h2 class="admin-room-card__name">{{ r.name }}</h2>
            <span
              class="admin-room-card__badge"
              :class="
                r.status === 'open' ? 'admin-room-card__badge--open' : 'admin-room-card__badge--closed'
              "
            >
              {{ r.status === 'open' ? '开放中' : '未开放' }}
            </span>
          </div>
          <div class="admin-room-card__stats">
            <span class="admin-stat"
              ><span class="admin-stat__label">ID</span> {{ r.id }}</span
            >
            <span class="admin-stat"
              ><span class="admin-stat__label">已进入</span> {{ r.member_count }} /
              {{ r.max_players }}</span
            >
            <span class="admin-stat"
              ><span class="admin-stat__label">在线</span> {{ r.online_count }}</span
            >
          </div>
        </div>
        <div class="admin-room-card__actions">
          <button type="button" class="btn-secondary" @click="goPolls(r.id)">题库管理</button>
          <button type="button" class="btn-secondary" @click="toggleOpen(r)">
            {{ r.status === 'open' ? '关闭房间' : '开放房间' }}
          </button>
          <button type="button" class="btn-danger" @click="removeRoom(r)">删除</button>
        </div>
      </li>
    </ul>

    <div v-if="!loading && rooms.length === 0" class="admin-rooms__empty">
      <p>暂无房间</p>
      <p class="admin-rooms__empty-hint">点击左侧「新建房间」创建第一个房间。</p>
    </div>
  </div>
</template>

<style scoped>
.admin-rooms {
  max-width: 720px;
  margin: 0 auto;
}

.admin-rooms__header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.25rem;
}

.admin-rooms__title {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 700;
  color: #0f172a;
}

.admin-rooms__sub {
  margin: 0.35rem 0 0;
  font-size: 0.9rem;
  color: #64748b;
}

.admin-rooms__refresh {
  padding: 0.45rem 0.9rem;
  font-size: 0.9rem;
  border-radius: 10px;
  border: 1px solid #cbd5e1;
  background: #fff;
  cursor: pointer;
}

.admin-rooms__refresh:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.admin-rooms__msg {
  margin: 0 0 1rem;
  font-size: 0.9rem;
}

.admin-rooms__msg--err {
  color: #b91c1c;
}

.admin-rooms__msg--ok {
  color: #15803d;
}

.admin-rooms__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.admin-room-card {
  display: flex;
  flex-wrap: wrap;
  align-items: stretch;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1.1rem;
  background: #fff;
  border-radius: 14px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}

.admin-room-card__body {
  flex: 1;
  min-width: 200px;
}

.admin-room-card__top {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-bottom: 0.5rem;
}

.admin-room-card__name {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: #0f172a;
}

.admin-room-card__badge {
  font-size: 0.75rem;
  padding: 0.2rem 0.5rem;
  border-radius: 999px;
  font-weight: 600;
}

.admin-room-card__badge--open {
  background: #dcfce7;
  color: #166534;
}

.admin-room-card__badge--closed {
  background: #f1f5f9;
  color: #64748b;
}

.admin-room-card__stats {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1.25rem;
  font-size: 0.875rem;
  color: #475569;
}

.admin-stat__label {
  color: #94a3b8;
  margin-right: 0.25rem;
}

.admin-room-card__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}

.btn-secondary {
  padding: 0.45rem 0.75rem;
  font-size: 0.875rem;
  border-radius: 10px;
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #334155;
  cursor: pointer;
}

.btn-secondary:hover {
  background: #f8fafc;
}

.btn-danger {
  padding: 0.45rem 0.75rem;
  font-size: 0.875rem;
  border-radius: 10px;
  border: 1px solid #fecaca;
  background: #fff;
  color: #b91c1c;
  cursor: pointer;
}

.btn-danger:hover {
  background: #fef2f2;
}

.admin-rooms__empty {
  text-align: center;
  padding: 2.5rem 1rem;
  color: #64748b;
}

.admin-rooms__empty-hint {
  font-size: 0.9rem;
  margin-top: 0.5rem;
}
</style>
