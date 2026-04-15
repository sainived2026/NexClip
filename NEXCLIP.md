# 🎬 NexClip & The Autonomous Intelligence Engine

## 🌟 What is NexClip?
**NexClip** is a production-grade, AI-powered SaaS platform designed to transform long-form videos into viral short-form clips. Unlike standard video clippers, NexClip doesn't just blindly cut and transcribe video; it is powered by an autonomous, self-evolving intelligence ecosystem that understands what makes content go viral and automatically publishes it across the internet.

## 🧠 What is Nexearch?
**Nexearch** is the brain inside NexClip—an autonomous social media intelligence engine. It makes NexClip a continuously learning system. Nexearch is responsible for scraping data across 6 major platforms (Instagram, TikTok, YouTube, LinkedIn, Twitter/X, Facebook), analyzing thousands of posts, scoring them, and evolving the content strategy. 

It synthesizes an **Account DNA**—a unique fingerprint of winning content patterns—and translates that into *ClipDirectives*, which guide exactly how NexClip edits the videos to maximize engagement.

## 🤖 The Agent Architecture (Complexity & Scope)

NexClip operates on a sophisticated hierarchical multi-agent system:

### 1. Nex Agent (Level 0 — Sovereign Intelligence)
Nex Agent is the master orchestrator of the entire NexClip ecosystem. It is the bridge between human intent and machine execution.
*   **What it does:** It controls video processing, manages client data, commands storage navigation, orchestrates uploads, and generates enterprise-grade captions, titles, and descriptions using LLMs.
*   **Autonomy & Self-Expansion:** It breaks down complex user requests autonomously. Furthermore, it possesses "self-expansion" capabilities—meaning it can write and create new tools for itself at runtime if it encounters a task it doesn't currently know how to perform.
*   **Memory:** It maintains a persistent memory of all conversations, corrections, and client preferences across sessions.

### 2. Arc Agent (Level 1 — Nexearch Director)
Arc Agent is the execution partner to Nex Agent, specifically focused on data science and social media mastery within the Nexearch engine.
*   **What it does:** It commands the entire social media intelligence pipeline. It manages a team of 6 specialized sub-agents (Scrape, Analyze, Score, Evolve, Bridge, Publish).
*   **Dual-Mode Evolution:** Arc Agent analyzes the performance of published content and self-evolves its strategies. It learns in two ways:
    *   *Client-Specific:* Tailoring formatting, hooks, and posting times to a specific user's audience.
    *   *Universal:* Abstracting broad patterns across all clients to understand platform-wide trends.
*   **Publishing Mastery:** Capable of logging into accounts and publishing content via APIs, Metricool, or headless browsers (Playwright) depending on what anti-bot measures require.

## ⚙️ How It All Works Together
The complexity of the system is immense, uniting FastAPI, Next.js, Celery, FFmpeg, Playwright, and local/cloud LLMs into a seamless pipeline:
1.  **Ingestion & Processing:** A user inputs a long video. NexClip's backend (FastAPI/Celery) processes it, transcribes it, and identifies key moments.
2.  **Intelligence Gathering:** Meanwhile, Arc Agent commands Nexearch to scrape the target audience or platform, finding out what hooks and formats are currently trending.
3.  **DNA & Directives:** Arc Agent analyzes this data based on 5 dimensions (Virality, Hook, Retention, Shareability, Production) to generate Account DNA. This DNA dictates the *ClipDirectives*.
4.  **Creation:** NexClip uses the ClipDirectives to crop (e.g., Speaker-Focused Cropping), caption, and style the clips perfectly tailored for high retention.
5.  **Orchestration & Publishing:** Nex Agent writes the perfect SEO-optimized titles and descriptions, then hands the finalized assets back to Arc Agent, who automatically publishes them across the 6 platforms.
6.  **Continuous Evolution:** Once published, Arc Agent monitors the performance. If a hook fails to retain viewers, Arc Agent learns from the failure and updates the Account DNA so the next batch of clips from NexClip is even better.

## 🎯 Why Use It?
You use NexClip because **it is an end-to-end, self-improving content agency in a box.** 

Standard tools require you to manually review clips, guess what your audience wants, write your own descriptions, and manually post them. NexClip handles the entire lifecycle. It not only does the heavy lifting of video editing, but via Nex Agent and Arc Agent, it figures out *how* the editing should be done to go viral, does the posting for you, tracks the results, and gets significantly smarter with every single video it processes.
