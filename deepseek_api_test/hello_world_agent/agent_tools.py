import os
import subprocess
from pathlib import Path
import re
import json

# ==================== 路径安全检查 ====================

BASE_DIR = Path.cwd().resolve()

def is_safe_path(target_path: str) -> bool:
    try:
        requested_path = Path(target_path).resolve()
        return requested_path.is_relative_to(BASE_DIR)
    except Exception:
        return False

# ==================== 基础文件操作 ====================

def read_file(filepath):
    if not is_safe_path(filepath):
        return f"Error: Access denied. You are only allowed to read files within {BASE_DIR}."
    try:
        # 尝试多种编码
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
        return f"✅ 成功写入文件: {filepath}"
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

# ==================== 精确替换功能（来自第一次代码） ====================

def replace_in_file(filepath, old_text, new_text):
    """
    精确替换文件内容
    支持：忽略首尾空格、自动检测编码
    """
    if not is_safe_path(filepath):
        return f"❌ 权限拒绝: 无法修改 {BASE_DIR} 外的文件"
    
    try:
        content = read_file(filepath)
        if not content.startswith("Error"):
            # 精确替换
            if old_text in content:
                new_content = content.replace(old_text, new_text)
                write_file(filepath, new_content)
                return f"✅ 已替换: {old_text[:50]} → {new_text[:50]}"
            else:
                # 尝试忽略首尾空格
                old_trim = old_text.strip()
                if old_trim in content:
                    new_content = content.replace(old_trim, new_text.strip())
                    write_file(filepath, new_content)
                    return f"✅ 已替换（忽略空格）: {old_text[:50]} → {new_text[:50]}"
                return f"❌ 未找到要替换的内容: {old_text[:50]}"
        else:
            return content
    except Exception as e:
        return f"❌ 替换失败: {e}"

# ==================== PowerShell 执行 ====================

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
                return "✅ 命令执行成功（无输出）"
            return output if not error else f"Output:\n{output}\nWarnings:\n{error}"
        else:
            return f"❌ 命令失败 (Exit Code {result.returncode}).\nError:\n{error}\nOutput:\n{output}"
            
    except subprocess.TimeoutExpired:
        return f"❌ 命令超时 ({timeout} 秒)"
    except Exception as e:
        return f"❌ 执行错误: {str(e)}"

# ==================== Git 核心功能（来自第一次代码） ====================

# 全局 Git 仓库路径
GIT_REPO_PATH = os.environ.get("GIT_REPO_PATH", str(Path.cwd().resolve()))

def _git_execute(command: str) -> str:
    """内部函数：执行 Git 命令"""
    # 如果包含 -C 参数，直接执行，否则添加
    if "-C" in command:
        full_command = f"git {command}"
    else:
        full_command = f"git -C \"{GIT_REPO_PATH}\" {command}"
    return execute_powershell(full_command)

def git_status() -> str:
    """查看 Git 状态"""
    return _git_execute("status")

def git_add(files: str = ".") -> str:
    """添加文件到暂存区"""
    return _git_execute(f"add {files}")

def git_commit(message: str) -> str:
    """提交更改"""
    safe_message = message.replace('"', '\\"').replace("'", "\\'")
    return _git_execute(f'commit -m "{safe_message}"')

def git_push(remote: str = "origin", branch: str = "") -> str:
    """推送到远程"""
    if branch:
        return _git_execute(f"push {remote} {branch}")
    else:
        # 获取当前分支
        branch_result = _git_execute("branch --show-current")
        if "❌" in branch_result:
            return f"❌ 无法获取当前分支: {branch_result}"
        current_branch = branch_result.strip()
        if current_branch and "✅" not in current_branch:
            return _git_execute(f"push {remote} {current_branch}")
        else:
            return _git_execute(f"push {remote}")

def git_pull(remote: str = "origin", branch: str = "") -> str:
    """拉取更新"""
    if branch:
        return _git_execute(f"pull {remote} {branch}")
    else:
        return _git_execute(f"pull {remote}")

def git_log(count: int = 10) -> str:
    """查看提交历史"""
    return _git_execute(f"log --oneline -{count}")

def git_branch() -> str:
    """查看分支"""
    return _git_execute("branch -a")

def git_checkout(branch: str) -> str:
    """切换分支"""
    return _git_execute(f"checkout {branch}")

def git_diff(staged: bool = False) -> str:
    """查看差异"""
    if staged:
        return _git_execute("diff --staged")
    else:
        return _git_execute("diff")

def git_clone(repo_url: str, target_dir: str = "") -> str:
    """克隆仓库"""
    if target_dir:
        return execute_powershell(f"git clone {repo_url} {target_dir}")
    else:
        return execute_powershell(f"git clone {repo_url}")

def git_stash() -> str:
    """暂存更改"""
    return _git_execute("stash")

def git_stash_pop() -> str:
    """恢复暂存"""
    return _git_execute("stash pop")

def git_reset(mode: str = "mixed", target: str = "HEAD") -> str:
    """重置"""
    return _git_execute(f"reset --{mode} {target}")

# ==================== 智能 Git 工作流（第一次代码的核心） ====================

def git_auto_workflow(message: str, files: str = ".", push: bool = True) -> str:
    """
    智能 Git 工作流：add → commit → (可选) push
    这是第一次代码的核心功能
    """
    results = []
    results.append("🚀 开始 Git 自动化工作流...")
    results.append("━" * 50)
    
    # 1. 检查状态
    status = git_status()
    if "❌" in status:
        results.append(f"❌ 状态检查失败: {status}")
        return "\n".join(results)
    
    results.append(f"📊 当前状态:\n{status}")
    results.append("━" * 50)
    
    # 2. 添加文件
    add_result = git_add(files)
    if "❌" in add_result:
        results.append(f"❌ 添加文件失败: {add_result}")
        return "\n".join(results)
    results.append(f"✅ 已添加: {files}")
    
    # 3. 提交
    commit_result = git_commit(message)
    if "❌" in commit_result:
        results.append(f"❌ 提交失败: {commit_result}")
        # 检查是否没有更改需要提交
        if "nothing to commit" in commit_result.lower():
            results.append("ℹ️ 没有更改需要提交")
        return "\n".join(results)
    results.append(f"✅ 已提交: {message}")
    
    # 4. 推送
    if push:
        results.append("📤 正在推送到远程仓库...")
        push_result = git_push()
        if "❌" in push_result:
            results.append(f"⚠️ 推送失败: {push_result}")
        else:
            results.append(f"✅ 推送成功")
    
    results.append("━" * 50)
    results.append("🎉 工作流完成！")
    return "\n".join(results)

# ==================== GitHub SSH 连接配置 ====================

def setup_github_ssh() -> str:
    """配置 GitHub SSH 连接"""
    results = []
    results.append("🔑 GitHub SSH 配置")
    results.append("━" * 50)
    
    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(exist_ok=True)
    
    ssh_key_path = ssh_dir / "id_rsa"
    ssh_pub_path = ssh_dir / "id_rsa.pub"
    
    # 检查是否已有密钥
    if ssh_key_path.exists() and ssh_pub_path.exists():
        results.append("✅ SSH 密钥已存在")
        with open(ssh_pub_path, 'r') as f:
            pub_key = f.read().strip()
        results.append(f"\n📋 你的 SSH 公钥:\n{pub_key}")
        results.append("\n📌 请将此公钥添加到 GitHub:")
        results.append("   Settings → SSH and GPG keys → New SSH Key")
        results.append("   https://github.com/settings/keys")
        return "\n".join(results)
    
    # 生成新密钥
    email = input("📧 请输入你的 GitHub 邮箱: ").strip()
    if not email:
        return "❌ 邮箱不能为空"
    
    import subprocess
    # 生成密钥（无密码）
    result = subprocess.run(
        f'ssh-keygen -t rsa -b 4096 -C "{email}" -f "{ssh_key_path}" -N "" -q',
        shell=True,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        return f"❌ 生成密钥失败: {result.stderr}"
    
    results.append("✅ SSH 密钥生成成功")
    
    # 启动 ssh-agent 并添加密钥
    subprocess.run('ssh-agent', shell=True, capture_output=True)
    subprocess.run(f'ssh-add "{ssh_key_path}"', shell=True, capture_output=True)
    results.append("✅ SSH Agent 已启动")
    
    # 显示公钥
    if ssh_pub_path.exists():
        with open(ssh_pub_path, 'r') as f:
            pub_key = f.read().strip()
        results.append(f"\n📋 你的 SSH 公钥:\n{pub_key}")
        results.append("\n📌 请将此公钥添加到 GitHub:")
        results.append("   Settings → SSH and GPG keys → New SSH Key")
        results.append("   https://github.com/settings/keys")
        
        # 尝试复制到剪贴板
        try:
            import pyperclip
            pyperclip.copy(pub_key)
            results.append("✅ 公钥已复制到剪贴板！")
        except:
            pass
    
    return "\n".join(results)

def test_github_connection() -> str:
    """测试 GitHub 连接"""
    result = execute_powershell("ssh -T git@github.com", timeout=10)
    if "successfully authenticated" in result:
        return "✅ GitHub SSH 连接成功！\n" + result
    elif "Permission denied" in result:
        return "❌ SSH 连接失败（权限拒绝）。请检查:\n" + result
    else:
        return "❌ SSH 连接失败:\n" + result

def configure_git_user(name: str = "", email: str = "") -> str:
    """配置 Git 用户"""
    results = []
    if not name:
        name = input("请输入 Git 用户名: ").strip()
    if not email:
        email = input("请输入 Git 邮箱: ").strip()
    
    if name:
        result = _git_execute(f'config --global user.name "{name}"')
        results.append(f"✅ 用户名已设置: {name}")
    if email:
        result = _git_execute(f'config --global user.email "{email}"')
        results.append(f"✅ 邮箱已设置: {email}")
    
    return "\n".join(results) if results else "未配置任何信息"

# ==================== 命令解析（来自第一次代码） ====================

def parse_replace_request(user_input: str) -> dict:
    """
    从用户输入解析替换请求
    支持：把A改成B、将A替换为B、修改A为B 等
    """
    # 检测关键词
    if not any(k in user_input for k in ['改成', '替换', '改为', '换为', '修改为']):
        return None
    
    # 提取文件路径
    file_match = re.search(r'([A-Za-z]:[\\/][^\s]+\.\w+)', user_input)
    if not file_match:
        # 尝试匹配相对路径
        file_match = re.search(r'([^\s]+\.\w+)', user_input)
    if not file_match:
        return None
    filepath = file_match.group(1)
    
    # 尝试多种模式提取 old → new
    patterns = [
        r'把\s*["\']?([^"\']+)["\']?\s*改成\s*["\']?([^"\']+)["\']?',
        r'将\s*["\']?([^"\']+)["\']?\s*替换为\s*["\']?([^"\']+)["\']?',
        r'修改\s*["\']?([^"\']+)["\']?\s*为\s*["\']?([^"\']+)["\']?',
        r'把\s*([^\s]+)\s*改成\s*([^\s]+)',
        r'将\s*([^\s]+)\s*替换为\s*([^\s]+)',
    ]
    
    for pattern in patterns:
        m = re.search(pattern, user_input)
        if m:
            old_text = m.group(1).strip()
            new_text = m.group(2).strip()
            return {'filepath': filepath, 'old': old_text, 'new': new_text}
    
    return None

# ==================== 工具列表（包含所有 Git 功能） ====================

agent_tools = [
    # 基础文件操作
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取文件内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "文件路径"}
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "写入文件内容（覆盖模式）",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "要写入的内容"}
                },
                "required": ["filepath", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "replace_in_file",
            "description": "【精确替换】在文件中查找并替换指定内容。用于用户说'把A改成B'的场景。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "文件路径"},
                    "old_text": {"type": "string", "description": "要查找的旧内容"},
                    "new_text": {"type": "string", "description": "要替换成的新内容"}
                },
                "required": ["filepath", "old_text", "new_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "列出目录内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "目录路径，默认当前目录", "default": "."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_powershell",
            "description": "执行 PowerShell 命令",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的命令"},
                    "timeout": {"type": "integer", "description": "超时秒数", "default": 30}
                },
                "required": ["command"]
            }
        }
    },
    
    # Git 核心功能（来自第一次代码）
    {
        "type": "function",
        "function": {
            "name": "git_auto_workflow",
            "description": "【最常用】完整的 Git 工作流：自动执行 add → commit → push。用于提交代码、推送更新等场景。",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "提交信息"},
                    "files": {"type": "string", "description": "要添加的文件，默认 '.'", "default": "."},
                    "push": {"type": "boolean", "description": "是否推送", "default": True}
                },
                "required": ["message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "查看 Git 仓库状态",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_add",
            "description": "添加文件到暂存区",
            "parameters": {
                "type": "object",
                "properties": {
                    "files": {"type": "string", "description": "要添加的文件", "default": "."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": "提交暂存的更改",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "提交信息"}
                },
                "required": ["message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_push",
            "description": "推送到远程仓库",
            "parameters": {
                "type": "object",
                "properties": {
                    "remote": {"type": "string", "description": "远程名称", "default": "origin"},
                    "branch": {"type": "string", "description": "分支名称"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_pull",
            "description": "从远程拉取更新",
            "parameters": {
                "type": "object",
                "properties": {
                    "remote": {"type": "string", "description": "远程名称", "default": "origin"},
                    "branch": {"type": "string", "description": "分支名称"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_log",
            "description": "查看提交历史",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "显示数量", "default": 10}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_branch",
            "description": "查看所有分支",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_checkout",
            "description": "切换分支",
            "parameters": {
                "type": "object",
                "properties": {
                    "branch": {"type": "string", "description": "分支名称"}
                },
                "required": ["branch"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "查看变更差异",
            "parameters": {
                "type": "object",
                "properties": {
                    "staged": {"type": "boolean", "description": "是否查看暂存区", "default": False}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_clone",
            "description": "克隆远程仓库",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_url": {"type": "string", "description": "仓库 URL"},
                    "target_dir": {"type": "string", "description": "目标目录"}
                },
                "required": ["repo_url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_stash",
            "description": "暂存当前更改",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_stash_pop",
            "description": "恢复暂存的更改",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_reset",
            "description": "重置 Git 状态",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "description": "重置模式: soft/mixed/hard", "default": "mixed"},
                    "target": {"type": "string", "description": "目标提交", "default": "HEAD"}
                },
                "required": []
            }
        }
    },
    
    # GitHub 连接配置
    {
        "type": "function",
        "function": {
            "name": "setup_github_ssh",
            "description": "配置 GitHub SSH 连接（生成密钥、显示公钥）",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "test_github_connection",
            "description": "测试 GitHub SSH 连接是否成功",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "configure_git_user",
            "description": "配置 Git 用户名和邮箱",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "用户名"},
                    "email": {"type": "string", "description": "邮箱"}
                },
                "required": []
            }
        }
    }
]

# 标记 Git 工具（自动执行，无需确认）
GIT_TOOL_NAMES = {
    "git_auto_workflow", "git_status", "git_add", "git_commit", 
    "git_push", "git_pull", "git_log", "git_branch", "git_checkout",
    "git_diff", "git_clone", "git_stash", "git_stash_pop", "git_reset",
    "setup_github_ssh", "test_github_connection", "configure_git_user"
}

def is_git_tool(func_name: str) -> bool:
    return func_name in GIT_TOOL_NAMES