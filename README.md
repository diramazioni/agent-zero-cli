# Agent Zero CLI Client

This project provides a command-line interface (CLI) client for interacting with Agent Zero, an AI assistant. It supports persistent chat sessions with history, command execution within messages, and system-wide installation for easy access.

## Features

-   **Persistent Chat History**: Engage in continuous conversations with Agent Zero. Your chat history is saved, allowing you to navigate previous messages with arrow keys and search with `Ctrl+R` (similar to Bash history).
-   **Default Persistent Mode**: Chat sessions are persistent by default, enabling seamless follow-up questions.
-   **One-Shot Mode**: Use the `-1` or `--one-shot` option for single-interaction queries where the script exits after receiving a response.
-   **In-Message Command Execution**: Embed shell commands within backticks (e.g., `` `ls -l` ``) directly in your messages. The CLI will execute these commands and replace them with their output before sending the message to Agent Zero.
-   **System-Wide Installation**: Install the client globally on your system, making it accessible from any directory using a convenient alias.
-   **`.env` Configuration**: Configure the Agent Zero MCP server URL using a `.env` file.
-   **File Inclusion (`@`)**: Include content from local files or remote URLs directly in your messages. The CLI will read the specified file or fetch the URL content and insert it into your message before sending it to Agent Zero.

## Installation

To install the Agent Zero CLI client system-wide, follow these steps:

1.  **Navigate to the project directory**:
    ```bash
    cd /path/to/your/agent-zero-cli
    ```

2.  **Run the installation script**:
    The `install.sh` script will make `agent_zero_cli.py` executable, copy it to `/usr/local/bin`, and create a symbolic link (alias) named `A0`.

    ```bash
    sudo ./install.sh
    ```

    You will see output similar to this:
    ```
    Installing Agent Zero CLI...
    1. Making agent_zero_cli.py executable...
    2. Copying agent_zero_cli.py to /usr/local/bin...
    3. Creating the 'A0' alias...
    4. Setting up system-wide configuration...
       - Configuration copied to /etc/agent_zero/.env
    ✅ Installation complete!
    You can now use 'A0' from anywhere in your terminal.
    ```

## Configuration (`.env`)

The client uses a `.env` file to configure the Agent Zero MCP server URL.

### Example `.env` file:

Create a file named `.env` in the root of your project directory (or in `/etc/agent_zero/` after installation) with the following content:

```dotenv
AGENT_ZERO_MCP_URL="http://localhost:5000"
```
replace the host and port accordingly

### Override Mechanics

The `agent_zero_cli.py` script looks for the `.env` file in two locations:

1.  **Local**: In the current working directory where the script is executed. This is useful for development or specific project configurations.
2.  **System-wide**: If not found locally, it checks `/etc/agent_zero/.env`. This is the default location for system-wide installations.

The local `.env` file takes precedence over the system-wide one.

## Usage

Once installed, you can use the `A0` alias from any terminal.

### Default Persistent Chat

By default, `A0` starts a persistent chat session. You can ask follow-up questions, and your input history will be saved.

```bash
A0 "Hello Agent Zero, how are you today?"
```

After the initial response, you will be prompted for follow-up questions:

```
💬 Your message: What can you do for me?
```

You can use **arrow keys (Up/Down)** to navigate through your command history and **Ctrl+R** to search the history.

To exit the persistent chat, type `quit`, `exit`, `q`, or press `Ctrl+C`.

### One-Shot Mode

For a single interaction without persistent history, use the `-1` or `--one-shot` option:

```bash
A0 -1 "What is the capital of France?"
```

The script will execute, provide a response, and then exit.

### Continuing an Existing Chat

If you have a `chat_id` from a previous persistent session, you can continue it:

```bash
A0 --chat-id "your_chat_id_here" "What was the last thing we discussed?"
```

### Executing Shell Commands within Messages

You can embed shell commands directly into your messages using backticks. The CLI will execute these commands and replace them with their output before sending the message to Agent Zero.

Example:

```bash
A0 "Can you tell me the current directory contents? `ls -la`"
```

The output will include the result of the `ls -la` command:

```
🔧 Executing: ls -la
✅ Command output (XXX chars)
📝 Processed initial message with command outputs:
📤 Sending to Agent Zero...
📨 Agent Zero Response:
(Agent Zero's response incorporating the command output)

### Including Files or URLs in Messages (`@`)

You can include the content of a local file or a remote URL in your message using the `@` prefix. The CLI will read the content and insert it into your message.

Example (local file):

```bash
A0 "Here is my code: @./src/main.py"
```

Example (remote URL):

```bash
A0 "Please summarize this article: @https://example.com/article.txt"
```

The CLI will check if it's a valid URL, but it will not process the url, it add a prompt to agent-zero to use the mcp tool `fetch` to fetch the content