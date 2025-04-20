import streamlit as st
import time  # For simulating typing effect

# Import functions from other modules
from config import ROLES, TICKET_TEAMS
from rag_processor import get_rag_chain, vector_store  # Import vector_store to check if initialized
from ticket_system import suggest_ticket_team, create_ticket
from feedback_system import record_feedback

# --- Streamlit Page Configuration ---
st.set_page_config(page_title="Internal Knowledge Assistant PoC", layout="wide")
st.title("🤖 Internal Knowledge Assistant PoC")
st.caption("Ask questions about company policies, projects, and procedures.")

# --- Initialize Database ---
# (Done implicitly by importing database_utils in other modules)

# --- Mock Login & Role Selection ---
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'rag_chain' not in st.session_state:
    st.session_state.rag_chain = None
if 'show_ticket_form' not in st.session_state:
    st.session_state.show_ticket_form = False
if 'last_question' not in st.session_state:
    st.session_state.last_question = ""
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []  # Store {'role': 'user'/'assistant', 'content': ...}

# Sidebar for role selection
with st.sidebar:
    st.header("User Role")
    selected_role = st.radio(
        "Select your role:",
        options=ROLES,
        key="role_selector",
        # index=0 # Default selection
        index=ROLES.index(st.session_state.user_role) if st.session_state.user_role else 0,
        # horizontal=True # Optional: make radio buttons horizontal
    )

    # Update role and RAG chain if role changes
    if selected_role != st.session_state.user_role:
        st.session_state.user_role = selected_role
        st.session_state.chat_history = []  # Clear history on role change
        st.session_state.show_ticket_form = False
        if vector_store:  # Only create chain if vector store is ready
            try:
                st.session_state.rag_chain = get_rag_chain(st.session_state.user_role)
                st.success(f"Role set to **{st.session_state.user_role}**. RAG chain updated.")
                st.rerun()  # Rerun to clear main page state if needed
            except Exception as e:
                st.error(f"Error initializing RAG chain: {e}")
                st.session_state.rag_chain = None  # Ensure it's None if error occurs
        else:
            st.error("RAG system not available. Cannot process queries.")
            st.session_state.rag_chain = None

    st.divider()
    if not vector_store:
        st.warning("RAG system failed to initialize. Please check logs and ensure documents are present.", icon="⚠️")
    elif not st.session_state.user_role:
        st.warning("Please select your role to begin.", icon="👤")

# --- Chat Interface ---
st.header("Chat")

# Display chat history
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        # Display feedback buttons for assistant messages if feedback exists
        if message["role"] == "assistant" and "feedback" in message:
            feedback_key = f"feedback_{message['msg_id']}"  # Unique key
            # Show feedback status, but disable buttons after click
            if message["feedback"]["rating"] == "👍":
                st.button("👍", key=f"{feedback_key}_up_voted", disabled=True)
                st.button("👎", key=f"{feedback_key}_down_disabled", disabled=True)
            elif message["feedback"]["rating"] == "👎":
                st.button("👍", key=f"{feedback_key}_up_disabled", disabled=True)
                st.button("👎", key=f"{feedback_key}_down_voted", disabled=True)

# Chat input
if prompt := st.chat_input("Ask a question...",
                           disabled=(not st.session_state.user_role or not st.session_state.rag_chain)):
    st.session_state.last_question = prompt
    st.session_state.show_ticket_form = False  # Hide ticket form when new question is asked

    # Add user message to history and display
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get response from RAG chain
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""


        # Simulate typing effect (optional)
        def stream_chars(text, delay=0.01):
            for char in text:
                yield char
                time.sleep(delay)


        try:
            if st.session_state.rag_chain:
                print(f"Invoking RAG chain for role '{st.session_state.user_role}' with question: '{prompt}'")
                # Pass the question correctly based on how the chain expects input
                response_stream = st.session_state.rag_chain.stream({"question": prompt})

                # Stream response character by character
                streamed_text = ""
                for chunk in response_stream:
                    # Assuming chunk is a string piece from StrOutputParser
                    streamed_text += chunk
                    message_placeholder.markdown(streamed_text + "▌")  # Blinking cursor effect
                full_response = streamed_text
                message_placeholder.markdown(full_response)  # Final response

            else:
                full_response = "Sorry, the knowledge assistant is not available right now."
                message_placeholder.markdown(full_response)

        except Exception as e:
            full_response = f"An error occurred: {e}"
            message_placeholder.error(full_response)
            print(f"Error during RAG chain invocation: {e}")

        # Check if the response indicates inability to answer
        # Add more sophisticated checks if needed (e.g., keywords like "don't know", "cannot find")
        offer_ticket = False
        if "don't have that information" in full_response.lower() or \
                "no relevant documents found" in full_response.lower() or \
                "cannot access that" in full_response.lower():  # Placeholder for explicit access denial
            offer_ticket = True
            st.session_state.show_ticket_form = True

        # Add assistant response to history
        msg_id = f"msg_{len(st.session_state.chat_history)}"  # Unique ID for feedback
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": full_response,
            "msg_id": msg_id,
            "question": prompt,  # Store question with answer for feedback context
            "offer_ticket": offer_ticket,
            "feedback": {"show": True, "rating": None}  # Add feedback state
        })

        # Add feedback buttons immediately after response (only if feedback not yet given)
        feedback_state = st.session_state.chat_history[-1]["feedback"]
        if feedback_state["show"] and feedback_state["rating"] is None:
            col1, col2, _ = st.columns([1, 1, 10])  # Layout for buttons
            with col1:
                if st.button("👍", key=f"up_{msg_id}"):
                    record_feedback(st.session_state.user_role, prompt, full_response, "👍")
                    st.session_state.chat_history[-1]["feedback"]["rating"] = "👍"
                    st.success("Feedback saved!")
                    time.sleep(1)  # Show message briefly
                    st.rerun()  # Rerun to update button state
            with col2:
                if st.button("👎", key=f"down_{msg_id}"):
                    record_feedback(st.session_state.user_role, prompt, full_response, "👎")
                    st.session_state.chat_history[-1]["feedback"]["rating"] = "👎"
                    st.success("Feedback saved!")
                    time.sleep(1)
                    st.rerun()

# --- Ticket Creation Form ---
if st.session_state.show_ticket_form:
    st.divider()
    st.subheader("Need More Help? Create a Ticket")

    # Suggest team based on the last question
    suggested_team = suggest_ticket_team(st.session_state.last_question)
    try:
        # Pre-select suggested team in dropdown
        default_index = TICKET_TEAMS.index(suggested_team)
    except ValueError:
        default_index = TICKET_TEAMS.index("General")  # Fallback if suggested team isn't in the list

    selected_team = st.selectbox(
        "Select the team to route your ticket to:",
        options=TICKET_TEAMS,
        index=default_index,
        key="ticket_team_select"
    )

    # Simple summary of chat history (e.g., last few exchanges)
    history_summary = "\n".join([f"{msg['role'].capitalize()}: {msg['content'][:100]}..."  # Truncate long messages
                                 for msg in st.session_state.chat_history[-5:]])  # Last 5 messages

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
            st.session_state.show_ticket_form = False  # Hide form after submission
            time.sleep(2)  # Show success message
            st.rerun()
        else:
            st.error("Failed to submit the ticket. Please try again or contact support directly.")