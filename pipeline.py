import os
import json
import sqlite3
import pdfplumber
from ollama import chat
from pydantic import BaseModel, Field
from typing import List, Literal

# ==========================================
# 1. DATA SCHEMAS
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
# 2. DATABASE INITIALIZATION
# ==========================================
DB_NAME = "local_bank_data.db"

def init_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Create table for accounts/profiles
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
    
    # Create table for transactional logs
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

# ==========================================
# 3. EXTRACTION AND INFERENCE
# ==========================================
def extract_pdf_text(pdf_path: str) -> str:
    raw_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            raw_text += page.extract_text() or ""
    return raw_text

def run_ai_extraction(text: str) -> StatementProfile:
    prompt = f"Analyze this bank statement and return the data strictly matching the requested format:\n\n{text}"
    
    response = chat(
        model='llama3.1',
        messages=[{'role': 'user', 'content': prompt}],
        format=StatementProfile.model_json_schema(),
        options={'temperature': 0.0}
    )
    return StatementProfile.model_validate_json(response['message']['content'])

# ==========================================
# 4. DATABASE INGESTION STORAGE
# ==========================================
def save_to_database(filename: str, profile: StatementProfile):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        # Insert account data
        cursor.execute("""
            INSERT INTO accounts (filename, account_holder, total_deposits, total_withdrawals, risk_rating, underwriting_notes, anomalies_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            filename,
            profile.account_holder,
            profile.financial_health.total_deposits,
            profile.financial_health.total_withdrawals,
            profile.financial_health.risk_rating,
            profile.financial_health.underwriting_notes,
            json.dumps(profile.financial_health.detected_anomalies)
        ))
        
        account_id = cursor.lastrowid
        
        # Insert individual transactions
        tx_data = [
            (account_id, tx.date, tx.description, tx.amount, tx.category)
            for tx in profile.transactions
        ]
        
        cursor.executemany("""
            INSERT INTO transactions (account_id, tx_date, description, amount, category)
            VALUES (?, ?, ?, ?, ?)
        """, tx_data)
        
        conn.commit()
        print(True)
    except sqlite3.IntegrityError:
        print(f"[-] Skipping {filename}: Already ingested into database.")
    finally:
        conn.close()

# ==========================================
# 5. BATCH RUNNER CORE
# ==========================================
def process_batch():
    input_folder = "input_pdfs"
    init_database()
    
    files = [f for f in os.listdir(input_folder) if f.endswith('.pdf')]
    if not files:
        print(f"No PDFs found in the './{input_folder}' directory. Add some files to test!")
        return

    print(f"Found {len(files)} files to process in batch.")
    
    for filename in files:
        file_path = os.path.getmtime # using path properties safely
        full_path = os.path.join(input_folder, filename)
        print(f"\n[+] Processing: {filename}")
        
        try:
            text = extract_pdf_text(full_path)
            if not text.strip():
                print(f"[-] {filename} appears to be empty or image-only. Skipping.")
                continue
                
            structured_profile = run_ai_extraction(text)
            save_to_database(filename, structured_profile)
            print(f"[✓] Successfully saved data for {structured_profile.account_holder}")
            
        except Exception as e:
            print(f"[!] Error processing {filename}: {str(e)}")

if __name__ == "__main__":
    process_batch()