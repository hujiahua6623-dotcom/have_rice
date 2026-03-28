import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useAdminAuthStore } from '../stores/adminAuth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/rooms' },
    { path: '/login', component: () => import('../views/LoginView.vue'), meta: { guest: true } },
    { path: '/register', component: () => import('../views/RegisterView.vue'), meta: { guest: true } },
    { path: '/rooms', component: () => import('../views/RoomListView.vue'), meta: { auth: true } },
    { path: '/room/:id', component: () => import('../views/RoomView.vue'), meta: { auth: true } },
    {
      path: '/admin/login',
      name: 'admin-login',
      component: () => import('../views/admin/AdminLoginView.vue'),
    },
    {
      path: '/admin',
      component: () => import('../views/admin/AdminLayout.vue'),
      children: [
        { path: '', redirect: { name: 'admin-rooms' } },
        {
          path: 'rooms',
          name: 'admin-rooms',
          component: () => import('../views/admin/AdminRoomsView.vue'),
        },
        {
          path: 'rooms/new',
          name: 'admin-room-new',
          component: () => import('../views/admin/AdminRoomCreateView.vue'),
        },
        {
          path: 'rooms/:roomId/polls',
          name: 'admin-room-polls',
          component: () => import('../views/admin/AdminPollTypesView.vue'),
        },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.auth && !auth.token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guest && auth.token) {
    return { path: '/rooms' }
  }

  const admin = useAdminAuthStore()
  const isAdminArea = to.path.startsWith('/admin') && to.path !== '/admin/login'
  const isAdminLogin = to.path === '/admin/login'
  if (isAdminArea && !admin.isLoggedIn) {
    return { path: '/admin/login', query: { redirect: to.fullPath } }
  }
  if (isAdminLogin && admin.isLoggedIn) {
    return { path: '/admin/rooms' }
  }

  return true
})

export default router
