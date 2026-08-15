@echo off

REM ===============================================================================
REM INSTRUCTIONS:
REM 1. Run this .bat file in the current directory where the .bat file is located.
REM 2. The second command is currently commented out. If you want to use it or run 
REM    it from another directory, you must modify the paths in the second command 
REM    to point to the correct PATH\TO\hello_world_agent on your system.
REM ===============================================================================

REM Run the agent in the current directory where the .bat file is located
"%~dp0.venv\Scripts\python.exe" "%~dp0hello_world_agent.py" 

REM Run the agent in another directory (Modify the PATH\TO\hello_world_agent if needed before uncommenting)
REM "D:\AI_Learn\AI-Learning-Repository\deepseek_api_test\hello_world_agent\.venv\Scripts\python.exe" "D:\AI_Learn\AI-Learning-Repository\deepseek_api_test\hello_world_agent\hello_world_agent.py"