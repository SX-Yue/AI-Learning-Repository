# DeepSeek Local Coding Agent

This project is a Python-based command-line AI coding assistant that connects to the DeepSeek API to provide an intelligent agent capable of interacting directly with your local Windows environment.

---

## 🧠 Main Idea & Realization Logic

The core logic of this project bridges advanced LLM reasoning with direct local system execution.

* **API & Reasoning:** The agent is powered by the `deepseek-v4-pro` model via the OpenAI Python client. It natively outputs its internal "thinking" process to the console, allowing you to see how it formulates solutions before responding.


* **Tool Calling:** The application uses a strict JSON schema (`agent_tools`) to define the assistant's capabilities. When the AI determines an OS-level action is necessary, it generates a structured tool call.


* **Action Routing:** The main loop intercepts these tool calls and routes them to specific Python functions (`read_file`, `write_file`, `list_files`, `execute_powershell`) designed to interact with the host system.


* **Security & Execution:** To prevent unintended system changes, the agent is securely sandboxed. It prompts the user for a `y/n` confirmation before executing any PowerShell commands or modifying files, and utilizes directory traversal checks to strictly confine operations to the project folder.



---

## ✨ Features

* **DeepSeek Integration:** Powered by the `deepseek-v4-pro` model.


* **Transparent Reasoning:** Visually displays the AI's internal thinking in the console before generating a final response.


* **System Interaction:** Explores directories, reads/writes files, and executes PowerShell commands.


* **Smart Output Handling:** Large PowerShell outputs or errors are automatically truncated at 4000 characters to maintain context window efficiency.


* **Interactive Safeguards:** Requires explicit user permission (`y/n`) before applying file modifications or running system commands.


* **Directory Traversal Protection:** Built-in `is_safe_path` checks restrict all file reading and writing operations to the current working directory and its subdirectories.



---

## 🛠️ User Workflow

Follow these steps to set up, run, and interact with the agent.

### 1. Environment Setup

Navigate to the project directory and create an isolated Python environment:

```bash
# Navigate to the project
cd PATH/TO/hello_world_agent

# Create the virtual environment
python3 -m venv .venv  # macOS/Linux
python -m venv .venv   # Windows

# Activate the environment
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

```

*(You will know it is active when `(.venv)` appears at the start of your terminal prompt.)*

### 2. Running the Agent

* **Standard Launch:** Run the `run_agent.bat` file in the current directory. This batch script automatically executes the application using the Python executable located inside the local `.venv\Scripts\` folder.


* **Custom Path Launch:** To run the agent from a different directory, modify and uncomment the secondary command in `run_agent.bat` to point to your specific project path.



### 3. Interacting with the Assistant

* **Chatting:** Once the agent starts, type your queries into the terminal prompt.


* **Interrupting:** If the AI is taking too long to think, press `Ctrl+C` to safely stop its reasoning process and start a new turn.


* **Exiting the Agent:** Type `exit` at the prompt to close the application.


* **Deactivating the Environment:** When you are completely finished, type `deactivate` in your terminal to return to your global Python environment.

---

## 📂 Project Structure

* **`hello_world_agent.py`:** The main entry point that manages the CLI interface with colored text formatting, maintains chat history, handles the DeepSeek API connection, and routes the AI's tool-call requests.


* **`agent_tools.py`:** Contains the underlying logic for the agent's capabilities. It defines the system interaction functions and supplies the JSON schema (`agent_tools`) that instructs the AI on how to use them.


* **`run_agent.bat`:** A convenient Windows batch wrapper designed to easily bootstrap the agent from the correct virtual environment path.