# 大家来投票（hava_rice）

趣味投票系统：FastAPI + SQLite/MySQL 后端，Vue 3 + Vite 前端。

## 文档

| 文档 | 说明 |
|------|------|
| [docs/项目设计文档.md](docs/项目设计文档.md) | 产品与系统设计 |
| [docs/部署说明.md](docs/部署说明.md) | 生产部署、Nginx 示例、安全清单 |
| [docs/接口文档.md](docs/接口文档.md) | HTTP / WebSocket 约定（详细模型见 `/docs` OpenAPI） |
| [docs/开源说明.md](docs/开源说明.md) | 许可证、贡献方式、免责声明 |
| [LICENSE](LICENSE) | MIT 许可证全文 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 参与贡献约定 |

## 后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # 配置 DATABASE_URL（MySQL 或默认 SQLite）
mkdir -p data
```

### 数据库迁移（推荐：MySQL 或首次建表）

在 `backend/` 目录、已配置好 `DATABASE_URL` 的前提下：

```bash
alembic upgrade head
```

- 首版迁移脚本：[backend/alembic/versions/001_initial_schema.py](backend/alembic/versions/001_initial_schema.py)（`create_all` 对齐当前 models）。
- 之后表结构变更可执行：`alembic revision --autogenerate -m "描述"`，再 `alembic upgrade head`。

未跑 Alembic 时，应用启动仍会 `create_all`（便于本地 SQLite 快速试跑）；**生产环境 MySQL 建议以 Alembic 为准**，避免仅依赖启动建表。

### 启动 API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API 文档：<http://127.0.0.1:8000/docs>
- 默认 SQLite：`backend/data/app.db`（当 `DATABASE_URL` 未改时）

## 前端

```bash
cd frontend
npm install
npm run dev
```

开发时 Vite 将 `/api` 与 `/ws` 代理到 `http://127.0.0.1:8000`。

## 试用流程

1. 打开 <http://localhost:5173/admin>：可**新建房间**或输入已有 **房间 ID + Admin Token** 后「加载题目列表」。
2. 添加/编辑题目与选项（管理端支持题目与选项 **完整 CRUD**），点击**开放房间**。
3. 注册/登录玩家端 <http://localhost:5173/register>，在房间列表进入房间。
4. 选题 → 确认 / 取消确认 → 全员确认后 5 秒内可取消 → 助力预览与 10 秒助力 → **跑马灯动画**与结果。

## 环境变量（后端）

| 变量 | 说明 |
|------|------|
| `DATABASE_URL` | SQLAlchemy URL，默认 SQLite；MySQL 须为 **`mysql+pymysql://...`**（同步），勿使用 `asyncmy` |
| `JWT_SECRET` | JWT 签名密钥 |
| `CORS_ORIGINS` | 逗号分隔的前端源 |
