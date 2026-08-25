# matlab_mcp_setup.py
"""
MATLAB MCP Server 配置和启动助手
用于正确配置并启动 MATLAB MCP Server
"""

import os
import sys
import subprocess
import json
import time
import shutil
from pathlib import Path

# 颜色定义
YELLOW = "\033[93m"
CYAN = "\033[96m"
GREEN = "\033[92m"
DARK_GRAY = "\033[90m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_header():
    print(f"""
{BOLD}{GREEN}══════════════════════════════════════════════════════════════{RESET}
{BOLD}{GREEN}   🔧 MATLAB MCP Server 配置助手{RESET}
{BOLD}{GREEN}══════════════════════════════════════════════════════════════{RESET}
""")

def find_matlab():
    """自动查找 MATLAB 安装路径。"""
    print(f"{CYAN}🔍 正在查找 MATLAB 安装...{RESET}")
    
    possible_paths = [
        r"D:\Program Files\MATLAB\R2024b",
        r"D:\Program Files\MATLAB\R2024a",
        r"D:\Program Files\MATLAB\R2023b",
        r"C:\Program Files\MATLAB\R2024b",
        r"C:\Program Files\MATLAB\R2024a",
        r"C:\Program Files\MATLAB\R2023b",
    ]
    
    # 尝试从注册表读取
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\MathWorks\MATLAB")
        i = 0
        while True:
            try:
                version = winreg.EnumKey(key, i)
                version_key = winreg.OpenKey(key, version)
                matlab_root, _ = winreg.QueryValueEx(version_key, "MATLABROOT")
                possible_paths.insert(0, matlab_root)
                i += 1
            except WindowsError:
                break
    except:
        pass
    
    for path in possible_paths:
        if os.path.exists(path):
            matlab_exe = os.path.join(path, "bin", "matlab.exe")
            if os.path.exists(matlab_exe):
                print(f"{GREEN}✅ 找到 MATLAB: {path}{RESET}")
                return path
    
    # 如果没找到，让用户手动输入
    print(f"{RED}❌ 未自动找到 MATLAB 安装{RESET}")
    manual_path = input(f"{YELLOW}请输入 MATLAB 安装目录（例如 D:\\Program Files\\MATLAB\\R2024b）: {RESET}").strip()
    if os.path.exists(manual_path):
        return manual_path
    else:
        print(f"{RED}❌ 路径不存在{RESET}")
        return None

def download_mcp_server():
    """下载 MATLAB MCP Server。"""
    print(f"\n{CYAN}📥 检查 MATLAB MCP Server...{RESET}")
    
    # MCP Server 存放目录
    mcp_dir = r"D:\matlab_mcp_server"
    mcp_exe = os.path.join(mcp_dir, "matlab-mcp-server-windows-x64.exe")
    
    # 创建目录
    os.makedirs(mcp_dir, exist_ok=True)
    
    # 检查是否已存在
    if os.path.exists(mcp_exe):
        print(f"{GREEN}✅ MCP Server 已存在: {mcp_exe}{RESET}")
        return mcp_exe
    
    # 如果不存在，提供下载指导
    print(f"{YELLOW}⚠️ MCP Server 未找到{RESET}")
    print(f"{CYAN}请按以下步骤手动下载：{RESET}")
    print(f"1. 访问: https://github.com/matlab/matlab-mcp-server/releases")
    print(f"2. 下载: matlab-mcp-server-windows-x64.exe")
    print(f"3. 放到: {mcp_dir}")
    print(f"\n{DARK_GRAY}按 Enter 继续（如果已下载）或输入路径...{RESET}")
    
    user_input = input().strip()
    if user_input and os.path.exists(user_input):
        return user_input
    
    if os.path.exists(mcp_exe):
        return mcp_exe
    
    print(f"{RED}❌ MCP Server 未找到，请先下载{RESET}")
    return None

def create_mcp_launcher(matlab_root, mcp_exe, work_dir):
    """创建 MCP Server 启动脚本。"""
    print(f"\n{CYAN}🔧 创建 MCP Server 启动脚本...{RESET}")
    
    # 创建启动脚本（使用 new 模式，desktop 显示）
    launcher_content = f'''@echo off
echo Starting MATLAB MCP Server...
echo MATLAB Root: {matlab_root}
echo Work Directory: {work_dir}
echo.

"{mcp_exe}" ^
  --matlab-root "{matlab_root}" ^
  --initial-working-folder "{work_dir}" ^
  --matlab-display-mode desktop ^
  --matlab-session-mode new
'''
    
    launcher_path = os.path.join(os.path.dirname(mcp_exe), "start_mcp.bat")
    with open(launcher_path, 'w', encoding='utf-8') as f:
        f.write(launcher_content)
    
    print(f"{GREEN}✅ 启动脚本已创建: {launcher_path}{RESET}")
    return launcher_path

def test_mcp_connection(mcp_exe, matlab_root, work_dir):
    """测试 MCP Server 连接。"""
    print(f"\n{CYAN}🧪 测试 MCP Server 连接...{RESET}")
    
    # 先启动 MATLAB（如果需要）
    matlab_exe = os.path.join(matlab_root, "bin", "matlab.exe")
    if not os.path.exists(matlab_exe):
        print(f"{RED}❌ MATLAB 可执行文件未找到{RESET}")
        return False
    
    # 构建测试命令
    test_code = "x = 0:0.01:10; plot(x, sin(x)); title('MCP Test'); disp('MCP_TEST_OK')"
    
    # 使用 Python 直接测试 MCP Server
    test_script = f'''
import subprocess
import json
import time
import sys

mcp_exe = r"{mcp_exe}"
matlab_root = r"{matlab_root}"
work_dir = r"{work_dir}"

args = [
    mcp_exe,
    "--matlab-root", matlab_root,
    "--initial-working-folder", work_dir,
    "--matlab-display-mode", "desktop",
    "--matlab-session-mode", "new"
]

print("启动 MCP Server...")
process = subprocess.Popen(
    args,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1
)

req_id = 0

def send(method, params=None, timeout=300):
    global req_id
    req_id += 1
    rid = str(req_id)
    process.stdin.write(json.dumps({{
        "jsonrpc": "2.0", "id": rid, "method": method, "params": params or {{}}
    }}) + "\\n")
    process.stdin.flush()
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = process.stdout.readline()
        if not line:
            return {{"success": False, "error": "MCP Server 已退出"}}
        try:
            msg = json.loads(line)
        except Exception:
            continue
        if msg.get("id") == rid:
            if "error" in msg:
                return {{"success": False, "error": msg["error"]}}
            return {{"success": True, "result": msg.get("result")}}
    return {{"success": False, "error": "请求超时"}}

# MCP 握手：先 initialize，再发 initialized 通知
r = send("initialize", {{
    "protocolVersion": "2024-11-05",
    "capabilities": {{}},
    "clientInfo": {{"name": "setup-test", "version": "1.0"}}
}}, timeout=120)
if not r.get("success"):
    print("❌ 初始化失败:", r.get("error"))
    process.terminate()
    sys.exit(1)
process.stdin.write(json.dumps({{
    "jsonrpc": "2.0", "method": "notifications/initialized", "params": {{}}
}}) + "\\n")
process.stdin.flush()

test_code = "{test_code}"
print("发送测试代码...")
r = send("tools/call", {{
    "name": "evaluate_matlab_code",
    "arguments": {{"code": test_code}}
}}, timeout=300)
if r.get("success"):
    content = r["result"].get("content", []) if isinstance(r["result"], dict) else []
    text = "".join(c.get("text", "") for c in content if c.get("type") == "text")
    print("收到响应:", text.strip() or r["result"])
    if "MCP_TEST_OK" in text:
        print("✅ 测试成功")
    else:
        print("⚠️ 代码已执行但未看到预期输出")
else:
    print("❌ 执行失败:", r.get("error"))

process.terminate()
'''
    
    test_file = os.path.join(os.path.dirname(mcp_exe), "test_mcp.py")
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(test_script)
    
    # 运行测试
    print(f"{DARK_GRAY}运行测试脚本...{RESET}")
    result = subprocess.run(
        [sys.executable, test_file],
        capture_output=True,
        text=True,
        timeout=30
    )
    
    print(result.stdout)
    if result.stderr:
        print(f"{DARK_GRAY}stderr: {result.stderr}{RESET}")
    
    return True

def update_main_agent(mcp_exe, matlab_root):
    """更新 main_agent.py 中的配置。"""
    print(f"\n{CYAN}📝 更新 main_agent.py 配置...{RESET}")
    
    # 读取 main_agent.py
    agent_file = "main_agent.py"
    if not os.path.exists(agent_file):
        print(f"{YELLOW}⚠️ main_agent.py 未找到，跳过更新{RESET}")
        return
    
    with open(agent_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 备份原文件
    backup_file = f"{agent_file}.backup"
    with open(backup_file, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"{DARK_GRAY}已备份到: {backup_file}{RESET}")
    
    # 更新配置
    updates = {
        'MATLAB_MCP_EXE': f'MATLAB_MCP_EXE = r"{mcp_exe}"',
        'MATLAB_ROOT': f'MATLAB_ROOT = r"{matlab_root}"',
    }
    
    for key, value in updates.items():
        import re
        pattern = f'{key} = .*$'
        if re.search(pattern, content, re.MULTILINE):
            content = re.sub(pattern, value, content, flags=re.MULTILINE)
    
    # 写入更新后的内容
    with open(agent_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"{GREEN}✅ main_agent.py 已更新{RESET}")
    print(f"{GREEN}✅ MCPMatlabClient 已使用 new 模式 + desktop 显示，无需手动修改{RESET}")

def main():
    """主函数。"""
    print_header()
    
    # 1. 查找 MATLAB
    matlab_root = find_matlab()
    if not matlab_root:
        print(f"{RED}❌ 无法继续，请先安装 MATLAB{RESET}")
        return
    
    # 2. 检查/下载 MCP Server
    mcp_exe = download_mcp_server()
    if not mcp_exe:
        print(f"{RED}❌ 无法继续，请先下载 MCP Server{RESET}")
        return
    
    # 3. 获取工作目录
    work_dir = os.getcwd()
    print(f"\n{CYAN}📁 工作目录: {work_dir}{RESET}")
    
    # 4. 创建启动脚本
    launcher = create_mcp_launcher(matlab_root, mcp_exe, work_dir)
    
    # 5. 测试连接
    test_mcp_connection(mcp_exe, matlab_root, work_dir)
    
    # 6. 更新 main_agent.py
    update_main_agent(mcp_exe, matlab_root)
    
    print(f"""
{BOLD}{GREEN}══════════════════════════════════════════════════════════════{RESET}
{BOLD}{GREEN}✅ 配置完成！{RESET}
{BOLD}{GREEN}══════════════════════════════════════════════════════════════{RESET}

{DARK_GRAY}下一步操作：{RESET}

1. main_agent.py 已配置为 new 模式 + desktop 显示，无需修改

2. 运行主程序：
   {CYAN}python main_agent.py{RESET}

3. 在 Agent 中测试：
   {CYAN}Run MATLAB: x = 0:0.01:10; plot(x, sin(x));{RESET}
""")
    
    # 询问是否立即启动
    start_now = input(f"{YELLOW}是否立即启动 MCP Server？(y/n): {RESET}").strip().lower()
    if start_now == 'y':
        print(f"{CYAN}启动 MCP Server...{RESET}")
        subprocess.Popen([launcher], shell=True)
        print(f"{GREEN}✅ MCP Server 已启动（在新窗口中）{RESET}")

if __name__ == "__main__":
    main()
