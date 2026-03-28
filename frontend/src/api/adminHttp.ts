import axios from 'axios'

/** 与 stores/adminAuth 共用，避免 adminHttp 依赖 Pinia 产生循环引用 */
export const ADMIN_ACCESS_TOKEN_KEY = 'admin_access_token'

const adminHttp = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

adminHttp.interceptors.request.use((config) => {
  const t = localStorage.getItem(ADMIN_ACCESS_TOKEN_KEY)
  if (t) {
    config.headers.Authorization = `Bearer ${t}`
  }
  return config
})

export default adminHttp
