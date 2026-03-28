<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAdminAuthStore } from '../../stores/adminAuth'

const router = useRouter()
const r = useRoute()
const admin = useAdminAuthStore()

const roomIdFromRoute = computed(() => {
  const id = r.params.roomId
  return id != null ? String(id) : null
})

function logout() {
  admin.logout()
  router.push({ name: 'admin-login' })
}
</script>

<template>
  <div class="admin-layout">
    <aside class="admin-layout__aside">
      <div class="admin-layout__brand">管理后台</div>
      <nav class="admin-layout__nav" aria-label="管理菜单">
        <router-link class="admin-layout__link" to="/admin/rooms" active-class="admin-layout__link--active">
          房间列表
        </router-link>
        <router-link class="admin-layout__link" to="/admin/rooms/new" active-class="admin-layout__link--active">
          新建房间
        </router-link>
        <router-link
          v-if="roomIdFromRoute"
          class="admin-layout__link"
          :to="`/admin/rooms/${roomIdFromRoute}/polls`"
          active-class="admin-layout__link--active"
        >
          题库管理
          <span class="admin-layout__hint">#{{ roomIdFromRoute }}</span>
        </router-link>
      </nav>
      <div class="admin-layout__aside-foot">
        <router-link class="admin-layout__link admin-layout__link--ghost" to="/rooms">玩家端</router-link>
        <button type="button" class="admin-layout__logout" @click="logout">退出登录</button>
      </div>
    </aside>
    <div class="admin-layout__main">
      <router-view />
    </div>
  </div>
</template>

<style scoped>
.admin-layout {
  min-height: 100dvh;
  display: flex;
  background: linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%);
}

.admin-layout__aside {
  width: 220px;
  flex-shrink: 0;
  background: #fff;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  padding: 1.25rem 0;
  box-sizing: border-box;
}

.admin-layout__brand {
  padding: 0 1rem 1rem;
  font-weight: 700;
  font-size: 1.1rem;
  color: #0f172a;
  border-bottom: 1px solid #f1f5f9;
  margin-bottom: 0.75rem;
}

.admin-layout__nav {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0 0.5rem;
  flex: 1;
}

.admin-layout__link {
  display: block;
  padding: 0.6rem 0.75rem;
  border-radius: 8px;
  color: #475569;
  text-decoration: none;
  font-size: 0.95rem;
}

.admin-layout__link:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.admin-layout__link--active {
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 600;
}

.admin-layout__link--ghost {
  font-size: 0.875rem;
}

.admin-layout__hint {
  display: block;
  font-size: 0.75rem;
  font-weight: 400;
  color: #94a3b8;
  margin-top: 0.15rem;
}

.admin-layout__aside-foot {
  padding: 1rem 0.5rem 0;
  border-top: 1px solid #f1f5f9;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.admin-layout__logout {
  margin: 0 0.25rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
  color: #64748b;
  background: transparent;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  cursor: pointer;
}

.admin-layout__logout:hover {
  background: #fef2f2;
  border-color: #fecaca;
  color: #b91c1c;
}

.admin-layout__main {
  flex: 1;
  min-width: 0;
  padding: 1.25rem 1rem 2rem;
  box-sizing: border-box;
}

@media (max-width: 720px) {
  .admin-layout {
    flex-direction: column;
  }
  .admin-layout__aside {
    width: 100%;
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
    padding: 0.75rem;
  }
  .admin-layout__brand {
    border: none;
    margin: 0;
    padding: 0 0.5rem 0 0;
  }
  .admin-layout__nav {
    flex-direction: row;
    flex-wrap: wrap;
    flex: 1;
  }
  .admin-layout__aside-foot {
    border: none;
    flex-direction: row;
    padding: 0;
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
