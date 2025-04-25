# config.py
import os

# --- Role Configuration ---
# Add 'customer' role
ROLES = ["customer", "staff", "hr", "manager"]
# Define role hierarchy (customer is lowest level 0)
ROLE_HIERARCHY = {
    "customer": 0, # Lowest access level
    "public": 0,   # Add alias for level 0 for clarity in doc tagging
    "staff": 1,
    "hr": 2,
    "manager": 3
}

# --- Document Configuration ---
DOCS_FOLDER = "sample_docs"
ALLOWED_EXTENSIONS = [".txt", ".pdf"]

# --- RAG Configuration ---
PERSIST_DIRECTORY = "chroma_db" # ChromaDB persistence path
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
# Make sure Ollama server is running and the model is pulled
LLM_MODEL = "deepseek-coder:1.3b-instruct-q4_K_M" # Or your chosen quantized model tag

# --- Ticket System Configuration ---
# Add a 'Customer Support' team
TICKET_TEAMS = ["Customer Support", "HR", "IT", "Product", "Legal", "General"]
TICKET_DB_PATH = "database/tickets.db"
FEEDBACK_DB_PATH = "database/feedback.db"

# Simple keyword mapping for team suggestions
# Add customer-specific keywords
TICKET_KEYWORD_MAP = {
    # Map general customer issues to Customer Support
    "customer support": ["account", "order", "website", "login", "purchase", "service", "product issue", "billing"],
    "hr": ["payroll", "leave", "benefits", "hiring", "policy", "pto", "salary"],
    "it": ["laptop", "password", "software", "printer", "network", "access", "computer", "wifi"],
    "product": ["feature", "roadmap", "sprint", "project", "omega", "update"],
    "legal": ["contract", "compliance", "nda", "agreement", "terms"]
}

# --- Create necessary directories ---
os.makedirs(os.path.dirname(TICKET_DB_PATH), exist_ok=True)
os.makedirs(os.path.dirname(FEEDBACK_DB_PATH), exist_ok=True)
# os.makedirs(PERSIST_DIRECTORY, exist_ok=True) # Chroma handles its own directory creation