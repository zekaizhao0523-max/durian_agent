# 榴莲电商 AI 售后 Agent

基于 **LangGraph + 大模型 + 规则引擎** 的榴莲电商智能助手。覆盖选购推荐、批次溯源验真、知识问答，以及 **AI 售后分诊**（问题分类、规则命中、凭证检查、客服话术、转人工决策）。

> 适合作为简历 / 作品集项目：Agent 编排、业务规则知识库、结构化输出、PostgreSQL 持久化、H5 对话前端、LangGraph Studio 可视化。

---

## 解决什么问题

榴莲电商售后场景常见痛点：

- 用户描述模糊（「坏了」「太生了」），客服需快速判断类型与优先级
- 规则分散（24 小时反馈、图片凭证、重量误差、预售发货），人工记忆成本高
- 凭证不齐导致反复沟通，缺少结构化「缺什么、下一步做什么」指引

本项目用 Agent 把上述流程自动化：**输入用户问题 → 输出可执行的售后分诊结果**，同时保留推荐、验真等购前能力，形成完整业务闭环。

---

## 核心能力

| 能力 | 说明 |
|------|------|
| **榴莲推荐** | 按预算、口味、送礼场景综合推荐，附商品卡片 |
| **品种评价** | 点名品种 + 用户条件 → 可以买 / 不建议 / 再等等 |
| **批次验真** | TR 溯源码查询，说明「一批一品类一码」 |
| **知识问答** | 品种对比、保存、开果等 FAQ |
| **售后分诊** | 8 类问题分类 + 9 条规则命中 + 7 项结构化输出 |
| **会话记忆** | 多轮对话、历史管理、长期偏好记忆（PostgreSQL） |
| **安全护栏** | 无关话题拒答、Prompt 注入拦截、输出脱敏 |

---

## 售后分诊闭环（简历核心）

用户输入售后问题后，Agent 输出以下 **7 项结构化字段**（`ChatResponse.after_sale` + 前端绿色分诊卡片）：

| 字段 | 说明 |
|------|------|
| 问题类型 | 坏果、过生、过熟、物流延迟、重量不足、预售发货、退款赔付 |
| 优先级 | P0 / P1 / P2 |
| 缺失凭证 | 订单号、签收时间、果肉照片、称重照片等 |
| 命中规则 | 从规则知识库匹配的业务规则标题 |
| 处理建议 | 退款 / 补发 / 催物流等操作建议 |
| 推荐客服回复 | 可直接粘贴给用户的标准话术 |
| 是否转人工 | 复杂单或凭证不全时升级人工 |

### 输入输出示例

**输入：**

```
订单号 ORD_10001，果子过熟坏了，昨天签收的，有照片
```

**输出：**

```
问题类型：坏果/破损
优先级：P0
命中规则：签收后24小时坏果反馈；图片凭证要求；过熟/变质处理
待补充凭证：无
处理建议：核实签收时间在24小时内后，引导用户提交坏果/过熟照片……
推荐客服回复：已收到您的反馈。请在签收24小时内提供订单号、签收时间……
是否转人工：否
```

更多场景见 [docs/demo-examples.md](docs/demo-examples.md)。

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 编排 | LangGraph（agent → tools → format）、规则引擎双模式 |
| 大模型 | OpenAI 兼容接口（DeepSeek / 通义 / GPT 等） |
| 后端 | FastAPI、SSE 流式、Pydantic v2 |
| 存储 | PostgreSQL（会话、记忆、商品/订单/批次演示数据） |
| 前端 | 原生 H5（`static/index.html`），无框架依赖 |
| 工具层 | 可切换 mock / http 适配器 |

**环境要求：** Python 3.11+、PostgreSQL 14+

---

## 系统架构

```mermaid
flowchart TB
    subgraph Client["客户端"]
        H5["H5 对话页<br/>static/index.html"]
    end

    subgraph API["接入层"]
        Routes["FastAPI routes.py<br/>/chat /chat/stream"]
    end

    subgraph Orchestrator["编排层"]
        Mode{"AGENT_MODE"}
        LG["LangGraph Runner<br/>tool-calling 循环"]
        Rules["Rule Orchestrator<br/>关键词意图路由"]
    end

    subgraph Business["业务层"]
        AS["aftersale/<br/>分类 + 规则 + 分诊"]
        Router["intent_router"]
        Knowledge["knowledge/ FAQ"]
        Tools["tools/ 溯源·商品·订单"]
    end

    subgraph Storage["数据层"]
        PG[("PostgreSQL")]
    end

    subgraph Studio["LangGraph Studio"]
        Demo["durian_demo/<br/>after_sale_triage 图"]
    end

    H5 --> Routes
    Routes --> Mode
    Mode -->|langgraph| LG
    Mode -->|rules| Rules
    LG --> Tools
    Rules --> AS
    Rules --> Tools
    LG --> AS
    AS --> Router
    Tools --> PG
    Routes --> PG
    Demo -.-> LG
    Demo -.-> AS
```

### 双运行模式

| 模式 | 配置 | 特点 |
|------|------|------|
| **rules** | `AGENT_MODE=rules` | 无需 API Key，关键词路由 + 规则分诊，**简历演示首选** |
| **langgraph** | `AGENT_MODE=langgraph` + `OPENAI_API_KEY` | LLM 自主 tool-calling，支持多轮推理与润色 |

两种模式共用同一套工具层与售后规则知识库，数据来源一致。

---

## 项目结构

```
agent/
├── durian_demo/              # LangGraph Studio 入口（Python 3.11）
│   ├── graph.py              # durian_agent + after_sale_triage 双图
│   ├── langgraph.json
│   └── README.md
├── static/index.html         # H5 前端（流式对话 + 售后分诊卡片）
├── src/
│   ├── aftersale/            # 售后分类器、规则库、分诊器
│   ├── api/routes.py         # REST / SSE 接口
│   ├── graph/                # LangGraph 节点、工具、状态机
│   ├── orchestrator/         # 双模式统一门面
│   ├── router/               # 意图识别与槽位提取
│   ├── tools/                # 溯源 / 商品 / 订单工具
│   ├── knowledge/            # FAQ 与品种对比
│   ├── storage/              # PostgreSQL 持久化
│   └── guardrails/           # 安全护栏
├── docs/                     # 架构文档、配置指南、演示示例
├── scripts/                  # 数据库初始化脚本
├── test_*.py                 # 单元与集成测试
├── run.py                    # 服务启动入口
└── requirements.txt
```

---

## 快速启动

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

Windows 一键配置 PostgreSQL（可选）：

```powershell
.\scripts\setup_postgres.ps1 -Password "你的密码"
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，至少填写：

```env
DATABASE_URL=postgresql://postgres:你的密码@localhost:5432/durian_agent
DEFAULT_USER_ID=demo_user
AGENT_MODE=rules
```

大模型模式（可选）：

```env
AGENT_MODE=langgraph
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
```

配置说明：[docs/配置-DeepSeek.md](docs/配置-DeepSeek.md) · [docs/配置-PostgreSQL.md](docs/配置-PostgreSQL.md)

### 3. 初始化数据库

```bash
python scripts/init_postgres.py --create-db
```

### 4. 启动服务

```bash
python run.py
# 或指定端口：python run.py --port 8080 --reload
```

浏览器打开 **http://localhost:8080**

左侧可切换用户 ID；点击 **「售后咨询」** 模板即可体验分诊闭环。

### 5. LangGraph Studio（作品集截图）

```bash
cd durian_demo
langgraph dev
```

在 Studio 选择 **`after_sale_triage`** 图，输入：

```json
{
  "user_message": "订单号 ORD_10001，果子过熟坏了，昨天签收的，有照片"
}
```

详见 [durian_demo/README.md](durian_demo/README.md)。

---

## 售后规则知识库

规则定义于 `src/aftersale/rules.py`，共 **9 条**：

| 规则 | 适用场景 |
|------|----------|
| 签收后24小时坏果反馈 | 坏果、过熟，需核实签收时效 |
| 图片凭证要求 | 坏果/过生/过熟/重量问题需附图 |
| 过生/夹生判定与处理 | 夹生、硬块、退款评估 |
| 过熟/变质处理 | 发酸、酒味、流汁发黑 |
| 重量误差规则 | 缺斤少两，允许 ±3% 误差 |
| 物流延迟规则 | 快递超时、迟迟不到 |
| 预售发货规则 | 预售订单发货时间说明 |
| 退款赔付通用流程 | 退款、理赔、赔偿 |
| 订单号定位原则 | 售后必须以订单号为主键 |

### 问题分类（8 类）

| 类型 ID | 中文 | 触发词示例 |
|---------|------|------------|
| `bad_fruit` | 坏果/破损 | 坏了、破损、发霉 |
| `unripe` | 过生/夹生 | 过生、夹生、太生 |
| `overripe` | 过熟 | 过熟、发酸 |
| `logistics_delay` | 物流延迟 | 物流慢、超时 |
| `weight_short` | 重量不足 | 缺斤、不够秤 |
| `presale_ship` | 预售发货 | 预售、什么时候发 |
| `refund_compensation` | 退款赔付 | 退款、赔付 |
| `general` | 一般售后咨询 | 售后、不满意 |

---

## 主要 API

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/chat` | 同步对话，返回 `after_sale` 结构化字段 |
| `POST` | `/chat/stream` | SSE 流式对话 |
| `GET` | `/sessions/{id}/history` | 会话历史 |
| `GET` | `/users/{id}/sessions` | 用户会话列表 |
| `DELETE` | `/sessions/{id}` | 删除单条会话 |
| `DELETE` | `/users/{id}/memory` | 清空长期记忆 |
| `GET` | `/trace/{code}` | 批次溯源查询 |
| `GET` | `/products` | 商品列表 |
| `GET` | `/health` | 健康检查 |

---

## 测试

```bash
pytest tests/ -q
```

常用子集：

```bash
pytest tests/test_aftersale.py -q      # 售后分诊单元测试
pytest tests/test_durian_demo.py -q    # LangGraph Studio 入口
pytest tests/test_mvp.py -q            # 推荐 / 验真 / 售后主链路
pytest tests/test_langgraph_unit.py -q # LangGraph 节点与工具
```

数据库与种子数据（脚本依赖，非 pytest）：

```bash
python test_memory.py
python test_catalog.py
python test_history.py
```

无 API Key 时默认 `AGENT_MODE=rules`，全部测试可本地通过。

命令行快速验证售后：

```bash
python -c "import os; os.environ['AGENT_MODE']='rules'; from src.orchestrator.orchestrator import orchestrator; r=orchestrator.handle('订单号 ORD_10001，果子过熟坏了，有照片', user_id='demo_user'); print(r.reply_text)"
```

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [docs/demo-examples.md](docs/demo-examples.md) | 演示输入输出、分类表、截图建议 |
| [docs/Agent架构-榴莲Agent.md](docs/Agent架构-榴莲Agent.md) | 技术架构详述 |
| [docs/PRD-榴莲Agent.md](docs/PRD-榴莲Agent.md) | 产品需求文档 |
| [durian_demo/README.md](durian_demo/README.md) | LangGraph Studio 使用说明 |

---

## 作品集 / 简历素材

建议准备以下截图或示例：

1. **H5 售后分诊卡片** — `http://localhost:8080` → 售后咨询 → 输入带订单号的问题
2. **LangGraph Studio** — `after_sale_triage` 图的输入与 `reply_text` 输出
3. **结构化 JSON** — API 响应中的 `after_sale` 字段（问题类型、优先级、命中规则等）

### 简历段落（可直接粘贴）

> 独立开发榴莲电商 AI 售后 Agent：基于 LangGraph 实现多轮 tool-calling，设计 8 类售后问题分类器与 9 条结构化规则知识库，输出问题类型、优先级、缺失凭证、命中规则、处理建议、客服话术及转人工决策；PostgreSQL 持久化会话与长期记忆，FastAPI + SSE 流式 H5 前端；规则模式可无 LLM 完整演示，并提供 LangGraph Studio 双图入口。

### 简历 Bullet Points

- 设计榴莲售后 **8 类问题分类器** 与 **9 条规则知识库**，实现签收 24h、图片凭证、重量 ±3% 等业务规则自动命中
- 构建售后分诊闭环，单次咨询输出 **7 项结构化字段**（类型、优先级、缺失凭证、规则、建议、话术、转人工），对接前端分诊卡片
- 基于 **LangGraph** 实现 agent → tools → format 编排，封装溯源、商品、订单、售后分诊等 7 个业务工具
- 实现 **rules / langgraph 双模式**，无 API Key 亦可完整演示，降低作品集部署门槛
- 使用 **PostgreSQL** 持久化会话、长期记忆与演示商品/订单数据；FastAPI 提供同步与 SSE 流式接口

---

## License

本项目为个人学习 / 作品集演示用途。
