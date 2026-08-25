@echo off
REM ===============================================================================
REM Abaqus Simulation Agent 启动脚本
REM 前提：Abaqus/CAE 已启动、插件已加载并执行了 mcp_start()（状态为 running）
REM ===============================================================================

chcp 65001 >nul
cd /d "%~dp0"
"%~dp0.venv\Scripts\python.exe" "%~dp0abaqus_agent.py"
pause
