<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import adminHttp from '../../api/adminHttp'

const router = useRouter()

const roomName = ref('测试房间')
const maxPlayers = ref(20)
const err = ref('')
const ok = ref('')
const loading = ref(false)

async function createRoom() {
  err.value = ''
  ok.value = ''
  loading.value = true
  try {
    const { data } = await adminHttp.post<{ room: { id: number } }>('/admin/rooms', {
      name: roomName.value,
      max_players: maxPlayers.value,
    })
    ok.value = '房间已创建'
    router.push(`/admin/rooms/${data.room.id}/polls`)
  } catch (e: unknown) {
    const x = e as { response?: { data?: { detail?: string } } }
    err.value = x.response?.data?.detail || '创建失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="admin-create">
    <header class="admin-create__header">
      <h1 class="admin-create__title">新建房间</h1>
      <p class="admin-create__sub">创建后将进入该房间的题库管理</p>
    </header>

    <div class="admin-create__card">
      <p v-if="err" class="admin-create__msg admin-create__msg--err">{{ err }}</p>
      <p v-if="ok" class="admin-create__msg admin-create__msg--ok">{{ ok }}</p>

      <label class="admin-create__field">
        <span>房间名称</span>
        <input v-model="roomName" type="text" maxlength="128" />
      </label>
      <label class="admin-create__field">
        <span>人数上限</span>
        <input v-model.number="maxPlayers" type="number" min="2" max="200" />
      </label>

      <button type="button" class="admin-create__submit" :disabled="loading" @click="createRoom">
        {{ loading ? '创建中…' : '创建并管理题库' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.admin-create {
  max-width: 480px;
  margin: 0 auto;
}

.admin-create__header {
  margin-bottom: 1.25rem;
}

.admin-create__title {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 700;
  color: #0f172a;
}

.admin-create__sub {
  margin: 0.35rem 0 0;
  font-size: 0.9rem;
  color: #64748b;
}

.admin-create__card {
  padding: 1.5rem;
  background: #fff;
  border-radius: 14px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}

.admin-create__field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 1rem;
  font-size: 0.875rem;
  color: #334155;
}

.admin-create__field input {
  padding: 0.55rem 0.75rem;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  font-size: 1rem;
}

.admin-create__field input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}

.admin-create__submit {
  width: 100%;
  margin-top: 0.5rem;
  padding: 0.65rem 1rem;
  font-size: 1rem;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(180deg, #3b82f6 0%, #2563eb 100%);
  border: none;
  border-radius: 10px;
  cursor: pointer;
}

.admin-create__submit:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.admin-create__msg {
  margin: 0 0 1rem;
  font-size: 0.9rem;
}

.admin-create__msg--err {
  color: #b91c1c;
}

.admin-create__msg--ok {
  color: #15803d;
}
</style>
