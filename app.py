import streamlit as st
import time # For simulating typing effect

# Import functions from other modules
from config import ROLES, TICKET_TEAMS, LLM_MODEL
# Import vector_store check and get_rag_chain
from rag_processor import get_rag_chain, vector_store
from ticket_system import suggest_ticket_team, create_ticket
from feedback_system import record_feedback

# --- Streamlit Page Configuration ---
st.set_page_config(page_title="Internal Knowledge Assistant PoC", layout="wide")
st.title("🤖 Internal Knowledge Assistant PoC")
st.caption("Ask questions about company policies, projects, and procedures.")


# --- Mock Login & Role Selection ---
# Initialize session state variables if they don't exist
default_role = ROLES[0] # Default to the first role in the list, e.g., 'staff'
if 'user_role' not in st.session_state:
    st.session_state.user_role = None # Start with no role selected initially
if 'rag_chain' not in st.session_state:
     st.session_state.rag_chain = None
if 'show_ticket_form' not in st.session_state:
    st.session_state.show_ticket_form = False
if 'last_question' not in st.session_state:
    st.session_state.last_question = ""
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = [] # Store {'role': 'user'/'assistant', 'content': ...}

# Sidebar for role selection
with st.sidebar:
    st.header("User Role")
    # Use index=None for initial state if user_role is None, otherwise find index
    current_role_index = ROLES.index(st.session_state.user_role) if st.session_state.user_role in ROLES else None

    selected_role = st.radio(
        "Select your role:",
        options=ROLES,
        key="role_selector",
        index=current_role_index, # Set index based on current state or None
        # horizontal=True # Optional: make radio buttons horizontal
    )

    # Update role and RAG chain if role changes *and* a role is actually selected
    if selected_role and selected_role != st.session_state.user_role:
        st.session_state.user_role = selected_role
        st.session_state.chat_history = [] # Clear history on role change
        st.session_state.show_ticket_form = False # Hide ticket form
        if vector_store: # Only create chain if vector store is ready
             try:
                 # Get the chain specifically for the newly selected role
                 st.session_state.rag_chain = get_rag_chain(st.session_state.user_role)
                 st.success(f"Role set to **{st.session_state.user_role}**. Assistant ready.")
             except Exception as e:
                  st.error(f"Error initializing RAG chain: {e}")
                  st.session_state.rag_chain = None # Ensure it's None if error occurs
        else:
             st.error("RAG system not available. Cannot process queries.")
             st.session_state.rag_chain = None

    st.divider()
    if not vector_store:
         st.warning("RAG system failed to initialize. Please check logs.", icon="⚠️")
    elif not st.session_state.user_role:
         st.info("Please select your role in the sidebar to start chatting.", icon="👤")


# --- Chat Interface ---
st.header("Chat")

# Display chat history
for i, message in enumerate(st.session_state.chat_history):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        # Display feedback buttons for assistant messages if feedback state exists
        if message["role"] == "assistant" and "feedback" in message:
             feedback_state = message["feedback"]
             # Ensure msg_id exists, default if necessary
             msg_id = message.get("msg_id", f"msg_{i}")
             feedback_key_base = f"feedback_{msg_id}"

             # Show feedback status, but disable buttons after click
             if feedback_state.get("rating") == "👍":
                  st.button("👍", key=f"{feedback_key_base}_up_voted", disabled=True)
                  st.button("👎", key=f"{feedback_key_base}_down_disabled", disabled=True)
             elif feedback_state.get("rating") == "👎":
                  st.button("👍", key=f"{feedback_key_base}_up_disabled", disabled=True)
                  st.button("👎", key=f"{feedback_key_base}_down_voted", disabled=True)
             # Add feedback buttons only if not yet rated
             elif feedback_state.get("show") and feedback_state.get("rating") is None:
                  col1, col2, _ = st.columns([1, 1, 10]) # Layout for buttons
                  with col1:
                     if st.button("👍", key=f"{feedback_key_base}_up"):
                         record_feedback(st.session_state.user_role, message.get("question", ""), message["content"], "👍")
                         # Update feedback state in chat history directly
                         st.session_state.chat_history[i]["feedback"]["rating"] = "👍"
                         st.success("Feedback saved!")
                         time.sleep(1) # Show message briefly
                         st.rerun() # Rerun to update button state
                  with col2:
                     if st.button("👎", key=f"{feedback_key_base}_down"):
                         record_feedback(st.session_state.user_role, message.get("question", ""), message["content"], "👎")
                         # Update feedback state in chat history directly
                         st.session_state.chat_history[i]["feedback"]["rating"] = "👎"
                         st.success("Feedback saved!")
                         time.sleep(1)
                         st.rerun()


# Chat input - disable if role not selected or RAG chain failed
chat_input_disabled = not st.session_state.user_role or not st.session_state.rag_chain
if prompt := st.chat_input("Ask a question...", disabled=chat_input_disabled):
    st.session_state.last_question = prompt
    st.session_state.show_ticket_form = False # Hide ticket form when new question is asked

    # Add user message to history and display
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get response from RAG chain
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""

        # Simulate typing effect (optional)
        # def stream_chars(text, delay=0.01): ...

        try:
            if st.session_state.rag_chain:
                 print(f"Invoking RAG chain for role '{st.session_state.user_role}' with question: '{prompt}'")
                 # Pass the question as a dictionary, matching the chain's expected input
                 # The RunnableLambda in the chain expects {"question": question_text} implicitly
                 response_stream = st.session_state.rag_chain.stream(prompt) # Pass prompt directly if chain expects raw string

                 # Or if the chain expects a dict:
                 # response_stream = st.session_state.rag_chain.stream({"question": prompt})


                 # Stream response character by character
                 streamed_text = ""
                 for chunk in response_stream:
                     # Assuming chunk is a string piece from StrOutputParser
                     streamed_text += chunk
                     message_placeholder.markdown(streamed_text + "▌") # Blinking cursor effect
                 full_response = streamed_text
                 message_placeholder.markdown(full_response) # Final response

            else:
                full_response = "Sorry, the knowledge assistant is not available right now (chain not loaded)."
                message_placeholder.markdown(full_response)

        except Exception as e:
            full_response = f"An error occurred: {e}"
            message_placeholder.error(full_response)
            print(f"Error during RAG chain invocation: {e}")


        # ---Ticket Trigger Logic ---
        offer_ticket = False
        response_lower = full_response.lower()
        failure_phrases = [
            "i cannot answer that question",
            "based on the documents i can access", # Partial phrase check
            "cannot answer that question", # More general
            "don't have that information",
            "unable to find information",
            "cannot find information",
            "no relevant documents found", # Exact phrase from format_docs
            "no relevant documents were found or accessible", # Partial phrase
            "knowledge base is currently unavailable", # From dummy chain error
            "rag system could not be initialized" # From dummy chain error
        ]

        # Check if *any* of the failure phrases are substrings of the response
        if any(phrase in response_lower for phrase in failure_phrases):
             offer_ticket = True
             # Optional: Log which phrase triggered it for debugging
             matched_phrase = next((p for p in failure_phrases if p in response_lower), "N/A")
             print(f"Ticket offered because response contained a failure phrase ('{matched_phrase}'): '{full_response[:100]}...'")

        # Set the state variable to control the ticket form visibility
        if offer_ticket:
            st.session_state.show_ticket_form = True
        # --- End Updated Ticket Trigger Logic ---

        # Add assistant response to history including ticket/feedback state
        msg_id = f"msg_{len(st.session_state.chat_history)}"
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": full_response,
            "msg_id": msg_id,
            "question": prompt, # Store question with answer for feedback/ticket context
            "offer_ticket": offer_ticket, # Store whether ticket should be offered
            "feedback": {"show": True, "rating": None} # Initialize feedback state
        })

        # Rerun to immediately show feedback buttons for the new message
        st.rerun()


# --- Ticket Creation Form ---
# Use .get() to safely access session state keys that might not be set initially
if st.session_state.get("show_ticket_form", False):
    st.divider()
    st.subheader("Need More Help? Create a Ticket")

    # Suggest team based on the last question asked
    suggested_team = suggest_ticket_team(st.session_state.last_question)
    try:
        # Pre-select suggested team in dropdown if it exists in the list
        default_index = TICKET_TEAMS.index(suggested_team)
    except ValueError:
        # Fallback to 'General' if suggested team isn't valid (e.g., no keywords matched)
        default_index = TICKET_TEAMS.index("General") if "General" in TICKET_TEAMS else 0

    selected_team = st.selectbox(
        "Select the team to route your ticket to:",
        options=TICKET_TEAMS,
        index=default_index,
        key="ticket_team_select"
    )

    # Simple summary of chat history (e.g., last few exchanges)
    history_summary = "\n".join([f"{msg['role'].capitalize()}: {msg['content'][:150]}..." # Truncate long messages slightly more
                                 for msg in st.session_state.chat_history[-5:]]) # Last 5 messages max

    st.text_area("Ticket Details (Question & Chat Summary):", value=f"Question: {st.session_state.last_question}\n\nRecent Chat:\n{history_summary}", height=200, disabled=True)


    if st.button("Submit Ticket", key="submit_ticket_btn"):
        success = create_ticket(
            user_role=st.session_state.user_role,
            question=st.session_state.last_question,
            chat_history_summary=history_summary,
            suggested_team=suggested_team,
            selected_team=selected_team
        )
        if success:
            st.success(f"Ticket submitted successfully to the **{selected_team}** team! They will follow up.")
            st.session_state.show_ticket_form = False # Hide form after submission
            # Keep last question
            time.sleep(2) # Show success message briefly
            st.rerun() # Rerun to hide the form and update UI
        else:
            st.error("Failed to submit the ticket. Please try again or contact support directly.")

# --- Add a footer or sidebar note about the model being used ---
# Placed here to be at the bottom or in sidebar
with st.sidebar:
     st.divider()
     st.caption(f"Powered by: {LLM_MODEL}")
     if not vector_store:
          st.caption("Vector Store Status: Offline")