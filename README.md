# 🇪🇺 EuroClaw

EuroClaw is an open-source, enterprise-grade agentic AI framework engineered for **absolute data sovereignty, zero-trust security, horizontal scalability, and operational flexibility**.

Designed to adhere strictly to European compliance and privacy boundaries, EuroClaw decouples your workflows from third-party US-hosted cloud dependencies.

> 🚀 **Release Status:** Core architecture is locked. Full enterprise release and documentation go **Live in July 2026**.

---

## 🛡️ Why EuroClaw? (The Mission)
EuroClaw wasn't built just to be another AI wrapper; it was engineered from the ground up to solve the critical adoption blockers faced by European enterprises, governments, and healthcare providers.

* **EU AI Act Compliance Built-In:** OpenTelemetry (OTel) logs every single LLM reasoning cycle and sandbox execution as an immutable trace.
* **True Air-Gapped Sovereignty:** Routes reasoning exclusively through local models and executes tools in zero-trust microVMs. Zero sensitive corporate data touches an external API.
* **Hardware & Cost Efficiency:** Optimized to run inference locally on standard unified-memory architecture before scaling out to sovereign data centers.
* **A European Digital Public Good:** Governed strictly under the Apache 2.0 license.

---

## ⚖️ Enterprise Governance & Safety
* **Federated Identity & SSO (OIDC/OAuth2):** Full support for modern Enterprise Single Sign-On via OpenID Connect and OAuth2.
* **Legacy Directory Bridging (LDAPS/AD):** Through Identity Brokers (like Keycloak), EuroClaw maps users from legacy on-premise AD and Secure LDAP (LDAPS) servers into modern execution roles.
* **Human-in-the-Loop (HITL) Checkpoints:** High-Risk tools pause execution and route an approval request to an administrator, maintaining state until authorization is granted.
* **Role-Based Tool Access (RBAC):** Strict capability bounding mapped directly to enterprise SSO groups.
* **Hardware-Level Sandboxing:** Utilizes **Firecracker MicroVMs** (KVM) to boot disposable, hardware-isolated Linux kernels for tool execution.

---

## 🌐 Execution Modes: Local vs. Distributed Cluster
EuroClaw separates the Orchestrator (decision-making) from the execution layer, allowing it to scale instantly from a single laptop to a 50-node data center cluster without rewriting code.

You control this via the `EXECUTION_MODE` variable in your `.env` file:

### Mode 1: Local (Synchronous)
Best for local development or single-server deployments. The Orchestrator waits and executes the tool locally.
   ```env
   EXECUTION_MODE="local"
   ```
### Mode 2: Distributed (Parallel Scaling)
Best for production. The Orchestrator drops the tool request into a Redis queue. Background worker nodes grab the tasks, process them in parallel inside Firecracker VMs, and return the results.
   ```
   EXECUTION_MODE="distributed"
   CELERY_BROKER_URL="redis://localhost:6379/0"
   CELERY_RESULT_BACKEND="redis://localhost:6379/1"
   ```

Booting a Distributed Worker Node:
Run this command on any secondary server connected to your Redis instance to spin up 4 parallel worker instances:

   ```
   celery -A src.worker celery_app worker --loglevel=info --concurrency=4
   ```
🛡️ Enterprise Use Case: Zero-Trust Processing of Sensitive Profiles
The Challenge:
An organization needs to process, summarize, and categorize highly sensitive biographical data (e.g., personal histories, healthcare logs, or digital memorial profiles). Sending this raw, unencrypted narrative data to a US-based cloud API violates local GDPR and data sovereignty policies.

The EuroClaw Solution:

Data Ingestion: The sensitive text profile is submitted to the EuroClaw Orchestrator.

Local Reasoning: The SovereignLLMGateway queries a local mistral model running on an air-gapped server (e.g., a Mac Mini M4 cluster) to determine what data needs to be extracted.

Isolated Execution: If the agent needs to run a data-transformation script, EuroClaw routes the task into a Firecracker MicroVM. The script executes, sanitizes the data, and the VM is instantly destroyed.

Immutable Audit: Every single step—from the LLM reasoning to the hardware execution—is logged to the local OpenTelemetry Jaeger database, proving exactly how the data was handled without ever leaking it to an external network.

### 🛠️ Quick Start & Environment Configuration
Clone the repository and configure your environment variables for core infrastructure, OIDC security, and enterprise messaging plugins.

   ``` Bash
   # Clone the repository
   git clone [https://github.com/astream2018/euroclaw.git](https://github.com/astream2018/euroclaw.git)
   cd euroclaw

   # Create your environment file
   cp .env_example .env

   # Create a virtual environment and install dependencies
   python -m venv venv
   source venv/bin/activate  # On Windows use: .\venv\Scripts\activate
   pip install -r requirements.txt
   pip install -e .
   ```
🚀 Developer Quick Start: Local LLM Inference
EuroClaw is optimized to run fully offline using local LLMs. For local development, we recommend using Ollama as your sovereign model provider.

Apple Silicon (Mac Mini M4 / M-Series)
Apple's unified memory architecture is exceptional for local AI inference, allowing you to run large models with high throughput.

Install Ollama:

   ```Bash
   brew install ollama
   ollama serve &
   ```

Install your model of choice:
   ```Bash
   ollama run mistral  # Or x/z-image-turbo, phi4, qwen3.5:9b etc.
   ```
Update your .env:
   ```
   LLM_PROVIDER="ollama"
   LLM_ENDPOINT="http://localhost:11434"
   DEFAULT_MODEL="mistral"
   ```
Windows (via WSL2)
Install Ollama:

   ```PowerShell
   wsl --install
   # Follow Ollama Linux installation inside WSL
   ```
Update your .env:

   ```
   LLM_PROVIDER="ollama"
   # If Ollama is running natively on Windows, WSL2 accesses it via the host IP
   LLM_ENDPOINT="[http://host.docker.internal:11434](http://host.docker.internal:11434)"
   DEFAULT_MODEL="mistral"
   ```
## 🏗️ Building Apps: Your Workspace Structure
When building custom AI agents with EuroClaw, structure your projects alongside the framework:

Plaintext
📁 my_projects/
├── 📁 euroclaw/            <-- The Framework Engine
└── 📁 my_instagram_agent/  <-- Your Custom App
   ├── .env
   ├── agents.yaml
   └── instagram_bot.py

🎓 Walkthrough: Building an Automated Instagram Agent
In this tutorial, we will build a real-world AI pipeline.

The Goal: Every day at 06:00 and 18:00, EuroClaw will design a branding image for our Open Source project. It will send the draft to Telegram for manual approval (Go/No-Go). If approved, it automatically posts to Instagram with generated hashtags.

1. Configure the Application Environment
Create a .env inside your my_instagram_agent folder:

   ```
   LLM_PROVIDER="ollama"
   LLM_ENDPOINT="http://localhost:11434"
   DEFAULT_MODEL="mistral"

   # Webhooks for your custom tools
   TELEGRAM_WEBHOOK_URL="[https://api.telegram.org/bot](https://api.telegram.org/bot)<YOUR_TOKEN>/sendMessage"
   INSTAGRAM_API_URL="[https://graph.facebook.com/v18.0/me/media](https://graph.facebook.com/v18.0/me/media)"
   ```
2. Define Your Agents
Create your agent profiles in agents.yaml:

   ```YAML
   agents:
   - name: "BrandStrategist"
      role: "Open Source Marketing Director"
      goal: "Generate high-converting image prompts and hashtags for our daily open-source software posts."
      backstory: "You are an expert in developer relations and open-source branding. You know exactly what visuals appeal to software engineers."
      llm_config:
         provider: "ollama"
         model: "mistral"
         endpoint_env_var: "LLM_ENDPOINT"
      allowed_tools:
         - "generate_image"
         - "request_telegram_approval"
         - "post_to_instagram"
      cron_schedule:
         - "06:00"
         - "18:00"
   ```

3. Write Your Application Logic
Create instagram_bot.py:

   ```Python
   import time
   import schedule
   from dotenv import load_dotenv

   # Import the EuroClaw engine
   from euroclaw.orchestrator import EuroclawOrchestrator
   from euroclaw.agent_loader import load_agents_from_yaml

   # 1. Load the local environment and agent configuration
   load_dotenv()
   agents_config = load_agents_from_yaml("agents.yaml")

   # Assuming load_agents returns a dict or list; adapt based on your loader logic
   # For this example, we grab the first matching agent
   strategist_profile = next(agent for agent in agents_config["agents"] if agent["name"] == "BrandStrategist")

   # 2. Initialize the EuroClaw Orchestrator
   orchestrator = EuroclawOrchestrator()
   orchestrator.name = strategist_profile["name"]

   def run_campaign():
      print(f"\n🚀 Starting Social Media Campaign...")
      prompt = "Create an image concept for Open Source Security and request Telegram approval."

      result = orchestrator.handle_request(prompt)
      print("\n--- CAMPAIGN RESULT ---")
      print(result)

   # 3. Dynamically load the schedule from your YAML file
   execution_times = strategist_profile.get("cron_schedule", [])

   print(f"Loading schedule for {orchestrator.name}...")
   for target_time in execution_times:
      schedule.every().day.at(target_time).do(run_campaign)
      print(f" - Scheduled daily run at {target_time}")

   while True:
      schedule.run_pending()
      time.sleep(60)
   ```

4. Execute
   ```
   python instagram_bot.py
   ```
