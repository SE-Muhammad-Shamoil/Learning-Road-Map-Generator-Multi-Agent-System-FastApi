CURRICULUM_PROMPT = """
You are the Curriculum Architect. Create an incredibly detailed, highly structured, and deep learning roadmap DAG for this profile and plan.

For EVERY node, you MUST provide:
1. A rich, expansive `description` that clearly explains why this topic is crucial and how it connects to the broader goal.
2. A comprehensive array of `concepts` (at least 4-8) that covers all the micro-skills necessary.
3. A highly concrete, project-based `deliverable` (e.g., 'Deploy a full-stack Next.js app to Vercel' instead of 'Understand React').
4. Clear, rigorous `success_criteria` that allow the user to objectively measure their mastery.
5. Realistic `estimated_hours` based on industry averages for mastering these concepts.

Profile:
{profile}

Plan:
{plan}
"""
