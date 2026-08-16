import os
import subprocess
from pathlib import Path
import re
import json

# ==================== Path Security Check ====================

BASE_DIR = Path.cwd().resolve()

def is_safe_path(target_path: str) -> bool:
    try:
        requested_path = Path(target_path).resolve()
        return requested_path.is_relative_to(BASE_DIR)
    except Exception:
        return False

# ==================== Basic File Operations ====================

def read_file(filepath):
    if not is_safe_path(filepath):
        return f"Error: Access denied. You are only allowed to read files within {BASE_DIR}."
    try:
        # Try multiple encodings
        encodings = ['utf-8', 'gbk', 'latin-1']
        for encoding in encodings:
            try:
                with open(filepath, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        return f"Error: Cannot decode file with any known encoding"
    except Exception as e:
        return f"Error reading file: {e}"

def write_file(filepath, content):
    if not is_safe_path(filepath):
        return f"Error: Access denied. You are only allowed to modify files within {BASE_DIR}."
    try:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"✅ Successfully wrote to file: {filepath}"
    except Exception as e:
        return f"Error writing file: {e}"

def list_files(directory="."):
    try:
        files = os.listdir(directory)
        result = []
        for f in files:
            path = os.path.join(directory, f)
            if os.path.isdir(path):
                result.append(f"{f}/")
            else:
                result.append(f)
        return "\n".join(result)
    except Exception as e:
        return f"Error listing directory: {e}"

# ==================== Exact Replacement Feature ====================

def replace_in_file(filepath, old_text, new_text):
    """
    Exactly replace file content.
    Supports: ignoring leading/trailing spaces, auto-detecting encoding.
    """
    if not is_safe_path(filepath):
        return f"❌ Permission denied: Cannot modify files outside of {BASE_DIR}"
    
    try:
        content = read_file(filepath)
        if not content.startswith("Error"):
            # Exact replacement
            if old_text in content:
                new_content = content.replace(old_text, new_text)
                write_file(filepath, new_content)
                return f"✅ Replaced: {old_text[:50]} → {new_text[:50]}"
            else:
                # Try ignoring leading/trailing spaces
                old_trim = old_text.strip()
                if old_trim in content:
                    new_content = content.replace(old_trim, new_text.strip())
                    write_file(filepath, new_content)
                    return f"✅ Replaced (ignored spaces): {old_text[:50]} → {new_text[:50]}"
                return f"❌ Content to replace not found: {old_text[:50]}"
        else:
            return content
    except Exception as e:
        return f"❌ Replacement failed: {e}"

# ==================== PowerShell Execution ====================

def execute_powershell(command: str, timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        output = result.stdout.strip()
        error = result.stderr.strip()
        
        MAX_CHARS = 4000
        if len(output) > MAX_CHARS:
            output = output[:MAX_CHARS] + f"\n\n...[OUTPUT TRUNCATED]..."
        if len(error) > MAX_CHARS:
            error = error[:MAX_CHARS] + f"\n\n...[ERROR TRUNCATED]..."
        
        if result.returncode == 0:
            if not output and not error:
                return "✅ Command executed successfully (no output)"
            return output if not error else f"Output:\n{output}\nWarnings:\n{error}"
        else:
            return f"❌ Command failed (Exit Code {result.returncode}).\nError:\n{error}\nOutput:\n{output}"
            
    except subprocess.TimeoutExpired:
        return f"❌ Command timed out ({timeout} seconds)"
    except Exception as e:
        return f"❌ Execution error: {str(e)}"

# ==================== Core Git Features (From First Version) ====================

# Global Git repository path
GIT_REPO_PATH = os.environ.get("GIT_REPO_PATH", str(Path.cwd().resolve()))

def _git_execute(command: str) -> str:
    """Internal function: Execute Git command"""
    # If the command includes the -C parameter, execute directly; otherwise, append it
    if "-C" in command:
        full_command = f"git {command}"
    else:
        full_command = f"git -C \"{GIT_REPO_PATH}\" {command}"
    return execute_powershell(full_command)

def git_status() -> str:
    """Check Git status"""
    return _git_execute("status")

def git_add(files: str = ".") -> str:
    """Add files to the staging area"""
    return _git_execute(f"add {files}")

def git_commit(message: str) -> str:
    """Commit changes"""
    safe_message = message.replace('"', '\\"').replace("'", "\\'")
    return _git_execute(f'commit -m "{safe_message}"')

def git_push(remote: str = "origin", branch: str = "") -> str:
    """Push to remote"""
    if branch:
        return _git_execute(f"push {remote} {branch}")
    else:
        # Get current branch
        branch_result = _git_execute("branch --show-current")
        if "❌" in branch_result:
            return f"❌ Cannot get current branch: {branch_result}"
        current_branch = branch_result.strip()
        if current_branch and "✅" not in current_branch:
            return _git_execute(f"push {remote} {current_branch}")
        else:
            return _git_execute(f"push {remote}")

def git_pull(remote: str = "origin", branch: str = "") -> str:
    """Pull updates"""
    if branch:
        return _git_execute(f"pull {remote} {branch}")
    else:
        return _git_execute(f"pull {remote}")

def git_log(count: int = 10) -> str:
    """View commit history"""
    return _git_execute(f"log --oneline -{count}")

def git_branch() -> str:
    """View branches"""
    return _git_execute("branch -a")

def git_checkout(branch: str) -> str:
    """Checkout branch"""
    return _git_execute(f"checkout {branch}")

def git_diff(staged: bool = False) -> str:
    """View differences"""
    if staged:
        return _git_execute("diff --staged")
    else:
        return _git_execute("diff")

def git_clone(repo_url: str, target_dir: str = "") -> str:
    """Clone repository"""
    if target_dir:
        return execute_powershell(f"git clone {repo_url} {target_dir}")
    else:
        return execute_powershell(f"git clone {repo_url}")

def git_stash() -> str:
    """Stash changes"""
    return _git_execute("stash")

def git_stash_pop() -> str:
    """Pop stash"""
    return _git_execute("stash pop")

def git_reset(mode: str = "mixed", target: str = "HEAD") -> str:
    """Reset git state"""
    return _git_execute(f"reset --{mode} {target}")

# ==================== Smart Git Workflow (Core of First Version) ====================

def git_auto_workflow(message: str, files: str = ".", push: bool = True) -> str:
    """
    Smart Git Workflow: add → commit → (optional) push
    This is the core feature of the first version.
    """
    results = []
    results.append("🚀 Starting automated Git workflow...")
    results.append("━" * 50)
    
    # 1. Check status
    status = git_status()
    if "❌" in status:
        results.append(f"❌ Status check failed: {status}")
        return "\n".join(results)
    
    results.append(f"📊 Current status:\n{status}")
    results.append("━" * 50)
    
    # 2. Add files
    add_result = git_add(files)
    if "❌" in add_result:
        results.append(f"❌ Failed to add files: {add_result}")
        return "\n".join(results)
    results.append(f"✅ Added: {files}")
    
    # 3. Commit
    commit_result = git_commit(message)
    if "❌" in commit_result:
        results.append(f"❌ Commit failed: {commit_result}")
        # Check if there are no changes to commit
        if "nothing to commit" in commit_result.lower():
            results.append("ℹ️ No changes to commit")
        return "\n".join(results)
    results.append(f"✅ Committed: {message}")
    
    # 4. Push
    if push:
        results.append("📤 Pushing to remote repository...")
        push_result = git_push()
        if "❌" in push_result:
            results.append(f"⚠️ Push failed: {push_result}")
        else:
            results.append(f"✅ Push successful")
    
    results.append("━" * 50)
    results.append("🎉 Workflow completed!")
    return "\n".join(results)

# ==================== GitHub SSH Connection Configuration ====================

def setup_github_ssh() -> str:
    """Configure GitHub SSH connection"""
    results = []
    results.append("🔑 GitHub SSH Configuration")
    results.append("━" * 50)
    
    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(exist_ok=True)
    
    ssh_key_path = ssh_dir / "id_rsa"
    ssh_pub_path = ssh_dir / "id_rsa.pub"
    
    # Check if key already exists
    if ssh_key_path.exists() and ssh_pub_path.exists():
        results.append("✅ SSH key already exists")
        with open(ssh_pub_path, 'r') as f:
            pub_key = f.read().strip()
        results.append(f"\n📋 Your SSH public key:\n{pub_key}")
        results.append("\n📌 Please add this public key to GitHub:")
        results.append("   Settings → SSH and GPG keys → New SSH Key")
        results.append("   https://github.com/settings/keys")
        return "\n".join(results)
    
    # Generate new key
    email = input("📧 Please enter your GitHub email: ").strip()
    if not email:
        return "❌ Email cannot be empty"
    
    import subprocess
    # Generate key (no password)
    result = subprocess.run(
        f'ssh-keygen -t rsa -b 4096 -C "{email}" -f "{ssh_key_path}" -N "" -q',
        shell=True,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        return f"❌ Failed to generate key: {result.stderr}"
    
    results.append("✅ SSH key generated successfully")
    
    # Start ssh-agent and add key
    subprocess.run('ssh-agent', shell=True, capture_output=True)
    subprocess.run(f'ssh-add "{ssh_key_path}"', shell=True, capture_output=True)
    results.append("✅ SSH Agent started")
    
    # Display public key
    if ssh_pub_path.exists():
        with open(ssh_pub_path, 'r') as f:
            pub_key = f.read().strip()
        results.append(f"\n📋 Your SSH public key:\n{pub_key}")
        results.append("\n📌 Please add this public key to GitHub:")
        results.append("   Settings → SSH and GPG keys → New SSH Key")
        results.append("   https://github.com/settings/keys")
        
        # Try to copy to clipboard
        try:
            import pyperclip
            pyperclip.copy(pub_key)
            results.append("✅ Public key copied to clipboard!")
        except:
            pass
    
    return "\n".join(results)

def test_github_connection() -> str:
    """Test GitHub connection"""
    result = execute_powershell("ssh -T git@github.com", timeout=10)
    if "successfully authenticated" in result:
        return "✅ GitHub SSH connection successful!\n" + result
    elif "Permission denied" in result:
        return "❌ SSH connection failed (Permission denied). Please check:\n" + result
    else:
        return "❌ SSH connection failed:\n" + result

def configure_git_user(name: str = "", email: str = "") -> str:
    """Configure Git user"""
    results = []
    if not name:
        name = input("Please enter Git username: ").strip()
    if not email:
        email = input("Please enter Git email: ").strip()
    
    if name:
        result = _git_execute(f'config --global user.name "{name}"')
        results.append(f"✅ Username set: {name}")
    if email:
        result = _git_execute(f'config --global user.email "{email}"')
        results.append(f"✅ Email set: {email}")
    
    return "\n".join(results) if results else "No information configured"

# ==================== Command Parsing (From First Version) ====================

def parse_replace_request(user_input: str) -> dict:
    """
    Parse replacement request from user input.
    Supports: change A to B, replace A with B, modify A to B, etc.
    """
    # Detect keywords
    if not any(k in user_input.lower() for k in ['change', 'replace', 'modify', 'swap']):
        return None
    
    # Extract file path
    file_match = re.search(r'([A-Za-z]:[\\/][^\s]+\.\w+)', user_input)
    if not file_match:
        # Try matching relative path
        file_match = re.search(r'([^\s]+\.\w+)', user_input)
    if not file_match:
        return None
    filepath = file_match.group(1)
    
    # Try multiple patterns to extract old → new
    patterns = [
        r'change\s*["\']?([^"\']+)["\']?\s*to\s*["\']?([^"\']+)["\']?',
        r'replace\s*["\']?([^"\']+)["\']?\s*with\s*["\']?([^"\']+)["\']?',
        r'modify\s*["\']?([^"\']+)["\']?\s*to\s*["\']?([^"\']+)["\']?',
        r'change\s*([^\s]+)\s*to\s*([^\s]+)',
        r'replace\s*([^\s]+)\s*with\s*([^\s]+)',
    ]
    
    for pattern in patterns:
        m = re.search(pattern, user_input, re.IGNORECASE)
        if m:
            old_text = m.group(1).strip()
            new_text = m.group(2).strip()
            return {'filepath': filepath, 'old': old_text, 'new': new_text}
    
    return None

# ==================== Tool List (Includes all Git features) ====================

agent_tools = [
    # Basic File Operations
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read file content",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "File path"}
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write file content (overwrite mode)",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "File path"},
                    "content": {"type": "string", "description": "Content to write"}
                },
                "required": ["filepath", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "replace_in_file",
            "description": "[Exact Replacement] Find and replace specified content in a file. Used when the user says 'Change A to B'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "File path"},
                    "old_text": {"type": "string", "description": "Old content to find"},
                    "new_text": {"type": "string", "description": "New content to replace with"}
                },
                "required": ["filepath", "old_text", "new_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List directory contents",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Directory path, default is current directory", "default": "."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_powershell",
            "description": "Execute PowerShell command",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command to execute"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30}
                },
                "required": ["command"]
            }
        }
    },
    
    # Core Git Features
    {
        "type": "function",
        "function": {
            "name": "git_auto_workflow",
            "description": "[Most Used] Complete Git workflow: automatically executes add → commit → push. Used for committing code, pushing updates, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Commit message"},
                    "files": {"type": "string", "description": "Files to add, default is '.'", "default": "."},
                    "push": {"type": "boolean", "description": "Whether to push", "default": True}
                },
                "required": ["message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Check Git repository status",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_add",
            "description": "Add files to staging area",
            "parameters": {
                "type": "object",
                "properties": {
                    "files": {"type": "string", "description": "Files to add", "default": "."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": "Commit staged changes",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Commit message"}
                },
                "required": ["message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_push",
            "description": "Push to remote repository",
            "parameters": {
                "type": "object",
                "properties": {
                    "remote": {"type": "string", "description": "Remote name", "default": "origin"},
                    "branch": {"type": "string", "description": "Branch name"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_pull",
            "description": "Pull updates from remote",
            "parameters": {
                "type": "object",
                "properties": {
                    "remote": {"type": "string", "description": "Remote name", "default": "origin"},
                    "branch": {"type": "string", "description": "Branch name"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_log",
            "description": "View commit history",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "Number of commits to display", "default": 10}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_branch",
            "description": "View all branches",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_checkout",
            "description": "Checkout branch",
            "parameters": {
                "type": "object",
                "properties": {
                    "branch": {"type": "string", "description": "Branch name"}
                },
                "required": ["branch"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "View differences",
            "parameters": {
                "type": "object",
                "properties": {
                    "staged": {"type": "boolean", "description": "Whether to view staging area", "default": False}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_clone",
            "description": "Clone remote repository",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_url": {"type": "string", "description": "Repository URL"},
                    "target_dir": {"type": "string", "description": "Target directory"}
                },
                "required": ["repo_url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_stash",
            "description": "Stash current changes",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_stash_pop",
            "description": "Pop stashed changes",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_reset",
            "description": "Reset Git state",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "description": "Reset mode: soft/mixed/hard", "default": "mixed"},
                    "target": {"type": "string", "description": "Target commit", "default": "HEAD"}
                },
                "required": []
            }
        }
    },
    
    # GitHub Connection Configuration
    {
        "type": "function",
        "function": {
            "name": "setup_github_ssh",
            "description": "Configure GitHub SSH connection (generate key, display public key)",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "test_github_connection",
            "description": "Test if GitHub SSH connection is successful",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "configure_git_user",
            "description": "Configure Git username and email",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Username"},
                    "email": {"type": "string", "description": "Email"}
                },
                "required": []
            }
        }
    }
]

# Tag Git tools (auto-execute, no confirmation needed)
GIT_TOOL_NAMES = {
    "git_auto_workflow", "git_status", "git_add", "git_commit", 
    "git_push", "git_pull", "git_log", "git_branch", "git_checkout",
    "git_diff", "git_clone", "git_stash", "git_stash_pop", "git_reset",
    "setup_github_ssh", "test_github_connection", "configure_git_user"
}

def is_git_tool(func_name: str) -> bool:
    return func_name in GIT_TOOL_NAMES