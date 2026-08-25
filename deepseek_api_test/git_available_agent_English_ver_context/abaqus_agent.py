# -*- coding: utf-8 -*-
"""
abaqus_agent.py — 自然语言驱动的 Abaqus/CAE 仿真 Agent
========================================================

基于 DeepSeek API + abaqus_bridge.py（文件 IPC 桥接），
让用户在 PowerShell 终端用自然语言完成 Abaqus 仿真全流程：
建模 → 赋材料 → 装配 → 网格 → 分析步 → 载荷/边界 → 提交作业 → 查看 ODB → 截取视口。

前提条件（Abaqus 侧）：
    1. Abaqus/CAE 已启动
    2. 已加载 abaqus_mcp_plugin.py（File → Run Script... 或 abaqus_v6.env 自动加载）
    3. 已在 Abaqus 命令行执行 mcp_start()（状态为 running）
"""

import sys
import json
import os
from pathlib import Path
from openai import OpenAI

# 桥接模块：封装了"写命令文件 → 等结果文件"的 IPC，并提供 OpenAI Function Calling 工具定义
from abaqus_bridge import (
    ABAQUS_TOOLS,
    route_abaqus_tool,
    check_connection,
    ping,
    get_model_info,
    execute_script,
    list_jobs,
    submit_job,
    get_odb_info,
    get_viewport_image,
    MCP_HOME,
)

sys.stdout.reconfigure(encoding='utf-8')

# ==================== 终端配色 ====================
YELLOW = "\033[93m"
CYAN = "\033[96m"
GREEN = "\033[92m"
DARK_GRAY = "\033[90m"
MAGENTA = "\033[95m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

# ==================== API 配置 ====================
API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not API_KEY:
    API_KEY = input("🔑 Please enter DeepSeek API Key: ").strip()
    if not API_KEY:
        print(f"{RED}❌ API Key cannot be empty{RESET}")
        exit(1)

client = OpenAI(
    api_key=API_KEY,
    base_url="https://api.deepseek.com"
)

# ==================== 系统提示词 ====================

SYSTEM_PROMPT = f"""你是一位精通 Abaqus/CAE 的仿真工程师助手，通过调用工具在用户的 Abaqus 会话中执行仿真任务。
你可以执行建模、材料赋值、装配、网格划分、设置分析步、施加载荷与边界条件、提交作业、读取 ODB 结果、截取视口图像。

[工作目录 / IPC 信息]
- 桥接模块 MCP_HOME: {MCP_HOME}
- Abaqus 插件会轮询 {MCP_HOME}/commands/ 目录下的命令文件并写回结果，你无需关心细节。

[可用工具]
1. check_connection — 检查 Abaqus 是否运行、插件是否已启动。**每次任务开始前必须首先调用一次**。
2. execute_script — 在 Abaqus 内核执行 Python 脚本。脚本可访问 mdb（模型数据库）和 session（会话）。
   - 示例：m=mdb.Model(name='M-1'); p=m.Part(name='P-1', dimensionality=THREE_D, type=DEFORMABLE_BODY); ...
   - 用 print() 输出信息，输出会被返回给你。
   - 脚本开始时建议先 os.chdir() 到工作目录，确保作业文件/ODB 输出到预期位置。
3. get_model_info — 查询当前会话所有模型：部件、材料、分析步、载荷、边界条件、相互作用、装配实例。
4. list_jobs — 列出已定义的分析作业及状态。
5. submit_job — 按名称提交作业并等待完成（最长 600 秒）。作业必须先存在于 mdb.jobs。
6. get_odb_info — 只读打开 .odb 结果文件，返回分析步/帧/部件/实例等元数据。
7. get_viewport_image — 截取视口图像。**建议始终提供 save_path 保存为图片文件（省 tokens），再告知用户图片路径**。
8. ping — 连通性测试。

[标准仿真工作流（务必按此顺序）]
1. check_connection()：确认 Abaqus 在线。若失败，告诉用户如何启动（启动 Abaqus/CAE → 加载插件 → 执行 mcp_start()），不要继续。
2. get_model_info()：了解当前会话状态（已有模型？空会话？）。
3. execute_script()：分步构建模型（Part → Material/Section → Assembly → Step → Load/BC → Mesh → Job）。
   建议每完成一个逻辑阶段就 print 关键信息，便于你确认后再进行下一步。
4. list_jobs() / submit_job(job_name)：提交并等待求解完成。
5. get_odb_info(odb_path)：验证结果（帧数、总时间等）。
6. get_viewport_image(save_path=...)：截取变形/应力云图，把图片文件路径告诉用户。
7. 用中文汇总：模型参数、材料、载荷、边界、网格数量、求解状态、结果要点、图片位置。

[重要规则]
- 思考过程用中文。
- 每次 execute_script 只做一件事的脚本要谨慎：若脚本较大，建议拆成多步，逐步确认。
- Abaqus 脚本里需要 import 的模块（如 part, material, assembly, step, load, mesh, job）在 Abaqus 内核已自动可用，无需 import。
- 数值单位由用户语境决定（通常 mm/N/s 制），建模前若不确定可先询问或按常见默认。
- 若工具返回错误（超时、异常），把错误原样转述给用户并给出排查建议（如确认 Abaqus 内已执行 mcp_start()）。
- 全部完成后，用清晰的 Markdown 结构输出最终仿真报告。
"""

chat_history = [
    {"role": "system", "content": SYSTEM_PROMPT}
]

# ==================== 上下文用量跟踪 ====================
CONTEXT_WINDOW = 1000000  # DeepSeek V4 Flash 1M 上下文
last_usage = None


def display_context_usage():
    if last_usage and last_usage.get('prompt_tokens'):
        prompt_tokens = last_usage['prompt_tokens']
        percentage = min(prompt_tokens / CONTEXT_WINDOW * 100, 100.0)
        bar_length = 20
        filled = int(percentage / 100 * bar_length)
        bar = '█' * filled + '░' * (bar_length - filled)
        if percentage < 50:
            color = GREEN
        elif percentage < 80:
            color = YELLOW
        else:
            color = RED
        print(f"{color}📊 Context usage: {percentage:.1f}% [{bar}] ({prompt_tokens:,}/{CONTEXT_WINDOW:,} tokens){RESET}")
    else:
        print(f"{DARK_GRAY}📊 Context usage: 0.0% (no conversation yet){RESET}")

# ==================== 工具执行器 ====================
# 直接复用 abaqus_bridge 的路由分发（它已实现 Function Calling → 具体函数的映射）

def execute_tool(func_name: str, args: dict) -> str:
    print(f"\n{MAGENTA}🔧 Executing Abaqus tool: {func_name}{RESET}")
    if args:
        print(f"{DARK_GRAY}Parameters: {json.dumps(args, ensure_ascii=False, indent=2)}{RESET}")
    try:
        return route_abaqus_tool(func_name, args)
    except Exception as e:
        return f"❌ 工具执行异常: {e}"

# 工具列表：abaqus_bridge 内置的 7 个 + 额外补充 ping
agent_tools = list(ABAQUS_TOOLS)
agent_tools.append({
    "type": "function",
    "function": {
        "name": "ping",
        "description": "向 Abaqus 插件发送 ping 进行连通性测试",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }
})

# ==================== 主循环 ====================

print(f"""
{BOLD}{GREEN}══════════════════════════════════════════════════════════════{RESET}
{BOLD}{GREEN}   ⚙️  Abaqus Simulation Agent (DeepSeek 驱动, 自然语言仿真){RESET}
{BOLD}{YELLOW}   📁 MCP_HOME: {MCP_HOME}{RESET}
{BOLD}{GREEN}══════════════════════════════════════════════════════════════{RESET}

{BOLD}{CYAN}📘 示例指令（自然语言）{RESET}
  "检查一下 Abaqus 是否在线"
  "帮我建一个 100×20×5 mm 的悬臂梁，一端固定，另一端施加 1000N 的力，材料用钢"
  "给上面的模型划分网格，单元尺寸 5mm"
  "提交分析作业并等待完成"
  "打开 ODB 结果，看看最大应力是多少"
  "截取当前视口图像，保存到 abaqus_results/vonmises.png"

{BOLD}{MAGENTA}⚙️  控制{RESET}
  🚪 exit   → 退出    🧹 clear → 清空对话历史

{BOLD}{DARK_GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}
""")

# 启动时自动做一次连通性自检
print(f"{DARK_GRAY}⏳ 正在自检 Abaqus 连接...{RESET}")
print(check_connection())
print()

while True:
    display_context_usage()
    try:
        user_input = input(f"\n{YELLOW}👤 You{RESET}\n> ")
    except (KeyboardInterrupt, EOFError):
        print(f"\n{YELLOW}👋 Goodbye!{RESET}")
        break

    if user_input.strip().lower() == 'exit':
        print(f"{YELLOW}👋 Goodbye!{RESET}")
        break

    if user_input.strip().lower() == 'clear':
        chat_history = [chat_history[0]]
        last_usage = None
        print(f"{GREEN}🧹 Chat history cleared{RESET}")
        continue

    chat_history.append({"role": "user", "content": user_input})

    # ==================== 工具调用循环 ====================
    while True:
        print(f"{DARK_GRAY}⏳ AI is thinking... (Press Ctrl+C to stop){RESET}")
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=chat_history,
                tools=agent_tools,
                stream=False,
                extra_body={
                    "thinking": {"type": "enabled"},
                    "reasoning_effort": "high"
                }
            )

            if response.usage:
                last_usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }

            message = response.choices[0].message

            # 显示推理过程
            ai_thinking = getattr(message, 'reasoning_content', None)
            if ai_thinking is None and hasattr(message, 'model_extra') and message.model_extra:
                ai_thinking = message.model_extra.get('reasoning_content', "")
            if ai_thinking:
                print(f"\n{CYAN}💭 AI Reasoning Process:{RESET}")
                print(f"{CYAN}{ai_thinking}{RESET}")

            chat_history.append(message)

            # ==================== 处理工具调用 ====================
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    func_name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)

                    result = execute_tool(func_name, args)

                    result_preview = result[:800] + ("..." if len(result) > 800 else "")
                    print(f"{GREEN}📊 Tool Result:{RESET}")
                    print(f"{GREEN}{result_preview}{RESET}")

                    chat_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": func_name,
                        "content": result
                    })
                continue  # 继续循环，让 AI 根据结果决定下一步

            # ==================== 显示最终回复 ====================
            else:
                ai_text = message.content or ""
                print(f"\n{GREEN}🤖 AI Response:{RESET}")
                print(f"{GREEN}{ai_text}{RESET}")
                break

        except KeyboardInterrupt:
            print(f"\n{YELLOW}⏹️  Stopped AI thinking, starting a new conversation turn{RESET}")
            if chat_history and chat_history[-1]["role"] == "user":
                chat_history.pop()
            break

        except Exception as e:
            print(f"\n{RED}❌ Error: {e}{RESET}")
            break
