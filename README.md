# 🇪🇺 EuroClaw

EuroClaw is an open-source, enterprise-grade agentic AI framework engineered for **absolute data sovereignty, zero-trust security, horizontal scalability, and operational flexibility**. Designed to adhere strictly to European compliance and privacy boundaries, EuroClaw decouples your workflows from third-party US-hosted cloud dependencies.

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

## 🛠️ Quick Start & Environment Configuration

Rename `.env_example` to  `.env`  in your root directory to configure the core infrastructure, OIDC security, and enterprise messaging plugins.

