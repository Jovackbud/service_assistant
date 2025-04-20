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
    if len(parts) > 1 and parts[-1].lower() == 'customer':
        return 'customer'
    elif len(parts) > 1 and parts[-1].lower() in ['staff', 'hr', 'manager']:
        return parts[-1].lower()
    else:
        print(f"Info: No specific role tag found for {filename}. Defaulting to 'manager' access level.")
        return 'manager'


def load_documents():
    print(f"Loading documents from: {DOCS_FOLDER}")
    docs = []
    for ext in ALLOWED_EXTENSIONS:
        for filepath in glob.glob(os.path.join(DOCS_FOLDER, f"*{ext}")):
            filename = os.path.basename(filepath)
            role = get_role_from_filename(filename)
            role_level = ROLE_HIERARCHY.get(role, ROLE_HIERARCHY['customer']) # Default safely
            print(f" - Loading {filename} (Role: {role}, Level: {role_level})")
            try:
                if ext == ".pdf":
                    loader = PyPDFLoader(filepath)
                elif ext == ".txt":
                    loader = TextLoader(filepath)
                else: continue
                loaded_docs = loader.load()
                for doc in loaded_docs:
                    doc.metadata["role"] = role
                    doc.metadata["source"] = filename
                    doc.metadata["role_level"] = role_level
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

# --- Vector Store (ChromaDB) ---
vector_store = None

def create_or_load_vector_store():
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
        documents = load_documents()
        if not documents:
            print("No documents found to create vector store. Aborting.")
            return None

        chunks = text_splitter.split_documents(documents)
        print(f"Split documents into {len(chunks)} chunks.")

        if chunks and 'role_level' not in chunks[0].metadata:
             print("Warning: Metadata ('role_level') might not be propagating correctly during splitting!")

        print("Creating Chroma database...")
        vector_store = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            persist_directory=PERSIST_DIRECTORY
        )
        print(f"Chroma database created and persisted to: {PERSIST_DIRECTORY}")
    return vector_store

vector_store = create_or_load_vector_store()

# --- LLM and RAG Chain ---
if vector_store:
    print(f"Initializing LLM: {LLM_MODEL}")
    llm = Ollama(model=LLM_MODEL)
    print("LLM initialized.")

    template = """
    You are an internal knowledge assistant for OurCompany.
    Answer the question based ONLY on the following context provided.
    If the context is empty, states 'No relevant documents were found or accessible for your role.', or does not contain the answer, state clearly: 'Based on the documents I can access, I cannot answer that question.'
    Do not make up information or use external knowledge. Be concise and helpful.

    Context: {context}
    Question: {question}
    Answer:
    """
    prompt = ChatPromptTemplate.from_template(template)
    output_parser = StrOutputParser()

    def format_docs(docs):
        if not docs:
            return "No relevant documents were found or accessible for your role."
        return "\n\n".join(doc.page_content for doc in docs)

    def get_rag_chain(user_role):
        if not vector_store:
            def explain_issue(_): return "Knowledge base is currently unavailable. Please try again later or contact support."
            return RunnableLambda(explain_issue)

        user_level = ROLE_HIERARCHY.get(user_role, -1)
        if user_level == -1:
             def explain_issue(_): return f"Error: Invalid role '{user_role}'. Access denied."
             return RunnableLambda(explain_issue)

        retriever = vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 5, "filter": {"role_level": {"$lte": user_level}}}
        )
        print(f"Configured Chroma retriever for role '{user_role}' (level {user_level}) with filter: role_level <= {user_level}")

        def retrieve_and_format_docs(data):
            """Retrieves documents using the role-filtered retriever and formats them."""
            if isinstance(data, dict):
                question = data.get("question", "")
            else:
                question = str(data)  # Assume input is the question string

            if not question:
                return "Please provide a question."

            docs = retriever.invoke(question)
            print(
                f"Retrieved {len(docs)} docs after filtering for role '{user_role}' matching query '{question[:50]}...'")
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