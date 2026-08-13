import sys
from openai import OpenAI

# 1. Force the Python console to read and write in UTF-8
sys.stdout.reconfigure(encoding='utf-8')

# ANSI escape codes to replicate PowerShell's Write-Host -ForegroundColor
YELLOW = "\033[93m"
CYAN = "\033[96m"
GREEN = "\033[92m"
DARK_GRAY = "\033[90m"
RESET = "\033[0m"

# 2. Setup the OpenAI client (pointing to DeepSeek's API)
client = OpenAI(
    api_key="sk-50427a897ede494dbab32b6e7496425b", # Put your key here
    base_url="https://api.deepseek.com"            # Override base URL for DeepSeek
)

# 3. Create a list to act as the AI's "Memory"
chat_history = [
    {"role": "system", "content": "You are a helpful assistant."}
]

print(f"{YELLOW}Chat started! Type 'exit' to quit.{RESET}")

# 4. Start an infinite loop to keep the conversation going
while True:
    try:
        # Get your input from the console
        user_input = input(f"\n{YELLOW}You{RESET}\n> ")
    except (KeyboardInterrupt, EOFError):
        break # Gracefully handle Ctrl+C

    # If you type 'exit', break the loop and end the script
    if user_input.strip().lower() == 'exit':
        print(f"{YELLOW}Goodbye!{RESET}")
        break

    # Add your new message to the chat history memory
    chat_history.append({"role": "user", "content": user_input})

    print(f"{DARK_GRAY}Thinking...{RESET}")

    try:
        # Send the request
        # Note: extra_body is used to pass DeepSeek-specific parameters 
        # that aren't native to standard OpenAI models.
        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=chat_history,
            stream=False,
            extra_body={
                "thinking": {"type": "enabled"},
                "reasoning_effort": "high"
            }
        )

        message = response.choices[0].message
        
        # Extract the text
        ai_text = message.content or ""
        
        # Extract reasoning content (DeepSeek sends this alongside standard content)
        # We check model_extra in case the standard library doesn't parse it natively
        ai_thinking = getattr(message, 'reasoning_content', None)
        if ai_thinking is None and hasattr(message, 'model_extra') and message.model_extra:
            ai_thinking = message.model_extra.get('reasoning_content', "")
        
        # Print the AI's response with colors
        print(f"\n{CYAN}--- AI Thinking ---{RESET}")
        print(f"{CYAN}{ai_thinking}{RESET}")
        
        print(f"\n{GREEN}--- AI Response ---{RESET}")
        print(f"{GREEN}{ai_text}{RESET}")

        # VERY IMPORTANT: Add the AI's response to the memory so it remembers this for next time!
        chat_history.append({"role": "assistant", "content": ai_text})

    except Exception as e:
        print(f"\nError connecting to API: {e}")