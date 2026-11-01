# **Product Requirements Document (PRD)**

**Product Name:** LeetBug

&nbsp;

**Document Version:** 1.0

&nbsp;

**Date:** September 14, 2026

&nbsp;

## **1\. Executive Summary**

**LeetBug** is an innovative coding evaluation and learning platform that inverts the traditional competitive programming paradigm. Rather than requiring users to write algorithms from scratch, LeetBug focuses exclusively on debugging, system troubleshooting, and AI-human collaboration. Users are presented with buggy code snippets—ranging from simple syntax errors to complex business flow violations—and are tasked with fixing them either manually via a code editor or by providing precise prompts to an AI agent.

&nbsp;

## **2\. Background & Objectives**

**Problem Statement:**

In modern software engineering, developers spend significantly more time reading, analyzing, and debugging existing code (including AI-generated code) than writing new algorithms from zero. Existing platforms fail to adequately train engineers for real-world scenarios, particularly regarding domain/business logic failures and the effective utilization of AI coding assistants.

&nbsp;

**Objectives:**

&nbsp;

1. Train users' analytical sensitivity to identify and resolve a wide spectrum of code issues, including Runtime, Logic, and Business Flow errors.  
2. &nbsp;  
3. Elevate technical Prompt Engineering skills, enabling users to accurately describe problems and direct LLMs to generate precise fixes.  
4. &nbsp;  
5. Provide a secure, highly isolated execution environment (sandbox) to validate code fixes through comprehensive test cases and state assertions.  
6. &nbsp;

## **3\. Core Features**

### **3.1. Problem Library & Bug Categorization**

A comprehensive catalog of debugging case studies featuring robust search, filtering, and tagging systems. Problems are classified into four main pillars:

&nbsp;

* **Runtime Errors:** Code that causes program crashes or panics during execution. Examples include *NullPointerException*, *Index Out of Bounds*, *Division by Zero*, or *Memory Leaks*.  
* &nbsp;  
* **Logic Errors:** Code that compiles and runs without crashing but produces incorrect algorithmic or mathematical outputs. Examples include off-by-one loop errors, incorrect variable initialization, or flawed conditional statements.  
* &nbsp;  
* **Business Flow Errors:** Violations of domain or business rules, simulating enterprise-level bugs. Examples include race conditions in digital wallet transactions, e-commerce shopping carts allowing negative totals, or Role-Based Access Control (RBAC) failing to block non-admin users.  
* &nbsp;  
* **Edge & Corner Cases:** Logic that functions perfectly for standard use cases but fails under extreme conditions. Examples include handling empty arrays, maximum integer boundaries (MAX\_INT), or unexpected API payloads.  
* &nbsp;

### **3.2. Dual-Mode Interactive Workspace**

The primary user interface is split into two distinct resolution paths:

&nbsp;

* **Manual Mode (Code Editor):** A fully featured, Monaco-based code editor with syntax highlighting where users can directly manipulate and fix the buggy code.  
* &nbsp;  
* **AI-Assist Mode (Prompt Editor):** A natural language input field where the user acts as the "Lead Engineer." The user must write a descriptive directive pinpointing the bug and the required solution (e.g., *"Fix the race condition on line 45 by applying a database lock before deducting the balance"*). The system routes this prompt to an LLM to generate the patched code.  
* &nbsp;

### **3.3. Execution & Evaluation Engine**

An advanced grading engine designed to evaluate both static outputs and dynamic system states:

&nbsp;

* **Unit & Integration Tests:** Executes the fixed code against both public and hidden test cases.  
* &nbsp;  
* **State Assertions:** Specifically for *Business Flow Errors*, the engine verifies mock database states (e.g., ensuring object properties or mock database tables have correctly transitioned, or verifying that a transaction rollback occurred smoothly after a simulated API failure).  
* &nbsp;  
* **Performance Metrics:** Returns the execution status (Passed/Failed/Runtime Error), execution time (runtime latency), and memory consumption.  
* &nbsp;

### **3.4. AI Explanation & Smart Fallback**

* If a user's fix fails the test cases repeatedly, they can request a "Hint."  
* &nbsp;  
* The system leverages a Retrieval-Augmented Generation (RAG) architecture to pull relevant context directly from official programming language or framework documentation (e.g., ORM transaction documentation for a database-related bug), ensuring AI hints are highly contextual, accurate, and grounded.  
* &nbsp;

## **4\. User Flow**

1. **Discovery:** The user navigates the dashboard and filters the catalog (e.g., Category: "Business Flow", Language: "Python", Difficulty: "Medium").  
2. &nbsp;  
3. **Problem Context:** The user reads the business requirements and inspects the buggy source code provided.  
4. &nbsp;  
5. **Action Selection:** The user chooses either the **Manual Editor** to write the fix directly or the **AI Prompt Editor** to draft a directive for the LLM.  
6. &nbsp;  
7. **Execution:** The user clicks "Run Code". The system either executes the manual code or processes the prompt through the LLM before executing the generated output.  
8. &nbsp;  
9. **Feedback Loop:** The evaluation engine visualizes the test results (e.g., *"Test Case 3 Failed: Account balance can drop below zero"*). The user iterates on their code or refines their prompt.  
10. &nbsp;  
11. **Resolution & Community:** Upon passing, the user unlocks optimal solutions and can compare their prompt efficiency with community submissions.  
12. &nbsp;

## **5\. System Architecture**

To support an interactive interface, heavy asynchronous processing, and dynamic LLM integrations, the platform will utilize the following technology stack:

&nbsp;

* **Frontend Web:** React built with TypeScript and Vite, utilizing Tailwind CSS for a fast, responsive workspace and dashboard interface.  
* &nbsp;  
* **Backend & Routing:** Django or FastAPI to handle API routing, user authentication, and business logic orchestration.  
* &nbsp;  
* **Database & Vector Store:**  
* 

  * PostgreSQL for relational data storage (user profiles, case studies, submission history).  
  * &nbsp;  
  * ChromaDB to store vector embeddings of official framework documentation, powering the RAG-based AI hinting system.  
  * &nbsp;  
* **Asynchronous Tasks (Workers):** Celery paired with Redis as a message broker to queue and process isolated code execution and LLM API calls without blocking the main application thread.  
* &nbsp;  
* **Code Sandbox (Execution Environment):** Containerized execution using Docker (e.g., Docker Compose stacks) to securely isolate user code, applying strict memory constraints and disabling external network access to prevent malicious host interactions.  
* &nbsp;  
* **AI Integrations:** OpenRouter API for routing prompts to commercial LLMs in production, alongside integrations with Ollama to run local, OpenAI-compatible endpoints for testing and latency optimization.  
* &nbsp;

## **6\. Success Metrics (KPIs)**

* **Completion Rate:** The percentage of case studies successfully passed versus total attempts.  
* &nbsp;  
* **Mode Adoption Ratio:** The usage distribution between "Manual Mode" and "AI-Assist Mode" (targeting a balanced adoption rate).  
* &nbsp;  
* **System Latency:**  
* 

  * P95 turnaround time for local sandbox code execution \< 2.5 seconds.  
  * &nbsp;  
  * P95 turnaround time for AI-generated code fixes \< 5.0 seconds.  
  * &nbsp;  
* **Retention Rate:** Monthly Active Users (MAU) and the percentage of users who return to debug another problem within 7 days of their first session.  
* &nbsp;

## **7\. Development Roadmap (Milestones)**

* **Phase 1 (MVP \- Foundation):**  
* 

  * Establish user authentication, problem database schemas, and the core Manual Code Editor UI.  
  * &nbsp;  
  * Implement the isolated Docker sandbox for basic Python and Java execution, focusing strictly on *Runtime* and *Logic Errors*.  
  * &nbsp;  
* **Phase 2 (AI Integration & Advanced Problems):**  
* 

  * Deploy the asynchronous Celery/Redis queue system.  
  * &nbsp;  
  * Integrate OpenAI-compatible LLM endpoints to enable the "AI-Assist Mode."  
  * &nbsp;  
  * Introduce *Business Flow Errors* supported by mock state assertions in the execution engine.  
  * &nbsp;  
* **Phase 3 (Scaling, RAG, & Community):**  
* 

  * Launch community discussion forums and prompt-efficiency leaderboards.  
  * &nbsp;  
  * Fully integrate ChromaDB to power the RAG-backed smart hint system.  
  * &nbsp;  
  * Expand programming language support (e.g., C++, JavaScript, Go).

&nbsp;
---

## **9. Community Submissions, WebMCP Agent Discovery & Monetization Stack**

### **9.1 Community Problem Submissions & Admin Review Dashboard**
* **User-Contributed Debugging Challenges:** Allows verified developers to submit novel buggy code snippets, test case assertions, and reference solutions across Python, JavaScript, Go, and Java.
* **Admin Governance Portal:** Dedicated administrative dashboard for reviewing, dry-running in Docker sandboxes, editing, and publishing user submissions.

### **9.2 Autonomous Agent Readiness & Machine Discovery (WebMCP)**
* **WebMCP Architecture:** Integrated WebMCP endpoints enabling autonomous coding agents to discover debugging problems, submit patches, and verify test assertions programmatically.
* **Agent Readiness Discovery (ARD):** Exposes `/.well-known/ard.json`, `/poppy.json`, and `/llms.txt` documenting platform capabilities and problem schemas for AI agents.
* **Markdown Content Negotiation:** Returns structured markdown for API and agent consumers using `Accept: text/markdown`.

### **9.3 Multi-Tier Monetization & Resilient Free-Tier Fallback**
* **Ad Network Integration:** Monetag meta tags and container scripts, Google AdSense ad units backed by an authoritative `ads.txt` and rigid Content Security Policy (CSP).
* **Shuffled OpenRouter Free Model Fallback:** Automatic zero-cost fallback rotating across free OpenRouter models (Gemini Flash, Llama 3) whenever API balance is exhausted.
