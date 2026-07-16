## The Challenge: The OptinMonster "Smart-Insights" Micro-Agent

### 1. The Goal

Build a lightweight Python CLI tool or micro-API that takes a messy, raw dataset of OptinMonster users (attached), normalizes the data, and uses an LLM to generate a personalized, plain-English "next-best-action" recommendation for each user.

## 2. The Core Tasks

- **Data Cleaning & Normalization:** Standardize the users' industries and catch any anomalies or impossible metrics in the dataset before passing them to the AI.
- **The Insight Generator:** Pass the cleaned data to an LLM to output a specific recommendation based on their current setup and conversion rates.
- **Reliability/Evaluation:** Include a basic script or mechanism to ensure the LLM's recommendations are structured and safe, rather than relying blindly on raw text outputs.

## What to Submit (The Deliverables)

To respect your time, this should take no more than 3 to 4 hours. Please provide a link to a GitHub repository containing:

1. **The Code:** Your functional Python script or micro-service.
2. **PROMPTS.md (Your AI Log):** A simple markdown file documenting the prompts you used, which LLMs you collaborated with, and where you had to manually override the AI's code because it hallucinated or wrote something sub-optimal.
3. **A 3-5 Minute Loom Video:** A relaxed, async screen-share video walking us through your solution. Don't worry about making the audio perfect. Just walk us through:
  - Your architectural choices.
  - How you handled data hygiene and edge cases.
  - One specific place where the AI gave you bad code/logic and how you corrected it.

## The Dataset

Please use the following 30-row mock JSON dataset for your project. Be aware that this is raw user data—it contains real-world messiness, typos, and systemic anomalies that your pipeline will need to navigate intelligently.