# Git & File System Agent Based on DeepSeek-v4-pro

This project is a Python-based, command-line AI coding assistant that connects to the DeepSeek API to provide an intelligent agent capable of direct local file manipulation and automated Git repository management.

---

## 🧠 Main Idea & Realization Logic

The core logic of this project bridges advanced LLM reasoning with direct local system and version control execution.

* **API & Reasoning:** The agent is powered by the DeepSeek API (`deepseek-chat`) and natively outputs its internal "thinking" or reasoning process to the console, allowing you to see how it formulates solutions before responding.


* **Tool Calling:** The application uses a strict JSON schema (`agent_tools`) to define the assistant's wide array of capabilities. When the AI determines an OS-level or Git action is necessary, it generates a structured tool call.


* **Action Routing:** The main loop intercepts these tool calls and routes them to specific Python functions (`read_file`, `replace_in_file`, `execute_powershell`, `git_auto_workflow`, etc.) designed to interact with your host system and code repository.


* **Security & Execution:** To prevent unintended system changes, the agent is securely sandboxed. It prompts the user for a `y/n` confirmation before executing any PowerShell commands or writing to files. However, to streamline the developer experience, standard Git operations are executed automatically without requiring manual confirmation. It also utilizes directory traversal checks (`is_safe_path`) to strictly confine file operations to the allowed base directory.



---

## ✨ Features

* **DeepSeek Integration:** Powered directly by the DeepSeek API with high reasoning effort enabled.


* **Transparent Reasoning:** Visually displays the AI's internal reasoning/thinking steps in the console before generating a final response.


* **Intelligent Git Automation:** Features a comprehensive suite of Git tools, including a `git_auto_workflow` that seamlessly handles adding, committing, and pushing code in one step. It also supports branching, diffing, logging, stashing, and cloning.


* **Precise Text Replacement:** Includes a specialized `replace_in_file` function designed to execute highly accurate, pinpoint text replacements based on user prompts like "change A to B".


* **GitHub SSH Configuration:** Built-in utilities (`setup_github_ssh`, `test_github_connection`, `configure_git_user`) allow the agent to seamlessly configure local Git user details and set up GitHub SSH keys.


* **System Interaction:** Explores directories, reads/writes files, and safely executes PowerShell commands with automatic output truncation for large payloads (capped at 4000 characters).


* **Interactive Safeguards:** Explicit user permission (`y/n`) is mandated prior to applying file modifications or running potentially dangerous system commands.



---

## 🛠️ User Workflow

Follow these steps to set up, run, and interact with the agent.

### 1. Environment Setup

Navigate to the project directory and create an isolated Python environment:

```bash
# Navigate to the project
cd PATH/TO/git_available_agent

# Create the virtual environment
python -m venv .venv

# Activate the environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install required dependencies
pip install openai

```

### 2. Running the Agent

* **Standard Launch (Windows):** Run the `run_agent.bat` file from the directory where it is located. This batch script automatically executes the application using the Python executable located inside the local `.venv\Scripts\` folder.


* **Custom Path Launch:** To run the agent from a different directory, modify and uncomment the secondary command in `run_agent.bat` to point to your specific absolute path.


* **API Key Prompt:** Upon starting, if the `DEEPSEEK_API_KEY` environment variable is not set, the agent will prompt you to input your API key directly into the terminal.



### 3. Interacting with the Assistant

* **Chatting:** Once the agent starts, simply type your queries (e.g., *"Change v1.0 to v2.0 in README.md"* or *"Commit and push these changes"*) into the terminal prompt.


* **Context Management:** Type `clear` to instantly wipe the conversational history (retaining only system prompts) and start fresh.


* **Interrupting:** If the AI is taking too long to think, press `Ctrl+C` to safely stop its reasoning process and start a new turn.


* **Exiting the Agent:** Type `exit` (or use `Ctrl+C` / `EOF`) at the prompt to close the application.



---

## 📂 Project Structure

* **`git_available_agent.py`:** The main entry point. It sets up the system prompts, connects to the DeepSeek API, manages the interactive CLI (complete with colored output formatting), handles user tool-call confirmations, and routes executions.


* **`agent_tools.py`:** Contains the underlying logic for all capabilities. This includes base file operations, precise string replacements, extensive Git tracking/workflow methods, PowerShell execution routing, and the `agent_tools` JSON schema list that instructs the AI on tool usage.


* **`run_agent.bat`:** A convenient Windows batch wrapper designed to easily bootstrap the agent from the correct virtual environment path without manual activation.