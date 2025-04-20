import streamlit as st
import time # For simulating typing effect

# Import functions from other modules
from config import ROLES, TICKET_TEAMS, LLM_MODEL # Import LLM_MODEL for display
# Import vector_store check and get_rag_chain
from rag_processor import get_rag_chain, vector_store
from ticket_system import suggest_ticket_team, create_ticket
from feedback_system import record_feedback

# --- Streamlit Page Configuration ---
st.set_page_config(page_title="Internal Knowledge Assistant PoC", layout="wide")
st.title("🤖 Company Knowledge Assistant PoC") # Broaden title slightly
st.caption("Ask questions about company information, policies, and procedures.")


# --- Session State Initialization ---
if 'user_role' not in st.session_state:
    st.session_state.user_role = None # Start with no role selected
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
    # Determine index for radio button based on current state
    current_role_index = ROLES.index(st.session_state.user_role) if st.session_state.user_role in ROLES else None

    selected_role = st.radio(
        "Select your role:",
        options=ROLES, # Dynamically uses roles from config, including 'customer'
        key="role_selector",
        index=current_role_index,
    )

    # Update state if a role is selected and it's different from the current one
    if selected_role and selected_role != st.session_state.user_role:
        st.session_state.user_role = selected_role
        st.session_state.chat_history = []
        st.session_state.show_ticket_form = False
        st.session_state.last_question = "" # Clear last question on role change

        if vector_store:
             try:
                 st.session_state.rag_chain = get_rag_chain(st.session_state.user_role)
                 st.success(f"Role set to **{st.session_state.user_role}**. Assistant ready.")
             except Exception as e:
                  st.error(f"Error initializing assistant for this role: {e}")
                  st.session_state.rag_chain = None
        else:
             st.error("Knowledge base not available.")
             st.session_state.rag_chain = None

        st.rerun()


    st.divider()
    if not vector_store:
         st.warning("Knowledge Base Status: Offline.", icon="⚠️")
    elif not st.session_state.user_role:
         st.info("Please select your role in the sidebar to begin.", icon="👤")
    else:
         # Display current role if selected
         st.info(f"Current Role: **{st.session_state.user_role}**")


    st.divider()
    st.caption(f"Model: {LLM_MODEL}")
    st.caption(f"DB: {'Chroma' if vector_store else 'Offline'}")


# --- Chat Interface ---
st.header("Chat Assistant")

# Display chat history
for i, message in enumerate(st.session_state.chat_history):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        # Display feedback buttons for assistant messages if feedback state exists
        if message["role"] == "assistant" and "feedback" in message:
             feedback_state = message["feedback"]
             msg_id = message.get("msg_id", f"msg_{i}")
             feedback_key_base = f"feedback_{msg_id}"

             if feedback_state.get("rating") == "👍":
                  st.button("👍", key=f"{feedback_key_base}_up_voted", disabled=True)
                  st.button("👎", key=f"{feedback_key_base}_down_disabled", disabled=True)
             elif feedback_state.get("rating") == "👎":
                  st.button("👍", key=f"{feedback_key_base}_up_disabled", disabled=True)
                  st.button("👎", key=f"{feedback_key_base}_down_voted", disabled=True)
             elif feedback_state.get("show") and feedback_state.get("rating") is None:
                  col1, col2, _ = st.columns([1, 1, 10])
                  with col1:
                     if st.button("👍", key=f"{feedback_key_base}_up"):
                         record_feedback(st.session_state.user_role, message.get("question", ""), message["content"], "👍")
                         st.session_state.chat_history[i]["feedback"]["rating"] = "👍"
                         st.success("Feedback saved!")
                         time.sleep(0.5)
                         st.rerun()
                  with col2:
                     if st.button("👎", key=f"{feedback_key_base}_down"):
                         record_feedback(st.session_state.user_role, message.get("question", ""), message["content"], "👎")
                         st.session_state.chat_history[i]["feedback"]["rating"] = "👎"
                         st.success("Feedback saved!")
                         time.sleep(0.5)
                         st.rerun()


# Chat input
chat_input_disabled = not st.session_state.user_role or not st.session_state.rag_chain
if prompt := st.chat_input("Ask a question...", disabled=chat_input_disabled, key="chat_input"):
    st.session_state.last_question = prompt
    st.session_state.show_ticket_form = False

    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = "Thinking..."
        message_placeholder.markdown(full_response + "▌")

        try:
            if st.session_state.rag_chain:
                 print(f"Invoking RAG chain for role '{st.session_state.user_role}' with question: '{prompt}'")
                 # Pass the prompt string directly (RunnableLambda handles dict wrapping if needed)
                 response_stream = st.session_state.rag_chain.stream(prompt)

                 streamed_text = ""
                 for chunk in response_stream:
                     streamed_text += chunk
                     message_placeholder.markdown(streamed_text + "▌")
                 full_response = streamed_text
                 message_placeholder.markdown(full_response)

            else:
                full_response = "Assistant is unavailable (chain not loaded)."
                message_placeholder.warning(full_response)

        except Exception as e:
            full_response = f"An error occurred processing your request: {e}"
            message_placeholder.error(full_response)
            print(f"Error during RAG chain invocation: {e}")


        offer_ticket = False
        response_lower = full_response.lower()
        failure_phrases = [
            "i cannot answer that question", "based on the documents i can access",
            "cannot answer that question", "don't have that information",
            "unable to find information", "cannot find information",
            "no relevant documents found", "no relevant documents were found or accessible",
            "knowledge base is currently unavailable", "rag system could not be initialized",
            "error: invalid role"
        ]

        if any(phrase in response_lower for phrase in failure_phrases):
             offer_ticket = True
             matched_phrase = next((p for p in failure_phrases if p in response_lower), "N/A")
             print(f"Ticket offered based on response ('{matched_phrase}'): '{full_response[:100]}...'")

        if offer_ticket:
            st.session_state.show_ticket_form = True
        # --- End Ticket Trigger Logic ---

        msg_id = f"msg_{len(st.session_state.chat_history)}"
        st.session_state.chat_history.append({
            "role": "assistant", "content": full_response, "msg_id": msg_id,
            "question": prompt, "offer_ticket": offer_ticket,
            "feedback": {"show": True, "rating": None}
        })

        st.rerun()


# --- Ticket Creation Form ---
if st.session_state.get("show_ticket_form", False):
    st.divider()
    st.subheader("Need More Help? Create a Ticket")

    # Suggest team based on the last question
    suggested_team = suggest_ticket_team(st.session_state.last_question)
    try:
        # Dynamically use TICKET_TEAMS from config
        default_index = TICKET_TEAMS.index(suggested_team)
    except ValueError:
        default_index = TICKET_TEAMS.index("General") if "General" in TICKET_TEAMS else 0

    selected_team = st.selectbox(
        "Select the most relevant team:",
        options=TICKET_TEAMS,
        index=default_index,
        key="ticket_team_select"
    )

    history_summary = "\n".join([f"{msg['role'].capitalize()}: {msg['content'][:150]}..."
                                 for msg in st.session_state.chat_history[-5:]])

    st.text_area("Ticket Details (auto-filled):",
                 value=f"User Role: {st.session_state.user_role}\nQuestion: {st.session_state.last_question}\n\nRecent Chat:\n{history_summary}",
                 height=250, disabled=True, key="ticket_details_display")

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
            st.session_state.show_ticket_form = False
            time.sleep(2)
            st.rerun()
        else:
            st.error("Failed to submit ticket. Please try again.")