# Contributing to EuroClaw

Thank you for your interest in contributing to EuroClaw! We are building the foundational, sovereign AI orchestration framework for Europe, and community contributions are essential.

## Development Process

1. **Fork the repository** and create your branch from `main`.
2. **Set up the local environment** using `make install` and `make up`.
3. **Write tests** for your code. If you are adding a new feature, ensure it does not bypass the Human-in-the-Loop (HITL) or RBAC security layers.
4. **Ensure tracing is intact.** If you add a new tool or gateway, you must instrument it with OpenTelemetry child spans to maintain EU AI Act compliance audits.
5. **Issue a Pull Request (PR)** with a clear description of the problem and the solution.

## Developing Plugins

We welcome new enterprise messaging plugins (e.g., Mattermost, Discord, SAP connectors). To submit a plugin:
* It must inherit from the `MessagingPlugin` abstract base class in `plugins/base.py`.
* It must NOT introduce blocking network calls that freeze the asynchronous Orchestrator loop.
* Provide an example `.env` configuration for your plugin in the documentation.

## Developer Certificate of Origin (DCO)
To ensure the legal integrity of the codebase under the Apache 2.0 license, we require all commits to be signed off. By using the `git commit -s` command, you agree to the DCO.

## Code of Conduct
By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).
