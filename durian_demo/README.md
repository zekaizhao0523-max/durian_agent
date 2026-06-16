# durian_demo — 榴莲电商 AI 售后 Agent

基于 LangGraph 的榴莲电商智能助手，**不是** Simple Agent Template。已实现完整售后业务闭环，可直接用于简历与作品集。

## 已实现（评审要求的「关键闭环」）

用户输入售后问题后，Agent 输出：

| 字段 | 说明 |
|------|------|
| 问题类型 | 坏果、过生、过熟、物流延迟、重量不足、预售发货、退款赔付 |
| 优先级 | P0 / P1 / P2 |
| 缺失凭证 | 订单号、签收时间、果肉照片等 |
| 命中规则 | 24h 坏果规则、图片凭证、重量 ±3%、预售发货等 |
| 处理建议 | 退款 / 补发 / 催物流等 |
| 推荐客服回复 | 可直接粘贴给用户的客服话术 |
| 是否转人工 | 是 / 否 |

## 业务工具（graph.py）

- `query_trace_code` — 批次溯源验真
- `search_products` / `get_product_detail` — 榴莲推荐
- `get_order_detail` — 订单查询（售后定位）
- `search_knowledge` — 榴莲百科与售后规则
- `after_sale_triage` — **售后分诊核心工具**

## 两个 LangGraph 图

1. **durian_agent** — 完整 Agent（agent → tools → format 循环）
2. **after_sale_triage** — 售后专用图（单节点分诊，适合 Studio 截图）

## 启动 LangGraph Studio

```bash
cd durian_demo
pip install -r ../requirements.txt
langgraph dev
```

浏览器打开 Studio 后选择 `after_sale_triage` 图，输入：

```json
{
  "user_message": "订单号 ORD_10001，果子过熟坏了，昨天签收的，有照片"
}
```

预期输出 `reply_text` 含：问题类型、优先级、命中规则、待补充凭证、处理建议、推荐客服回复、是否转人工。

## 无 Studio 时本地验证

```bash
cd ..
set AGENT_MODE=rules
pytest tests/test_aftersale.py -q
python run.py
```

浏览器 http://localhost:8080 → 售后咨询。

## 简历描述

> 基于 LangGraph 构建榴莲电商 AI 售后 Agent：设计 8 类问题分类器与 9 条结构化规则知识库，实现售后分诊闭环（问题类型、优先级、缺失凭证、命中规则、处理建议、客服话术、转人工）；提供 LangGraph Studio 双图入口与 FastAPI H5 前端演示。
