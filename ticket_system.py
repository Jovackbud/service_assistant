# ticket_system.py
import re
from config import TICKET_KEYWORD_MAP, TICKET_TEAMS
from database_utils import save_ticket

def suggest_ticket_team(question):
    """Suggests a ticket team based on keywords in the question."""
    question_lower = question.lower()

    # Iterate through the configured teams and their keywords
    for team_name, keywords in TICKET_KEYWORD_MAP.items():
        # Standardize team name from config key (e.g., "customer support" -> "Customer Support")
        display_team_name = " ".join(word.capitalize() for word in team_name.split())

        for keyword in keywords:
            # Use word boundaries for more precise matching
            if re.search(r'\b' + re.escape(keyword) + r'\b', question_lower):
                print(f"Keyword '{keyword}' matched for team '{display_team_name}'")
                return display_team_name
            # Fallback to simple substring check
            elif keyword in question_lower:
                 print(f"Substring '{keyword}' matched for team '{display_team_name}'")
                 return display_team_name

    # If no specific keywords match across any team
    print("No specific keywords matched, suggesting 'General'.")
    # Ensure 'General' is in the TICKET_TEAMS list from config for consistency
    return "General" if "General" in TICKET_TEAMS else TICKET_TEAMS[0] # Fallback safely

def create_ticket(user_role, question, chat_history_summary, suggested_team, selected_team):
    """Creates a ticket entry in the database."""
    print(f"Creating ticket for team '{selected_team}' (Suggested: '{suggested_team}') submitted by role '{user_role}'")
    success = save_ticket(
        user_role=user_role,
        question=question,
        chat_history=chat_history_summary, # Store summary or relevant part
        suggested_team=suggested_team,
        selected_team=selected_team
    )
    return success