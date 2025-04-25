# rag_processor.py
import os
import glob
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.llms import Ollama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document

from config import (
    DOCS_FOLDER, ALLOWED_EXTENSIONS, ROLE_HIERARCHY,
    PERSIST_DIRECTORY,
    CHUNK_SIZE, CHUNK_OVERLAP,
    EMBEDDING_MODEL, LLM_MODEL
)

# --- Document Loading & Role Tagging ---

def get_role_from_filename(filename):
    """Extracts the minimum required role from the filename suffix."""
    base = os.path.splitext(filename)[0]
    parts = base.split('_')
    if len(parts) > 1:
        role_tag = parts[-1].lower()
        # Check if the tag exists in our hierarchy (covers 'public', 'staff', 'hr', 'manager')
        if role_tag in ROLE_HIERARCHY:
            return role_tag # Return the tag ('public', 'staff', 'hr', 'manager')
    # If no valid tag found or tag isn't in hierarchy, default to highest restriction
    # OR, safer: default to *no access* unless explicitly tagged 'public'.
    # Let's default to 'manager' level implicitly if untagged (most restrictive internal).
    # Consider changing this default based on security policy. For PoC, 'manager' is safer than 'staff'.
    # A better approach might be to *require* a tag.
    # For now, let's map untagged to a high level to prevent accidental exposure.
    # We return the role *name* here.
    # print(f"Warning: No valid role tag found for {filename}. Defaulting to restricted access (manager).")
    # return "manager"
    # --- Updated Default Logic: If no tag, assume it's NOT public. Let's default to staff for simplicity in PoC.
    # print(f"Info: No specific role tag found for {filename}. Defaulting to 'staff' access.")
    # return "staff"
    # --- Even Better Logic: Default to 'public' only if specifically tagged _public. Otherwise, treat as 'staff' if no other tag.
    if len(parts) > 1 and parts[-1].lower() == 'public':
        return 'public'
    elif len(parts) > 1 and parts[-1].lower() in ['staff', 'hr', 'manager']:
        return parts[-1].lower()
    else:
        # If file is untagged (e.g., my_document.txt), assign a default internal level.
        print(f"Info: No specific role tag found for {filename}. Defaulting to 'staff' access level.")
        return 'staff'


def load_documents():
    """Loads documents, extracts role, assigns role_level metadata."""
    print(f"Loading documents from: {DOCS_FOLDER}")
    docs = []
    for ext in ALLOWED_EXTENSIONS:
        for filepath in glob.glob(os.path.join(DOCS_FOLDER, f"*{ext}")):
            filename = os.path.basename(filepath)
            # Determine the role string ('public', 'staff', 'hr', 'manager')
            role = get_role_from_filename(filename)
            # Get the corresponding numeric level from the hierarchy
            role_level = ROLE_HIERARCHY.get(role, ROLE_HIERARCHY['manager']) # Default to high level if role somehow invalid
            print(f" - Loading {filename} (Role: {role}, Level: {role_level})")
            try:
                if ext == ".pdf":
                    loader = PyPDFLoader(filepath)
                elif ext == ".txt":
                    loader = TextLoader(filepath)
                else:
                    continue

                loaded_docs = loader.load()
                for doc in loaded_docs:
                    doc.metadata["role"] = role # Store role name
                    doc.metadata["source"] = filename
                    doc.metadata["role_level"] = role_level # Store numeric level for filtering
                docs.extend(loaded_docs)
            except Exception as e:
                print(f"   Error loading {filename}: {e}")
    print(f"Total documents loaded: {len(docs)}")
    return docs

# --- Text Splitting --- (No changes)
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP
)

# --- Embeddings --- (No changes)
print(f"Loading embedding model: {EMBEDDING_MODEL}")
embeddings = SentenceTransformerEmbeddings(model_name=EMBEDDING_MODEL)
print("Embedding model loaded.")

# --- Vector Store (ChromaDB) --- (Logic remains the same, relies on updated load_documents)
vector_store = None

def create_or_load_vector_store():
    """Creates the Chroma vector store if it doesn't exist, otherwise loads it."""
    global vector_store
    if os.path.exists(PERSIST_DIRECTORY):
        print(f"Loading existing Chroma vector store from: {PERSIST_DIRECTORY}")
        vector_store = Chroma(
            persist_directory=PERSIST_DIRECTORY,
            embedding_function=embeddings
        )
        print("Chroma vector store loaded.")
    else:
        print("Creating new Chroma vector store...")
        # load_documents now adds 'role' and 'role_level' correctly based on updated logic
        documents = load_documents()
        if not documents:
            print("No documents found to create vector store. Aborting.")
            return None

        chunks = text_splitter.split_documents(documents)
        print(f"Split documents into {len(chunks)} chunks.")

        if chunks and 'role_level' not in chunks[0].metadata:
             print("Warning: Metadata ('role_level') might not be propagating correctly during splitting!")
             # Check metadata of a sample chunk
             # print(f"Sample chunk metadata: {chunks[0].metadata if chunks else 'N/A'}")


        print("Creating Chroma database...")
        vector_store = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            persist_directory=PERSIST_DIRECTORY
        )
        print(f"Chroma database created and persisted to: {PERSIST_DIRECTORY}")
    return vector_store

vector_store = create_or_load_vector_store()

# --- LLM and RAG Chain --- (Prompt and Chain logic remain the same, relies on updated hierarchy/filtering)

if vector_store:
    print(f"Initializing LLM: {LLM_MODEL}")
    llm = Ollama(model=LLM_MODEL)
    print("LLM initialized.")

    template = """
    You are an internal knowledge assistant for OurCompany.
    Answer the question based ONLY on the following context provided.
    If the context is empty, states 'No relevant documents were found or accessible for your role.', or does not contain the answer, state clearly: 'Based on the documents I can access, I cannot answer that question.'
    Do not make up information or use external knowledge.
    Be concise and helpful.

    Context:
    {context}

    Question:
    {question}

    Answer:
    """
    prompt = ChatPromptTemplate.from_template(template)

    output_parser = StrOutputParser()

    def format_docs(docs):
        """Helper function to format documents for the prompt context."""
        if not docs:
            return "No relevant documents were found or accessible for your role."
        return "\n\n".join(doc.page_content for doc in docs)


    def get_rag_chain(user_role):
        """Creates RAG chain with Chroma pre-filtering based on user_role."""
        if not vector_store:
            print("Error: Vector store not available.")
            def explain_issue(_):
                 return "Knowledge base is currently unavailable. Please try again later or contact support."
            return RunnableLambda(explain_issue)

        # Get numeric level for the user's role (customer=0, staff=1, etc.)
        user_level = ROLE_HIERARCHY.get(user_role, -1) # Default to -1 (no access) if role is invalid

        if user_level == -1:
             print(f"Error: Invalid user role '{user_role}' provided.")
             def explain_issue(_):
                  return f"Error: Invalid role '{user_role}'. Access denied."
             return RunnableLambda(explain_issue)


        retriever = vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={
                "k": 5,
                "filter": {
                    # Filter chunks where metadata 'role_level' is less than or equal to user's level
                    "role_level": {"$lte": user_level}
                }
            }
        )
        print(f"Configured Chroma retriever for role '{user_role}' (level {user_level}) with filter: role_level <= {user_level}")

        def retrieve_and_format_docs(data):
             """Retrieves documents using the role-filtered retriever and formats them."""
             # Handle both string input and dict input for question robustness
             if isinstance(data, dict):
                 question = data.get("question", "")
             else:
                 question = str(data) # Assume input is the question string

             if not question:
                 return "Please provide a question."

             docs = retriever.invoke(question)
             print(f"Retrieved {len(docs)} docs after filtering for role '{user_role}' matching query '{question[:50]}...'")
             return format_docs(docs)

        rag_chain = (
            # Assumes input is the question string, passes it to retriever context
            {"context": RunnableLambda(retrieve_and_format_docs), "question": RunnablePassthrough()}
            | prompt
            | llm
            | output_parser
        )
        return rag_chain

else:
    print("Cannot initialize RAG chain because vector store failed to load/create.")
    def get_rag_chain(user_role):
         def explain_issue(_):
             return "Error: RAG system could not be initialized. Check logs."
         return RunnableLambda(explain_issue)