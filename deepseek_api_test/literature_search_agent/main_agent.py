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
    search_literature, get_paper_details, get_citations, get_references,
    chain_search, score_papers, list_top_papers, generate_markdown_report,
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

def load_api_key():
    """Smarter API key loading:
    1. Check the DEEPSEEK_API_KEY environment variable first.
    2. Scan the project directory for api-key.env:
       - If found with a valid key → read it and load it into the
         environment automatically.
       - If found but only contains the template placeholder (sk-*) →
         inform the user and ask them to type in the real key.
    3. If api-key.env is NOT found → ask the user to type in the key.
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if api_key:
        return api_key

    env_file = Path.cwd() / "api-key.env"

    if env_file.exists():
        print(f"{GREEN}📄 Found api-key.env, reading API key...{RESET}")
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                var_name, _, value = line.partition("=")
                var_name = var_name.strip()
                value = value.strip().strip('"').strip("'")
                if var_name == "DEEPSEEK_API_KEY" and value:
                    # Template placeholder found → ask user for the real key
                    if value == "sk-*" or value.startswith("sk-*") or "YOUR" in value.upper():
                        print(f"{YELLOW}⚠️  api-key.env only contains the template placeholder, "
                              f"please enter your real DeepSeek API Key:{RESET}")
                    else:
                        os.environ[var_name] = value
                        print(f"{GREEN}✅ API key loaded from api-key.env{RESET}")
                        return value
        except Exception as e:
            print(f"{RED}⚠️ Failed to read api-key.env: {e}{RESET}")
    else:
        print(f"{YELLOW}🔎 api-key.env not found in {Path.cwd()}, "
              f"please enter your DeepSeek API Key manually.{RESET}")

    # Fallback: ask the user to type in the key
    api_key = input("🔑 Please enter DeepSeek API Key: ").strip()
    if not api_key:
        print(f"{RED}❌ API Key cannot be empty{RESET}")
        exit(1)
    return api_key


API_KEY = load_api_key()

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

[Literature Search (Academic Research)]
You are also a literature search assistant for a PhD student in fluid/solid mechanics.
- Search ONLY through these free academic APIs (no API key needed): Semantic Scholar, Crossref, arXiv, OpenAlex.
- Typical workflow:
  1. search_literature(query, sources=[...], year_from, year_to) → initial candidates
  2. (optional) get_citations / get_references / chain_search(root_paper, direction, depth) → chained expansion from a root article the user provides (or you find)
  3. score_papers(query, papers_json, emphasis_terms, fulltext) → relevance ranking (abstract + keywords, intro/conclusion if open-access)
  4. list_top_papers(papers_json, top_n) → show simple title + authors + year list in the command line
  5. If the user asks for a detailed report: generate_markdown_report(query, papers_json, filepath, notes)
- Always tell the user the number of papers found and present the top-ranked ones (title + authors + year).
- Respect API rate limits: Semantic Scholar ~1 request/second; keep queries focused.

[Workflow Example]
User: "Change v1.0 to v2.0 in README.md, then commit and push"
Steps:
  1. replace_in_file("README.md", "v1.0", "v2.0")
  2. git_auto_workflow(message="Update version to v2.0")
"""

chat_history = [
    {"role": "system", "content": SYSTEM_PROMPT}
]

# ==================== Skip Operation ====================

class OperationSkipped(Exception):
    """Raised when the user chooses 's' (skip) at a confirmation prompt.
    Denies the requested operation and tells the main loop to ask the AI
    for a final response, then return to the 'You>' prompt."""
    pass

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
        
        confirm = input(f"{YELLOW}Allow this operation? (y/n/s - s=skip & return): {RESET}").strip().lower()
        if confirm == 'y':
            return write_file(filepath, content)
        elif confirm == 's':
            raise OperationSkipped()
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
        
        confirm = input(f"{YELLOW}Allow this operation? (y/n/s - s=skip & return): {RESET}").strip().lower()
        if confirm == 'y':
            print(f"📝 Exact replacement: {filepath}")
            print(f"  Old: {old_text[:50]}{'...' if len(old_text) > 50 else ''}")
            print(f"  New: {new_text[:50]}{'...' if len(new_text) > 50 else ''}")
            return replace_in_file(filepath, old_text, new_text)
        elif confirm == 's':
            raise OperationSkipped()
        else:
            return "❌ Operation cancelled: User declined to modify file"
            
    elif func_name == "list_files":
        return list_files(args.get("directory", "."))
        
    elif func_name == "execute_powershell":
        command = args.get("command")
        timeout = args.get("timeout", 30)
        
        print(f"\n{YELLOW}⚠️  Confirmation required: Execute PowerShell command{RESET}")
        print(f"💻 Command: {command}")
        
        confirm = input(f"{YELLOW}Allow this operation? (y/n/s - s=skip & return): {RESET}").strip().lower()
        if confirm == 'y':
            return execute_powershell(command, timeout)
        elif confirm == 's':
            raise OperationSkipped()
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
    
    # ==================== Literature Search Tools ====================
    
    elif func_name == "search_literature":
        return search_literature(
            args.get("query"),
            max_results=args.get("max_results", 10),
            sources=args.get("sources"),
            year_from=args.get("year_from"),
            year_to=args.get("year_to"),
        )
        
    elif func_name == "get_paper_details":
        return get_paper_details(args.get("paper_id"), args.get("source", "auto"))
        
    elif func_name == "get_citations":
        return get_citations(args.get("paper_id"), args.get("limit", 20))
        
    elif func_name == "get_references":
        return get_references(args.get("paper_id"), args.get("limit", 20))
        
    elif func_name == "chain_search":
        return chain_search(
            args.get("root_paper"),
            direction=args.get("direction", "both"),
            depth=args.get("depth", 2),
            limit=args.get("limit", 30),
            neighbors_per_hop=args.get("neighbors_per_hop", 10),
        )
        
    elif func_name == "score_papers":
        return score_papers(
            args.get("query"),
            args.get("papers_json"),
            emphasis_terms=args.get("emphasis_terms"),
            fulltext=args.get("fulltext", False),
        )
        
    elif func_name == "list_top_papers":
        return list_top_papers(args.get("papers_json"), args.get("top_n", 10))
        
    elif func_name == "generate_markdown_report":
        return generate_markdown_report(
            args.get("query"),
            args.get("papers_json"),
            filepath=args.get("filepath", "literature_report.md"),
            notes=args.get("notes"),
            top_n=args.get("top_n", 20),
        )
    
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

{BOLD}{CYAN}📚 LITERATURE SEARCH{RESET}
  🔎 Search      →  "Search literature on vortex-induced vibration of cylinders"
  🔗 Chain       →  "Expand citations/references from root paper DOI:10.xxxx, depth 2"
  🏆 Score       →  "Rank the results by relevance to my thesis topic"
  📋 List        →  "List the top 10 papers (title + authors + year)"
  📝 Report      →  "Generate a detailed .md report of the search results"

{BOLD}{MAGENTA}⚙️  CONTROLS{RESET}
  🚪 exit        →  Quit the agent
  🧹 clear       →  Clear conversation history
  ⏭️ s (skip)    →  At (y/n/s) prompts: deny the operation & return to You>

{BOLD}{DARK_GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}
""")

while True:
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
                skipped = False
                for tool_call in message.tool_calls:
                    func_name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    
                    # Execute tool
                    try:
                        result = execute_tool(func_name, args)
                    except OperationSkipped:
                        # User chose 's' (skip): deny the current operation and
                        # force the agent to give a final response, then go back
                        # to the 'You>' prompt for the next user input.
                        skipped = True
                        
                        # Tell the AI the operation was skipped
                        chat_history.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": func_name,
                            "content": (
                                f"⏭️ Operation '{func_name}' was SKIPPED by the user "
                                f"(they chose 's' = skip). The operation was NOT executed. "
                                f"Give your final response now: acknowledge the skip and "
                                f"briefly summarize what you would have done. "
                                f"Do not call any more tools."
                            )
                        })
                        
                        print(f"\n{YELLOW}⏭️ Operation skipped by user. Asking AI for final response...{RESET}")
                        
                        # Ask the AI for a final response (no tools available)
                        try:
                            final_response = client.chat.completions.create(
                                model="deepseek-chat",
                                messages=chat_history,
                                tools=[],
                                stream=False,
                                extra_body={
                                    "thinking": {"type": "enabled"},
                                    "reasoning_effort": "high"
                                }
                            )
                            final_message = final_response.choices[0].message
                            
                            # Display AI reasoning process
                            ai_thinking = getattr(final_message, 'reasoning_content', None)
                            if ai_thinking is None and hasattr(final_message, 'model_extra') and final_message.model_extra:
                                ai_thinking = final_message.model_extra.get('reasoning_content', "")
                            if ai_thinking:
                                print(f"\n{CYAN}💭 AI Reasoning Process:{RESET}")
                                print(f"{CYAN}{ai_thinking}{RESET}")
                            
                            chat_history.append(final_message)
                            
                            # Display final response
                            ai_text = final_message.content or ""
                            print(f"\n{GREEN}🤖 AI Response:{RESET}")
                            print(f"{GREEN}{ai_text}{RESET}")
                        except Exception as e:
                            print(f"\n{RED}❌ Error getting final response: {e}{RESET}")
                        
                        break  # stop processing remaining tool calls in this batch
                    
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
                
                if skipped:
                    break  # Operation skipped → back to 'You>' prompt
                
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