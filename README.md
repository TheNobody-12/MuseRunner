# 🛡️ MuseRunner

**A verifiable, zero-trust AI quality engineering control plane that translates BDD specs into self-healing Playwright, Robot Framework, and legacy desktop automation.**

[![Meta Global AI Hackathon 2026](https://img.shields.io/badge/Meta_Global_AI_Hackathon-2026-0668E1?style=for-the-badge&logo=meta)](https://cerebralvalley.ai)
[![Track: Indie Developer](https://img.shields.io/badge/Track-Indie_Developer-success?style=for-the-badge)]()
[![Model: Muse Spark Open](https://img.shields.io/badge/Model-muse--spark--open--1026-blue?style=for-the-badge)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

> **Hackathon Compliance Declaration (Rule 4 - New Work Only):**  
> 100% of the architecture, codebase, guardrails, and worker integrations in this repository were designed and built from scratch during the **Meta Global AI Developer Hackathon (October 26 – November 4, 2026)**.

---

## 🎥 3-Minute Live Demo & Viral Post
* 📺 **Watch the 3-Minute Demo Video:** `[Insert YouTube / Loom Link Here]`
* 🐦 **X (Twitter) Launch Thread:** `[Insert X Post Link Here]`

---

## 🚨 The Problem

Enterprise Quality Engineering (QE) teams in regulated industries (finance, banking, healthcare, insurance) face three compounding bottlenecks:
1. **Brittle Selectors & Flaky Pipelines:** A minor frontend deployment that alters a single CSS class or button ID breaks hundreds of Playwright, Selenium, and Robot Framework tests.
2. **Legacy Desktop Lock-In:** Critical enterprise workflows still traverse legacy Windows desktop applications (`Win32`/`pywinauto`), Citrix virtual machines, and canvas interfaces where clean DOM trees do not exist.
3. **Compliance & PII Blockers:** Regulated enterprises cannot adopt off-the-shelf AI testing agents because sending raw DOM snapshots containing customer PII, account numbers, or session tokens to external LLM APIs violates strict zero-trust governance.

---

## 💡 The Solution: MuseRunner

**MuseRunner** is an autonomous, multi-agent QE control plane built on Meta's newest multimodal and open-weight models. It acts as a universal translation, execution, and self-healing layer between human BDD specifications (`Given / When / Then`) and heterogeneous execution runtimes (**Playwright**, **Robot Framework**, and **Pywinauto**), wrapped inside a cryptographic compliance boundary.

### Key Capabilities
* **🔒 Pre-Inference Zero-Trust PII Guardrail:** Deterministic regex + NER interceptor scrubs sensitive customer data (`SSN/SIN`, credit cards, credentials, API keys) into reversible local vault tokens (`{{REDACTED_SIN_1}}`) *before* any payload leaves the local environment.
* **🎙️ Voice-to-BDD Spec Synthesis:** QA engineers can speak bug reports or test scenarios directly into the dashboard using **Muse Voice Transcribe**, automatically generating structured Gherkin `.feature` files.
* **🧠 Verifiable Multi-Runtime Orchestration:** Powered by `meta-models/muse-spark-open-1026` on Baseten, translating Gherkin clauses into strongly typed Pydantic tool calls across Web and Desktop workers.
* **🩹 Autonomous Visual & DOM Self-Healing:** When a UI selector breaks at runtime, MuseRunner pauses the test, captures the failure state, uses **SAM 3.1** to visually segment moved buttons or legacy desktop controls, and invokes **Muse Wonder** to patch the selector in-flight without human intervention.
* **📜 Tamper-Evident SHA-256 Audit Ledger:** Every test step, redacted prompt, visual bounding box, and self-healed diff is recorded to an append-only, hash-chained `audit_trail.jsonl` file and exported as a ready-to-merge **Muse Code** PR patch.

---

## 🏗️ System Architecture

```text
  [Spoken Bug Report / BDD Gherkin .feature / Jira Test Case]
                               │
                               ▼
         (Muse Voice Transcribe: Audio -> Gherkin Spec)
                               │
                               ▼
  ┌─────────────────────────────────────────────────────────┐
  │            Zero-Trust PII & Compliance Gate             │
  │  • Scrubs PII/Secrets -> {{REDACTED_TOKEN_ID}}          │
  │  • Enforces Deterministic Tool Whitelist                │
  └────────────────────────────┬────────────────────────────┘
                               │ (Sanitized Context Only)
                               ▼
  ┌─────────────────────────────────────────────────────────┐
  │       Orchestrator: meta-models/muse-spark-open-1026    │
  │  • Synthesizes deterministic AtomicQEStep JSON plan     │
  └────────────────────────────┬────────────────────────────┘
                               │ FastMCP / Worker Dispatch
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
  ┌───────────────┐    ┌───────────────┐    ┌───────────────┐
  │  Web Worker   │    │ Robot Worker  │    │ Legacy Desktop│
  │ (Playwright)  │    │ (.robot KWDs) │    │  (Pywinauto)  │
  └───────┬───────┘    └───────┬───────┘    └───────┬───────┘
          └────────────────────┼────────────────────┘
                               │
                  [Runtime Selector Exception!]
                               │
                               ▼
  ┌─────────────────────────────────────────────────────────┐
  │         Visual & DOM Self-Healing State Machine         │
  │  1. SAM 3.1: Segments UI elements & bounding boxes      │
  │  2. Muse Wonder: Diagnoses DOM/Control diff & heals     │
  │  3. Muse Code: Generates patched .spec.py / .robot PR   │
  └────────────────────────────┬────────────────────────────┘
                               │
                               ▼
  ┌─────────────────────────────────────────────────────────┐
  │         SHA-256 Hash-Chained Audit Ledger (.jsonl)      │
  └─────────────────────────────────────────────────────────┘

```

---

## 🧠 How We Used Meta AI Tooling & Partner Infrastructure

MuseRunner orchestrates **five specialized Meta models** alongside **Baseten** and **Modal** infrastructure:

| Meta Model / Partner Tool | Role in MuseRunner | Hackathon Track / Prize Alignment |
| --- | --- | --- |
| **`meta-models/muse-spark-open-1026`** *(via Baseten)* | Core agentic planner and BDD-to-tool-call orchestrator utilizing structured outputs and high-throughput 2M TPM limits. | **Best Build on Meta Open Weight Models** & **Best Agentic Use-Case** |
| **`SAM 3.1`** *(Meta Model API)* | Zero-shot visual UI grounding. Segments buttons, modals, and legacy Win32 controls when DOM/Control IDs are obfuscated or missing, returning exact `(x, y)` click coordinates. | **Push the Frontier** |
| **`Muse Wonder`** *(Meta Model API)* | Deep multimodal root-cause diagnosis during test failures, comparing expected state against failure screenshots and DOM trees to synthesize self-healing patches. | **Use of Meta AI Tooling (25%)** |
| **`Muse Voice Transcribe`** *(Meta Model API)* | Converts spoken QA exploration notes directly into standardized Gherkin `Given/When/Then` test suites. | **Build for Your World** |
| **`Muse Code`** | Accelerates repository scaffolding and synthesizes permanent Git diffs/patches for broken Playwright and Robot Framework suites after runtime healing. | **Technical Depth & Execution (20%)** |
| **Modal Sandboxes** | Provides isolated, ephemeral container execution environments for headless browser and Robot Framework workers. | **Partner Infrastructure** |

---

## 📂 Repository Structure

```text
muserunner/
├── src/
│   ├── core/
│   │   ├── schemas.py          # Pydantic schemas (AtomicQEStep, HealingDiagnosis)
│   │   └── meta_client.py      # Baseten (muse-spark-open-1026) & Meta API clients
│   ├── guardrails/
│   │   ├── sanitizer.py        # Pre-inference PII vault & regex/token redaction
│   │   └── audit_logger.py     # SHA-256 hash-chained compliance logger
│   ├── workers/
│   │   ├── web_playwright.py   # Async Playwright runner + DOM/screenshot capture
│   │   ├── robot_bridge.py     # Robot Framework keyword emitter & runner
│   │   └── legacy_desktop.py   # Pywinauto control-tree extractor & clicker
│   ├── graph/
│   │   └── healing_agent.py    # LangGraph state machine (PLAN -> EXEC -> HEAL)
│   └── app.py                  # Streamlit Zero-Trust Control Plane UI
├── demo_targets/
│   ├── mock_banking_web/       # FastAPI target app with 'Break UI Selectors' toggle
│   └── sample_specs/           # Sample BDD .feature files
├── audit_trail.jsonl           # Sample cryptographic execution ledger
├── pyproject.toml              # Dependencies managed via uv
└── README.md

```

---

## 🚀 Quickstart & Local Setup

### Prerequisites

* Python 3.11+ and [`uv`](https://github.com/astral-sh/uv) (or standard `pip`)
* API keys for **Meta Model API** and **Baseten**

### 1. Clone & Install Dependencies

```bash
git clone [https://github.com/](https://github.com/)<your-username>/muserunner.git
cd muserunner

uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
playwright install chromium

```

### 2. Configure Environment Variables

```bash
cp .env.example .env

```

Populate `.env` with your hackathon credentials:

```ini
META_API_KEY="your_meta_model_api_key"
BASETEN_API_KEY="your_baseten_api_key"
BASETEN_MODEL_ID="meta-models/muse-spark-open-1026"
MODAL_TOKEN_ID="your_modal_token_id"
MODAL_TOKEN_SECRET="your_modal_token_secret"

```

### 3. Launch the Target App & MuseRunner Control Plane

In Terminal 1, start the local mock enterprise banking portal (includes a live toggle to intentionally mutate DOM selectors and trigger self-healing):

```bash
uvicorn demo_targets.mock_banking_web.main:app --port 8080

```

In Terminal 2, launch the **MuseRunner Control Plane**:

```bash
streamlit run src/app.py

```

---

## 🧪 Reproducing the Live Demo Flow

1. Open the MuseRunner dashboard (`http://localhost:8501`).
2. Select the **`Wire Transfer Compliance Flow.feature`** spec (or record a voice prompt via **Muse Voice Transcribe**).
3. Enable the **"Simulate Broken Production UI"** toggle on the target banking app (mutates `#confirm-transfer-btn` into an obfuscated dynamic node).
4. Click **Execute Verifiable Run**:
* Observe the **Zero-Trust Gate** mask customer account numbers and SSNs into `{{REDACTED_...}}` tokens in real time.
* Watch step 4 fail on the missing selector, automatically triggering **SAM 3.1** visual segmentation and **Muse Wonder** healing.
* Inspect the auto-generated `.robot` / Playwright code diff and verify the cryptographic chain in `audit_trail.jsonl`.



---

## 📜 License

Distributed under the MIT License. Built for the **Meta Global AI Developer Hackathon 2026**.
