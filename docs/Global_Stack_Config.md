# Global Stack Config: AI Workflow Template

## 🧠 AI Orchestration Strategy
This project follows the **"Isolated Instances" Architecture**. Every project is treated as a self-contained context window to prevent cross-project hallucinations and minimize token drift.

## 🛠️ Toolchain
- **Primary Agents:**
  - **Gemini (Google)**: Large-context reasoning, multi-modal analysis, and architectural mapping.
  - **Claude (Anthropic)**: Precision coding, surgical refactors, and semantic consistency.
- **Local Intelligence:**
  - **Bonsai (Local LLM)**: Air-gapped reasoning and sensitive data processing.
- **Connectivity & Protocol:**
  - **Model Context Protocol (MCP)**: The bridge between LLMs and local/remote datasets.
  - **MCP Servers**: 
    - [Structure for specific extensions to be added here]

## 📋 Context Management Protocol
1. **Project_Context.md**: High-signal project summary for ingestion.
2. **CLAUDE.md**: Project-specific coding standards and rule enforcement.
3. **AGENTS.md**: Specific instructions for sub-agent handoffs.

---
*This file serves as a global baseline for manual sync across projects.*
