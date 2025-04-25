import streamlit as st
import time # For simulating typing effect

# Import functions and configurations
from config import ROLES, TICKET_TEAMS, LLM_MODEL # Use lists directly from config
from rag_processor import get_rag_chain, vector_store # Import check and function
from ticket_system import suggest_ticket_team, create_ticket
from feedback_system import record_feedback

# --- Streamlit Page Configuration ---
st.set_page_config(page_title="Company Knowledge Assistant PoC", layout="wide")
st.title("🤖 Company Knowledge Assistant PoC")
st.caption("Ask questions about company information, policies, and procedures.")

# --- Session State Initialization ---
# Ensure session state keys exist
if 'user_role' not in st.session_state:
    st.session_state.user_role = None # Start without a role selected
if 'rag_chain' not in st.session_state:
     st.session_state.rag_chain = None
if 'show_ticket_form' not in st.session_state:
    st.session_state.show_ticket_form = False
if 'last_question' not in st.session_state:
    st.session_state.last_question = ""
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# --- Sidebar ---
with st.sidebar:
    st.header("User Role")
    # Find the index of the current role for the radio button default
    current_role_index = ROLES.index(st.session_state.user_role) if st.session_state.user_role in ROLES else None

    selected_role = st.radio(
        "Select your role:",
        options=ROLES, # Use roles defined in config.py
        key="role_selector",
        index=current_role_index, # Set default based on current state
    )

    # Handle role change
    if selected_role and selected_role != st.session_state.user_role:
        print(f"Role changed from {st.session_state.user_role} to {selected_role}")
        st.session_state.user_role = selected_role
        # Reset state on role change
        st.session_state.chat_history = []
        st.session_state.show_ticket_form = False
        st.session_state.last_question = ""
        st.session_state.rag_chain = None # Reset chain

        if vector_store:
             try:
                 # Get a new RAG chain configured for the selected role
                 st.session_state.rag_chain = get_rag_chain(st.session_state.user_role)
                 st.success(f"Role set to **{st.session_state.user_role}**. Ready to chat.")
             except Exception as e:
                  st.error(f"Error initializing assistant for role '{selected_role}': {e}")
                  st.session_state.rag_chain = None
        else:
             st.error("Knowledge base connection failed.")
             st.session_state.rag_chain = None

        # Rerun to update the main page state after role change
        st.rerun()

    st.divider()
    # Display status messages
    if not vector_store:
         st.warning("Knowledge Base: Offline.", icon="⚠️")
    elif not st.session_state.user_role:
         st.info("Please select your role to start.", icon="👤")
    else:
         st.info(f"Current Role: **{st.session_state.user_role}**") # Confirm selected role

    # Display backend info
    st.divider()
    st.caption(f"Model: {LLM_MODEL}")
    st.caption(f"Vector DB: {'Chroma' if vector_store else 'Offline'}")

# --- Chat Interface ---
st.header("Chat Assistant")

# Display chat history
for i, message in enumerate(st.session_state.chat_history):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        # Display feedback buttons for previous assistant messages if applicable
        if message["role"] == "assistant" and "feedback" in message:
             feedback_state = message["feedback"]
             msg_id = message.get("msg_id", f"msg_{i}")
             feedback_key_base = f"feedback_{msg_id}"

             # Show feedback status if already rated
             if feedback_state.get("rating") == "👍":
                  st.button("👍", key=f"{feedback_key_base}_up_voted", disabled=True)
                  st.button("👎", key=f"{feedback_key_base}_down_disabled", disabled=True)
             elif feedback_state.get("rating") == "👎":
                  st.button("👍", key=f"{feedback_key_base}_up_disabled", disabled=True)
                  st.button("👎", key=f"{feedback_key_base}_down_voted", disabled=True)
             # Show buttons if feedback is pending
             elif feedback_state.get("show") and feedback_state.get("rating") is None:
                  col1, col2, _ = st.columns([1, 1, 10])
                  with col1:
                     if st.button("👍", key=f"{feedback_key_base}_up"):
                         record_feedback(st.session_state.user_role, message.get("question", ""), message["content"], "👍")
                         st.session_state.chat_history[i]["feedback"]["rating"] = "👍" # Update state
                         st.toast("Feedback saved!", icon="✅")
                         time.sleep(0.5)
                         st.rerun()
                  with col2:
                     if st.button("👎", key=f"{feedback_key_base}_down"):
                         record_feedback(st.session_state.user_role, message.get("question", ""), message["content"], "👎")
                         st.session_state.chat_history[i]["feedback"]["rating"] = "👎" # Update state
                         st.toast("Feedback saved!", icon="✅")
                         time.sleep(0.5)
                         st.rerun()


# Chat input area
chat_input_disabled = not st.session_state.user_role or not st.session_state.rag_chain
if prompt := st.chat_input("Ask your question here...", disabled=chat_input_disabled, key="chat_input"):
    st.session_state.last_question = prompt
    # Hide ticket form when a new question is asked
    st.session_state.show_ticket_form = False

    # Display user message
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Process and display assistant response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("Thinking...▌")  # Initial placeholder

        full_response = ""
        try:
            if st.session_state.rag_chain:
                print(f"Invoking RAG chain for role '{st.session_state.user_role}' with question: '{prompt}'")
                response_stream = st.session_state.rag_chain.stream(prompt)

                streamed_text = ""
                for chunk in response_stream:
                    streamed_text += chunk
                    message_placeholder.markdown(streamed_text + "▌")
                full_response = streamed_text
                # message_placeholder.markdown(full_response) # <-- Display happens *after* cleanup now

            else:
                full_response = "Assistant is currently unavailable..."
                # message_placeholder.warning(full_response) # <-- Display happens *after* potential cleanup

        except Exception as e:
            full_response = f"An error occurred: {e}"
            # message_placeholder.error(full_response) # <-- Display happens *after* potential cleanup
            print(f"Error during RAG chain invocation: {e}")

        # --- START: Add <think> tag cleanup ---
        original_llm_output = full_response  # Keep original for potential debugging
        if "</think>" in full_response:
            print(f"Original LLM output includes </think> tag: {original_llm_output[:150]}...")
            # Split by the closing tag and take the last part
            cleaned_response = full_response.split("</think>")[-1].strip()

            # Optional: Handle cases where cleanup might leave an empty string
            if not cleaned_response:
                print(
                    "Warning: Cleanup resulted in empty string. Falling back to original response minus tags (simple approach).")
                # A simple fallback, might need refinement based on observed LLM behavior
                import re

                cleaned_response = re.sub(r"<think>.*?</think>", "", full_response, flags=re.DOTALL).strip()
                if not cleaned_response:  # If still empty, use original
                    cleaned_response = original_llm_output

            full_response = cleaned_response  # Update full_response with the cleaned version
            print(f"Cleaned LLM response: {full_response[:150]}...")
        # --- END: Add <think> tag cleanup ---

        # Now display the potentially cleaned response
        # Determine message type based on original or error status
        if "An error occurred:" in original_llm_output:
            message_placeholder.error(full_response)
        elif "Assistant is currently unavailable" in original_llm_output:
            message_placeholder.warning(full_response)
        else:
            message_placeholder.markdown(full_response)

        # --- Ticket Trigger Logic ---
        # This logic now uses the potentially cleaned 'full_response'
        offer_ticket = False
        response_lower = full_response.lower()
        failure_phrases = [
            # ... (keep your list of failure phrases) ...
            "i cannot answer that question",
            "based on the documents i can access",
            "cannot answer that question",
            "don't have that information",
            "unable to find information",
            "cannot find information",
            "no relevant documents found",
            "no relevant documents were found or accessible",
            "knowledge base is currently unavailable",
            "rag system could not be initialized",
            "error: invalid role"
        ]
        # ... (rest of ticket logic remains the same) ...
        if any(phrase in response_lower for phrase in failure_phrases):
            offer_ticket = True
            # ...

        if offer_ticket:
            st.session_state.show_ticket_form = True
        # --- End Ticket Trigger Logic ---

        # Store assistant message details in history
        # Crucially, store the *cleaned* full_response here
        msg_id = f"msg_{len(st.session_state.chat_history)}"
        st.session_state.chat_history.append({
            "role": "assistant", "content": full_response,  # <-- Store cleaned response
            "msg_id": msg_id,
            "question": prompt,
            "offer_ticket": offer_ticket,
            "feedback": {"show": True, "rating": None}
        })

        st.rerun()


# --- Ticket Creation Form ---
# Display form if the 'show_ticket_form' state is True
if st.session_state.get("show_ticket_form", False):
    st.divider()
    st.subheader("Request Further Assistance?")
    st.caption("If the assistant couldn't help, you can create a ticket for the appropriate team.")

    # Suggest team based on the last question
    suggested_team = suggest_ticket_team(st.session_state.last_question)
    try:
        # Find index of suggested team, fallback to General
        default_index = TICKET_TEAMS.index(suggested_team)
    except ValueError:
        default_index = TICKET_TEAMS.index("General") if "General" in TICKET_TEAMS else 0

    # Team selection dropdown
    selected_team = st.selectbox(
        "Select the most relevant team:",
        options=TICKET_TEAMS, # Use teams from config
        index=default_index,
        key="ticket_team_select"
    )

    # Prepare chat summary for the ticket
    history_summary = "\n".join([f"{msg['role'].capitalize()}: {msg['content'][:150]}..." # Truncate long messages
                                 for msg in st.session_state.chat_history[-5:]]) # Last 5 messages

    # Display ticket details (read-only)
    st.text_area("Ticket Details (auto-filled):",
                 value=f"User Role: {st.session_state.user_role}\nQuestion: {st.session_state.last_question}\n\nRecent Chat:\n{history_summary}",
                 height=250, disabled=True, key="ticket_details_display")

    # Submit button
    if st.button("Submit Ticket", key="submit_ticket_btn"):
        success = create_ticket(
            user_role=st.session_state.user_role,
            question=st.session_state.last_question,
            chat_history_summary=history_summary,
            suggested_team=suggested_team,
            selected_team=selected_team
        )
        if success:
            st.success(f"Ticket submitted successfully to **{selected_team}**!")
            st.session_state.show_ticket_form = False # Hide form
            time.sleep(2.5) # Show success message
            st.rerun() # Update UI
        else:
            st.error("Failed to submit the ticket. Please try again later.")