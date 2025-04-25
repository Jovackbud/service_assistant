# config.py
import os

# --- Role Configuration ---
# Add 'customer' role
ROLES = ["customer", "staff", "hr", "manager"]
# Define role hierarchy (customer is lowest level 0)
# 'public' is used as an alias for level 0 tagging in filenames
ROLE_HIERARCHY = {
    "customer": 0, # Lowest access level
    "public": 0,   # Documents tagged '_public' get level 0
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
# Ensure this matches the model tag you pulled and are running with Ollama
LLM_MODEL = "deepseek-r1:1.5b" # Or your chosen model

# --- Ticket System Configuration ---
# Add 'Customer Support' team
TICKET_TEAMS = ["Customer Support", "HR", "IT", "Product", "Legal", "General"]
TICKET_DB_PATH = "database/tickets.db"
FEEDBACK_DB_PATH = "database/feedback.db"

# Simple keyword mapping for team suggestions
# Added specific keywords for Customer Support
TICKET_KEYWORD_MAP = {
    # Map general customer issues to Customer Support
    "customer support": ["account", "order", "website", "login", "purchase", "service", "product issue", "billing", "faq", "contact", "support"],
    "hr": ["payroll", "leave", "benefits", "hiring", "policy", "pto", "salary", "employee"],
    "it": ["laptop", "password", "software", "printer", "network", "access", "computer", "wifi", "system"],
    "product": ["feature", "roadmap", "sprint", "project", "omega", "update", "deployment"],
    "legal": ["contract", "compliance", "nda", "agreement", "terms", "policy"] # Legal might overlap with HR/General
}

# --- Create necessary directories ---
# Ensure the parent directory for the databases exists
os.makedirs(os.path.dirname(TICKET_DB_PATH), exist_ok=True)
os.makedirs(os.path.dirname(FEEDBACK_DB_PATH), exist_ok=True)
# ChromaDB will create its own directory defined by PERSIST_DIRECTORY