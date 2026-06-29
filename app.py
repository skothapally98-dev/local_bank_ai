import streamlit as st
import os
import json
import sqlite3
import pdfplumber
import pandas as pd
import plotly.express as px
from ollama import chat
from pydantic import BaseModel, Field
from typing import List, Literal

DB_NAME = "local_bank_data.db"

# ==========================================
# 1. AI DATA SCHEMAS
# ==========================================
class Transaction(BaseModel):
    date: str
    description: str
    amount: float
    category: Literal["Income", "Utilities", "Rent/Mortgage", "Dining/Entertainment", "Retail/Shopping", "Transfer", "Unknown"]

class RiskAnalysis(BaseModel):
    total_deposits: float
    total_withdrawals: float
    detected_anomalies: List[str]
    risk_rating: Literal["Low", "Medium", "High"]
    underwriting_notes: str

class StatementProfile(BaseModel):
    account_holder: str
    transactions: List[Transaction]
    financial_health: RiskAnalysis

# ==========================================
# 2. CORE STORAGE & PIPELINE FUNCTIONS
# ==========================================
def init_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE,
            account_holder TEXT,
            total_deposits REAL,
            total_withdrawals REAL,
            risk_rating TEXT,
            underwriting_notes TEXT,
            anomalies_json TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            tx_date TEXT,
            description TEXT,
            amount REAL,
            category TEXT,
            FOREIGN KEY(account_id) REFERENCES accounts(id)
        )
    """)
    conn.commit()
    conn.close()

def process_pdf_bytes(uploaded_file) -> str:
    raw_text = ""
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            raw_text += page.extract_text() or ""
    return raw_text

def run_ai_extraction(text: str) -> StatementProfile:
    prompt = f"Analyze this bank statement and return the data strictly matching the requested format:\n\n{text}"
    response = chat(
        model='llama3.1',  # <-- Change 'llama3.1' to 'llama3' or 'mistral' here
        messages=[{'role': 'user', 'content': prompt}],
        format=StatementProfile.model_json_schema(),
        options={'temperature': 0.0}
    )
    return StatementProfile.model_validate_json(response['message']['content'])

def save_to_database(filename: str, profile: StatementProfile):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO accounts (filename, account_holder, total_deposits, total_withdrawals, risk_rating, underwriting_notes, anomalies_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            filename, profile.account_holder, profile.financial_health.total_deposits,
            profile.financial_health.total_withdrawals, profile.financial_health.risk_rating,
            profile.financial_health.underwriting_notes, json.dumps(profile.financial_health.detected_anomalies)
        ))
        account_id = cursor.lastrowid
        tx_data = [(account_id, tx.date, tx.description, tx.amount, tx.category) for tx in profile.transactions]
        cursor.executemany("""
            INSERT INTO transactions (account_id, tx_date, description, amount, category)
            VALUES (?, ?, ?, ?, ?)
        """, tx_data)
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Already exists
    finally:
        conn.close()

# ==========================================
# 3. STREAMLIT DATA FETCHERS
# ==========================================
def load_accounts():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM accounts", conn)
    conn.close()
    return df

def load_transactions(account_id):
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM transactions WHERE account_id = ?", conn, params=(int(account_id),))
    conn.close()
    return df

# ==========================================
# 4. WEB INTERFACE (STREAMLIT)
# ==========================================
st.set_page_config(page_title="AI Bank Pipeline", layout="wide")
init_database()

st.title("🏦 Local AI Banking Data Pipeline & Analytics Engine")
st.markdown("Upload transactional statement documents to run private, secure local text analysis and risk scoring.")

# --- SECTION 1: INTERACTIVE FILE UPLOADER ---
st.subheader("📥 Ingest New Bank Statement")
uploaded_file = st.file_uploader("Drag and drop your statement PDF here", type=["pdf"])

if uploaded_file is not None:
    upload_name = uploaded_file.name
    
    if st.button(f"Process '{upload_name}' via Local AI"):
        with st.spinner("Extracting PDF layout text and running local Ollama inference..."):
            try:
                text_content = process_pdf_bytes(uploaded_file)
                
                if not text_content.strip():
                    st.error("Could not extract clean text. The file might be scanned/image-only.")
                else:
                    structured_data = run_ai_extraction(text_content)
                    is_new = save_to_database(upload_name, structured_data)
                    
                    if is_new:
                        st.success(f"Successfully processed and cataloged profile for: {structured_data.account_holder}!")
                    else:
                        st.warning(f"File '{upload_name}' was already processed previously. Displaying historical data below.")
            except Exception as e:
                st.error(f"Pipeline error: {str(e)}")

st.markdown("---")

# --- SECTION 2: METRICS & VISUALIZATION DASHBOARD ---
try:
    df_accounts = load_accounts()
except Exception:
    df_accounts = pd.DataFrame()

if df_accounts.empty:
    st.info("💡 No profiles loaded yet. Drop a test statement PDF above to kickstart the system database.")
else:
    st.subheader("📊 Portfolio Insight Dashboard")
    
    # Dropdown inside sidebar to change profiles
    account_options = {row['account_holder']: row['id'] for _, row in df_accounts.iterrows()}
    selected_holder = st.sidebar.selectbox("Active Account Target", list(account_options.keys()))
    selected_id = account_options[selected_holder]
    
    account_profile = df_accounts[df_accounts['id'] == selected_id].iloc[0]
    df_tx = load_transactions(selected_id)
    
    # Structural KPI Metric blocks
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="Total Inward Deposits", value=f"${account_profile['total_deposits']:,}")
    with col2:
        st.metric(label="Total Outward Withdrawals", value=f"${abs(account_profile['total_withdrawals']):,}")
    with col3:
        risk = account_profile['risk_rating']
        if risk == "Low":
            st.success(f"Pipeline Risk Status: {risk}")
        elif risk == "Medium":
            st.warning(f"Pipeline Risk Status: {risk}")
        else:
            st.error(f"Pipeline Risk Status: {risk}")
            
    # Display the source document cleanly from database memory safely
    st.markdown(f"**Source Document:** `{account_profile['filename']}`")
    
    # Risk notes & structural parsing outputs
    st.markdown("#### AI Verification Notes")
    st.text_area("Underwriter Memo Summary", value=account_profile['underwriting_notes'], height=70, disabled=True)
    
    anomalies = json.loads(account_profile['anomalies_json'])
    if anomalies:
        for anomaly in anomalies:
            st.markdown(f"🚨 **Anomaly Found:** {anomaly}")
            
    st.markdown("---")
    
    # Graphs
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        if not df_tx.empty:
            df_spend = df_tx[df_tx['amount'] < 0].copy()
            df_spend['amount'] = df_spend['amount'].abs()
            fig_pie = px.pie(df_spend, values='amount', names='category', title="Spending Distribution", hole=0.35)
            st.plotly_chart(fig_pie, use_container_width=True)
    
    with col_chart2:
        if not df_tx.empty:
            df_trend = df_tx.sort_values(by="tx_date")
            fig_bar = px.bar(df_trend, x='tx_date', y='amount', color='category', title="Daily Transaction Vectors")
            st.plotly_chart(fig_bar, use_container_width=True)
            
    # Clean Searchable Table Grid
    st.markdown("#### Transaction Ledger Lookup")
    search = st.text_input("Filter transactions by merchant text...")
    if search:
        df_filtered = df_tx[df_tx['description'].str.contains(search, case=False, na=False)]
    else:
        df_filtered = df_tx
        
    st.dataframe(df_filtered[['tx_date', 'description', 'amount', 'category']], use_container_width=True)