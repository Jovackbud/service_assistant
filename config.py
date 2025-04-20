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
# Use a directory name for ChromaDB persistence
PERSIST_DIRECTORY = "chroma_db"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
LLM_MODEL = "deepseek-r1:1.5b"

# --- Ticket System Configuration ---
TICKET_TEAMS = ["HR", "IT", "Product", "Legal", "General"]
TICKET_DB_PATH = "database/tickets.db"
FEEDBACK_DB_PATH = "database/feedback.db"

# Simple keyword mapping for team suggestions
TICKET_KEYWORD_MAP = {
    "hr": ["payroll", "leave", "benefits", "hiring", "policy", "pto", "salary"],
    "it": ["laptop", "password", "software", "printer", "network", "login", "access", "computer", "wifi"],
    "product": ["feature", "roadmap", "sprint", "project", "omega", "update"],
    "legal": ["contract", "compliance", "nda", "agreement"]
}

# --- Create necessary directories ---
os.makedirs(os.path.dirname(TICKET_DB_PATH), exist_ok=True)
os.makedirs(os.path.dirname(FEEDBACK_DB_PATH), exist_ok=True)
# Chroma will create its own directory if needed, but ensure parent exists if nested deeper
# os.makedirs(PERSIST_DIRECTORY, exist_ok=True) # Chroma handles its own directory creation