import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

http.interceptors.request.use((config) => {
  const t = localStorage.getItem('access_token')
  if (t) {
    config.headers.Authorization = `Bearer ${t}`
  }
  return config
})

export default http
