import sqlite3
import chromadb
import os

# ==========================================
# 1. SQLITE SETUP (For Structured Numbers)
# ==========================================
def init_sqlite_db():
    """Initializes the SQLite database and creates tables if they don't exist."""
    # This will create a file named 'life_copilot.db' in your folder
    conn = sqlite3.connect('life_copilot.db')
    cursor = conn.cursor()

    # Create Wealth Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS wealth_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        transaction_type TEXT,
        amount REAL,
        currency TEXT,
        category TEXT,
        merchant TEXT,
        notes TEXT
    )
    ''')

    # Create Health Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS health_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        sleep_hours REAL,
        workout_type TEXT,
        calories_consumed INTEGER,
        notes TEXT
    )
    ''')

    # Create Learning Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS learning_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        topic TEXT,
        duration_minutes INTEGER,
        url_reference TEXT
    )
    ''')

    conn.commit()
    conn.close()
    print("SQLite Database initialized successfully.")

def insert_wealth_log(date, transaction_type, amount, currency, category, merchant, notes):
    conn = sqlite3.connect('life_copilot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO wealth_logs (date, transaction_type, amount, currency, category, merchant, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (date, transaction_type, amount, currency, category, merchant, notes))
    conn.commit()
    conn.close()


def insert_health_log(date, sleep_hours, workout_type, calories_consumed, notes):
    conn = sqlite3.connect('life_copilot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO health_logs (date, sleep_hours, workout_type, calories_consumed, notes)
        VALUES (?, ?, ?, ?, ?)
    ''', (date, sleep_hours, workout_type, calories_consumed, notes))
    conn.commit()
    conn.close()

def insert_learning_log(date, topic, duration_minutes, url_reference):
    conn = sqlite3.connect('life_copilot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO learning_logs (date, topic, duration_minutes, url_reference)
        VALUES (?, ?, ?, ?)
    ''', (date, topic, duration_minutes, url_reference))
    conn.commit()
    conn.close()

# ==========================================
# 2. CHROMADB SETUP (For Vector Embeddings)
# ==========================================
def init_chroma_db():
    """Initializes the local ChromaDB vector store."""
    # This creates a folder called 'chroma_data' to store the vectors locally
    client = chromadb.PersistentClient(path="./chroma_data")
    
    # We create a specific collection just for your learning summaries (Your "Second Brain")
    learning_collection = client.get_or_create_collection(name="learning_summaries")
    print("ChromaDB initialized successfully.")
    
    return learning_collection

def add_learning_vector(collection, date, topic, summary_text, url_reference):
    """Embeds and saves the learning summary into the vector DB."""
    # ChromaDB automatically uses a lightweight embedding model to convert 'summary_text' into a vector
    collection.add(
        documents=[summary_text],
        metadatas=[{"date": date, "topic": topic, "url": url_reference or "None"}],
        ids=[f"learning_{date}_{topic.replace(' ', '_')}"]
    )


# ==========================================
# 3. RETRIEVAL FUNCTIONS (The "R" in RAG)
# ==========================================

def query_sqlite(query_string: str):
    """Executes a SQL SELECT query to retrieve numerical/structured data."""
    conn = sqlite3.connect('life_copilot.db')
    cursor = conn.cursor()
    try:
        # Only allow SELECT queries for safety
        if not query_string.strip().upper().startswith("SELECT"):
            return "Error: Only SELECT queries are allowed."
            
        cursor.execute(query_string)
        results = cursor.fetchall()
        return results
    except Exception as e:
        return f"SQL Error: {e}"
    finally:
        conn.close()

def search_learning_vectors(query_text: str, n_results: int = 3):
    """Searches ChromaDB for semantically similar learning notes."""
    client = chromadb.PersistentClient(path="./chroma_data")
    collection = client.get_collection(name="learning_summaries")
    
    # ChromaDB automatically converts your query_text into a vector and finds the closest matches
    results = collection.query(
        query_texts=[query_text],
        n_results=n_results
    )
    return results
    
# Run this once when the file is executed to create the tables
if __name__ == "__main__":
    init_sqlite_db()
    init_chroma_db()