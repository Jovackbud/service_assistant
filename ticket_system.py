import re
from config import TICKET_KEYWORD_MAP, TICKET_TEAMS
from database_utils import save_ticket

def suggest_ticket_team(question):
    """Suggests a ticket team based on keywords in the question."""
    question_lower = question.lower()

    # Check customer support keywords first if applicable
    if "customer support" in TICKET_KEYWORD_MAP:
         for keyword in TICKET_KEYWORD_MAP["customer support"]:
             if re.search(r'\b' + re.escape(keyword) + r'\b', question_lower):
                 print(f"Keyword '{keyword}' matched for team 'Customer Support'")
                 return "Customer Support"
             elif keyword in question_lower: # Broader substring match as fallback
                 print(f"Substring '{keyword}' matched for team 'Customer Support'")
                 return "Customer Support"

    # Check internal teams
    for team, keywords in TICKET_KEYWORD_MAP.items():
        # Skip customer support keywords if already checked
        if team == "customer support":
            continue

        standardized_team_name = team.upper() # e.g., HR, IT
        for keyword in keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', question_lower):
                print(f"Keyword '{keyword}' matched for team '{standardized_team_name}'")
                return standardized_team_name
            elif keyword in question_lower:
                 print(f"Substring '{keyword}' matched for team '{standardized_team_name}'")
                 return standardized_team_name

    print("No specific keywords matched, suggesting 'General'.")
    return "General" # Default team

def create_ticket(user_role, question, chat_history_summary, suggested_team, selected_team):
    """Creates a ticket entry."""
    print(f"Creating ticket for team '{selected_team}' (Suggested: '{suggested_team}') by user role '{user_role}'")
    success = save_ticket(
        user_role=user_role,
        question=question,
        chat_history=chat_history_summary,
        suggested_team=suggested_team,
        selected_team=selected_team
    )
    return success