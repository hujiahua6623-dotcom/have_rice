# 参与贡献

感谢你有意改进「大家来投票」（hava_rice）。以下为协作方式说明。

## 环境与运行

1. **后端**：`backend/` 下创建虚拟环境，安装 `requirements.txt`，配置 `.env`（可参考 `.env.example`）。  
2. **前端**：`frontend/` 下 `npm install`，`npm run dev`。  
3. 更完整的步骤见仓库根目录 [README.md](./README.md) 与 [docs/部署说明.md](./docs/部署说明.md)。

## 代码约定

- **范围**：改动尽量聚焦单一问题，避免无关格式化或大段重构。  
- **风格**：与现有文件保持一致（Python / Vue / TypeScript 命名与结构）。  
- **数据库**：表结构变更请通过 Alembic 迁移，并在说明中写清升级步骤。

## 提交问题与合并请求

- **Issue**：描述复现步骤、期望行为、实际行为，以及环境（OS、Python/Node 版本等）。  
- **Pull Request**：简要说明动机与改动点；若涉及接口或部署行为变化，请同步更新 [docs/接口文档.md](./docs/接口文档.md) 或 [docs/部署说明.md](./docs/部署说明.md)。

## 许可

向本仓库提交代码即表示你同意在 [LICENSE](./LICENSE)（MIT）下授权你的贡献。
