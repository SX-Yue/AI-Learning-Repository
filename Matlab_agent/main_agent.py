# -*- coding: utf-8 -*-
"""
main_agent.py — 统一 AI Agent (Git + 文件系统 + MATLAB)
========================================================

基于 DeepSeek API，支持：
1. 文件读写、替换、列表
2. Git 完整工作流 (commit, push, pull, branch, stash, etc.)
3. GitHub SSH 配置与连接测试
4. MATLAB MCP Server 集成（执行代码、获取变量）
5. 上下文占用实时监控
6. PowerShell 命令执行（需确认）
"""

import sys
import json
import os
import subprocess
import threading
import time
import queue
from pathlib import Path
from openai import OpenAI

# ==================== 导入 Git + 文件系统工具 ====================
from agent_tools import (
    read_file, write_file, replace_in_file, list_files, execute_powershell,
    git_auto_workflow, git_status, git_add, git_commit, git_push,
    git_pull, git_log, git_branch, git_checkout, git_diff,
    git_clone, git_stash, git_stash_pop, git_reset,
    setup_github_ssh, test_github_connection, configure_git_user,
    agent_tools as git_tools, is_git_tool, GIT_REPO_PATH, parse_replace_request
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

# ==================== 配置区域 ====================

# ----- Git 配置 -----
DEFAULT_GIT_PATH = os.environ.get("GIT_REPO_PATH", str(Path.cwd().resolve()))

# ----- MATLAB MCP Server 配置 -----
# 使用官方 Agentic Toolkit 安装的 MCP Server（v0.12.0）
MATLAB_MCP_EXE = r"C:\Users\18801\.matlab\agentic-toolkits\bin\matlab-mcp-server.exe"
# MATLAB 根目录
MATLAB_ROOT = r"D:\Program Files\MATLAB\R2024b"

# ==================== API 配置 ====================
print(f"{CYAN}🔑 请输入 DeepSeek API Key（每次启动都需要输入）{RESET}")
API_KEY = input("API Key: ").strip()
while not API_KEY:
    print(f"{RED}❌ API Key cannot be empty. Please try again.{RESET}")
    API_KEY = input("API Key: ").strip()

client = OpenAI(
    api_key=API_KEY,
    base_url="https://api.deepseek.com"
)

# ==================== MATLAB 工作目录询问 ====================
print(f"\n{CYAN}📁 请指定 MATLAB 工作目录（脚本和文件将保存在此目录）{RESET}")
print(f"{DARK_GRAY}提示：直接按 Enter 将使用当前目录: {os.getcwd()}{RESET}")
matlab_work_dir_input = input("工作目录路径: ").strip()
if matlab_work_dir_input:
    MATLAB_WORK_DIR = matlab_work_dir_input
else:
    MATLAB_WORK_DIR = os.getcwd()

os.makedirs(MATLAB_WORK_DIR, exist_ok=True)
print(f"{GREEN}✅ MATLAB 工作目录设置为: {MATLAB_WORK_DIR}{RESET}\n")

# ==================== MATLAB MCP 客户端 ====================

class MCPMatlabClient:
    """通过 stdio 与 MATLAB MCP Server 通信的客户端。"""
    
    def __init__(self, exe_path: str, matlab_root: str = None, work_dir: str = None):
        self.exe_path = exe_path
        self.matlab_root = matlab_root
        self.work_dir = work_dir or os.getcwd()
        self.process = None
        self.request_id = 0
        self.pending_requests = {}
        self.receiver_thread = None
        self.running = False
        self.stderr_buffer = []
        self._initialized = False
        
    def start(self):
        """启动 MATLAB MCP Server 子进程并完成 MCP 握手。"""
        if not os.path.exists(self.exe_path):
            raise FileNotFoundError(f"MATLAB MCP exe not found: {self.exe_path}")
        
        args = [self.exe_path]
        
        # v0.12.0 自动检测 MATLAB 路径，但手动指定更可靠
        if self.matlab_root:
            args.extend(["--matlab-root", self.matlab_root])
        
        if self.work_dir:
            args.extend(["--initial-working-folder", self.work_dir])
        
        args.extend(["--matlab-display-mode", "desktop"])
        args.extend(["--matlab-session-mode", "new"])
        
        print(f"{DARK_GRAY}🚀 启动 MATLAB MCP Server: {' '.join(args)}{RESET}")
        
        self.process = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            encoding='utf-8',
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        self.running = True
        self.pending_requests = {}
        
        # 启动 stderr 读取线程
        self.stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self.stderr_thread.start()
        
        self.receiver_thread = threading.Thread(target=self._receiver_loop, daemon=True)
        self.receiver_thread.start()
        
        # 等待进程启动
        print(f"{DARK_GRAY}⏳ 等待 MATLAB 启动（可能需要 10-20 秒）...{RESET}")
        time.sleep(8)
        
        # 检查进程是否还在运行
        if self.process.poll() is not None:
            stdout, stderr = self.process.communicate(timeout=1)
            error_msg = f"进程已退出 (代码: {self.process.returncode})\n"
            if stderr:
                error_msg += f"错误输出: {stderr}"
            if self.stderr_buffer:
                error_msg += f"\n缓冲区错误: {''.join(self.stderr_buffer)}"
            raise RuntimeError(error_msg)

        # ========== MCP 握手（新版服务器必需） ==========
        # 步骤 1: 发送 initialize 请求
        print(f"{DARK_GRAY}⏳ 发送 MCP initialize 请求...{RESET}")
        init_result = self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "my-matlab-agent", "version": "1.0"},
        }, timeout=120)
        
        if not init_result.get('success'):
            raise RuntimeError(f"MCP initialize 失败: {init_result.get('error')}")
        
        # 步骤 2: 发送 initialized 通知
        print(f"{DARK_GRAY}⏳ 发送 MCP initialized 通知...{RESET}")
        self._notify("notifications/initialized", {})
        
        self._initialized = True
        print(f"{GREEN}✅ MATLAB MCP Server 已启动并完成握手{RESET}")
        
    def _read_stderr(self):
        """读取 stderr 用于调试。"""
        while self.running and self.process and self.process.stderr:
            try:
                line = self.process.stderr.readline()
                if not line:
                    break
                self.stderr_buffer.append(line)
                if "Error" in line or "error" in line:
                    print(f"{YELLOW}⚠️ MCP Server 警告: {line.strip()}{RESET}")
            except Exception:
                break

    def _notify(self, method: str, params: dict = None):
        """发送 MCP 通知（无需响应）。"""
        if not self.process or not self.process.stdin:
            return
        msg = json.dumps({"jsonrpc": "2.0", "method": method, "params": params or {}}) + "\n"
        try:
            self.process.stdin.write(msg)
            self.process.stdin.flush()
        except BrokenPipeError:
            pass

    def _receiver_loop(self):
        """持续接收 MCP Server 的响应。"""
        while self.running:
            try:
                if not self.process or not self.process.stdout:
                    break
                line = self.process.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    self._handle_message(msg)
                except json.JSONDecodeError:
                    if line:
                        print(f"{DARK_GRAY}📝 MCP 输出: {line}{RESET}")
            except Exception as e:
                if self.running:
                    print(f"{RED}❌ 接收循环错误: {e}{RESET}")
                break
                
    def _handle_message(self, msg: dict):
        """处理收到的 MCP 消息。"""
        if isinstance(msg, dict):
            req_id = msg.get("id")
            if req_id is not None and req_id in self.pending_requests:
                self.pending_requests[req_id].put(msg)

    def _send_request(self, method: str, params: dict = None, timeout: float = 120.0) -> dict:
        """发送 MCP 请求并等待响应。"""
        self.request_id += 1
        req_id = str(self.request_id)
        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {}
        }
        
        q = queue.Queue()
        self.pending_requests[req_id] = q
        
        msg = json.dumps(request) + "\n"
        try:
            self.process.stdin.write(msg)
            self.process.stdin.flush()
        except (BrokenPipeError, AttributeError) as e:
            return {"success": False, "error": f"MCP Server 连接已断开: {e}"}
        
        try:
            response = q.get(timeout=timeout)
            self.pending_requests.pop(req_id, None)
            if response.get("error"):
                return {"success": False, "error": response["error"]}
            if response.get("result") is None:
                return {"success": False, "error": "MCP Server 返回空结果"}
            return {"success": True, "result": response.get("result")}
        except queue.Empty:
            self.pending_requests.pop(req_id, None)
            return {"success": False, "error": f"请求超时 ({timeout}s)"}
    
    def _call_tool(self, tool_name: str, arguments: dict, timeout: float = 120.0) -> dict:
        """调用 MCP 工具（统一入口）。"""
        return self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        }, timeout)
    
    def execute_code(self, code: str, timeout: float = 120.0) -> dict:
        """在 MATLAB 中执行代码（使用 evaluate_matlab_code 工具）。"""
        return self._call_tool("evaluate_matlab_code", {"code": code}, timeout)

    def run_file(self, filepath: str, timeout: float = 120.0) -> dict:
        """运行 MATLAB 文件（使用 run_matlab_file 工具）。"""
        return self._call_tool("run_matlab_file", {"file": filepath}, timeout)
    
    def list_toolboxes(self, timeout: float = 120.0) -> dict:
        """列出已安装的工具箱（使用 detect_matlab_toolboxes 工具）。"""
        return self._call_tool("detect_matlab_toolboxes", {}, timeout)
    
    def get_variable(self, name: str) -> dict:
        """获取 MATLAB 工作区中的变量值。"""
        # 使用 evaluate_matlab_code 来获取变量
        code = f"""
try
    val = evalin('base', '{name}');
    if isobject(val) || isstruct(val) || iscell(val)
        disp(jsonencode(val));
    else
        disp(val);
    end
catch ME
    fprintf('ERROR: %s\\n', ME.message);
end
"""
        return self.execute_code(code)
    
    def list_variables(self) -> dict:
        """列出 MATLAB 工作区中的所有变量。"""
        return self.execute_code("disp(whos)")
    
    def close(self):
        """关闭 MCP Server。"""
        self.running = False
        if self.process:
            try:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=2)
            except Exception:
                pass
            self.process = None
        print(f"{DARK_GRAY}🔴 MATLAB MCP Server 已关闭{RESET}")

# ==================== 系统提示词 ====================
SYSTEM_PROMPT = f"""You are a powerful unified engineering assistant with file system, Git, and MATLAB capabilities.

[Repository Information]
- Git Repository Path: {GIT_REPO_PATH}
- MATLAB Working Directory: {MATLAB_WORK_DIR}

[Available Tools]

1. **File Operations**:
   - read_file, write_file (requires confirmation), replace_in_file (requires confirmation), list_files

2. **Git Operations** (automatic, no confirmation):
   - git_auto_workflow, git_status, git_add, git_commit, git_push, git_pull, git_log, git_branch, git_checkout, git_diff, git_clone, git_stash, git_stash_pop, git_reset

3. **MATLAB Operations** (via MCP Server):
   - matlab_execute_code: Execute MATLAB code and return output
   - matlab_get_variable: Get variable value from MATLAB workspace
   - matlab_list_variables: List all variables in MATLAB workspace

4. **System**:
   - execute_powershell (requires confirmation)
   - show_config: Display current configuration

[Important Rules]
- Think in English by default, answer in English by default
- Git operations: executed automatically, no confirmation needed
- File writes/modifications: require user confirmation
- PowerShell commands: require user confirmation
- MATLAB: Server starts automatically when first MATLAB tool is called
- All MATLAB files and outputs will be saved to: {MATLAB_WORK_DIR}
- Always inform the user what you are doing
- Use dedicated tools; avoid execute_powershell if possible
"""

chat_history = [
    {"role": "system", "content": SYSTEM_PROMPT}
]

# ==================== 上下文用量跟踪 ====================
CONTEXT_WINDOW = 1000000
last_usage = None

def display_context_usage():
    """显示当前上下文使用情况。"""
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

def show_config():
    """显示当前配置信息。"""
    masked_key = "***" + API_KEY[-4:] if len(API_KEY) > 4 else "***"
    return f"""
📁 Git Repository: {GIT_REPO_PATH}
📁 MATLAB Work Dir: {MATLAB_WORK_DIR}
🔑 API Key: {masked_key}
📊 Context window: {CONTEXT_WINDOW:,} tokens
🔧 Git Tools: {len(git_tools)}
📦 MATLAB MCP: {MATLAB_MCP_EXE}
📦 MATLAB Root: {MATLAB_ROOT}
"""

# ==================== MATLAB 客户端管理 ====================
matlab_client = None

def get_matlab_client():
    """获取或创建 MATLAB 客户端（懒加载）。"""
    global matlab_client
    
    if matlab_client is None:
        print(f"{DARK_GRAY}⏳ 正在启动 MATLAB MCP Server...{RESET}")
        print(f"{YELLOW}💡 注意：将启动新的 MATLAB 桌面实例，请稍候...{RESET}")
        
        matlab_client = MCPMatlabClient(
            exe_path=MATLAB_MCP_EXE,
            matlab_root=MATLAB_ROOT,
            work_dir=MATLAB_WORK_DIR
        )
        
        try:
            matlab_client.start()
            
            # 验证连接：列出可用工具
            print(f"{DARK_GRAY}⏳ 验证 MCP Server 连接...{RESET}")
            tools_result = matlab_client._send_request("tools/list", {}, timeout=30.0)
            if tools_result.get('success'):
                tools = tools_result.get('result', {}).get('tools', [])
                tool_names = [t.get('name') for t in tools]
                print(f"{GREEN}✅ MCP Server 连接验证成功，可用工具: {', '.join(tool_names[:5])}{'...' if len(tool_names) > 5 else ''}{RESET}")
            else:
                print(f"{YELLOW}⚠️ MCP Server 响应异常: {tools_result.get('error')}{RESET}")
                
        except Exception as e:
            print(f"{RED}❌ 启动 MATLAB MCP Server 失败: {e}{RESET}")
            print(f"{YELLOW}💡 诊断建议：{RESET}")
            print(f"  1. 检查 MCP Server 路径: {MATLAB_MCP_EXE}")
            print(f"  2. 检查 MATLAB 安装路径: {MATLAB_ROOT}")
            print(f"  3. 尝试手动运行: {MATLAB_MCP_EXE} --matlab-root \"{MATLAB_ROOT}\" --matlab-session-mode new")
            matlab_client = None
            return None
    
    # 检查客户端是否还活着
    if matlab_client and matlab_client.process:
        if matlab_client.process.poll() is not None:
            print(f"{YELLOW}⚠️ MCP Server 已断开，重新连接...{RESET}")
            matlab_client.close()
            matlab_client = None
            return get_matlab_client()
    
    return matlab_client

# ==================== MATLAB 工具函数 ====================

def _extract_text_from_result(result: dict) -> str:
    """从 MCP tools/call 结果中提取文本内容。"""
    content = (result or {}).get("content", []) or []
    return "".join(c.get("text", "") for c in content if c.get("type") == "text")

def matlab_execute_code(code: str) -> str:
    """在 MATLAB 中执行代码。"""
    client = get_matlab_client()
    if client is None:
        return "❌ MATLAB MCP Server 未启动"

    print(f"{DARK_GRAY}📤 发送代码到 MATLAB...{RESET}")
    result = client.execute_code(code)

    if result.get('success'):
        res = result.get('result', {})
        text = _extract_text_from_result(res)
        if res.get('isError'):
            return f"❌ MATLAB 执行错误:\n{text.strip()}"
        return f"✅ MATLAB 执行成功\n{text.strip()}" if text.strip() else "✅ MATLAB 执行成功（无输出）"

    return f"❌ MATLAB 执行失败: {result.get('error')}"

def matlab_get_variable(name: str) -> str:
    """获取 MATLAB 变量值。"""
    client = get_matlab_client()
    if client is None:
        return "❌ MATLAB MCP Server 未启动"
    result = client.get_variable(name)
    if result.get('success'):
        text = _extract_text_from_result(result.get('result', {}))
        if "ERROR:" in text:
            return f"❌ 变量 '{name}' 不存在或无法读取"
        return f"✅ 变量 {name}:\n{text.strip()}" if text.strip() else f"✅ 变量 {name} 为空"
    return f"❌ 获取变量失败: {result.get('error')}"

def matlab_list_variables() -> str:
    """列出 MATLAB 所有变量。"""
    client = get_matlab_client()
    if client is None:
        return "❌ MATLAB MCP Server 未启动"
    result = client.list_variables()
    if result.get('success'):
        text = _extract_text_from_result(result.get('result', {}))
        return f"✅ 工作区变量:\n{text.strip()}" if text.strip() else "✅ 工作区为空"
    return f"❌ 列出变量失败: {result.get('error')}"

# ==================== 工具列表构建 ====================

# 基础工具
agent_tools = list(git_tools)

# 添加 MATLAB 工具
agent_tools.extend([
    {
        "type": "function",
        "function": {
            "name": "matlab_execute_code",
            "description": "Execute MATLAB code and return the output. Variables persist in MATLAB workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "MATLAB code to execute"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "matlab_get_variable",
            "description": "Get the value of a variable from MATLAB workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Variable name"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "matlab_list_variables",
            "description": "List all variables currently in MATLAB workspace.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    }
])

# ==================== 工具执行器 ====================

def execute_tool(func_name: str, args: dict) -> str:
    """统一工具执行入口。"""
    print(f"\n{MAGENTA}🔧 Executing tool: {func_name}{RESET}")
    
    if args:
        print(f"{DARK_GRAY}Parameters: {json.dumps(args, ensure_ascii=False, indent=2)}{RESET}")
    
    # ==================== 文件系统工具 ====================
    if func_name == "read_file":
        return read_file(args.get("filepath"))
        
    elif func_name == "write_file":
        filepath = args.get("filepath")
        content = args.get("content")
        print(f"\n{YELLOW}⚠️  Confirmation required: Write to file{RESET}")
        print(f"📄 File: {filepath}")
        print(f"📝 Content preview: {content[:200]}...")
        confirm = input(f"{YELLOW}Allow this operation? (y/n): {RESET}").strip().lower()
        if confirm == 'y':
            return write_file(filepath, content)
        return "❌ Operation cancelled"
            
    elif func_name == "replace_in_file":
        filepath = args.get("filepath")
        old_text = args.get("old_text")
        new_text = args.get("new_text")
        print(f"\n{YELLOW}⚠️  Confirmation required: Modify file{RESET}")
        print(f"📄 File: {filepath}")
        print(f"  Old: {old_text[:100]}{'...' if len(old_text) > 100 else ''}")
        print(f"  New: {new_text[:100]}{'...' if len(new_text) > 100 else ''}")
        confirm = input(f"{YELLOW}Allow this operation? (y/n): {RESET}").strip().lower()
        if confirm == 'y':
            return replace_in_file(filepath, old_text, new_text)
        return "❌ Operation cancelled"
            
    elif func_name == "list_files":
        return list_files(args.get("directory", "."))
        
    elif func_name == "execute_powershell":
        command = args.get("command")
        timeout = args.get("timeout", 30)
        print(f"\n{YELLOW}⚠️  Confirmation required: Execute PowerShell{RESET}")
        print(f"💻 Command: {command}")
        confirm = input(f"{YELLOW}Allow this operation? (y/n): {RESET}").strip().lower()
        if confirm == 'y':
            return execute_powershell(command, timeout)
        return "❌ Operation cancelled"
    
    # ==================== Git 工具 ====================
    elif func_name == "git_auto_workflow":
        return git_auto_workflow(args.get("message", "Update code"), args.get("files", "."), args.get("push", True))
    elif func_name == "git_status":
        return git_status()
    elif func_name == "git_add":
        return git_add(args.get("files", "."))
    elif func_name == "git_commit":
        return git_commit(args.get("message"))
    elif func_name == "git_push":
        return git_push(args.get("remote", "origin"), args.get("branch", ""))
    elif func_name == "git_pull":
        return git_pull(args.get("remote", "origin"), args.get("branch", ""))
    elif func_name == "git_log":
        return git_log(args.get("count", 10))
    elif func_name == "git_branch":
        return git_branch()
    elif func_name == "git_checkout":
        return git_checkout(args.get("branch"))
    elif func_name == "git_diff":
        return git_diff(args.get("staged", False))
    elif func_name == "git_clone":
        return git_clone(args.get("repo_url"), args.get("target_dir", ""))
    elif func_name == "git_stash":
        return git_stash()
    elif func_name == "git_stash_pop":
        return git_stash_pop()
    elif func_name == "git_reset":
        return git_reset(args.get("mode", "mixed"), args.get("target", "HEAD"))
    elif func_name == "setup_github_ssh":
        return setup_github_ssh()
    elif func_name == "test_github_connection":
        return test_github_connection()
    elif func_name == "configure_git_user":
        return configure_git_user(args.get("name", ""), args.get("email", ""))
    
    # ==================== MATLAB 工具 ====================
    elif func_name == "matlab_execute_code":
        return matlab_execute_code(args.get("code", ""))
    elif func_name == "matlab_get_variable":
        return matlab_get_variable(args.get("name", ""))
    elif func_name == "matlab_list_variables":
        return matlab_list_variables()
    
    # ==================== 系统工具 ====================
    elif func_name == "show_config":
        return show_config()
    
    else:
        return f"❌ Error: Unknown tool {func_name}"

# ==================== 主循环 ====================

print(f"""
{BOLD}{GREEN}══════════════════════════════════════════════════════════════{RESET}
{BOLD}{GREEN}   🚀 Engineering Agent (Git + 文件系统 + MATLAB){RESET}
{BOLD}{YELLOW}   📁 Git Repo: {GIT_REPO_PATH}{RESET}
{BOLD}{YELLOW}   📁 MATLAB Work Dir: {MATLAB_WORK_DIR}{RESET}
{BOLD}{YELLOW}   📦 MATLAB MCP: {MATLAB_MCP_EXE}{RESET}
{BOLD}{GREEN}══════════════════════════════════════════════════════════════{RESET}

{BOLD}{CYAN}📘 FILE & GIT OPERATIONS{RESET}
  📖 Read        →  "Read config.json"
  🔍 Replace     →  "Change v1.0 to v2.0 in README.md"
  💾 Commit      →  "Commit changes, message: fix bug"
  📊 Status      →  "Check Git status"

{BOLD}{CYAN}📦 MATLAB OPERATIONS{RESET}
  📝 Execute      →  "Run MATLAB: A = [1 2 3; 4 5 6; 7 8 9]; inv(A)"
  🔍 Get var     →  "Get MATLAB variable: A"
  📋 List vars   →  "List MATLAB workspace variables"

{BOLD}{MAGENTA}⚙️  CONTROLS{RESET}
  🚪 exit        →  Quit the agent
  🧹 clear       →  Clear conversation history
  🔍 config      →  Show current configuration

{BOLD}{DARK_GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}
""")

print(f"{DARK_GRAY}📋 当前配置:{RESET}")
print(show_config())
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

    if user_input.strip().lower() == 'config':
        print(show_config())
        continue

    chat_history.append({"role": "user", "content": user_input})

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
            
            ai_thinking = getattr(message, 'reasoning_content', None)
            if ai_thinking is None and hasattr(message, 'model_extra') and message.model_extra:
                ai_thinking = message.model_extra.get('reasoning_content', "")
            
            if ai_thinking:
                print(f"\n{CYAN}💭 AI Reasoning Process:{RESET}")
                print(f"{CYAN}{ai_thinking}{RESET}")

            chat_history.append(message)

            if message.tool_calls:
                for tool_call in message.tool_calls:
                    func_name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    
                    result = execute_tool(func_name, args)
                    
                    result_preview = result[:500] + ("..." if len(result) > 500 else "")
                    print(f"{GREEN}📊 Tool Result:{RESET}")
                    print(f"{GREEN}{result_preview}{RESET}")
                    
                    chat_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": func_name,
                        "content": result
                    })
                
                continue
                
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

# ==================== 清理 ====================
if matlab_client:
    matlab_client.close()