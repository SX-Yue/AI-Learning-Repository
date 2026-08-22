@echo off

REM ===============================================================================
REM INSTRUCTIONS:
REM 1. Run this .bat file in the current directory where the .bat file is located.
REM 2. The second command is currently commented out. If you want to use it or run 
REM    it from another directory, you must modify the paths in the second command 
REM    to point to the correct PATH\TO\main_agent on your system.
REM ===============================================================================

REM Run the agent in the current directory where the .bat file is located
"%~dp0.venv\Scripts\python.exe" "%~dp0main_agent.py" 

REM Run the agent in another directory
REM "D:\AI_Learn\AI-Learning-Repository\deepseek_api_test\literature_search_agent_ver2\.venv\Scripts\python.exe" ^
REM "D:\AI_Learn\AI-Learning-Repository\deepseek_api_test\literature_search_agent_ver2\main_agent.py"