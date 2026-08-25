# -*- coding: utf-8 -*-
"""
abaqus_bridge.py — 自建 Agent 驱动 Abaqus/CAE 仿真的桥接模块（完全绕开 MCP 协议）
=================================================================================

为什么能这么做？
    abaqus-mcp 项目的架构是：

        MCP Client (Cursor/Claude)  ⇄  mcp_server.py  ⇄  文件IPC  ⇄  Abaqus 插件

    而 Abaqus 内部的 abaqus_mcp_plugin.py 根本不认识 MCP 协议，
    它只做一件事：轮询 ~/.abaqus-mcp/commands/ 目录下的 JSON 命令文件，
    执行后把结果写回 ~/.abaqus-mcp/results/<id>.json。

    所以"写命令文件 → 等结果文件"这两步（即 mcp_server.py 里的 _send_command），
    就是自建 Agent 唯一需要复用的逻辑。本模块已实现，开箱即用。

使用前提
--------
1. 启动 Abaqus/CAE（GUI 或 CAE 内核）
2. 加载插件：File → Run Script... → 选择 abaqus_mcp_plugin.py
   （或把 abaqus_v6.env.example 复制为 ~/abaqus_v6.env 实现自动加载）
3. 在 Abaqus 命令行执行（任选其一）：
       mcp_start()        # 后台线程，推荐（GUI 不卡）
       mcp_coop_loop()    # 协作式
       mcp_loop()         # 阻塞式，最稳
4. 本模块与插件共享同一个 MCP_HOME（默认 ~/.abaqus-mcp，
   也可用环境变量 ABAQUS_MCP_HOME 指定；本模块会自动探测活着的那个）

快速验证
--------
    from abaqus_bridge import check_connection, execute_script
    print(check_connection())
    print(execute_script('print("Hello from Abaqus!")'))
"""

import base64
import json
import os
import time
import uuid

# ==================== 路径探测 ====================

# 已知的 abaqus-mcp 项目目录（插件若直接从该目录加载，MCP_HOME 就是它）
KNOWN_PROJECT_DIR = r"C:\Users\18801\Desktop\text-to-cae\abaqus-mcp-main"


def detect_mcp_home() -> str:
    """自动探测插件实际使用的 MCP_HOME 目录（取 status.json 最新鲜的那个）。"""
    # 1. 环境变量优先（与插件 _resolve_mcp_home 保持一致）
    env_home = os.environ.get("ABAQUS_MCP_HOME", "").strip()
    if env_home:
        return os.path.abspath(os.path.expanduser(env_home))

    # 2. 候选目录：插件默认位置 + 已知项目目录
    candidates = [
        os.path.join(os.path.expanduser("~"), ".abaqus-mcp"),
        KNOWN_PROJECT_DIR,
    ]

    # 3. 谁有"活着"的插件痕迹（status.json 最新），就选谁
    best, best_mtime = None, -1.0
    for c in candidates:
        sf = os.path.join(c, "status.json")
        if os.path.exists(sf):
            try:
                mtime = os.path.getmtime(sf)
            except Exception:
                mtime = -1.0
            if mtime > best_mtime:
                best, best_mtime = c, mtime
        elif os.path.isdir(os.path.join(c, "commands")) and best is None:
            best = c
    return best or candidates[0]


MCP_HOME = detect_mcp_home()
COMMANDS_DIR = os.path.join(MCP_HOME, "commands")
RESULTS_DIR = os.path.join(MCP_HOME, "results")
STATUS_FILE = os.path.join(MCP_HOME, "status.json")
DEFAULT_TIMEOUT = 30.0


# ==================== 核心 IPC（等价于 mcp_server.py 的 _send_command） ====================

def _send_command(cmd_type: str, timeout: float = DEFAULT_TIMEOUT, **kwargs) -> dict:
    """写命令文件 → 轮询结果文件 → 返回结果 dict。"""
    os.makedirs(COMMANDS_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)

    cmd_id = uuid.uuid4().hex[:8]
    command = {"id": cmd_id, "type": cmd_type, "timestamp": time.time(), **kwargs}
    cmd_path = os.path.join(COMMANDS_DIR, f"cmd_{cmd_id}.json")
    result_path = os.path.join(RESULTS_DIR, f"{cmd_id}.json")

    with open(cmd_path, "w", encoding="utf-8") as f:
        json.dump(command, f, ensure_ascii=False)

    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(result_path):
            try:
                with open(result_path, "r", encoding="utf-8") as f:
                    result = json.load(f)
                os.remove(result_path)  # 取走即删，避免重复消费
                return result
            except Exception:
                time.sleep(0.05)  # 容忍插件写入中的半成品文件
        time.sleep(0.05)

    try:
        os.remove(cmd_path)
    except Exception:
        pass
    return {"success": False,
            "error": f"Timeout: Abaqus 插件 {timeout}s 内无响应（确认已执行 mcp_start()？）"}


def read_status() -> dict:
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# ==================== 对 Agent 暴露的功能（全部返回字符串，便于放进对话历史） ====================

def check_connection() -> str:
    """检查 Abaqus 是否在运行、插件是否已加载并响应。"""
    status = read_status()
    if not status:
        return (f"❌ 未找到 {STATUS_FILE}。请确认：1) Abaqus 已启动；"
                f"2) 已加载 abaqus_mcp_plugin.py；3) 已执行 mcp_start()")
    s = status.get("status", "unknown")
    msg = status.get("message", "")
    if s != "running":
        return f"⚠️ 插件已加载但未运行（status={s}）。请在 Abaqus 命令行执行 mcp_start()"
    result = _send_command("ping", timeout=10.0)
    if result.get("success"):
        ver = result.get("data", {}).get("version", "?")
        return f"✅ 已连接 Abaqus MCP v{ver} | {msg}"
    return f"⚠️ 插件未响应 ping：{result}"


def ping() -> str:
    """连通性测试。"""
    result = _send_command("ping", timeout=10.0)
    if result.get("success"):
        return "pong"
    return f"❌ {result.get('error')}"


def execute_script(script: str) -> str:
    """在 Abaqus 内核中执行 Python 脚本（可操作 mdb / session：建模、网格、求解等）。"""
    result = _send_command("execute_script", script=script)
    if result.get("success"):
        out = result.get("output", "")
        return f"✅ 脚本执行成功\n输出:\n{out}" if out else "✅ 脚本执行成功（无输出）"
    return (f"❌ 脚本执行失败\n错误: {result.get('error')}\n"
            f"{result.get('traceback', '')}")


def get_model_info() -> str:
    """获取所有模型信息：零件、材料、分析步、载荷、边界条件等。"""
    result = _send_command("get_model_info")
    if result.get("success"):
        return json.dumps(result.get("data", {}), indent=2, ensure_ascii=False)
    return f"❌ {result.get('error')}"


def list_jobs() -> str:
    """列出所有已定义的分析作业及状态。"""
    result = _send_command("list_jobs")
    if result.get("success"):
        return json.dumps(result.get("data", {}), indent=2, ensure_ascii=False)
    return f"❌ {result.get('error')}"


def submit_job(job_name: str) -> str:
    """按名称提交分析作业并等待完成（最长 600s）。"""
    result = _send_command("submit_job", timeout=600.0, job_name=job_name)
    if result.get("success"):
        return json.dumps(result.get("data", {}), indent=2, ensure_ascii=False)
    return f"❌ {result.get('error')}"


def get_odb_info(odb_path: str) -> str:
    """只读打开 ODB 结果文件，返回分析步/帧/部件等元数据。"""
    result = _send_command("get_odb_info", timeout=60.0, odb_path=odb_path)
    if result.get("success"):
        return json.dumps(result.get("data", {}), indent=2, ensure_ascii=False)
    return f"❌ {result.get('error')}"


def get_viewport_image(viewport_name: str = "", image_format: str = "PNG",
                       save_path: str = "") -> str:
    """截取 Abaqus 视口图像。

    save_path 非空时：把 base64 解码保存为图片文件，返回文件路径（推荐，省 tokens）；
    为空时：返回 base64 data URI。
    """
    kwargs = {"format": image_format.upper()}
    if viewport_name:
        kwargs["viewport_name"] = viewport_name
    result = _send_command("get_viewport_image", timeout=30.0, **kwargs)
    if not result.get("success"):
        return f"❌ {result.get('error')}"
    data = result.get("data", {})
    if not (isinstance(data, dict) and data.get("success")):
        return json.dumps(data, indent=2, ensure_ascii=False)
    b64 = data.get("image_base64", "")
    fmt = data.get("format", "png").lower()
    if save_path:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(base64.b64decode(b64))
            return f"✅ 视口截图已保存: {save_path}"
        except Exception as e:
            return f"⚠️ 截图已获取但保存失败: {e}"
    return f"data:image/{fmt};base64,{b64}"


# ==================== OpenAI Function Calling 工具定义（JSON Schema） ====================

ABAQUS_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_connection",
            "description": "检查 Abaqus/CAE 是否在运行、插件是否已加载并响应。开始任何工作前先调用一次。",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_script",
            "description": "在 Abaqus/CAE 内核中执行 Python 脚本。脚本可操作 mdb（模型数据库）和 session（会话），"
                           "用于建模、赋材料、装配、网格划分、设置分析步、提交作业等。"
                           "示例：m=mdb.Model(name='M-1'); print(mdb.models.keys())",
            "parameters": {
                "type": "object",
                "properties": {
                    "script": {"type": "string", "description": "要执行的 Abaqus Python 脚本源码"}
                },
                "required": ["script"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_model_info",
            "description": "获取当前 Abaqus 会话中所有模型的信息：零件、材料、分析步、载荷、边界条件、相互作用、装配实例",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_jobs",
            "description": "列出当前会话中定义的所有分析作业及其状态",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "submit_job",
            "description": "按名称提交分析作业并等待完成（最长 600 秒）",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_name": {"type": "string", "description": "作业名称（需已存在于 mdb.jobs）"}
                },
                "required": ["job_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_odb_info",
            "description": "以只读方式打开 ODB 结果文件并返回元数据：分析步、帧、部件、实例等",
            "parameters": {
                "type": "object",
                "properties": {
                    "odb_path": {"type": "string", "description": ".odb 文件完整路径"}
                },
                "required": ["odb_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_viewport_image",
            "description": "截取 Abaqus 视口图像。save_path 提供时保存为图片文件并返回路径，否则返回 base64 编码",
            "parameters": {
                "type": "object",
                "properties": {
                    "viewport_name": {"type": "string", "description": "视口名称，留空使用当前视口", "default": ""},
                    "image_format": {"type": "string", "description": "图片格式 PNG/SVG/TIFF", "default": "PNG"},
                    "save_path": {"type": "string", "description": "保存图片的文件路径（可选，推荐填写以节省 tokens）", "default": ""}
                },
                "required": []
            }
        }
    },
]


def route_abaqus_tool(func_name: str, args: dict) -> str:
    """把大模型发出的工具调用路由到具体实现（统一返回字符串）。"""
    if func_name == "check_connection":
        return check_connection()
    elif func_name == "ping":
        return ping()
    elif func_name == "execute_script":
        return execute_script(args.get("script", ""))
    elif func_name == "get_model_info":
        return get_model_info()
    elif func_name == "list_jobs":
        return list_jobs()
    elif func_name == "submit_job":
        return submit_job(args.get("job_name", ""))
    elif func_name == "get_odb_info":
        return get_odb_info(args.get("odb_path", ""))
    elif func_name == "get_viewport_image":
        return get_viewport_image(
            args.get("viewport_name", ""),
            args.get("image_format", "PNG"),
            args.get("save_path", ""),
        )
    return f"❌ 未知的 Abaqus 工具: {func_name}"


if __name__ == "__main__":
    print(f"MCP_HOME = {MCP_HOME}")
    print(check_connection())
