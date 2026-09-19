# Verification results

## 221 problems and 42 course lessons — September 19, 2026

Added **100 Python problems** as IDs 122–221, with 20 additions per category, 500 independently authored expected test results, three progressive hints per problem, and executable reference solutions. The complete catalog now has **221 problems, 259 language variants, and 1,299 test cases**, including 857 hidden cases. Existing IDs and definitions are preserved. The running local PostgreSQL catalog was seeded to 221 problems.

Added **11 courses and 33 lessons**, for 14 courses and 42 lessons across debugging fundamentals, runtime errors, logic errors, business flow, edge and corner cases, and system design. New lessons include a diagnosis method, worked steps, code where useful, answer feedback, source links, and related executable practice cases. Section filters use shareable URLs; existing lesson URLs and browser progress keys remain compatible.

| Check | Result |
| --- | --- |
| Backend | 128 tests passed, including reference answers and public starter failures for all 100 additions, category totals, API redaction, and upgrades from 40, 100, 101, and 121 problems preserving content and progress. Ruff passed. |
| Isolated execution | 207/207 checks passed: 100 buggy starters, 100 reference solutions, and seven execution-boundary probes. Every starter compiles and fails a public case; every solution passes all five authored cases. Existing problem programs were not rerun in this scoped execution pass. |
| Frontend | TypeScript, ESLint, and the production build passed. The existing Monaco chunk-size warning remains. Course content stays in its separate route bundle. |
| Course browser flows | 17 tests passed, covering all 42 lessons, incorrect and correct feedback, idempotent completion, reloads, resuming, course sequencing, all practice links, malformed/unavailable storage, unknown routes, six section filters, guest/member separation, and desktop/mobile themes. |
| Library browser flow | All 12 pages expose 221 unique IDs; final-problem navigation, search, language filtering, theme persistence, and mobile layout passed. Updated the old final-problem test expectation before rerunning this flow successfully. |
| New problem submission | A new account opened the fixed-width complement problem, reproduced its starter failure, submitted a repair through the real API/Celery/sandbox path, unlocked its solution, and recorded 1/49 edge-case progress. |
| Local browser verification | The course and library routes render meaningful content with no framework error overlay or reported page errors. The API reports 221 problems. |

Browser checks used `http://localhost:5173` with the running Compose API, database, worker, and execution sandbox. Local evidence includes `artifacts/catalog-expansion-sandbox.jsonl`, `artifacts/frontend-build-221.log`, and `artifacts/course*.png`. These artifacts are ignored by Git. Browser submission checks create named local test accounts and real submissions; the direct sandbox verifier does not create submission history.

Reproduce with `.venv/bin/pytest backend/tests -q -m 'not sandbox'`, `.venv/bin/ruff check backend`, and `npm run check && npm run build` in `frontend`. For the relevant browser flows, run `BASE_URL=http://localhost:5173 npm run test:e2e -- --grep 'course|catalog filtering|new catalog problem'`. The complete catalog can be checked with `docker compose exec worker python -m app.verify_catalog`.

## 121-problem catalog — September 16, 2026

Added 20 problems as IDs 102–121: four each in runtime, logic, edge cases, business flow, and system design. The catalog contains **121 problems, 159 language variants, and 799 test cases**, including 557 hidden cases. The additions include five easy, eleven medium, and four hard problems, each with three progressive hints and a reference explanation.

The verification flow was library → API → seeded PostgreSQL catalog → workspace → Celery → execution sandbox → persisted feedback. Browser checks used Vite at `http://localhost:5177` with the real Compose API, database, queue, worker, and sandbox.

| Check | Result |
| --- | --- |
| Backend | 26 tests passed; Ruff passed. Upgrade regressions cover 40-, 100-, and 101-problem installations, preserving local content, bookmarks, and solved submissions after repeated seeding. |
| New problem execution | 46/46 checks passed in the real sandbox: all 23 starters execute and fail at least one public case, and all 23 reference solutions pass their complete public/hidden tests. The new problems contain 163 test cases. The final Java circuit-breaker pair was rerun after correcting its response format. |
| Catalog preservation | All original 101 definitions are unchanged from the previous Git revision. Two PostgreSQL seed runs expanded the library from 101 to 121 while preserving the full row digests of all existing problems and all 45 existing submissions. |
| Frontend checks | TypeScript and ESLint passed. Browser verification found meaningful content, 121 catalog entries, working filters, and no page errors or framework error overlay. |
| Browser regressions | Two Playwright flows passed: all seven pages and 121 unique IDs, navigation to the final new Java case, Go filtering, mobile layout, theme switching, five system design cases, solution submission/unlock, and guest/member course progress separation. |
| Live submissions | Five new problems across Python, JavaScript, C++, Go, and Java reproduced starter failures and accepted reference solutions through the API and worker. Ten attempts and five solves persisted; hidden feedback stayed redacted and all five solution pages unlocked. |

Local evidence is recorded in `artifacts/catalog-verification-121.jsonl`, `artifacts/catalog-seed-121.log`, `artifacts/browser-catalog-121.log`, and `artifacts/http-catalog-121.jsonl`. Browser captures include `artifacts/catalog-121-browser.png` and `artifacts/system-design-121.png`. Artifacts are ignored by Git. The catalog verifier creates no submission history; the browser and HTTP flows create clearly named local test accounts and real submissions.

Reproduce the backend checks with `.venv/bin/pytest backend/tests -q` and `.venv/bin/ruff check backend`. With the local preview and Compose services running, run `BASE_URL=http://localhost:5177 npm run test:e2e -- --grep 'catalog filtering|course progress'` from `frontend`. The complete catalog, including these additions, remains executable with `docker compose exec worker python -m app.verify_catalog`; only the new problem variants were re-executed for this expansion.

## System design cases and courses — September 15, 2026

Verified against Vite at `http://localhost:5177` and the real Docker Compose API, PostgreSQL, queue, worker, and execution sandbox. The preview uses port 5177 because another local project occupies 5173.

| Check | Result |
| --- | --- |
| Backend | Full suite: 24 passed; after adding the 100-to-101 upgrade scenario, all 13 API tests passed (25 tests total across the suite). Both 40- and 100-case upgrades preserve existing content, bookmarks, and solved submissions across repeated seeding. Ruff passed. |
| Frontend | TypeScript and ESLint passed; production build passed with the existing Monaco chunk-size warning. Courses and lesson content load in a separate bundle. |
| New case execution | Python and JavaScript starters each fail both public scenarios; both reference solutions pass all 15 public/hidden scenarios in the actual sandbox. |
| Courses | All nine lessons exercised through the browser, including incorrect feedback, correct answers, completion, reloads, resuming the next unfinished lesson, and links to existing practice cases. |
| Persistence and errors | Guest/member progress separation, duplicate completion, malformed browser storage, unavailable storage, unknown courses, and unknown lessons verified. Course progress is stored only in the current browser, per guest or user. |
| Complete submission flow | Register, filter System design, reproduce the starter failure, paste a solution, submit all tests, unlock the reference explanation, and confirm the solved category in personal progress. |
| Catalog and layout | All six catalog pages, final system design case, filters, desktop light/dark themes, and mobile navigation/overflow verified. No page errors in the course walkthrough. |

That revision contained **101 problems, 136 language variants, and 636 test cases**. Its new execution checks cover the added problem; the complete 100-problem execution results below describe the earlier run. The browser tests create named local test accounts and real submissions. Local captures are saved under `artifacts/system-design-*.png`.

Reproduce the new browser checks with `BASE_URL=http://localhost:5177 npm run test:e2e -- --grep 'courses|course progress|catalog filtering'` from `frontend` when the preview and Compose worker are running. Include the preview origin in `ALLOWED_ORIGINS` for authenticated submissions.

## Previous 100-problem verification

Verified on September 15, 2026 against the Docker Compose deployment at `http://localhost:8080`.

The 100-problem expansion was checked with sandbox execution, database upgrade verification, backend tests, frontend checks, browser pagination, and live manual submissions. Earlier same-day AI, community, documentation-ingestion, and broader platform results are retained below.

All functional PRD sections and all three roadmap phases are implemented. The local AI latency target remains unmet; measured results are recorded below rather than treating implementation of the KPI dashboard as achievement of the target.

## Completed checks

| Check | Result |
| --- | --- |
| Backend behavior and regression suite | 23 tests passed; authentication, CSRF, ownership, filtering, solution gates, job limits, queue failure, worker idempotency, grading, hints, provider contracts, document redirects, cleanup, metrics, and a repeated 40-to-100 catalog upgrade preserving local edits and progress |
| Real catalog execution | 275/275 checks passed across 100 problems: 134 buggy starters, 134 reference solutions, and seven execution-boundary probes; each starter compiles where applicable and fails a public test |
| Catalog coverage | 25 problems per category; 32 easy, 52 medium, 16 hard; 621 test cases, including 421 hidden cases; three progressive hints per problem |
| Catalog upgrade | Expanded the existing PostgreSQL library from 40 to 100 problems; two seed runs preserved all 40 original problem records and all 29 existing submissions, confirmed by row digests; original catalog definitions also match the prior Git revision |
| Supported languages | Python, Java 17, JavaScript, C++17, and Go all executed successfully inside the restricted Docker sandbox |
| Browser: catalog and themes | All five 20-row pages with 100 unique IDs, navigation to problem 100, search resets pagination, all 18 Go cases, contextual case action, light/dark persistence, Monaco theme switching, mobile navigation |
| Browser: manual debugging | Register, fail twice, retrieve a cited hint, edit Monaco, pass all tests, unlock and share a solution, persist progress and profile changes, log out and sign back in |
| Browser: community | Register, create a discussion, reply, vote, reload persisted content, delete the author's discussion |
| Browser: live AI | Real Ollama directive, accepted generated patch, sharing, restored prompt/patch after reload, prompt-efficiency leaderboard entry |
| HTTP deployment smoke | Real API → PostgreSQL → Celery/Redis → Docker execution → feedback, including a live accepted AI fix |
| Expanded-catalog HTTP smoke | Six new problems across Python, Java, Go, C++, and JavaScript, including problem 100: reproduce starter failures, submit accepted fixes through the live queue, redact hidden feedback, unlock solutions, persist six solves and 12 attempts, and report 25 problems per category |
| Official documentation ingestion | 703 chunks fetched from reviewed official documentation pages; 12 bundled summaries; 715 total records in both lexical and semantic Chroma collections |
| Semantic retrieval | Actual `nomic-embed-text` embeddings; a rollback query returned official Python sqlite3 transaction documentation through `chroma-semantic` retrieval |
| TypeScript and React checks | Strict TypeScript, ESLint, and the production frontend build passed |
| Dependency audit | Frontend runtime dependency audit reported zero vulnerabilities |
| Deployment | `docker-compose.yaml` and the development override both validate; persistent PostgreSQL migration is at Alembic head; API, web, worker, Redis, PostgreSQL, and sandbox-daemon health checks pass |
| API replacement | Forced API container replacement recovered through Nginx without restarting the web service; catalog and queue readiness remained available |
| Visual verification | Desktop light/dark catalog, light/dark Monaco, accepted fixes, progress, and a 390-pixel mobile layout inspected; case actions remain visible on mobile |
| API documentation | Swagger UI loads through `/api/docs` |

The execution probes cover disabled networking, a read-only root, the unprivileged UID, execution deadlines, bounded output, absence of a Docker socket, and rejection of forged grading output. Expected test answers stay in the trusted worker; hidden feedback is redacted by the API grading boundary.

## Timing observations

These are local functional samples, not a concurrency or production capacity benchmark. The table summarizes the latest complete catalog-verification run. Sandbox times include compilation and container overhead, but exclude queueing and model generation.

| Language | Reference solutions | Observed maximum sandbox runtime |
| --- | ---: | ---: |
| Python | 49 | 330 ms |
| JavaScript | 28 | 1,161 ms |
| Java | 23 | 2,319 ms |
| C++ | 16 | 1,984 ms |
| Go | 18 | 309 ms |

The six accepted submissions in the 100-problem expansion smoke check took **241–1,683 ms** end to end. These cover one case per language plus the final waitlist case, and are functional samples rather than a latency benchmark.

The earlier, smaller-catalog submission sample recorded a manual turnaround P95 of approximately **1.49 seconds**. During the earlier 40-problem expansion, the strict Java JSON case passed all 16 tests through the live queue in **2.79 seconds** end to end, including **2.68 seconds** in the sandbox; the earlier P95 should not be treated as a benchmark for the larger catalog. The earlier same-day live browser AI submission took **6.37 seconds** end to end, including **260 ms** in the sandbox, and used **223 provider-reported tokens**. An earlier AI smoke run under competing local model work took **54.56 seconds**. Consequently, the PRD's **AI P95 below five seconds is not achieved on this tested CPU setup**. A faster model service, appropriate hardware, and a representative load test are required before claiming that target. The configured model is the small `qwen2.5-coder:0.5b` integration model; passing these cases does not imply it can reliably solve every challenge.

Hints bound model generation to 12 seconds and retain documentation-backed guidance when the model is slow or unavailable. This fallback was exercised against the actual deployment.

## Evidence and reproduction

- `artifacts/catalog-verification-100.jsonl` — all 275 real language/case and execution-boundary checks, combined from the original-catalog run and four new 15-problem batches.
- `artifacts/backend-tests-100.log` — 23 passing backend tests. Upstream deprecation notices are present under the host's Python 3.14; Compose uses Python 3.12.
- `artifacts/catalog-upgrade-before.json`, `artifacts/catalog-upgrade-after.json`, and `artifacts/catalog-seed-100.log` — database row digests and two successful seed runs for the 40-to-100 upgrade.
- `artifacts/browser-catalog-community.log`, `artifacts/browser-workspace.log`, and `artifacts/browser-live-ai.log` — four passing browser flows.
- `artifacts/browser-catalog-100.log` — all five pages, filters, themes, mobile layout, and navigation to problem 100.
- `artifacts/http-catalog-100.jsonl` — six new cases in all five languages through the deployed API, persistence, queue, and sandbox.
- `artifacts/library-100.png` and `artifacts/workspace-problem-100.png` — browser captures of the current library and final problem.
- `artifacts/live-ai-smoke.log` — persisted HTTP smoke with a real model.
- `artifacts/document-ingestion.log` and `artifacts/semantic-ingestion.log` — live official-document refresh results.
- `artifacts/library-light.png`, `artifacts/library-dark.png`, `artifacts/library-mobile-light.png`, `artifacts/library-expanded-mobile.png`, `artifacts/workspace-dark.png`, `artifacts/accepted-workspace.png`, `artifacts/progress-desktop.png`, and `artifacts/ai-workspace.png` — browser captures.

Artifacts are local and ignored by Git. Commands to reproduce these checks are in the README. Browser and HTTP tests create clearly named test accounts and real submissions; the catalog verifier does not create submission history. OpenRouter is covered by HTTP contract tests, while live provider execution was verified with Ollama. The supplied GitHub Actions workflow has not been run on a remote GitHub repository during this session.
