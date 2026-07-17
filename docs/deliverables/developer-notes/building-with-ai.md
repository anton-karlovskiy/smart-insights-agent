# Developer's Notes: Building the Smart Insights Agent with AI

*These are my personal notes from developing this project. They are not part of the requested deliverables, but I believe they offer useful insight into how the tool was built and how I work.*

## 1. The overfitting trap, and why a human's eyes still matter

I built the architecture and workflow with AI, based on the given assignment brief and the sample data. Specifically, I used Claude Code driven by the Opus 4.8 and Fable 5 models. At first, though, the result was not what I expected. The AI knew both the project spec and the exact data it would have to handle, so it produced an architecture that fit the sample data *too* well. It already knew the specific edge cases and anomalies in those 30 rows: an impossible `opt_in_rate` of 105.0 or -0.5, a rate of 0.0 alongside 15,000 unique visitors, a "SaaS" industry label on a site whose notes describe selling baking sheets, and the disagreements between `opt_in_rate`, `reported_industry`, and `current_setup_notes`. It quietly designed around those exact rows.

You can see how wrong the initial architecture and workflow were by going back through the git commit history to the first version of `SPEC.md`. (`SPEC.md` is the description of what you are building that is fed to the AI: a plain-English contract covering the pipeline, the data schemas, and the commands, which the coding agent then compiles into working code. In this workflow the specification is the real artifact, and the code is a compilation target.) With that first architecture, the AI would have built a tool that overfits the sample data: perfect results on the given sample, wrong results on any other data.

I think that is where a human's engineering eyes are necessary. I reviewed the initially generated `SPEC.md` very thoroughly, and I refined and corrected it by prompting (steering the AI) rather than editing it by hand. That is the first step in agentic engineering: with AI coding agents, we engineers now spend more time writing technical specs and plans than writing code. This project bears that out. Of the 38 curated prompts that built it, 23 (sixty percent) landed before a single line of code was generated. The full analysis of how the agent was steered, prompt by prompt, is in the accompanying [agentic engineering review](../developer-ai-log/agentic-engineering-review.md).

I updated `SPEC.md` by combining different models. In general, I use Opus 4.8 for everyday complex tasks, Fable 5 for the hardest and longest-running tasks, and Haiku for the fastest quick answers, because tokens cost money in the AI world.

## 2. Designed for production scale, not just 30 rows

Although only a 30-row dataset was given for this prototype, I designed and built the tool with production in mind, so it can be applied to real-world data that could run to millions of rows.

My pitch split the tool into two layers. Layer 1 is the data layer: group all websites into peer segments by industry, then for each segment compute the average opt-in rate and identify what the top performers have in common. Layer 2 is where a scoped LLM turns the facts computed in layer 1 into a friendly, plain-English message. The averaging and counting in layer 1 are ordinary data work: no AI, just grouping and arithmetic.

But the grouping itself turned out to need a scoped LLM too, and this is where the build diverged from the plan. I had pitched layer 1 as pure data work with no AI. In practice, the industry labels are messy free text ("eCommerce", "E-comm", "Retail / Ecom", "SaaS"), and no fixed lookup table can merge wordings it has never seen. With millions of rows, building such a table would be impossible anyway. So one LLM call derives the segment set from the data's own industry values, deterministic code validates and applies it, and the result is committed to disk so every later run reads the exact same segments. The LLM only decides which labels mean the same industry. It never touches the numbers. So the honest picture is that AI appears in both layers, cleaning the inputs in layer 1 and wording the recommendation in layer 2, while deterministic code still owns every statistic.

Traditional cleaning (regex, string operations) can only get you so far. The interesting part is that an LLM serves as a data-normalization engine sitting upstream in the pipeline, turning messy, heterogeneous free-text notes (the kind of thing a support rep types into a CRM) into uniform, information-dense records. The general principle: cheap and deterministic first, LLM second, and never spend a token on a row you would have dropped.

At production scale, a huge number of synchronous API calls is the wrong shape. The right move is the provider's batch API: you trade latency (a 24-hour completion window) for a substantial discount. I did not use the batch API here, since the data is just 30 rows, but I documented that use case in `README.md` for the millions-of-rows scenario.

## 3. Edge cases

I ran into three edge cases while developing this tool. There could be more, depending on the angle you look at the project from.

1. **Fields that disagree.** `reported_industry`, `opt_in_rate`, and `current_setup_notes` can contradict each other: a rate of 0.0 with 15k visitors, a rate with no email field to opt into, an industry label that contradicts the notes. These are detectable only by reading prose, so an LLM reads them, and its explanation is recorded as the value of the `edge_case_anomaly` field.

2. **Thin segments.** A peer benchmark averaged over one or two websites is not a real benchmark. The LLM call that derives the segment set is shown how many websites each industry wording covers, and it is steered to avoid creating segments too thin to benchmark in the first place. Where a small segment still occurs (fewer than three clean websites), the benchmark is computed anyway but flagged `low_confidence`. The flag is surfaced in the report, and the recommendation for those rows is never allowed to claim high confidence. There is no invented fallback logic: the tool simply says that the comparison rests on thin evidence.

3. **The target row is itself the top performer.** How do you generate an insight for the site that nobody in its segment beats? The insight prompt handles this as an explicit case. When the list of better-performing peers is empty, the model states that the site leads its segment and shifts from "imitate the top performers" to "protect and probe": keep the winning setup and A/B test exactly one variation of it, grounded in the site's own setup notes. And when the site is the only one in its segment, the tool says plainly that there are no comparable sites yet (no congratulations for leading a field of one) and recommends the one A/B test its own setup most invites.

## 4. Reading the git history

- `82e3dbf` to `a5142c0`: Claude Code setup (the `.claude` directory contents and `.mcp.json`)
- `d3641fc` to `b85a70c`: `SPEC.md` write-up and tuning
- `88b4df4` onward: building and polishing

## 5. Honest reflections

To be honest, this project took me a bit more time than I expected. I could have built a quick version without considering production standards and scalability. But I believe it is more important to do it right than to do it quickly, and throughout this project I wanted to show that I am a detail-oriented software developer with a production mindset.

Professionally speaking, I should have studied OptinMonster's operations in depth before building this tool. But the given data was small and compact, and the project description was clear, so I proceeded on that basis.

## 6. How I develop in the current AI era

I do not start vibecoding right after receiving project specs and requirements. First I do a lot of research on the project (paperwork, if you like), checking its specs and requirements in detail, and on top of that I decide the direction of the project. Architecture and workflow come before vibecoding.

After every vibecoding session, I manually review and evaluate the generated code and refine it, because AI can hallucinate facts, make logical errors, introduce security vulnerabilities, and produce output that would not pass a basic code review, let alone be suitable for production. So for AI-generated code I make sure I understand the syntax, recognize potential bugs, identify performance bottlenecks, and check adherence to coding standards.

These days, AI replaces much of human work, including software engineering. AI tools can produce code faster than most humans, handle repetitive tasks with ease, and suggest solutions to tricky problems. But they do not understand the *why* behind your project. They just execute instructions. AI coding assistants amplify your existing abilities: they are force multipliers, not replacements for fundamental knowledge. They automate tedious work, but they do not replace critical thinking and design expertise.

My main coding agent is Claude Code, but I do not use it casually. I learned how to use Claude Code effectively from [Claude Code – The Practical Guide](https://github.com/anton-karlovskiy/anton-karlovskiy/blob/main/certificates/Udemy%20certificates/UC-49fa0206-f1c4-46a3-ae59-281af386ed26%20(Claude%20Code%20-%20The%20Practical%20Guide).pdf) and applied those practices to this project too.

So what I do is not vibecoding. It is agentic engineering.

![Vibecoding vs Agentic Engineering](vibecoding-vs-agentic-engineering.png)
