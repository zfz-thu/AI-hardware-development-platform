# -*- coding: utf-8 -*-
"""
WCCA 被动放电分析 —— 后端 API
聊天式专家引导 + 文件上传 + 计算引擎调用
"""
import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse

from engine.models import (
    CircuitParams, Configuration, ResistorDef, CapacitorDef,
    Topology, Branch, BranchElement,
)
from engine.calculator import calculate
import agent_runner

router = APIRouter(prefix="/api/wcca", tags=["wcca"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# WCCA 专用大模型配置 —— 直连真 Claude，锁定 Opus 4.8 多模态。
# 不读公共的 ANTHROPIC_* 变量，因此与 CC Switch / Claude Code 的全局模型切换完全隔离，互不影响。
# WCCA 对话涉及原理图图片识别，必须用具备多模态能力的 Claude Opus，故 model 写死。
WCCA_BASE_URL = os.environ.get("WCCA_BASE_URL", "https://api.peng-us.com")
WCCA_AUTH_TOKEN = os.environ.get("WCCA_AUTH_TOKEN", "")
WCCA_MODEL = "claude-opus-4-8"   # 写死：多模态必需，不随环境变量变化

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
3a. **母线电容典型值** (uF) 及 **电容偏差** — 如 500uF ±10%，这是放电时间计算的必需输入，务必向工程师确认，不可省略
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
    "Cap_uF": 500.0,
    "Cap_tol": 0.10,
    "T_max": 105.0,
    "T_min": -40.0,
    "configurations": [
      {"name": "7串6并", "n_serial": 7, "n_parallel": 6}
    ],
    "topology": {
      "combine": "parallel",
      "branches": [
        {"name": "主放电支路", "role": "main",
         "elements": [{"ref": "R39", "n_serial": 7, "n_parallel": 6}]},
        {"name": "采样支路", "role": "sampling",
         "elements": [{"ref": "R749", "n_serial": 10, "n_parallel": 1},
                      {"ref": "R1151", "n_serial": 1, "n_parallel": 2}]}
      ]
    },
    "resistors": [
      {"ref": "R39", "mpn": "AC1206FR-07100KL", "R_typ": 100000.0,
       "TOL_max": 0.01, "TOL_min": -0.01, "TCR": 100, "P_rated": 0.25,
       "V_max": 200.0, "EOL_max": 0.01, "EOL_min": -0.01,
       "description": "主放电电阻", "manufacturer": "YAGEO", "package": "1206"}
    ]
  }
}
```

### 关于 topology（拓扑结构）—— 非常重要
- 拓扑必须由你**从原理图识别**后填入，不要凭空假设。位号、支路数量、每条支路的元件全部以原理图为准。
- 结构说明：
  - 一条 `branch`（支路）= 它的 `elements` 串联相加。
  - 一个 `element` = 该位号电阻 × (`n_serial` / `n_parallel`)，省略时默认各为 1。
  - 多条支路之间按 `combine` 合并：`"parallel"`（并联，最常见）或 `"series"`（串联）。
  - 给主放电支路标 `"role": "main"` —— 它用于功率降额判定。
- 上面的 R39/R749/R1151 只是**示例**。实际请根据你识别到的原理图填写真实位号与连接关系。

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

    configs = [
        Configuration(
            name=c["name"],
            n_serial=c["n_serial"],
            n_parallel=c["n_parallel"],
            t_typ_known=c.get("t_typ_known"),
        )
        for c in p.get("configurations", [])
    ]

    # 解析拓扑结构（由 AI 从原理图识别后提供，零硬编码位号）
    topo_raw = p.get("topology")
    if not topo_raw or not topo_raw.get("branches"):
        raise ValueError("缺少拓扑结构（topology）—— 需先从原理图识别支路结构")
    branches = []
    for b in topo_raw["branches"]:
        elements = [
            BranchElement(
                ref=e["ref"],
                n_serial=e.get("n_serial", 1),
                n_parallel=e.get("n_parallel", 1),
            )
            for e in b.get("elements", [])
        ]
        branches.append(Branch(
            name=b.get("name", ""),
            elements=elements,
            role=b.get("role", ""),
        ))
    topology = Topology(
        branches=branches,
        combine=topo_raw.get("combine", "parallel"),
    )

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
        topology=topology,
        configurations=configs,
    )


async def _stream_chat(messages: list[dict]) -> Any:
    """流式调用 LLM。"""
    import httpx

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {WCCA_AUTH_TOKEN}",
        "anthropic-version": "2023-06-01",
    }

    payload = {
        "model": WCCA_MODEL,
        "max_tokens": 4096,
        "system": WCCA_SYSTEM_PROMPT,
        "messages": messages,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{WCCA_BASE_URL}/v1/messages?beta=true",
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
        raise HTTPException(status_code=400, detail="messages 格式错误，需为 JSON 数组")

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
        raise HTTPException(status_code=400, detail="未选择文件")

    file_path = UPLOAD_DIR / file.filename
    content = await file.read()

    with open(file_path, "wb") as f:
        f.write(content)

    # 如果是 Excel，尝试解析并返回内容摘要
    summary = None
    if file.filename.endswith((".xlsx", ".xls")):
        try:
            import pandas as pd
            import math
            df = pd.read_excel(file_path)
            preview = df.head(20).to_dict(orient="records")
            for row in preview:
                for k, v in row.items():
                    if isinstance(v, float) and math.isnan(v):
                        row[k] = None
            summary = {
                "columns": list(df.columns),
                "rows": len(df),
                "preview": preview,
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

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"计算失败: {str(e)}")


@router.post("/run-agent")
async def wcca_run_agent(payload: dict):
    """Run the full WCCA skill via the claude CLI agent.

    Chat flow: the schematic + BOM were already uploaded via /upload, so this
    takes their server-side paths (not re-uploaded files) plus engineer params,
    drives the real wcca-passive-discharge skill (vision + BOM + calc +
    LaTeX -> PDF), copies the produced PDF into uploads/, and returns a download
    path. Blocking; the agent can take several minutes.

    Expected JSON body:
      {
        "schematic_path": "<abs path under uploads/>",
        "bom_path": "<abs path under uploads/>",
        "params": {"V_HVDC_typ":..., "V_HVDC_tol":..., "T_max":..., "T_min":...,
                   "config":"7,7", "Cap_uF":..., "Cap_tol":...}
      }
    """
    schematic_path = payload.get("schematic_path", "")
    bom_path = payload.get("bom_path", "")
    params = payload.get("params", {}) or {}

    if not schematic_path or not bom_path:
        raise HTTPException(
            status_code=400,
            detail="schematic_path and bom_path are required",
        )

    # Security: both paths must resolve to a location inside UPLOAD_DIR, so a
    # crafted path cannot make the agent read arbitrary files on disk.
    upload_root = UPLOAD_DIR.resolve()
    for label, p in (("schematic", schematic_path), ("bom", bom_path)):
        try:
            rp = Path(p).resolve()
        except (OSError, ValueError):
            raise HTTPException(status_code=400, detail=f"invalid {label} path")
        if upload_root not in rp.parents and rp != upload_root:
            raise HTTPException(
                status_code=400,
                detail=f"{label} path must be inside the uploads directory",
            )
        if not rp.exists():
            raise HTTPException(status_code=400, detail=f"{label} file not found")

    run_id = uuid.uuid4().hex[:12]
    run_dir = UPLOAD_DIR / f"run_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    result = agent_runner.run_wcca_agent(
        schematic_path, bom_path, params, run_dir=str(run_dir)
    )

    if not result.get("ok"):
        return {
            "ok": False,
            "error": result.get("error", "agent failed"),
            "log_tail": result.get("log_tail", ""),
        }

    # Copy the produced PDF into uploads/ with a unique name for download.
    src_pdf = Path(result["pdf_path"])
    dest_name = f"wcca_{run_id}.pdf"
    dest_pdf = UPLOAD_DIR / dest_name
    try:
        shutil.copyfile(src_pdf, dest_pdf)
    except OSError as e:
        return {
            "ok": False,
            "error": f"PDF produced but copy failed: {e}",
            "log_tail": result.get("log_tail", ""),
            "pdf_source": str(src_pdf),
        }

    return {
        "ok": True,
        "download": f"/uploads/{dest_name}",
        "pdf_source": str(src_pdf),
        "log_tail": result.get("log_tail", ""),
    }
