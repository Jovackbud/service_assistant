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
    """
    Extracts the minimum required role ('public', 'staff', 'hr', 'manager')
    from the filename suffix (e.g., '_public', '_staff').
    Defaults to 'staff' if no valid, recognized tag is found.
    """
    base = os.path.splitext(filename)[0]
    parts = base.split('_')
    if len(parts) > 1:
        # Check the last part as potential tag
        role_tag = parts[-1].lower()
        # Verify if the tag is one of the defined roles or 'public'
        if role_tag in ROLE_HIERARCHY: # Checks against keys: 'customer', 'public', 'staff', 'hr', 'manager'
             # Return the valid tag found (e.g., 'public', 'staff')
            return role_tag
    # If no recognized tag found after '_', default to 'staff' access level.
    # This means untagged files require at least staff level access.
    print(f"Info: No specific role tag (e.g., _public, _staff) found for '{filename}'. Defaulting to 'staff' access level.")
    return 'staff'


def load_documents():
    """
    Loads documents from DOCS_FOLDER, extracts role from filename suffix,
    and adds 'role' (name) and 'role_level' (numeric) metadata.
    """
    print(f"Loading documents from: {DOCS_FOLDER}")
    docs = []
    for ext in ALLOWED_EXTENSIONS:
        for filepath in glob.glob(os.path.join(DOCS_FOLDER, f"*{ext}")):
            filename = os.path.basename(filepath)
            # Determine the role string ('public', 'staff', 'hr', 'manager') using the updated function
            role = get_role_from_filename(filename)
            # Get the corresponding numeric level from the hierarchy, default high if role invalid
            role_level = ROLE_HIERARCHY.get(role, ROLE_HIERARCHY['manager'])
            print(f" - Loading {filename} (Role Tag: {role}, Assigned Level: {role_level})")
            try:
                if ext == ".pdf":
                    loader = PyPDFLoader(filepath)
                elif ext == ".txt":
                    loader = TextLoader(filepath)
                else:
                    continue # Should not happen due to glob pattern

                loaded_docs = loader.load()
                # Add metadata to each document page/chunk precursor
                for doc in loaded_docs:
                    doc.metadata["role"] = role # Store role name/tag used
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

# --- Vector Store (ChromaDB) ---
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
        # load_documents now adds 'role' and 'role_level' based on filename tag
        documents = load_documents()
        if not documents:
            print("No documents found to create vector store. Aborting.")
            return None

        chunks = text_splitter.split_documents(documents)
        print(f"Split documents into {len(chunks)} chunks.")

        # Verify metadata propagation (optional check)
        if chunks and 'role_level' not in chunks[0].metadata:
             print("Warning: Metadata ('role_level') might not be propagating correctly during splitting!")

        print("Creating Chroma database and adding documents...")
        vector_store = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            persist_directory=PERSIST_DIRECTORY # Tell Chroma where to save/persist
        )
        print(f"Chroma database created and persisted to: {PERSIST_DIRECTORY}")
    return vector_store

# Initialize vector store on module import
vector_store = create_or_load_vector_store()

# --- LLM and RAG Chain ---
if vector_store:
    print(f"Initializing LLM: {LLM_MODEL}")
    llm = Ollama(model=LLM_MODEL)
    print("LLM initialized.")

    # RAG prompt template instructing the LLM on behavior
    template = """
    You are an internal knowledge assistant for African Institute for Artificial Intelligence (AI4AI).
        Answer the question(s) based ONLY on the following context provided. Do not output your reasoning or expose context information
        If the context is empty, states 'No relevant documents were found or accessible for your role. Kindly open a ticket', or does not contain the answer, state clearly: 'Based on the documents I can access, I cannot answer that question. Kindly open a ticket'
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
            # This message is crucial for the ticket trigger logic
            return "No relevant documents were found or accessible for your role."
        return "\n\n".join(doc.page_content for doc in docs)


    def get_rag_chain(user_role):
        """Creates the RAG chain with Chroma pre-filtering based on the user's role."""
        if not vector_store:
            print("Error: Vector store is not available.")
            def explain_issue(_): return "Knowledge base is currently unavailable. Please try again later."
            return RunnableLambda(explain_issue)

        # Get numeric level for the user's role (customer=0, staff=1, etc.)
        user_level = ROLE_HIERARCHY.get(user_role, -1) # Default to -1 (no access) if role is invalid

        if user_level == -1:
             print(f"Error: Invalid user role '{user_role}' provided.")
             def explain_issue(_): return f"Error: Invalid role '{user_role}'. Access denied."
             return RunnableLambda(explain_issue)

        # Configure the retriever with Chroma's metadata filtering
        retriever = vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={
                "k": 5, # Retrieve top 5 relevant chunks matching the filter
                "filter": {
                    # Only retrieve documents where 'role_level' <= user's level
                    "role_level": {"$lte": user_level}
                }
            }
        )
        print(f"Configured Chroma retriever for role '{user_role}' (level {user_level}) with filter: role_level <= {user_level}")

        def retrieve_and_format_docs(input_data):
            """Retrieves docs using the role-filtered retriever and formats them."""
            question = str(input_data) # Input is the question string
            if not question:
                return "No question provided."
            docs = retriever.invoke(question)
            print(f"Retrieved {len(docs)} docs after filtering for role '{user_role}' matching query '{question[:50]}...'")
            return format_docs(docs)

        # Define the RAG chain
        rag_chain = (
            # The input question goes to both context retrieval and the final prompt
            {"context": RunnableLambda(retrieve_and_format_docs), "question": RunnablePassthrough()}
            | prompt
            | llm
            | output_parser
        )
        return rag_chain

else:
    # Handle case where vector store failed to initialize
    print("Cannot initialize RAG chain because vector store failed to load/create.")
    def get_rag_chain(user_role):
         def explain_issue(_): return "Error: RAG system could not be initialized. Check logs."
         return RunnableLambda(explain_issue)