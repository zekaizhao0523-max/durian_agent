# PostgreSQL 记忆配置指南

榴莲 Agent 使用 PostgreSQL 存储 **短期记忆**（会话、消息）和 **长期记忆**（用户画像、批次体验）。

## 1. 配置连接

编辑 `d:\agent\.env`：

```env
DATABASE_URL=postgresql://postgres:你的密码@localhost:5432/durian_agent
```

常见本地默认值：
- 主机：`localhost`
- 端口：`5432`
- 用户：`postgres`

## 2. 初始化数据库

```bash
cd d:\agent
pip install psycopg[binary]
python scripts/init_postgres.py --create-db
```

若 `--create-db` 权限不足，可手动建库：

```sql
CREATE DATABASE durian_agent;
```

再执行：

```bash
python scripts/init_postgres.py
```

## 3. 验证

启动服务后访问：

```
http://localhost:8080/api/v1/health
```

应看到：

```json
{
  "database": "postgresql",
  ...
}
```

查看用户长期记忆（需先有对话）：

```
http://localhost:8080/api/v1/users/demo_user/profile
```

## 4. 表说明

| 表 | 记忆类型 | 内容 |
|----|----------|------|
| `sessions` | 短期 | 会话槽位、turn_count、expires_at |
| `messages` | 短期 | 对话历史 |
| `user_profiles` | 长期 | 口味、预算、偏好品种 |
| `batch_experiences` | 长期 | 批次评价记录 |
| `user_memories` | 长期 | 用户说过要记住的事实 |
| `events` | 运营 | 埋点事件 |

## 5. 记忆如何工作

- **短期**：每次对话读写 `sessions` + `messages`，LangGraph 加载最近 N 轮
- **长期**：对话结束后从槽位同步到 `user_profiles`；含「好吃/记住/下次」等词写入 `user_memories`
- **注入**：下次对话时长期记忆写入 System Prompt 的「用户长期记忆」段落

## 6. 演示业务数据（商品 / 批次 / 订单）

启动或执行 `python scripts/init_postgres.py` 时，若 `products` 表为空，会自动写入演示数据（见 `src/storage/seed_data.py`）：

- 溯源批次：`trace_batches`
- 在售商品：`products`
- 演示订单：`orders`（默认归属 `demo_user`）
