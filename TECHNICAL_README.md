# Jarvis Antigravity Agent: Technical Specification and Architecture Manual

## 1. System Overview and Core Philosophy

Jarvis Antigravity Agent is an autonomous engineering assistant designed as a headless, cost-free counterpart to Hermes-Agent, replacing commercial API endpoints with local invocations of the Google Antigravity Command Line Interface (agy). The system exposes full agentic reasoning, shell execution, filesystem mutation, and Model Context Protocol (MCP) integrations through a Telegram bot interface.

The design principles are:
1. Zero commercial API inference cost: All reasoning and tool-calling capabilities are derived from local agy CLI executions using Google frontier models without metered per-token API charges.
2. Complete network isolation on ingress: The daemon operates via outbound HTTPS long-polling to the Telegram Bot API servers. No incoming firewall ports, reverse proxies, or static public IP addresses are required.
3. Strict privacy and local processing: Voice messages are processed entirely on local hardware using faster-whisper quantized to 8-bit integers on CPU.
4. Process resilience: Subprocesses are isolated, monitored with strict execution timeouts, and capable of in-place self-updating without configuration loss.

## 2. Component Architecture

### 2.1. Telegram Bridge Daemon (main.py, handlers.py)
The daemon initializes an asynchronous long-polling event loop using python-telegram-bot. The application lifecycle is wired as follows:
- Authorization Filter: Every incoming update is evaluated against an allowed_users whitelist configured in Settings. Unauthorized requests are rejected immediately without invoking downstream execution pipelines.
- Message Demultiplexing: Dispatches incoming updates into text message handling, audio voice message handling, or explicit command handlers.
- Process Concurrency Guard: An asyncio.Lock (process_lock) ensures that only one primary foreground conversation interacts with the agy engine at a given moment, preventing race conditions on local filesystems and conversational context buffers.

### 2.2. Antigravity CLI Execution Engine (executor.py)
The execution engine acts as the intermediary between the Telegram bridge and the agy binary:
- Process Invocation: Spawns the agy executable as an asynchronous subprocess (asyncio.create_subprocess_exec).
- Command-Line Construction: Invokes agy with the autonomous execution flag (--dangerously-skip-permissions), the output format flag (--output-format stream-json), the optional model flag (--model), and the reasoning effort flag (--effort).
- Dynamic Model & Effort Routing: Active model and reasoning effort levels can be switched dynamically via Telegram commands (/model, /effort) or interactive inline keyboards, persisting selections across sessions in state.json.
- Context Maintenance: If the continue_session flag in state.json is active, the engine appends the continuation flag (-c), instructing agy to retain prior conversation and memory buffers.
- Stream JSON Processing: The standard output of agy is consumed line by line. Structured JSON events are decoded and processed in real time.
- Rate-Limited Feedback: Status messages on Telegram are edited dynamically to report progress as tools are invoked, subject to a configurable throttle interval (edit_throttle_seconds) to comply with Telegram API rate limits.
- Intermediate Agent Output: If agy produces conversational output prior to executing a tool, that output is dispatched immediately to Telegram, ensuring transparent visibility into multi-step operations.

### 2.3. Speech-to-Text Pipeline (stt.py)
Voice notes and audio files sent to the Telegram bot are transcribed locally:
- Temporary Ingestion: Audio payloads in Ogg Opus format (.oga) are downloaded into temporary file storage.
- Model Architecture: Transcriptions are performed using faster-whisper (CTranslate2 implementation of Whisper).
- Compute Specification: The default configuration employs the base model quantized to int8 on CPU, using a beam size of 5.
- Lifecycle: The Whisper model is instantiated lazily on the first audio update, keeping initial startup time and idle memory footprint minimal.
- Cleanup: Ingested temporary audio files are removed from the filesystem upon completion of the transcription step.

### 2.4. Autonomous Subagent Orchestrator (agent_manager.py)
For long-running, parallel, or exploratory tasks, Jarvis supports detached subagent execution:
- Isolation: Subagents run as distinct operating system processes with independent working directories and dedicated process identifiers.
- Concurrency: Background subagents execute outside the primary process lock, allowing the user to continue interactive conversations without waiting for task completion.
- Lifecycle Tracking: The SubagentManager tracks agent metadata, start time, termination time, execution status, process handles, and captured output buffers.
- Notification Delivery: Upon task termination, the subagent formats its result and delivers it directly to the designated Telegram chat through the internal notification utility.
- CLI Entrypoint: Registered as jarvis-spawn-agent in pyproject.toml, allowing both human operators and autonomous agents to spawn subagents from shell commands.

### 2.5. Model Context Protocol Subsystem (mcp.py)
The Model Context Protocol (MCP) subsystem allows Jarvis to interface with structured external tools:
- Configuration Storage: MCP server definitions are resolved from global configuration (typically ~/.gemini/config/mcp_config.json) or workspace configuration (.agents/mcp_config.json).
- Server Schema: Each server configuration specifies the command binary (such as npx, uvx, or docker), command-line arguments, and environment variables (such as API keys or access tokens).
- Programmatic and Command Management: The subsystem provides APIs and Telegram commands (/mcp list, /mcp add, /mcp remove) to register, query, and modify tool configurations.
- CLI Entrypoint: Exposed as jarvis-mcp for terminal-based configuration.

### 2.6. Continuous Delivery Self-Updater (updater.py)
The self-updater enables running instances to synchronize with the upstream GitHub repository:
- Non-destructive Synchronization: The updater identifies tracked repository files versus local personal files. User configurations (config.yaml, config.yml, config.json), environment secrets (.env), conversation state (state.json), and persistent memories (cognitive/MEMORY.md) are strictly preserved.
- Fast-Forward Verification: Updates are fetched from the remote tracking branch and merged using git merge --ff-only to prevent unintended divergence or merge conflicts.
- Dependency Synchronization: When updates include modified dependencies, the updater invokes uv sync to align the local virtual environment.
- Process Reload: Following an update, the daemon triggers a graceful reload by exiting with return code 143 (SIGTERM), which systemd monitors recognize as a restart trigger under Restart=always policies.

## 3. Communication and Data Protocols

### 3.1. Antigravity Stream JSON Protocol
When agy is invoked with --output-format stream-json, standard output delivers newline-delimited JSON objects. The bridge parses three primary event types:
1. Event step with state ACTIVE and step_type tool: Indicates tool execution. Tool parameters are inspected to construct descriptive user-facing strings (such as file reads, writes, terminal commands, or code searches).
2. Event step with state DONE and step_type agent_response: Contains text fragments emitted by the model during its reasoning phase.
3. Event result: Contains the terminal response payload and final status.

### 3.2. Deduplication Algorithm
Because agy may repeat introductory text in its final response that was already transmitted to the user during an intermediate step, the bridge implements a prefix deduplication routine. The clean terminal text is scanned against all previously dispatched intermediate chunks; if a matching prefix is identified, it is stripped before delivery.

## 4. Configuration Schema and Precedence

Settings are managed via Pydantic BaseSettings in config.py, adhering to the following precedence hierarchy (highest to lowest):
1. Runtime overrides passed directly to load_settings().
2. Environment variables prefixed with double underscores (for example, TELEGRAM__BOT_TOKEN).
3. Explicit configuration file path specified via JARVIS_CONFIG_PATH or AGY_TELEGRAM_CONFIG.
4. Local configuration files discovered in the working directory or project root (config.yaml, config.yml, config.json).
5. Dotenv file (.env).
6. Built-in defaults defined in Constants.

## 5. State Management and Fault Tolerance

- Session & Model State: Maintained in state.json. When an agy execution completes successfully, continue_session is set to true. When the user issues /new, continue_session is set to false, resetting the conversational context. Active model and reasoning effort selections (/model, /effort) are persisted under active_model and active_effort, persisting across system reloads and service restarts.
- Corrupted State Handling: If state.json is unreadable or malformed, the system falls back to default state parameters rather than aborting.
- Safety Timeouts: Process execution is bounded by process_timeout (default 360 seconds) and communicate_timeout (default 10 seconds). Exceeding these thresholds terminates the subprocess via SIGKILL and notifies the user.
- Restart Codes: Return codes -15, -9, 143, and 137 are treated as intentional lifecycle events, alerting the user that the bridge is reloading rather than treating the termination as a fatal failure.

## 6. Security Architecture

- Whitelist Authorization: Access control is strictly enforced on user ID rather than username, protecting against username spoofing.
- Execution Boundary: agy runs within the host system using the permissions of the executing user account. Running under a dedicated non-privileged user account is recommended.
- Outbound Exclusivity: Because no inbound network ports are opened, external network reconnaissance and unauthorized inbound connections are mitigated at the transport layer.
