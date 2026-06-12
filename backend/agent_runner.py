# -*- coding: utf-8 -*-
"""
WCCA agent runner.

This module is a thin routing window: instead of reimplementing the WCCA
calculation, it shells out to the local `claude` CLI in headless mode and
lets the real `wcca-passive-discharge` skill do the full job (schematic
vision + BOM parse + datasheet search + calculation + LaTeX -> PDF report).

Everything that is environment specific (CLI binary, skill work dir, timeout)
is read from env vars so the same code can run on a future server deploy by
only changing env, not code.

NOTE: the prompt sent to the agent contains Chinese text. We build it here at
runtime and write it to a UTF-8 temp file; we never put Chinese into a source
file via tooling. The agent reads the prompt from stdin.

Session mode (start_wcca_session / send_to_session):
  The persistent-session path uses `claude --resume <session_id>` to maintain
  multi-turn context inside the skill agent.  send_to_session streams
  --output-format stream-json and filters events so only assistant text tokens
  are yielded to callers; tool calls, system events, and internal scaffolding
  are swallowed (logged to stderr only).  When the agent prints RESULT_PDF: the
  pdf path is extracted and returned as the generator's StopIteration value via
  a sentinel tuple.
"""
import json
import os
import re
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Generator


# --- Configuration (all overridable via env) ---------------------------------

def _cfg_cli() -> str:
    # On Windows we call claude.exe directly to avoid the sh wrapper's MSYS
    # path conversion. Override with WCCA_CLI for other environments.
    return os.environ.get(
        "WCCA_CLI",
        r"D:\claude\node\node_modules\@anthropic-ai\claude-code\bin\claude.exe",
    )


def _cfg_workdir() -> Path:
    explicit = os.environ.get("WCCA_WORKDIR")
    return Path(explicit) if explicit else Path.cwd()


def _cfg_timeout() -> int:
    try:
        return int(os.environ.get("WCCA_TIMEOUT", "1800"))
    except ValueError:
        return 1800


# Tools the agent is allowed to use (bypassPermissions is blocked by the
# safety classifier, so we enumerate explicitly).
_ALLOWED_TOOLS = ["Bash", "Read", "Write", "Edit", "WebSearch", "Glob", "Grep"]

# Marker the agent is asked to print so we can reliably locate the result PDF.
_RESULT_MARKER = "RESULT_PDF:"

# --- Session store ------------------------------------------------------------
# Maps user_id -> {"session_id": str, "workdir": str, "created_at": float}
# TTL: sessions older than SESSION_TTL_S are discarded on next access.
SESSION_TTL_S = 86400  # 24 hours

_SESSION_STORE: dict[str, dict] = {}
_SESSION_LOCK = threading.Lock()


def _prune_sessions() -> None:
    """Remove sessions older than SESSION_TTL_S."""
    cutoff = time.time() - SESSION_TTL_S
    with _SESSION_LOCK:
        stale = [uid for uid, s in _SESSION_STORE.items()
                 if s.get("created_at", 0) < cutoff]
        for uid in stale:
            _SESSION_STORE.pop(uid, None)


def get_session(user_id: str) -> dict | None:
    _prune_sessions()
    with _SESSION_LOCK:
        return _SESSION_STORE.get(user_id)


def set_session(user_id: str, session_id: str, workdir: str) -> None:
    with _SESSION_LOCK:
        _SESSION_STORE[user_id] = {
            "session_id": session_id,
            "workdir": workdir,
            "created_at": time.time(),
        }


def clear_session(user_id: str) -> None:
    with _SESSION_LOCK:
        _SESSION_STORE.pop(user_id, None)


# --- Prompt construction ------------------------------------------------------

def _build_prompt(schematic_paths: list, bom_paths: list, params: dict,
                  workdir: str) -> str:
    """Build the instruction prompt for the agent. May contain Chinese."""
    v_typ = params.get("V_HVDC_typ", 500.0)
    v_tol = params.get("V_HVDC_tol", 0.0)
    t_max = params.get("T_max", 105.0)
    t_min = params.get("T_min", -40.0)
    config = params.get("config", "")
    cap_uf = params.get("Cap_uF", params.get("cap_uf", None))
    cap_tol = params.get("Cap_tol", params.get("cap_tol", None))
    t_limit = params.get("t_limit", params.get("T_limit", None))
    topology = params.get("topology")
    comp_src = params.get("components_source") or {}

    lines = [
        "请执行 WCCA 被动放电分析（使用 wcca-passive-discharge 技能的完整六步流程）。",
        "",
        "## 输入材料（绝对路径）",
    ]
    if len(schematic_paths) == 1:
        lines.append("- 电路原理图: " + schematic_paths[0])
    else:
        lines.append("- 电路原理图（共 " + str(len(schematic_paths)) + " 张，均为同一电路的不同图页/区域）:")
        for i, sp in enumerate(schematic_paths, 1):
            lines.append("  " + str(i) + ". " + sp)
        lines.append("注意：上面是同一个电路的多张原理图，请逐张 Read 识别每一张，"
                     "并合并成一个跨图页的完整拓扑；不要只看其中一张。")
    if bom_paths:
        if len(bom_paths) == 1:
            lines.append("- BOM 表: " + bom_paths[0])
        else:
            lines.append("- BOM 表（共 " + str(len(bom_paths)) + " 个，请全部解析并按位号合并）:")
            for i, bp in enumerate(bom_paths, 1):
                lines.append("  " + str(i) + ". " + bp)
    lines += [
        "",
        "## 工程师提供的参数",
        "- 母线电压额定值 V_HVDC_typ: " + str(v_typ) + " V",
        "- 母线电压偏差 V_HVDC_tol: " + str(v_tol),
        "- 最高工作温度 T_max: " + str(t_max) + " C",
        "- 最低工作温度 T_min: " + str(t_min) + " C",
    ]
    if cap_uf is not None:
        lines.append("- 母线电容典型值 Cap_uF: " + str(cap_uf) + " uF")
    if cap_tol is not None:
        lines.append("- 母线电容偏差 Cap_tol: " + str(cap_tol))
    if config:
        lines.append("- 主放电电阻串并联配置: " + str(config))
    if topology:
        lines.append("")
        lines.append("## 对话中已与工程师确认的电路拓扑（先验，供交叉验证）")
        lines.append("以下拓扑是对话阶段专家看原理图识别并经工程师确认的，"
                     "请在你自己识别图像后与之交叉验证；若有出入，以原理图实际为准并在报告中说明差异：")
        lines.append(json.dumps(topology, ensure_ascii=False, indent=2))
    if comp_src.get("components"):
        lines.append("")
        lines.append("## 器件来源：工程师口述的位号与 MPN（无 BOM 文件）")
        lines.append("请用这些位号和 MPN 联网 WebSearch 查询 datasheet 参数：")
        for c in comp_src["components"]:
            lines.append("- " + str(c.get("ref", "")) + " : " + str(c.get("mpn", "")))
    lines += [
        "",
        "## 工作目录（干净目录，只放本次产物）",
        "本次所有中间文件、extracted-circuit JSON、报告，都生成在: " + workdir,
        "不要从其它历史项目目录读取或复用任何 BOM/JSON/报告残留文件；只用本提示给出的输入材料。",
        "",
        "## 任务要求（通用方法：识别当前电路，禁止套用任何历史电路的位号/参数/结果）",
        "1. 识别**当前**原理图的真实拓扑（几条支路、主放电电阻矩阵、串并联数、采样/分压支路；灰色器件视为空贴不计入）。若上面提供了已确认拓扑先验，与你的识别交叉验证，有出入以原理图为准并在报告说明。",
        "2. 获取每个器件的 MPN：有 BOM 则按位号查 BOM；工程师口述了位号+MPN（见上）则用之；都没有则在报告标注缺失。对每个 MPN 先查知识库、没有再 WebSearch，提取 TOL/TCR/EOL/额定功率/耐压。",
        "3. 把识别到的电路写成 extracted-circuit JSON（位号、MPN、各器件参数、topology branches），字段对照 skill 的 engine/models.py；可参考 references/d11-baseline.json 的格式（只学格式，不抄其数据）。",
        "4. 用 skill 的脚本计算并出报告（电路数据全部来自你写的 JSON，脚本不内置任何电路）：",
        "   python <skill>/scripts/run_wcca.py --circuit-json <你的extracted.json> --config <串,并> --v-hvdc <V> --v-hvdc-tol <tol> --cap-uf <uF> --cap-tol <tol>" + ((" --t-limit " + str(t_limit)) if t_limit is not None else " --t-limit 120") + " --compile",
        "   必须传入工程师给出的母线电容值（--cap-uf/--cap-tol）和放电时间限值（--t-limit），不得自行假设或使用任何默认值。",
        "5. 通用报告生成器会遍历你 JSON 里的器件/支路生成中文 LaTeX 计算书并用 xelatex 编译成 PDF。",
        "6. 全部完成后，在最后**只**打印一行，给出最终 PDF 的绝对路径，格式严格为:",
        "   " + _RESULT_MARKER + " <PDF绝对路径>",
        "   这一行必须是纯 ASCII 标记加路径，便于程序解析。不要输出 datasheet 路径、中间文件路径或任何其他内容。",
    ]
    return "\n".join(lines)


# --- PDF location -------------------------------------------------------------

def _find_pdf_from_marker(stdout: str) -> str | None:
    for line in stdout.splitlines():
        idx = line.find(_RESULT_MARKER)
        if idx != -1:
            candidate = line[idx + len(_RESULT_MARKER):].strip().strip('"')
            if candidate:
                return candidate
    return None


def _newest_pdf(workdir: Path, since_ts: float) -> str | None:
    if not workdir.is_dir():
        return None
    newest = None
    newest_mtime = since_ts
    for p in workdir.glob("*.pdf"):
        try:
            m = p.stat().st_mtime
        except OSError:
            continue
        if m >= newest_mtime:
            newest_mtime = m
            newest = p
    return str(newest) if newest else None


# --- Public entry point -------------------------------------------------------

def _as_list(paths) -> list[str]:
    """Normalize a str | list | None of paths into a clean list of non-empty strs.

    Back-compat: callers may still pass a single path string.
    """
    if paths is None:
        return []
    if isinstance(paths, str):
        return [paths] if paths else []
    return [p for p in paths if p]


def run_wcca_agent(schematic_paths, bom_paths, params: dict,
                   run_dir: str | None = None) -> dict:
    """Run the WCCA skill via the claude CLI and return the produced PDF.

    schematic_paths / bom_paths may be a list of absolute paths OR a single
    path string (back-compat). At least one schematic is required; BOMs are
    optional (the engineer may dictate refs+MPNs instead).

    Returns a dict:
      {ok: bool, pdf_path: str|None, log_tail: str, error: str|None}
    """
    cli = _cfg_cli()
    workdir = _cfg_workdir()
    timeout = _cfg_timeout()

    schematic_list = _as_list(schematic_paths)
    bom_list = _as_list(bom_paths)

    if not Path(cli).exists():
        return {"ok": False, "pdf_path": None, "log_tail": "",
                "error": "claude CLI not found at " + cli}
    if not schematic_list:
        return {"ok": False, "pdf_path": None, "log_tail": "",
                "error": "at least one schematic path is required"}
    # schematics are required; BOMs are optional.
    checks = [("schematic", p) for p in schematic_list]
    checks += [("BOM", p) for p in bom_list]
    for label, pth in checks:
        if not Path(pth).exists():
            return {"ok": False, "pdf_path": None, "log_tail": "",
                    "error": label + " file not found: " + pth}

    # Use a CLEAN per-run working dir so the agent never sees stale residue from
    # other projects (old BOM/JSON/reports) in the shared work dir. Falls back to
    # the configured work dir only if no run_dir was given.
    effective_workdir = Path(run_dir) if run_dir else workdir
    effective_workdir.mkdir(parents=True, exist_ok=True)
    prompt = _build_prompt(schematic_list, bom_list, params,
                           str(effective_workdir))

    # Write the prompt to a UTF-8 temp file with an ASCII name.
    tmp_dir = effective_workdir
    fd, prompt_file = tempfile.mkstemp(prefix="wcca_prompt_", suffix=".txt",
                                       dir=str(tmp_dir))
    os.close(fd)
    Path(prompt_file).write_text(prompt, encoding="utf-8")

    # bypassPermissions: headless unattended mode — no human to click approve.
    cmd = [cli, "-p", "--permission-mode", "bypassPermissions",
           "--allowedTools", *_ALLOWED_TOOLS,
           "--add-dir", str(effective_workdir)]

    start = time.time()
    timed_out = False
    try:
        with open(prompt_file, "r", encoding="utf-8") as stdin_f:
            proc = subprocess.run(
                cmd,
                stdin=stdin_f,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                cwd=str(effective_workdir),
            )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        returncode = proc.returncode
    except subprocess.TimeoutExpired as e:
        timed_out = True
        stdout = (e.stdout or "") if isinstance(e.stdout, str) else ""
        stderr = (e.stderr or "") if isinstance(e.stderr, str) else ""
        returncode = -1
    finally:
        try:
            os.remove(prompt_file)
        except OSError:
            pass

    combined = (stdout + "\n" + stderr).strip()
    log_tail = combined[-4000:]

    if timed_out:
        return {"ok": False, "pdf_path": None, "log_tail": log_tail,
                "error": "agent timed out after " + str(timeout) + "s"}

    pdf = _find_pdf_from_marker(stdout)
    if pdf and not Path(pdf).exists():
        pdf = None
    if not pdf:
        # prefer the clean run dir; fall back to the shared work dir just in case
        pdf = _newest_pdf(effective_workdir, start)
    if not pdf and effective_workdir != workdir:
        pdf = _newest_pdf(workdir, start)

    if not pdf:
        return {"ok": False, "pdf_path": None, "log_tail": log_tail,
                "error": "no PDF produced (returncode=" + str(returncode) + ")"}

    return {"ok": True, "pdf_path": pdf, "log_tail": log_tail, "error": None}


# --- Persistent-session API ---------------------------------------------------

def start_wcca_session(user_id: str, workdir: str | None = None) -> str:
    """Start a new persistent WCCA skill session and return the session_id.

    Sends a greeting message to the skill agent via `claude -p --output-format
    json`.  The JSON response contains a `session_id` field that is stored in
    the in-memory session store keyed by user_id.

    workdir: absolute path for this session's output files.  Defaults to a
    fresh subdirectory under _cfg_workdir().
    """
    cli = _cfg_cli()
    if not Path(cli).exists():
        raise RuntimeError("claude CLI not found at " + cli)

    if workdir is None:
        base = _cfg_workdir()
        session_dir = base / ("wcca_session_" + str(int(time.time())))
    else:
        session_dir = Path(workdir)
    session_dir.mkdir(parents=True, exist_ok=True)

    # First turn: empty greeting so the skill agent introduces itself and asks
    # for the schematic.  We use --output-format json to get the session_id.
    cmd = [
        cli, "-p",
        "--permission-mode", "bypassPermissions",
        "--allowedTools", *_ALLOWED_TOOLS,
        "--add-dir", str(session_dir),
        "--output-format", "json",
    ]

    # Write greeting to temp file (avoid shell quoting issues with non-ASCII)
    fd, greeting_file = tempfile.mkstemp(prefix="wcca_greet_", suffix=".txt",
                                         dir=str(session_dir))
    os.close(fd)
    # ASCII-safe greeting — SKILL.md will make the agent self-introduce
    Path(greeting_file).write_text("Hello, please start the WCCA analysis.",
                                   encoding="utf-8")

    try:
        with open(greeting_file, "r", encoding="utf-8") as f:
            proc = subprocess.run(
                cmd, stdin=f,
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                timeout=120,
                cwd=str(session_dir),
            )
    finally:
        try:
            os.remove(greeting_file)
        except OSError:
            pass

    raw = (proc.stdout or "").strip()
    session_id = None

    # --output-format json returns a single JSON object on stdout
    if raw:
        try:
            data = json.loads(raw)
            session_id = data.get("session_id")
        except json.JSONDecodeError:
            # Some CLI versions wrap in a container; try last non-empty line
            for line in reversed(raw.splitlines()):
                line = line.strip()
                if line.startswith("{"):
                    try:
                        data = json.loads(line)
                        session_id = data.get("session_id")
                        if session_id:
                            break
                    except json.JSONDecodeError:
                        continue

    if not session_id:
        raise RuntimeError(
            "Failed to obtain session_id from CLI.\n"
            "stdout: " + raw[:500] + "\n"
            "stderr: " + (proc.stderr or "")[:200]
        )

    set_session(user_id, session_id, str(session_dir))
    return session_id


# Event types from --output-format stream-json that carry visible assistant text
_TEXT_EVENT_TYPES = {"assistant"}


def _extract_text_from_event(event: dict) -> str:
    """Return the text delta from a stream-json event, or '' if not text."""
    # Format: {"type":"assistant","message":{"content":[{"type":"text","text":"..."}]}}
    # or streaming delta: {"type":"content_block_delta","delta":{"type":"text_delta","text":"..."}}
    etype = event.get("type", "")

    # Streaming delta events
    if etype == "content_block_delta":
        delta = event.get("delta", {})
        if delta.get("type") == "text_delta":
            return delta.get("text", "")

    # Complete assistant message (used by non-streaming json output)
    if etype == "assistant":
        msg = event.get("message", {})
        parts = []
        for block in msg.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)

    return ""


def send_to_session(
    user_id: str,
    message: str,
    image_b64: str | None = None,
    media_type: str = "image/jpeg",
) -> Generator[str | tuple, None, None]:
    """Send a message to an existing session and stream assistant text tokens.

    Yields str tokens as the agent responds.  When the agent finishes and a
    RESULT_PDF path was detected, yields a final sentinel tuple:
        ("__PDF__", "/abs/path/to/report.pdf")
    followed by the post-PDF summary text (if any).

    image_b64: optional base64-encoded image to include as a vision block.
    media_type: MIME type of the image (default "image/jpeg").

    Raises RuntimeError if the session is not found or the CLI is missing.
    """
    info = get_session(user_id)
    if not info:
        raise RuntimeError("No active session for user_id=" + user_id +
                           ". Call start_wcca_session first.")

    cli = _cfg_cli()
    session_id = info["session_id"]
    session_dir = Path(info["workdir"])
    timeout = _cfg_timeout()

    # Build the message content.  If an image is attached we write a JSON
    # content-block array to the temp file; otherwise plain text.
    if image_b64:
        content = json.dumps([
            {"type": "image",
             "source": {"type": "base64",
                        "media_type": media_type,
                        "data": image_b64}},
            {"type": "text", "text": message or "请分析这张原理图。"},
        ], ensure_ascii=False)
        msg_bytes = content.encode("utf-8")
    else:
        msg_bytes = message.encode("utf-8")

    fd, msg_file = tempfile.mkstemp(prefix="wcca_msg_", suffix=".txt",
                                    dir=str(session_dir))
    os.close(fd)
    Path(msg_file).write_bytes(msg_bytes)

    cmd = [
        cli, "-p",
        "--resume", session_id,
        "--permission-mode", "bypassPermissions",
        "--allowedTools", *_ALLOWED_TOOLS,
        "--add-dir", str(session_dir),
        "--output-format", "stream-json",
        "--verbose",
    ]

    pdf_path: str | None = None
    past_pdf_path_line = False  # True once we've consumed the RESULT_PDF: path line

    try:
        with open(msg_file, "r", encoding="utf-8") as stdin_f:
            proc = subprocess.Popen(
                cmd,
                stdin=stdin_f,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(session_dir),
            )

        # Read stdout line-by-line; each line is a JSON event
        for raw_line in proc.stdout:
            raw_line = raw_line.rstrip("\n")
            if not raw_line:
                continue

            # Try to parse as JSON event
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                # Non-JSON lines (rare) — scan for PDF marker in plain text
                idx = raw_line.find(_RESULT_MARKER)
                if idx != -1:
                    candidate = raw_line[idx + len(_RESULT_MARKER):].strip().strip('"')
                    if candidate:
                        pdf_path = candidate
                continue

            text = _extract_text_from_event(event)
            if not text:
                continue

            # Post-PDF summary: yield directly (marker + path already consumed)
            if past_pdf_path_line:
                yield text
                continue

            # Check if the RESULT_PDF marker appears in this text chunk.
            marker_idx = text.find(_RESULT_MARKER)
            if marker_idx != -1:
                # Yield any text before the marker line
                before = text[:marker_idx]
                if before:
                    yield before
                # Extract the path (rest of the line after the marker)
                after = text[marker_idx + len(_RESULT_MARKER):]
                path_line, _, rest = after.partition("\n")
                pdf_path = path_line.strip().strip('"')
                past_pdf_path_line = True
                # Yield any text after the path line (start of summary)
                if rest:
                    yield rest
            else:
                yield text

        proc.wait(timeout=timeout)

    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        yield "\n[分析超时，请重试]\n"
        return
    finally:
        try:
            os.remove(msg_file)
        except OSError:
            pass

    # Signal PDF availability as a sentinel tuple AFTER all text has been yielded
    if pdf_path and Path(pdf_path).exists():
        yield ("__PDF__", pdf_path)
    elif pdf_path:
        # Marker was printed but file doesn't exist yet — try newest fallback
        fallback = _newest_pdf(session_dir, time.time() - 60)
        if fallback:
            yield ("__PDF__", fallback)
