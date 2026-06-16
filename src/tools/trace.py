"""批次溯源工具：根据溯源码查询 PostgreSQL 中的批次信息。"""

from __future__ import annotations

import time

from src.models.schemas import ToolResult
from src.storage.db import get_trace_batch


def query_trace_code(trace_code: str) -> ToolResult:
    """查询我方自主生成的批次溯源码详情。

    溯源码代表「批次 + 品类」，同一批次同品种共用一枚码。
    成功时 data 含产地、入库日期、成熟度区间、在售状态、关联 SKU 等。

    Args:
        trace_code: 用户提供的码，如 TR20260609002（大小写不敏感）。

    Returns:
        success=True 且 valid=True 时返回完整批次；
        未找到时 error_code=TRACE_NOT_FOUND。
    """
    start = time.perf_counter()
    code = trace_code.strip().upper()
    data = get_trace_batch(code)

    if data and data.get("valid"):
        return ToolResult(
            success=True,
            source="trace_service",
            data=data,
            latency_ms=int((time.perf_counter() - start) * 1000),
        )

    return ToolResult(
        success=False,
        source="trace_service",
        error_code="TRACE_NOT_FOUND",
        data={"trace_code": code, "valid": False},
        latency_ms=int((time.perf_counter() - start) * 1000),
    )
