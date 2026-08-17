import sys
import json
import os
from pathlib import Path
from openai import OpenAI

# Import all tools
from agent_tools import (
    read_file, write_file, replace_in_file, list_files, execute_powershell,
    git_auto_workflow, git_status, git_add, git_commit, git_push,
    git_pull, git_log, git_branch, git_checkout, git_diff,
    git_clone, git_stash, git_stash_pop, git_reset,
    setup_github_ssh, test_github_connection, configure_git_user,
    agent_tools, is_git_tool, GIT_REPO_PATH, parse_replace_request
)

sys.stdout.reconfigure(encoding='utf-8')

# Color definitions
YELLOW = "\033[93m"
CYAN = "\033[96m"
GREEN = "\033[92m"
DARK_GRAY = "\033[90m"
MAGENTA = "\033[95m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

# ==================== Configuration ====================

DEFAULT_GIT_PATH = os.environ.get("GIT_REPO_PATH", str(Path.cwd().resolve()))

# ==================== API Configuration ====================

# Read API Key from environment variables or config file
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

# ==================== System Prompt ====================

SYSTEM_PROMPT = f"""You are a powerful coding assistant with full file system and Git operation capabilities.

[Repository Information]
- Git Repository Path: {GIT_REPO_PATH}

[Core Features]

1. **Exact Replacement** (Most Used):
   - When the user says "change A to B", use the replace_in_file tool
   - Example: The user says "Change v1.0 to v2.0 in README.md"
   - Call: replace_in_file(filepath="README.md", old_text="v1.0", new_text="v2.0")

2. **Git Workflow** (Automated):
   - When the user says "commit", "push", or "update code", use git_auto_workflow
   - Example: The user says "Commit changes, message is fix bug" 
   - Call: git_auto_workflow(message="Fix bug")
   - Example: The user says "Push code"
   - Call: git_auto_workflow(message="Update code", push=True)

3. **File Operations**:
   - Read file: read_file
   - Write file: write_file (requires user confirmation)
   - Replace content: replace_in_file (requires user confirmation)
   - List directory: list_files

4. **Advanced Git Operations**:
   - Check status: git_status
   - View history: git_log
   - Checkout branch: git_checkout
   - Pull updates: git_pull
   - View differences: git_diff
   - Clone repository: git_clone

5. **GitHub Connection**:
   - Configure SSH: setup_github_ssh
   - Test connection: test_github_connection
   - Configure user: configure_git_user

[Important Rules]
- Think (reasoning process) in English by default, unless the user explicitly asks you to think in another language
- Answer (final response) in English by default, unless the user explicitly asks you to respond in another language
- Git operations are executed automatically (the user trusts you), no confirmation needed
- File writes (write_file) and file modifications (replace_in_file) require user confirmation
- PowerShell commands require user confirmation
- Always inform the user what you are doing
- Try to use dedicated tools; avoid using execute_powershell if possible

[Workflow Example]
User: "Change v1.0 to v2.0 in README.md, then commit and push"
Steps:
  1. replace_in_file("README.md", "v1.0", "v2.0")
  2. git_auto_workflow(message="Update version to v2.0")
"""

chat_history = [
    {"role": "system", "content": SYSTEM_PROMPT}
]

# ==================== Context Usage Tracking ====================

# Context window size for DeepSeek V4 Flash model (in tokens)
CONTEXT_WINDOW = 1000000  # DeepSeek V4 Flash supports 1M context window

# Track the token usage of the latest API response
last_usage = None


def display_context_usage():
    """Display current context usage as a percentage"""
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

# ==================== Tool Executor ====================

def execute_tool(func_name: str, args: dict) -> str:
    """Unified tool execution entry point"""
    print(f"\n{MAGENTA}🔧 Executing tool: {func_name}{RESET}")
    
    is_git = is_git_tool(func_name)
    
    if args:
        print(f"{DARK_GRAY}Parameters: {json.dumps(args, ensure_ascii=False, indent=2)}{RESET}")
    
    # ==================== Basic Tools ====================
    
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
        else:
            return "❌ Operation cancelled: User declined to write to file"
            
    elif func_name == "replace_in_file":
        # Exact replacement - also writes to file, requires confirmation
        filepath = args.get("filepath")
        old_text = args.get("old_text")
        new_text = args.get("new_text")
        
        print(f"\n{YELLOW}⚠️  Confirmation required: Modify file (replacement){RESET}")
        print(f"📄 File: {filepath}")
        print(f"  Old: {old_text[:100]}{'...' if len(old_text) > 100 else ''}")
        print(f"  New: {new_text[:100]}{'...' if len(new_text) > 100 else ''}")
        
        confirm = input(f"{YELLOW}Allow this operation? (y/n): {RESET}").strip().lower()
        if confirm == 'y':
            print(f"📝 Exact replacement: {filepath}")
            print(f"  Old: {old_text[:50]}{'...' if len(old_text) > 50 else ''}")
            print(f"  New: {new_text[:50]}{'...' if len(new_text) > 50 else ''}")
            return replace_in_file(filepath, old_text, new_text)
        else:
            return "❌ Operation cancelled: User declined to modify file"
            
    elif func_name == "list_files":
        return list_files(args.get("directory", "."))
        
    elif func_name == "execute_powershell":
        command = args.get("command")
        timeout = args.get("timeout", 30)
        
        print(f"\n{YELLOW}⚠️  Confirmation required: Execute PowerShell command{RESET}")
        print(f"💻 Command: {command}")
        
        confirm = input(f"{YELLOW}Allow this operation? (y/n): {RESET}").strip().lower()
        if confirm == 'y':
            return execute_powershell(command, timeout)
        else:
            return "❌ Operation cancelled: User declined to execute PowerShell command"
    
    # ==================== Git Tools ====================
    
    elif func_name == "git_auto_workflow":
        message = args.get("message", "Update code")
        files = args.get("files", ".")
        push = args.get("push", True)
        print(f"{GREEN}🚀 Starting automated Git workflow...{RESET}")
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
    
    # ==================== GitHub Connection Tools ====================
    
    elif func_name == "setup_github_ssh":
        return setup_github_ssh()
        
    elif func_name == "test_github_connection":
        return test_github_connection()
        
    elif func_name == "configure_git_user":
        name = args.get("name", "")
        email = args.get("email", "")
        return configure_git_user(name, email)
    
    else:
        return f"❌ Error: Unknown tool {func_name}"

# ==================== Main Loop ====================

print(f"""
{BOLD}{GREEN}══════════════════════════════════════════════════════════════{RESET}
{BOLD}{GREEN}   🤖 Git Repository Control + File System Agent{RESET}
{BOLD}{YELLOW}   📁 Repository: {GIT_REPO_PATH}{RESET}
{BOLD}{GREEN}══════════════════════════════════════════════════════════════{RESET}

{BOLD}{CYAN}📘 FILE OPERATIONS{RESET}
  📖 Read        →  "Read config.json"
  🔍 Replace     →  "Change v1.0 to v2.0 in README.md"  ⚠️ requires confirmation
  ✍️  Write       →  "Create file hello.py"  ⚠️ requires confirmation
  📂 List        →  "List files in src/"

{BOLD}{CYAN}🚀 GIT OPERATIONS{RESET}
  💾 Commit      →  "Commit changes, message: fix bug A"
  📊 Status      →  "Check Git status"
  🌿 Branch      →  "Checkout main" / "List branches"
  📜 History     →  "Show last 5 commits"
  🔄 Pull        →  "Pull latest changes"
  🔀 Stash       →  "Stash my changes"

{BOLD}{CYAN}🔑 GITHUB CONNECTION{RESET}
  🔧 SSH Setup   →  "Configure GitHub SSH"
  ✅ Test        →  "Test GitHub connection"
  👤 Identity    →  "Set git user to John / john@example.com"

{BOLD}{MAGENTA}⚙️  CONTROLS{RESET}
  🚪 exit        →  Quit the agent
  🧹 clear       →  Clear conversation history

{BOLD}{DARK_GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}
""")

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
        chat_history = [chat_history[0]]  # Keep system prompt
        last_usage = None  # Reset context usage tracking
        print(f"{GREEN}🧹 Chat history cleared{RESET}")
        continue

    chat_history.append({"role": "user", "content": user_input})

    # ==================== Tool Calling Loop ====================
    
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

            # Record context usage from this response
            if response.usage:
                last_usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }

            message = response.choices[0].message
            
            # Display AI reasoning process
            ai_thinking = getattr(message, 'reasoning_content', None)
            if ai_thinking is None and hasattr(message, 'model_extra') and message.model_extra:
                ai_thinking = message.model_extra.get('reasoning_content', "")
            
            if ai_thinking:
                print(f"\n{CYAN}💭 AI Reasoning Process:{RESET}")
                print(f"{CYAN}{ai_thinking}{RESET}")

            chat_history.append(message)

            # ==================== Handle Tool Calls ====================
            
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    func_name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    
                    # Execute tool
                    result = execute_tool(func_name, args)
                    
                    # Display results (truncated)
                    result_preview = result[:500] + ("..." if len(result) > 500 else "")
                    print(f"{GREEN}📊 Tool Result:{RESET}")
                    print(f"{GREEN}{result_preview}{RESET}")
                    
                    # Return result to AI
                    chat_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": func_name,
                        "content": result
                    })
                
                continue  # Continue loop, let AI decide the next step based on the result
                
            # ==================== Display Final Response ====================
            
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