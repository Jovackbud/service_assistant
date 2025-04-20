from database_utils import save_feedback

def record_feedback(user_role, question, answer, rating):
    """Records user feedback."""
    print(f"Recording feedback: {rating} for question: '{question[:50]}...'")
    success = save_feedback(
        user_role=user_role,
        question=question,
        answer=answer,
        rating=rating
    )
    return success