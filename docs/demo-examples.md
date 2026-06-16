# 演示输入输出示例

本文档可用于简历作品集、面试讲解或 README 配图说明。

---

## 1. 售后分诊（核心亮点）

### 示例 A：过熟坏果 + 订单号 + 照片

**用户输入：**

```
订单号 ORD_10001，果子过熟坏了，昨天签收的，有照片
```

**Agent 结构化输出（`after_sale` 字段）：**

| 字段 | 值 |
|------|-----|
| 问题类型 | 过熟 |
| 优先级 | P0 |
| 命中规则 | 签收后24小时坏果反馈；图片凭证要求；过熟/变质处理 |
| 待补充凭证 | 无 |
| 是否转人工 | 否 |

---

### 示例 B：过生退款（无订单号）

**用户输入：** `榴莲过生了，要退款`

| 字段 | 值 |
|------|-----|
| 问题类型 | 过生/夹生 |
| 待补充凭证 | 订单号、榴莲果肉/整体照片 |
| 是否转人工 | 是 |

---

### 示例 C：物流延迟

**用户输入：** `订单号 ORD_10002，快递太慢了，物流延迟怎么办`

| 字段 | 值 |
|------|-----|
| 问题类型 | 物流延迟 |
| 是否转人工 | 是 |

---

## 2. 售后问题分类

| 类型 | 中文 | 触发词示例 |
|------|------|------------|
| bad_fruit | 坏果/破损 | 坏了、破损、发霉 |
| unripe | 过生/夹生 | 过生、夹生、太生 |
| overripe | 过熟 | 过熟、发酸 |
| logistics_delay | 物流延迟 | 物流慢、超时 |
| weight_short | 重量不足 | 缺斤、不够秤 |
| presale_ship | 预售发货 | 预售、什么时候发 |
| refund_compensation | 退款赔付 | 退款、赔付 |

规则库见 `src/aftersale/rules.py`

---

## 3. 本地复现

```bash
set AGENT_MODE=rules
pytest tests/test_aftersale.py -q
```

```bash
python -c "import os; os.environ['AGENT_MODE']='rules'; from src.orchestrator.orchestrator import orchestrator; r=orchestrator.handle('订单号 ORD_10001，果子过熟坏了，有照片', user_id='demo_user'); print(r.reply_text)"
```

---

## 4. 前端演示截图建议

1. 打开 http://localhost:8080
2. 点击 **售后咨询** → 输入示例 A
3. 截图包含：用户消息 + **售后分诊绿色卡片** + 订单卡片

---

## 5. LangGraph 流程（可代替 Studio 截图）

```
用户消息 → Agent(LLM) → Tools → Agent → Format → 回复 + 卡片
```

详见 [Agent架构-榴莲Agent.md](Agent架构-榴莲Agent.md)
