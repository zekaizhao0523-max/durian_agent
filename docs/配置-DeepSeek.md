# DeepSeek 配置指南

榴莲 Agent 通过 **OpenAI 兼容接口** 调用 DeepSeek，无需改代码。

## 1. 获取 API Key

1. 打开 [DeepSeek 开放平台](https://platform.deepseek.com/)
2. 注册 / 登录
3. 进入 [API Keys](https://platform.deepseek.com/api_keys) 创建密钥
4. 复制以 `sk-` 开头的 Key

## 2. 填写 `.env`

在项目根目录 `d:\agent\.env` 中配置：

```env
AGENT_MODE=langgraph
OPENAI_API_KEY=sk-你的密钥
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
```

### 模型选择

| 模型 | 说明 |
|------|------|
| `deepseek-chat` | 通用对话（**推荐**，响应快） |
| `deepseek-reasoner` | 推理增强，适合复杂决策，更慢更贵 |

## 3. 启动并验证

```bash
cd d:\agent
pip install -r requirements.txt
uvicorn src.main:app --reload --host 127.0.0.1 --port 8080
```

浏览器访问健康检查：

```
http://localhost:8080/api/v1/health
```

期望结果：

```json
{
  "status": "ok",
  "agent_mode": "langgraph",
  "llm_enabled": true
}
```

再打开聊天页：http://localhost:8080

试一句：`300左右，要甜一点，推荐一下`

## 4. 常见问题

### `agent_mode` 仍是 `rules`

- 检查 `.env` 中 `OPENAI_API_KEY` 是否已填写且非空
- 修改 `.env` 后需**重启** uvicorn

### 401 / Invalid API Key

- 确认 Key 完整、无多余空格
- 确认账户有余额（DeepSeek 按量计费）

### 连接超时

- 检查网络能否访问 `api.deepseek.com`
- 如在内网环境，确认防火墙未拦截

### 工具调用异常

- 优先使用 `deepseek-chat`；`deepseek-reasoner` 对 tool-calling 支持可能不稳定
- 可将 `GRAPH_RECURSION_LIMIT` 设为 `16` 给多轮工具调用更多步数

## 5. 安全提醒

- **不要**将 `.env` 提交到 Git（已在 `.gitignore` 中忽略）
- 密钥泄露请立即在 DeepSeek 控制台作废并重新创建
