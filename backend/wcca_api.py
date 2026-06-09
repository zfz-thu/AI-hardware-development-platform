# -*- coding: utf-8 -*-
"""
WCCA 被动放电分析 —— 后端 API
聊天式专家引导 + 文件上传 + 计算引擎调用
"""
import json
import os
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import StreamingResponse

from engine.models import (
    CircuitParams, Configuration, ResistorDef, CapacitorDef,
)
from engine.calculator import calculate

router = APIRouter(prefix="/api/wcca", tags=["wcca"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# DeepSeek API endpoint (Anthropic-compatible)
ANTHROPIC_BASE_URL = os.environ.get(
    "ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic"
)
ANTHROPIC_AUTH_TOKEN = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_DEFAULT_HAIKU_MODEL", "deepseek-v4-flash")

WCCA_SYSTEM_PROMPT = """你是一位资深的汽车电子 WCCA（最坏情况电路分析）专家，专门负责被动放电电路的分析。

## 你的角色
- 你有超过15年的汽车电子硬件设计经验
- 你擅长从 BOM 表和电路原理图中提取参数
- 你对 ISO 26262、GB/T 18384.3 等法规标准非常熟悉
- 你说话专业但不生硬，愿意耐心引导工程师

## 被动放电电路所需参数
你需要从与工程师的对话中收集以下信息：

### 必须由工程师提供的：
1. **BOM 表** (Excel .xlsx 文件) — 包含位号、MPN、描述等信息
2. **电路原理图** (JPG/PNG 图片或 PDF) — 用于识别拓扑和位号
3. **母线电压额定值** (V) — 如 500V
4. **母线电压偏差** — 如 ±5%（没有提供则认为 0%）
5. **主放电电阻的串并联配置** — 如 7串6并
6. **工作温度范围** — 最高温度和最低温度（如未提供，默认 -40°C ~ 105°C）

### 可从 BOM + Datasheet 提取的：
- 各电阻的标称阻值、精度等级(TOL)、TCR、额定功率
- 电容的容值、精度、温度系数

## 对话流程
1. 先自我介绍，然后请工程师上传 BOM 表
2. 收到 BOM 后，解析并确认关键器件信息
3. 请工程师上传原理图
4. 收到原理图后，识别拓扑结构
5. 询问母线电压、偏差、温度范围等参数
6. 确认所有信息后，说「信息已齐全，开始计算」

## 重要规则
- 每次只问1-2个问题，不要一次问太多
- 收到文件后先解析确认，再问下一个
- 如果工程师不确定某个参数，给出合理的默认值建议
- 当你确认所有信息齐全后，请在回复末尾附上 JSON 格式的参数摘要，
  用 ```json 代码块包裹，格式如下：

```json
{
  "ready": true,
  "params": {
    "V_HVDC_typ": 500.0,
    "V_HVDC_tol": 0.05,
    "T_max": 105.0,
    "T_min": -40.0,
    "configurations": [
      {"name": "7串6并", "n_serial": 7, "n_parallel": 6}
    ],
    "resistors": [
      {"ref": "R39", "mpn": "AC1206FR-07100KL", "R_typ": 100000.0,
       "TOL_max": 0.01, "TOL_min": -0.01, "TCR": 100, "P_rated": 0.25,
       "V_max": 200.0, "EOL_max": 0.01, "EOL_min": -0.01,
       "description": "主放电电阻", "manufacturer": "YAGEO", "package": "1206"}
    ]
  }
}
```

## 特别提醒
- 工程师上传文件后，你会看到文件内容（如果系统支持多模态的话）
- 保持友善和耐心，工程师可能不熟悉 WCCA 的术语
- 对于电阻精度的描述（如"F级"→±1%，"B级"→±0.1%），请主动帮工程师转换
"""


def _parse_chat_params(text: str) -> dict | None:
    """尝试从聊天回复中提取 JSON 参数。"""
    m = re.search(r"```json\s*([\s\S]*?)\s*```", text)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _build_circuit_params(p: dict) -> CircuitParams:
    """将前端传来的参数转换成 CircuitParams。"""
    resistors = {}
    for r in p.get("resistors", []):
        resistors[r["ref"]] = ResistorDef(
            ref=r["ref"],
            description=r.get("description", ""),
            mpn=r.get("mpn", ""),
            manufacturer=r.get("manufacturer", ""),
            package=r.get("package", ""),
            R_typ=r["R_typ"],
            TOL_max=r["TOL_max"],
            TOL_min=r["TOL_min"],
            TCR=r["TCR"],
            P_rated=r["P_rated"],
            V_max=r["V_max"],
            EOL_max=r["EOL_max"],
            EOL_min=r["EOL_min"],
        )

    # 引入 topology_fn
    from engine.topology import passive_discharge_r_parallel
    from engine.topology import build_r_dict as _unused  # noqa

    configs = [
        Configuration(
            name=c["name"],
            n_serial=c["n_serial"],
            n_parallel=c["n_parallel"],
        )
        for c in p.get("configurations", [])
    ]

    caps = {}
    for c in p.get("capacitors", []):
        caps[c["ref"]] = CapacitorDef(
            ref=c["ref"],
            Cap_typ=c.get("Cap_typ", 0.0),
            TOL_max=c.get("TOL_max", 0.0),
            TOL_min=c.get("TOL_min", 0.0),
            TCR_max=c.get("TCR_max", 0),
            TCR_min=c.get("TCR_min", 0),
            V_rated=c.get("V_rated", 0),
        )

    return CircuitParams(
        circuit_id="passive-discharge",
        circuit_name="被动放电电路 WCCA 分析",
        T_max=p.get("T_max", 105.0),
        T_min=p.get("T_min", -40.0),
        V_HVDC_typ=p.get("V_HVDC_typ", 500.0),
        V_HVDC_tol=p.get("V_HVDC_tol", 0.0),
        V_Safety=p.get("V_Safety", 60.0),
        resistors=resistors,
        capacitors=caps,
        topology_fn=passive_discharge_r_parallel,
        configurations=configs,
    )


async def _stream_chat(messages: list[dict]) -> Any:
    """流式调用 LLM。"""
    import httpx

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ANTHROPIC_AUTH_TOKEN}",
        "anthropic-version": "2023-06-01",
    }

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 4096,
        "system": WCCA_SYSTEM_PROMPT,
        "messages": messages,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{ANTHROPIC_BASE_URL}/messages",
            headers=headers,
            json=payload,
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        yield "event: done\ndata: [DONE]\n\n"
                        break
                    try:
                        data = json.loads(data_str)
                        t = data.get("type", "")
                        if t == "content_block_delta":
                            delta = data.get("delta", {})
                            if "text" in delta:
                                yield f"data: {json.dumps({'text': delta['text']})}\n\n"
                        elif t == "message_stop":
                            yield "event: done\ndata: [DONE]\n\n"
                            break
                    except json.JSONDecodeError:
                        continue


@router.post("/chat")
async def wcca_chat(messages: str = Form(...)):
    """WCCA 专家对话接口 (SSE 流式)。"""
    try:
        msgs = json.loads(messages)
    except json.JSONDecodeError:
        return {"error": "messages 格式错误，需为 JSON 数组"}

    return StreamingResponse(
        _stream_chat(msgs),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/upload")
async def wcca_upload(file: UploadFile = File(...)):
    """上传 BOM 或原理图文件。"""
    if not file.filename:
        return {"error": "未选择文件"}

    file_path = UPLOAD_DIR / file.filename
    content = await file.read()

    with open(file_path, "wb") as f:
        f.write(content)

    # 如果是 Excel，尝试解析并返回内容摘要
    summary = None
    if file.filename.endswith((".xlsx", ".xls")):
        try:
            import pandas as pd
            df = pd.read_excel(file_path)
            summary = {
                "columns": list(df.columns),
                "rows": len(df),
                "preview": df.head(20).to_dict(orient="records"),
            }
        except Exception:
            summary = {"error": "无法解析 Excel 文件"}

    return {
        "filename": file.filename,
        "size": len(content),
        "path": str(file_path),
        "summary": summary,
    }


@router.post("/calculate")
async def wcca_calculate(params: dict):
    """执行 WCCA 计算。"""
    try:
        cp = _build_circuit_params(params)
        results = calculate(cp)

        # 转为 JSON 可序列化格式
        config_results = []
        for cr in results.config_results:
            config_results.append({
                "config_name": cr.config_name,
                "n_serial": cr.n_serial,
                "n_parallel": cr.n_parallel,
                "R_parallel_typ": cr.R_parallel_typ,
                "R_parallel_max": cr.R_parallel_max,
                "C_max": cr.C_max,
                "V_HVDC_max": cr.V_HVDC_max,
                "t_discharge_typ": round(cr.t_discharge_typ, 3),
                "t_discharge_max": round(cr.t_discharge_max, 3),
                "t_passed": cr.t_passed,
                "t_limit": 120.0,
                "P_all_max": round(cr.P_all_max, 4),
                "P_single_max": round(cr.P_single_max, 4),
                "P_derate_target": round(cr.P_derate_target, 4),
                "P_passed": cr.P_passed,
            })

        wc_resistors = {}
        for ref, wc in results.resistors_wc.items():
            wc_resistors[ref] = {
                "ref": wc.ref,
                "R_typ": wc.R_typ,
                "R_max_Tmax": round(wc.R_max_Tmax, 2),
                "R_min_Tmax": round(wc.R_min_Tmax, 2),
            }

        return {
            "circuit_id": results.circuit_id,
            "circuit_name": results.circuit_name,
            "T_max": results.T_max,
            "T_min": results.T_min,
            "V_HVDC_typ": results.V_HVDC_typ,
            "V_Safety": results.V_Safety,
            "Cap_HVDC_typ": results.Cap_HVDC_typ,
            "ln_ratio": round(results.ln_ratio, 6),
            "resistors_wc": wc_resistors,
            "config_results": config_results,
            "all_t_pass": results.all_t_pass,
            "all_P_pass": results.all_P_pass,
        }

    except Exception as e:
        return {"error": f"计算失败: {str(e)}"}, 500
