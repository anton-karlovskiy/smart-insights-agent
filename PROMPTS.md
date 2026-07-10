## 1.

Read all files inside @applications/AI-First Developer - Awesome Motive/take-home-assignment first.
- @applications/AI-First Developer - Awesome Motive/take-home-assignment/assignment-brief.md
- @applications/AI-First Developer - Awesome Motive/take-home-assignment/understanding-the-pitch.md
- @applications/AI-First Developer - Awesome Motive/take-home-assignment/OptinMonster_Dataset.json

I'm going to develop this assignment project using Claude Code. So the fist step is to write SPEC.md well. Please specify all steps well in SPEC.md in order to complete a high-quality Python CLI project.

The file path is G:\anton\02_projects\smart-insights-agent.

## 2.

Add .gitignore with relevant items for this project.

## 3.

The SPEC.md is a technical specification document which I can use as a foundation to then build this project. So with that in mind, review it again and improve if necessary.

## 4.

I'm using OpenAI GPT model not Claude. Can you update @SPEC.md accordingly?

## 5.

@applications/AI-First Developer - Awesome Motive/take-home-assignment/OptinMonster_Dataset.json

Please review all "current_setup_notes" contents. And give me some insight into what they are for in general. Of course, there are some anomalies but most of them are related to some setup for improving their conversion rates.

Write down what you've described into @"applications/AI-First Developer - Awesome Motive/temp\" as an md file.

## 6.

You can reference the assignment at G:\anton\02_projects\cyber-galaxy\applications\AI-First Developer - Awesome Motive\take-home-assignment\assignment-brief.md .

For data preprocessing namely Cleaning & Normalization, I'm also going to use LLM not just deterministic Python.

As you can see the data at G:\anton\02_projects\smart-insights-agent\data\optinmonster_users.json
- "reported_industry" is messy and expressed with different wording for the same segment. I think we should harmonize them first by adding a separate field named "canonical_industry_segment".
- "current_setup_notes" is is a free-text, human-written description of how each customer has configured their OptinMonster campaign on their site. It is not structured data. It reads like something a support rep or onboarding specialist typed into a CRM: inconsistent casing, some entries in full sentences, some in lowercase fragments, no schema. It also includes some parts that are not related to conversion setup, which should be flagged/filtered in the process of data preprocessing. I'll specify how to handle them down the line.

Review ## 1. Design principles at @SPEC.md and update accordingly.

For your reference, you can check G:\anton\02_projects\cyber-galaxy\applications\AI-First Developer - Awesome Motive\temp\llm-for-data-preprocessing.md to see how LLM is used for modern data science/analysis.

## 7.

Now the design principles look too specific. It should be architecture level main points not implementation details. Please update them. Make them compact and to the point.

## 8.

current_setup_notes is a free-text. So I'm going to use LLM to split it into a list of meaningful passages. And add that list as a separate field again. You can help me name that field.
And when splitting, LLM can also polish passages without inventing new content. The meaning should stay the same but typos and grammar mistakes can be fixed by LLM.
LLM needs to use structured output in this case too.

Review 1. Design principles and update if necessary since I've specified the usage of LLM more.