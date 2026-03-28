<template>
  <router-view />
</template>

<style>
html, body, #app { height: 100%; margin: 0; font-family: system-ui, -apple-system, sans-serif; }
a { color: #2563eb; }
button { cursor: pointer; padding: 0.4rem 0.75rem; border-radius: 6px; border: 1px solid #ccc; background: #fff; }
button.primary { background: #2563eb; color: #fff; border-color: #2563eb; }
button.danger { background: #dc2626; color: #fff; border-color: #dc2626; }
button.warn { background: #ca8a04; color: #fff; border-color: #ca8a04; }
input { padding: 0.4rem 0.5rem; border: 1px solid #ccc; border-radius: 4px; min-width: 200px; }
pre { background: #f4f4f5; padding: 0.5rem; overflow: auto; }
.tag { display: inline-block; padding: 0.15rem 0.5rem; background: #e4e4e7; border-radius: 4px; font-size: 0.85rem; }

/* 登录 / 注册页（与房间列表、房间内页同一视觉） */
.auth-page {
  min-height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem 1rem 3rem;
  background: linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%);
  box-sizing: border-box;
}
.auth-card {
  width: 100%;
  max-width: 400px;
  padding: 1.75rem 1.5rem 1.5rem;
  background: #fff;
  border-radius: 20px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 12px 40px rgba(15, 23, 42, 0.08);
}
.auth-card__head {
  margin-bottom: 1.25rem;
}
.auth-card__title {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}
.auth-card__sub {
  margin: 0.4rem 0 0;
  font-size: 0.9rem;
  color: #64748b;
  line-height: 1.45;
}
.auth-err {
  margin: 0 0 1rem;
  padding: 0.55rem 0.75rem;
  font-size: 0.875rem;
  color: #b91c1c;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 10px;
}
.auth-field {
  margin-bottom: 1rem;
}
.auth-label {
  display: block;
  margin-bottom: 0.35rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: #475569;
  letter-spacing: 0.02em;
}
.auth-input {
  width: 100%;
  box-sizing: border-box;
  padding: 0.6rem 0.75rem;
  font-size: 0.95rem;
  color: #0f172a;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #f8fafc;
  transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
}
.auth-input:hover {
  border-color: #cbd5e1;
}
.auth-input:focus {
  outline: none;
  border-color: #93c5fd;
  background: #fff;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
}
.auth-btn {
  width: 100%;
  margin-top: 0.25rem;
  padding: 0.65rem 1rem;
  font-size: 0.95rem;
  font-weight: 700;
  color: #fff;
  border: none;
  border-radius: 14px;
  cursor: pointer;
  background: linear-gradient(180deg, #3b82f6, #2563eb);
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4);
  transition: transform 0.1s, box-shadow 0.15s, opacity 0.15s;
}
.auth-btn:hover:not(:disabled) {
  box-shadow: 0 6px 18px rgba(37, 99, 235, 0.5);
}
.auth-btn:active:not(:disabled) {
  transform: scale(0.99);
}
.auth-btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}
.auth-footer {
  margin: 1.25rem 0 0;
  padding-top: 1.25rem;
  border-top: 1px solid #f1f5f9;
  text-align: center;
  font-size: 0.9rem;
  color: #64748b;
}
.auth-footer a,
.auth-link {
  color: #2563eb;
  font-weight: 600;
  text-decoration: none;
}
.auth-footer a:hover,
.auth-link:hover {
  text-decoration: underline;
}
</style>
