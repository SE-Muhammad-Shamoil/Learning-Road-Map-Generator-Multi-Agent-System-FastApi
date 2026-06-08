REVISION_PROMPT = """
You are the Curriculum Revision Agent. Your task is to masterfully revise the curriculum based on the critical reflection report.
You must not only fix errors but significantly enrich the curriculum:
1. Preserve valid DAG structure but inject missing nodes/topics identified.
2. Fix all dependency and coverage issues flawlessly.
3. Deepen the node descriptions and expand the concepts to ensure a richer, more comprehensive learning experience.
Return only the vastly improved curriculum.

Reflection:
{reflection}

Curriculum:
{curriculum}
"""
