import re
from config import TICKET_KEYWORD_MAP, TICKET_TEAMS
from database_utils import save_ticket


def suggest_ticket_team(question):
    """Suggests a ticket team based on keywords in the question."""
    question_lower = question.lower()
    # Use word boundaries to avoid partial matches (e.g., 'manager' in 'management')

    for team, keywords in TICKET_KEYWORD_MAP.items():
        for keyword in keywords:
            # Simple check if keyword exists as a whole word or part of the question
            # Using regex for slightly better matching (e.g., handles plurals simply sometimes)
            if re.search(r'\b' + re.escape(keyword) + r'\b', question_lower):  # \b is word boundary
                print(f"Keyword '{keyword}' matched for team '{team.upper()}'")
                return team.upper()  # Return the standardized team name
            # Fallback simple check if regex fails or for broader match
            elif keyword in question_lower:
                print(f"Substring '{keyword}' matched for team '{team.upper()}'")
                return team.upper()

    print("No specific keywords matched, suggesting 'General'.")
    return "General"  # Default team if no keywords match


def create_ticket(user_role, question, chat_history_summary, suggested_team, selected_team):
    """Creates a ticket entry."""
    print(f"Creating ticket for team '{selected_team}' (Suggested: '{suggested_team}')")
    success = save_ticket(
        user_role=user_role,
        question=question,
        chat_history=chat_history_summary,  # Store summary or relevant part
        suggested_team=suggested_team,
        selected_team=selected_team
    )
    return success