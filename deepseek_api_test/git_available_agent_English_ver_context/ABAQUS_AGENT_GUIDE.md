# 自然语言驱动 Abaqus 仿真 —— 操作指南

通过 PowerShell 中的自建 DeepSeek Agent，用中文自然语言完成一次完整的 Abaqus/CAE 仿真。

---

## 一、整体架构

```
PowerShell 终端（你在这里输入自然语言）
   │
   ▼
abaqus_agent.py  ── DeepSeek API（带 8 个 Function Calling 工具定义）
   │                    │ 模型返回 tool_calls
   │                    ▼
   │         abaqus_bridge.route_abaqus_tool()  （工具路由分发）
   │                    │
   │                    ▼
   │         写命令文件 commands/cmd_xxx.json（文件 IPC，无 socket）
   │                    │
   ▼                    ▼
Abaqus/CAE 内核中 abaqus_mcp_plugin.py 轮询执行 → 写回 results/xxx.json
```

**关键点**：AI 只负责"想"，真正执行建模/求解的是运行在 Abaqus 内核里的插件。二者通过 JSON 文件目录通信。

---

## 二、一次性准备工作

### 1. 启动 Abaqus 侧（每次都要做，除非配置了自动加载）

| 步骤 | 操作 |
|---|---|
| ① 启动 | 打开 Abaqus/CAE |
| ② 加载插件 | `File → Run Script...` → 选择 `C:\Users\18801\Desktop\text-to-cae\abaqus-mcp-main\abaqus_mcp_plugin.py` |
| ③ 启动轮询 | 在 Abaqus 命令行执行：`mcp_start()` |

> 💡 **可选**：把 `abaqus_v6.env.example` 复制为 `C:\Users\18801\abaqus_v6.env`，以后 Abaqus 启动自动加载插件，只需执行 `mcp_start()`。

### 2. 验证插件状态

```powershell
Get-Content "$env:USERPROFILE\.abaqus-mcp\status.json"
```

期望看到 `"status": "running"` 且时间戳新鲜（每 2 秒更新一次）。

### 3. 启动 Agent（PowerShell）

```powershell
cd D:\AI_Learn\AI-Learning-Repository\deepseek_api_test\git_available_agent_English_ver_context
run_abaqus_agent.bat
```

> 首次运行若未设置 `DEEPSEEK_API_KEY` 环境变量，会提示输入。

---

## 三、使用示例（直接说中文）

启动后你会看到连通性自检结果，然后直接输入自然语言：

```
> 检查一下 Abaqus 是否在线

> 帮我建一个悬臂梁，长100mm、宽20mm、高5mm，材料用钢（弹性模量210000MPa，泊松比0.3），
  一端完全固定，另一端施加向下的集中力1000N

> 划分网格，单元尺寸5mm

> 提交分析作业

> 打开ODB结果，告诉我最大应力在哪

> 截取当前视口的应力云图，保存到 abaqus_results\vonmises.png
```

Agent 会自动：
1. `check_connection()` 确认在线 → 2. `get_model_info()` 看会话状态 → 3. `execute_script()` 逐步建模 → 4. `submit_job()` 求解 → 5. `get_odb_info()` 读结果 → 6. `get_viewport_image()` 截图，最后输出中文仿真报告。

---

## 四、Agent 拥有的 8 个工具

| 工具 | 作用 |
|---|---|
| `check_connection` | 检查 Abaqus 是否在线、插件是否响应 |
| `ping` | 连通性测试 |
| `execute_script` | 在 Abaqus 内核执行 Python 脚本（建模/材料/网格/求解全流程） |
| `get_model_info` | 查询模型：部件/材料/分析步/载荷/边界/相互作用/装配 |
| `list_jobs` | 列出已定义的作业 |
| `submit_job` | 提交作业并等待完成（600s 超时） |
| `get_odb_info` | 只读打开 ODB 结果，返回步/帧/部件/实例 |
| `get_viewport_image` | 截取视口图像（建议填 `save_path` 存文件省 tokens） |

---

## 五、常见问题排查

| 现象 | 原因 / 解决 |
|---|---|
| 自检显示"插件未找到 status.json" | Abaqus 没启动或插件没加载 |
| 状态是 `ready` 而非 `running` | 还没执行 `mcp_start()`，去 Abaqus 命令行执行 |
| `execute_script` 超时（30s） | 脚本太大或插件没在轮询；重试或拆小脚本 |
| `submit_job` 超时（600s） | 求解时间过长；可让 AI 分步执行 |
| 中文乱码 | 确认用 `run_abaqus_agent.bat` 启动（含 `chcp 65001`） |
| 后台线程模式不稳定 | 在 Abaqus 里改用 `mcp_loop()`（阻塞式，最稳） |

---

## 六、相关文件

| 文件 | 说明 |
|---|---|
| `abaqus_agent.py` | 自然语言仿真 Agent 主程序（本次新增） |
| `abaqus_bridge.py` | 文件 IPC 桥接模块（复制自 abaqus-mcp 项目，含工具定义与路由） |
| `run_abaqus_agent.bat` | Agent 启动脚本（本次新增） |
| `main_agent.py` / `agent_tools.py` | 原有的文件/Git 操作 Agent（未改动） |
