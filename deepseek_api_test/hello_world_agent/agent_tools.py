import os
import subprocess
from pathlib import Path
# --- 1. The Python Functions ---

def read_file(filepath):
    # --- SECURITY CHECK ---
    if not is_safe_path(filepath):
        return f"Error: Access denied. You are only allowed to read files within {BASE_DIR}."
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

def write_file(filepath, content):
    # --- SECURITY CHECK ---
    if not is_safe_path(filepath):
        return f"Error: Access denied. You are only allowed to modify files within {BASE_DIR}."
    try:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote to {filepath}"
    except Exception as e:
        return f"Error writing file: {e}"

def list_files(directory="."):
    try:
        return str(os.listdir(directory)) 
    except Exception as e:
        return f"Error listing directory: {e}"


def execute_powershell(command: str, timeout: int = 30) -> str:
    """Executes a PowerShell command and returns the output or errors."""
    try:
        # -NoProfile skips loading user configs (makes it faster)
        # -NonInteractive prevents the shell from pausing for user input
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        output = result.stdout.strip()
        error = result.stderr.strip()
        
        # --- ADD MAX TRUNCATION HERE ---
        MAX_CHARS = 4000
        if len(output) > MAX_CHARS:
            output = output[:MAX_CHARS] + f"\n\n...[OUTPUT TRUNCATED: Exceeded {MAX_CHARS} characters]..."
        if len(error) > MAX_CHARS:
            error = error[:MAX_CHARS] + f"\n\n...[ERROR TRUNCATED: Exceeded {MAX_CHARS} characters]..."
        # ---------------------------
        
        # Handle successful execution
        if result.returncode == 0:
            if not output and not error:
                return "Command executed successfully with no output."
            # Sometimes PS writes to stderr even on success (e.g., warnings)
            return output if not error else f"Output:\n{output}\nWarnings:\n{error}"
            
        # Handle command failure
        else:
            return f"Command failed (Exit Code {result.returncode}).\nError:\n{error}\nOutput:\n{output}"
            
    except subprocess.TimeoutExpired:
        return f"Execution failed: Command timed out after {timeout} seconds. The agent must avoid interactive or infinite commands."
    except Exception as e:
        return f"Critical error executing command: {str(e)}"


# Get the absolute path of the directory containing the script
# Alternatively, use Path.cwd().resolve() if you want the working directory
# BASE_DIR = Path(__file__).parent.resolve()
BASE_DIR = Path.cwd().resolve()

def is_safe_path(target_path: str) -> bool:
    """
    Checks if the target_path is within the BASE_DIR.
    Prevents directory traversal attacks (e.g., '../../etc/passwd').
    """
    try:
        # .resolve() converts to absolute path and resolves all '..' and symlinks
        requested_path = Path(target_path).resolve()
        
        # .is_relative_to() checks if requested_path is inside BASE_DIR
        # Note: is_relative_to requires Python 3.9+
        return requested_path.is_relative_to(BASE_DIR)
    except Exception:
        # Fail closed: if path parsing fails, deny access
        return False

# --- 2. The JSON Schema ---

agent_tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads the content of a local file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "The path to the file to read."}
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Writes content to a local file. Overwrites existing content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "The path to the file."},
                    "content": {"type": "string", "description": "The exact content to write."}
                },
                "required": ["filepath", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "Lists all files and folders in a given directory. Helps you discover the local file structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "The path to the directory to explore (e.g., '.', './src'). Defaults to current directory."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_powershell",
            "description": (
                "Executes a PowerShell command on the host Windows machine. "
                "Use this to interact with the OS, manage files, run scripts, or retrieve system info. "
                "WARNING: You must never run interactive commands that require user input. "
                "Always use force flags (e.g., -Force, -Confirm:$false). "
                "You are strictly forbidden from reading, writing, or modifying any files outside the project directory using PowerShell."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string", 
                        "description": "The exact PowerShell command to execute."
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Optional timeout in seconds. Defaults to 30. Increase this only if you expect a long-running process.",
                        "default": 30
                    }
                },
                "required": ["command"]
            }
        }
    }
]