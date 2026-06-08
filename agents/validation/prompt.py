VALIDATION_PROMPT = """
Analyze the user's input and determine if it describes a realistic, actionable learning goal.
If it is unrealistic, too vague, or contains unsafe/harmful intent, set 'valid' to false and provide a brief, polite explanation in 'feedback'.
If it is valid, set 'valid' to true and rephrase the goal into a clear, specific, and ambitious one-sentence target.
Return the result as a JSON object with keys: 'valid' (boolean), 'feedback' (string), and 'refined_goal' (string).

Input:
{user_input}
"""
