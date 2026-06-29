# 🏦 Local AI Banking Data Pipeline & Analytics Engine

A 100% free, private, and local enterprise-grade banking data processing application. This pipeline extracts unstructured transaction data from bank statement PDFs, enforces strict validation schemas using Pydantic, executes risk underwriting analysis using a local Large Language Model, and visualizes the results on an interactive web dashboard.

---

## 🏗️ Architecture Overview

1. **Document Ingestion:** Layout-aware text extraction from uploaded bank statement PDFs using `pdfplumber`.
2. **Structured AI Processing:** The raw text is passed to a local instance of **Ollama (Llama 3.1)**. Token probabilities are constrained dynamically using a `Pydantic` schema to prevent hallucinations and enforce strict JSON layout mapping.
3. **Relational Storage:** Processed records (Accounts and Transactions logs) are structured and committed to a local **SQLite** database.
4. **Analytics Interface:** A local **Streamlit** dashboard fetches relational records to render real-time cash flow trends, categorical expense breakdowns, and automated anomaly risk alerts.

---

## 🛠️ Tech Stack

* **Frontend Dashboard:** Streamlit, Pandas, Plotly
* **AI Orchestration Engine:** Ollama (Llama 3.1)
* **Data Validation:** Pydantic v2
* **PDF Extraction Engine:** pdfplumber
* **Database Layer:** SQLite3

---

## 🚀 Getting Started

### 1. Prerequisites
Ensure you have [Ollama](https://ollama.com/) installed and running natively on your Mac machine.

Pull the required model in your terminal:
```bash
ollama pull llama3.1

2. Set Up the Environment & Run
Clone the repository, initialize your environment, and boot up the dashboard server:
# Setup virtual environment
python3 -m venv venv
source venv/bin/activate

# Install required dependencies
pip install streamlit pandas plotly ollama pydantic pdfplumber

# Start the browser dashboard application
streamlit run app.py

<img width="1710" height="1112" alt="Screenshot 2026-06-29 at 11 16 26 AM" src="https://github.com/user-attachments/assets/e862e1ab-fa6a-428e-bd27-047ff7805885" />

<img width="1710" height="1112" alt="Screenshot 2026-06-29 at 11 14 46 AM" src="https://github.com/user-attachments/assets/3cc1e607-ea11-4cc1-a44f-3ea1df21c8d9" />


