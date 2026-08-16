import sys
import json
import os
from pathlib import Path
from openai import OpenAI

# 导入所有工具
from agent_tools import (
    read_file, write_file, replace_in_file, list_files, execute_powershell,
    git_auto_workflow, git_status, git_add, git_commit, git_push,
    git_pull, git_log, git_branch, git_checkout, git_diff,
    git_clone, git_stash, git_stash_pop, git_reset,
    setup_github_ssh, test_github_connection, configure_git_user,
    agent_tools, is_git_tool, GIT_REPO_PATH, parse_replace_request
)

sys.stdout.reconfigure(encoding='utf-8')

# 颜色定义
YELLOW = "\033[93m"
CYAN = "\033[96m"
GREEN = "\033[92m"
DARK_GRAY = "\033[90m"
MAGENTA = "\033[95m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

# ==================== 配置 ====================

DEFAULT_GIT_PATH = os.environ.get("GIT_REPO_PATH", str(Path.cwd().resolve()))

# ==================== API 配置 ====================

# 从环境变量或配置文件读取 API Key
API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not API_KEY:
    API_KEY = input("🔑 请输入 DeepSeek API Key: ").strip()
    if not API_KEY:
        print(f"{RED}❌ API Key 不能为空{RESET}")
        exit(1)

client = OpenAI(
    api_key=API_KEY,
    base_url="https://api.deepseek.com"
)

# ==================== 系统提示 ====================

SYSTEM_PROMPT = f"""你是一个强大的编码助手，拥有完整的文件系统和 Git 操作能力。

【仓库信息】
- Git 仓库路径: {GIT_REPO_PATH}

【核心功能】

1. **精确替换**（最常用）：
   - 当用户说"把A改成B"时，使用 replace_in_file 工具
   - 示例：用户说"把 README.md 里的 v1.0 改成 v2.0"
   - 调用: replace_in_file(filepath="README.md", old_text="v1.0", new_text="v2.0")

2. **Git 工作流**（自动完成）：
   - 当用户说"提交"、"推送"、"更新代码"时，使用 git_auto_workflow
   - 示例：用户说"提交修改，信息是修复bug" 
   - 调用: git_auto_workflow(message="修复bug")
   - 示例：用户说"推送代码"
   - 调用: git_auto_workflow(message="更新代码", push=True)

3. **文件操作**：
   - 读取文件: read_file
   - 写入文件: write_file（会请求用户确认）
   - 列出目录: list_files

4. **Git 高级操作**：
   - 查看状态: git_status
   - 查看历史: git_log
   - 切换分支: git_checkout
   - 拉取更新: git_pull
   - 查看差异: git_diff
   - 克隆仓库: git_clone

5. **GitHub 连接**：
   - 配置 SSH: setup_github_ssh
   - 测试连接: test_github_connection
   - 配置用户: configure_git_user

【重要规则】
- Git 操作自动执行（用户信任你），无需确认
- 文件写入需要用户确认
- PowerShell 命令需要用户确认
- 始终告知用户你在做什么
- 尽量使用专用工具，不要用 execute_powershell

【工作流示例】
用户: "把 README.md 里的 v1.0 改成 v2.0，然后提交推送"
步骤:
  1. replace_in_file("README.md", "v1.0", "v2.0")
  2. git_auto_workflow(message="更新版本号到 v2.0")
"""

chat_history = [
    {"role": "system", "content": SYSTEM_PROMPT}
]

# ==================== 工具执行器 ====================

def execute_tool(func_name: str, args: dict) -> str:
    """统一的工具执行入口"""
    print(f"\n{MAGENTA}🔧 执行工具: {func_name}{RESET}")
    
    is_git = is_git_tool(func_name)
    
    if args:
        print(f"{DARK_GRAY}参数: {json.dumps(args, ensure_ascii=False, indent=2)}{RESET}")
    
    # ==================== 基础工具 ====================
    
    if func_name == "read_file":
        return read_file(args.get("filepath"))
        
    elif func_name == "write_file":
        filepath = args.get("filepath")
        content = args.get("content")
        
        print(f"\n{YELLOW}⚠️  需要确认: 写入文件{RESET}")
        print(f"📄 文件: {filepath}")
        print(f"📝 内容预览: {content[:200]}...")
        
        confirm = input(f"{YELLOW}允许此操作吗? (y/n): {RESET}").strip().lower()
        if confirm == 'y':
            return write_file(filepath, content)
        else:
            return "❌ 操作已取消: 用户拒绝写入文件"
            
    elif func_name == "replace_in_file":
        # 精确替换 - Git 工具，自动执行
        filepath = args.get("filepath")
        old_text = args.get("old_text")
        new_text = args.get("new_text")
        print(f"📝 精确替换: {filepath}")
        print(f"  旧: {old_text[:50]}...")
        print(f"  新: {new_text[:50]}...")
        return replace_in_file(filepath, old_text, new_text)
            
    elif func_name == "list_files":
        return list_files(args.get("directory", "."))
        
    elif func_name == "execute_powershell":
        command = args.get("command")
        timeout = args.get("timeout", 30)
        
        print(f"\n{YELLOW}⚠️  需要确认: 执行 PowerShell 命令{RESET}")
        print(f"💻 命令: {command}")
        
        confirm = input(f"{YELLOW}允许此操作吗? (y/n): {RESET}").strip().lower()
        if confirm == 'y':
            return execute_powershell(command, timeout)
        else:
            return "❌ 操作已取消: 用户拒绝执行 PowerShell 命令"
    
    # ==================== Git 工具（自动执行） ====================
    
    elif func_name == "git_auto_workflow":
        message = args.get("message", "更新代码")
        files = args.get("files", ".")
        push = args.get("push", True)
        print(f"{GREEN}🚀 启动 Git 自动化工作流...{RESET}")
        return git_auto_workflow(message, files, push)
        
    elif func_name == "git_status":
        return git_status()
        
    elif func_name == "git_add":
        files = args.get("files", ".")
        return git_add(files)
        
    elif func_name == "git_commit":
        return git_commit(args.get("message"))
        
    elif func_name == "git_push":
        remote = args.get("remote", "origin")
        branch = args.get("branch", "")
        return git_push(remote, branch)
        
    elif func_name == "git_pull":
        remote = args.get("remote", "origin")
        branch = args.get("branch", "")
        return git_pull(remote, branch)
        
    elif func_name == "git_log":
        count = args.get("count", 10)
        return git_log(count)
        
    elif func_name == "git_branch":
        return git_branch()
        
    elif func_name == "git_checkout":
        return git_checkout(args.get("branch"))
        
    elif func_name == "git_diff":
        staged = args.get("staged", False)
        return git_diff(staged)
        
    elif func_name == "git_clone":
        repo_url = args.get("repo_url")
        target_dir = args.get("target_dir", "")
        return git_clone(repo_url, target_dir)
        
    elif func_name == "git_stash":
        return git_stash()
        
    elif func_name == "git_stash_pop":
        return git_stash_pop()
        
    elif func_name == "git_reset":
        mode = args.get("mode", "mixed")
        target = args.get("target", "HEAD")
        return git_reset(mode, target)
    
    # ==================== GitHub 连接工具 ====================
    
    elif func_name == "setup_github_ssh":
        return setup_github_ssh()
        
    elif func_name == "test_github_connection":
        return test_github_connection()
        
    elif func_name == "configure_git_user":
        name = args.get("name", "")
        email = args.get("email", "")
        return configure_git_user(name, email)
    
    else:
        return f"❌ 错误: 未知工具 {func_name}"

# ==================== 主循环 ====================

print(f"""
{BOLD}{GREEN}🤖 终极 Git + 文件系统 Agent{RESET}
{BOLD}{YELLOW}📁 仓库路径: {GIT_REPO_PATH}{RESET}
{BOLD}{CYAN}💡 使用说明:{RESET}
  ────────────────────────────────────────
  📝 精确替换: "把 README.md 里的 v1.0 改成 v2.0"
  🚀 提交推送: "提交修改，信息是修复bug" 
  📊 查看状态: "查看 Git 状态"
  🌿 切换分支: "切换到 main 分支"
  🔑 GitHub配置: "配置 GitHub SSH"
  ────────────────────────────────────────
  💡 输入 'exit' 退出，'clear' 清空历史
{BOLD}{DARK_GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}
""")

while True:
    try:
        user_input = input(f"\n{YELLOW}👤 你{RESET}\n> ")
    except (KeyboardInterrupt, EOFError):
        print(f"\n{YELLOW}👋 再见！{RESET}")
        break

    if user_input.strip().lower() == 'exit':
        print(f"{YELLOW}👋 再见！{RESET}")
        break
    
    if user_input.strip().lower() == 'clear':
        chat_history = [chat_history[0]]  # 保留系统提示
        print(f"{GREEN}🧹 对话历史已清空{RESET}")
        continue

    chat_history.append({"role": "user", "content": user_input})

    # ==================== Tool Calling 循环 ====================
    
    while True:
        print(f"{DARK_GRAY}⏳ AI 思考中... (按 Ctrl+C 停止){RESET}")

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

            message = response.choices[0].message
            
            # 显示 AI 思考过程
            ai_thinking = getattr(message, 'reasoning_content', None)
            if ai_thinking is None and hasattr(message, 'model_extra') and message.model_extra:
                ai_thinking = message.model_extra.get('reasoning_content', "")
            
            if ai_thinking:
                print(f"\n{CYAN}💭 AI 推理过程:{RESET}")
                print(f"{CYAN}{ai_thinking}{RESET}")

            chat_history.append(message)

            # ==================== 处理工具调用 ====================
            
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    func_name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    
                    # 执行工具
                    result = execute_tool(func_name, args)
                    
                    # 显示结果（截断）
                    result_preview = result[:500] + ("..." if len(result) > 500 else "")
                    print(f"{GREEN}📊 工具结果:{RESET}")
                    print(f"{GREEN}{result_preview}{RESET}")
                    
                    # 将结果返回给 AI
                    chat_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": func_name,
                        "content": result
                    })
                
                continue  # 继续循环，让 AI 根据结果做下一步
                
            # ==================== 显示最终回复 ====================
            
            else:
                ai_text = message.content or ""
                print(f"\n{GREEN}🤖 AI 回复:{RESET}")
                print(f"{GREEN}{ai_text}{RESET}")
                break

        except KeyboardInterrupt:
            print(f"\n{YELLOW}⏹️  已停止 AI 思考，开始新的对话回合{RESET}")
            if chat_history and chat_history[-1]["role"] == "user":
                chat_history.pop()
            break

        except Exception as e:
            print(f"\n{RED}❌ 错误: {e}{RESET}")
            break