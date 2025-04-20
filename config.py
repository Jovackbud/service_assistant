import os

# --- Role Configuration ---
ROLES = ["staff", "hr", "manager"]
# Define role hierarchy (higher number means more access)
ROLE_HIERARCHY = {
    "staff": 1,
    "hr": 2,
    "manager": 3
}

# --- Document Configuration ---
DOCS_FOLDER = "sample_docs"
ALLOWED_EXTENSIONS = [".txt", ".pdf"]

# --- RAG Configuration ---
VECTOR_STORE_PATH = "vector_store_db"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
# Make sure Ollama server is running and the model is pulled
LLM_MODEL = "deepseek-r1:1.5b"

# --- Ticket System Configuration ---
TICKET_TEAMS = ["HR", "IT", "Product", "Legal", "General"]
TICKET_DB_PATH = "database/tickets.db"
FEEDBACK_DB_PATH = "database/feedback.db"

# Simple keyword mapping for team suggestions
TICKET_KEYWORD_MAP = {
    "hr": ["payroll", "leave", "benefits", "hiring", "policy", "pto"],
    "it": ["laptop", "password", "software", "printer", "network", "login", "access"],
    "product": ["feature", "roadmap", "sprint", "project", "omega"],
    "legal": ["contract", "compliance", "nda"]
}

# --- Create necessary directories ---
os.makedirs(os.path.dirname(TICKET_DB_PATH), exist_ok=True)
os.makedirs(os.path.dirname(FEEDBACK_DB_PATH), exist_ok=True)