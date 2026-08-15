import sys
import json
from openai import OpenAI

# IMPORT YOUR TOOLS HERE
from agent_tools import read_file, write_file, list_files, execute_powershell, agent_tools

sys.stdout.reconfigure(encoding='utf-8')

YELLOW = "\033[93m"
CYAN = "\033[96m"
GREEN = "\033[92m"
DARK_GRAY = "\033[90m"
MAGENTA = "\033[95m"
RESET = "\033[0m"

client = OpenAI(
    api_key="sk-50427a897ede494dbab32b6e7496425b", 
    base_url="https://api.deepseek.com"            
)

chat_history = [
    {"role": "system", "content": "You are a helpful coding agent. You have the ability to read and write files on the user's local system using tools. Always inform the user of what you are doing. "
    "NOTE: You are restricted to the current working directory and its subdirectories. Do not attempt to use absolute paths outside of this project."}
]

print(f"{YELLOW}Agent started! Type 'exit' to quit.{RESET}")

while True:
    try:
        user_input = input(f"\n{YELLOW}You{RESET}\n> ")
    except (KeyboardInterrupt, EOFError):
        break 

    if user_input.strip().lower() == 'exit':
        print(f"{YELLOW}Goodbye!{RESET}")
        break

    chat_history.append({"role": "user", "content": user_input})

    while True:
        print(f"{DARK_GRAY}Thinking... (Press Ctrl+C to stop){RESET}")

        try:
            response = client.chat.completions.create(
                model="deepseek-v4-pro",
                messages=chat_history,
                tools=agent_tools, # <--- USE THE IMPORTED SCHEMA HERE
                stream=False,
                extra_body={
                    "thinking": {"type": "enabled"},
                    "reasoning_effort": "high"
                }
            )

            message = response.choices[0].message
            
            ai_thinking = getattr(message, 'reasoning_content', None)
            if ai_thinking is None and hasattr(message, 'model_extra') and message.model_extra:
                ai_thinking = message.model_extra.get('reasoning_content', "")
            
            if ai_thinking:
                print(f"\n{CYAN}--- AI Thinking ---{RESET}")
                print(f"{CYAN}{ai_thinking}{RESET}")

            chat_history.append(message)

            if message.tool_calls:
                for tool_call in message.tool_calls:
                    func_name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    
                    print(f"\n{MAGENTA}--- Executing Tool: {func_name} ---{RESET}")
                    
                    if func_name == "read_file":
                        print(f"{MAGENTA}Target: {args.get('filepath')}{RESET}")
                        result = read_file(args.get("filepath"))
                        
                    elif func_name == "write_file":
                        filepath = args.get("filepath")
                        content = args.get("content")
                        
                        print(f"\n{YELLOW}  WARNING: The agent wants to write/modify a file.{RESET}")
                        print(f"{YELLOW}Filepath: {filepath}{RESET}")
                        print(f"{DARK_GRAY}Preview of content: {content[:100]}...{RESET}")
                        
                        confirm = input(f"{YELLOW}Allow this action? (y/n): {RESET}").strip().lower()
                        
                        if confirm == 'y':
                            result = write_file(filepath, content)
                        else:
                            result = "Action blocked: The user denied permission to write this file."
                            print(f"{YELLOW}Action cancelled by user.{RESET}")
                            
                    elif func_name == "list_files":
                        directory = args.get("directory", ".")
                        print(f"{MAGENTA}Target Directory: {directory}{RESET}")
                        result = list_files(directory)

                    elif func_name == "execute_powershell":
                        command = args.get("command")
                        timeout = args.get("timeout", 30)  # Default to 30 if omitted by the agent
                        
                        print(f"\n{YELLOW}  WARNING: The agent wants to execute a PowerShell command.{RESET}")
                        print(f"{YELLOW}Command: {command}{RESET}")
                        
                        if timeout != 30:
                            print(f"{DARK_GRAY}Custom timeout: {timeout} seconds{RESET}")
                        
                        confirm = input(f"{YELLOW}Allow this execution? (y/n): {RESET}").strip().lower()
                        
                        if confirm == 'y':
                            print(f"{MAGENTA}Executing command...{RESET}")
                            # Assuming you imported execute_powershell at the top of your file
                            result = execute_powershell(command, timeout)
                        else:
                            result = "Action blocked: The user denied permission to execute this PowerShell command."
                            print(f"{YELLOW}Action cancelled by user.{RESET}")
                            
                    else:
                        result = f"Error: Unknown function {func_name}"

                    print(f"{MAGENTA}Tool Result: {result[:100]}...{RESET}")

                    chat_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": func_name,
                        "content": result
                    })
                
                continue
            
            else:
                ai_text = message.content or ""
                print(f"\n{GREEN}--- AI Response ---{RESET}")
                print(f"{GREEN}{ai_text}{RESET}")
                break 

        except KeyboardInterrupt:
            print(f"\n{YELLOW} AI thinking stopped by user. Starting a new turn...{RESET}")
            # Remove the last user message so we don't send two user messages in a row
            if chat_history and chat_history[-1]["role"] == "user":
                chat_history.pop()
            # Break out of the inner tool-calling loop and go back to user input
            break

        except Exception as e:
            print(f"\nError connecting to API or executing tool: {e}")
            break