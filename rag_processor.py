import os
import glob
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.llms import Ollama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document

from config import (
    DOCS_FOLDER, ALLOWED_EXTENSIONS, ROLE_HIERARCHY,
    VECTOR_STORE_PATH, CHUNK_SIZE, CHUNK_OVERLAP,
    EMBEDDING_MODEL, LLM_MODEL
)


# --- Document Loading & Role Tagging ---

def get_role_from_filename(filename):
    """Extracts the minimum required role from the filename suffix."""
    base = os.path.splitext(filename)[0]
    parts = base.split('_')
    if len(parts) > 1:
        role_tag = parts[-1].lower()
        if role_tag in ROLE_HIERARCHY:
            return role_tag
    return "staff"  # Default to lowest access if no valid tag


def load_documents():
    """Loads documents from DOCS_FOLDER, extracts role from filename, and adds metadata."""
    print(f"Loading documents from: {DOCS_FOLDER}")
    docs = []
    for ext in ALLOWED_EXTENSIONS:
        for filepath in glob.glob(os.path.join(DOCS_FOLDER, f"*{ext}")):
            filename = os.path.basename(filepath)
            role = get_role_from_filename(filename)
            print(f" - Loading {filename} (Role: {role})")
            try:
                if ext == ".pdf":
                    loader = PyPDFLoader(filepath)
                elif ext == ".txt":
                    loader = TextLoader(filepath)
                else:
                    continue  # Should not happen due to glob pattern

                loaded_docs = loader.load()
                # Add metadata (role and source) to each document page/chunk precursor
                for doc in loaded_docs:
                    doc.metadata["role"] = role
                    doc.metadata["source"] = filename  # Keep track of original file
                docs.extend(loaded_docs)
            except Exception as e:
                print(f"   Error loading {filename}: {e}")
    print(f"Total documents loaded: {len(docs)}")
    return docs


# --- Text Splitting ---
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP
)

# --- Embeddings ---
print(f"Loading embedding model: {EMBEDDING_MODEL}")
embeddings = SentenceTransformerEmbeddings(model_name=EMBEDDING_MODEL)
print("Embedding model loaded.")

# --- Vector Store ---
vector_store = None


def create_or_load_vector_store():
    """Creates the vector store if it doesn't exist, otherwise loads it."""
    global vector_store
    if os.path.exists(VECTOR_STORE_PATH):
        print(f"Loading existing vector store from: {VECTOR_STORE_PATH}")
        vector_store = FAISS.load_local(VECTOR_STORE_PATH, embeddings,
                                        allow_dangerous_deserialization=True)  # Be careful with this in production
        print("Vector store loaded.")
    else:
        print("Creating new vector store...")
        documents = load_documents()
        if not documents:
            print("No documents found to create vector store. Aborting.")
            return None

        chunks = text_splitter.split_documents(documents)
        # Ensure metadata is preserved during splitting
        # RecursiveCharacterTextSplitter usually does this automatically
        print(f"Split documents into {len(chunks)} chunks.")

        # Example check for metadata persistence
        if chunks and 'role' not in chunks[0].metadata:
            print("Warning: Metadata might not be preserved correctly during splitting!")

        print("Creating FAISS index...")
        vector_store = FAISS.from_documents(chunks, embeddings)
        print("FAISS index created.")
        print(f"Saving vector store to: {VECTOR_STORE_PATH}")
        vector_store.save_local(VECTOR_STORE_PATH)
        print("Vector store saved.")
    return vector_store


# Ensure vector store is loaded/created when module is imported
vector_store = create_or_load_vector_store()

# --- LLM and RAG Chain ---

if vector_store:
    print(f"Initializing LLM: {LLM_MODEL}")
    llm = Ollama(model=LLM_MODEL)
    print("LLM initialized.")

    # Define the RAG prompt template
    # Explicitly telling the LLM to use *only* the context is crucial for reducing hallucinations.
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

    # Output parser
    output_parser = StrOutputParser()


    def filter_documents_by_role(docs, user_role):
        """Filters retrieved documents based on user's role hierarchy."""
        user_level = ROLE_HIERARCHY.get(user_role, 0)
        allowed_docs = []
        print(f"Filtering {len(docs)} retrieved docs for user role '{user_role}' (level {user_level})...")
        for doc in docs:
            doc_role = doc.metadata.get("role", "staff")  # Default to lowest if missing
            doc_level = ROLE_HIERARCHY.get(doc_role, 0)
            if user_level >= doc_level:
                print(
                    f"  - Allowing doc from '{doc.metadata.get('source', 'N/A')}' (role: {doc_role}, level: {doc_level})")
                allowed_docs.append(doc)
            else:
                print(
                    f"  - Denying doc from '{doc.metadata.get('source', 'N/A')}' (role: {doc_role}, level: {doc_level}) - Requires higher role.")
        print(f"Allowed {len(allowed_docs)} docs after filtering.")
        return allowed_docs


    def format_docs(docs):
        """Helper function to format documents for the prompt context."""
        if not docs:
            return "No relevant documents found or accessible."
        # Include source and role info in context for clarity (optional but helpful for debugging)
        # return "\n\n".join(f"Source: {doc.metadata.get('source', 'N/A')}, Role: {doc.metadata.get('role', 'N/A')}\nContent: {doc.page_content}" for doc in docs)
        # Simpler version for final prompt:
        return "\n\n".join(doc.page_content for doc in docs)


    # Define the RAG chain
    def get_rag_chain(user_role):
        """Creates and returns the RAG chain, incorporating role-based filtering."""
        if not vector_store:
            print("Error: Vector store not available.")
            # Return a dummy chain or raise an error
            return RunnablePassthrough()  # Placeholder that does nothing useful

        retriever = vector_store.as_retriever(search_kwargs={"k": 5})  # Retrieve top 5 chunks initially

        # Chain definition
        rag_chain = (
                {"context": (lambda x: x['question']) | retriever | (
                    lambda docs: filter_documents_by_role(docs, user_role)) | format_docs,
                 "question": RunnablePassthrough()}
                | prompt
                | llm
                | output_parser
        )
        return rag_chain

else:
    print("Cannot initialize RAG chain because vector store failed to load/create.")


    # Define a placeholder function or handle this error appropriately in the app
    def get_rag_chain(user_role):
        raise RuntimeError("RAG system could not be initialized. Check document loading and vector store creation.")