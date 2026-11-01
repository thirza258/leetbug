# Verification results

## 344 problems — October 29, 2026

Added **20 problems** as IDs 325–344: ten data science and ten data analytics cases, all Python. Each has a single-fragment defect, three progressive hints, a reference solution, and five or six independently authored expected results (116 in total, 76 hidden). The complete catalog now has **344 problems, 382 language variants, and 1,950 test cases**, including 1,262 hidden cases. The first 324 definitions are unchanged.

| Check | Result |
| --- | --- |
| Backend | 331 tests passed, including reference and public-reproducer checks for all 20 additions, category totals, and an upgrade from 324 problems. Ruff passed. |
| Catalog integrity | 40/40 in-process checks passed: every starter fails a public case, and every reference solution passes all five or six cases. |
| Frontend | TypeScript and ESLint passed (`npm run check`). |
| Not run | Real sandbox execution and Playwright browser flows were not rerun for this expansion; the new cases were validated in process. |

## 324 problems — September 28, 2026

Added **53 problems** as IDs 272–324: ten each for runtime, logic, business flow, and edge cases, plus thirteen for system design, the smallest category. By language there are 27 Python, 7 Java, 7 JavaScript, 6 Go, and 6 C++ problems. Each has a single-fragment defect, three progressive hints, a reference solution, and five or six independently authored expected results (277 in total, 171 hidden). The complete catalog now has **324 problems, 362 language variants, and 1,834 test cases**, including 1,186 hidden cases. Categories hold 69 problems each, with 48 for system design. The first 271 definitions are unchanged.

| Check | Result |
| --- | --- |
| Backend | 289 tests passed. They add structure checks for the 53 additions, in-process reference and public-reproducer checks for the 27 Python additions, the new category and language totals, and an upgrade from 271 problems. Ruff passed. |
| New problem execution | 106/106 checks passed in the real sandbox image. Every starter compiles and fails a public case: all ten runtime starters crash on it, and all 43 other starters return wrong answers without crashing on any case. Every reference solution passes all of its cases. Afterwards, the `stacked-percent-coupons` starter was reformatted from two assignments into one line with the same bug. It was re-verified 2/2, and local row 295 was synced to the new starter. |
| PostgreSQL upgrade | Seeding the local database took it from 271 to 324 problems. Row digests of all 271 existing problems and all 75 existing submissions were unchanged, and IDs 272–324 follow category order. |
| Frontend | TypeScript, ESLint, and the production build passed, with the existing Monaco chunk-size warning. |
| Browser flows | 19 Playwright tests passed against the rebuilt Compose stack at `http://localhost:8080`. They cover all 17 library pages with 324 unique IDs, navigation to the new final problem, the Go filter (34 cases), the mobile layout, 1/69 edge progress, 1/48 system design progress, and all course lessons. |
| Live submissions | Five new problems, one per language (IDs 272, 273, 277, 321, and 324), ran through the API, Celery, and the sandbox. Each starter reproduced its failure and each reference solution was accepted. Hidden feedback stayed redacted, all five solutions unlocked, and progress reported 69 runtime and 48 system design cases. |

One draft, `float-sum-exact-cents`, first used `sum()` over floats. Python 3.12 made float `sum()` compensated, so that starter failed only in the Python 3.11 sandbox and passed under the host test runner. The problem now accumulates with `+=`, which behaves the same from Python 3.11 through 3.14. Browser and live checks again ran without the Ollama profile, using lexical embeddings. Local evidence is in `artifacts/catalog-verification-324.jsonl`, `artifacts/catalog-verification-324-coupons.jsonl`, `artifacts/catalog-verification-full-324.jsonl`, `artifacts/catalog-verification-324-queue-underflow.jsonl`, `artifacts/catalog-upgrade-324-before.txt`, `artifacts/catalog-upgrade-324-after.txt`, `artifacts/browser-catalog-324.log`, and `artifacts/http-catalog-324.jsonl`; these files are ignored by Git.

## 271 problems — September 28, 2026

Added **50 problems** as IDs 222–271, ten per category, in all five languages: 29 Python, 7 Go, 6 Java, 5 JavaScript, and 3 C++. Each has a single-fragment defect, three progressive hints, a reference solution, and five or six independently authored expected results (258 in total, 158 hidden). Most non-Python cases target language-specific traps: Go nil pointers, slice aliasing and range copies; Java unboxing, `List.remove` overloads, `Integer` identity and subtraction comparators; C++ unsigned wraparound, accumulator types and partial `stoi` parsing; JavaScript `parseInt` radix, `var` closures, `Number()` coercion and circular JSON. The complete catalog now has **271 problems, 309 language variants, and 1,557 test cases**, including 1,015 hidden cases. The first 221 definitions are byte-identical to the previous revision.

| Check | Result |
| --- | --- |
| Backend | 208 tests passed. These include structure checks for all 50 additions, in-process reference and public-reproducer checks for the 29 Python additions, category and language totals, and upgrades from 40, 100, 101, 121, and 221 problems preserving content and progress. Ruff passed. |
| New problem execution | 100/100 checks passed in the real sandbox image (Python 3.11.2, Node 18.20.4, Go 1.19.8, OpenJDK 17.0.20.1, g++ 12.2 with nlohmann/json 3.11.2). Every starter compiles and fails a public case: runtime starters crash on it, while the other categories return a wrong answer. Every reference solution passes all of its cases. |
| Full catalog execution | `app.verify_catalog` passed 625/625 checks: the starter and reference solution of all 309 language variants across the 271 problems, plus seven execution-boundary probes (network isolation, read-only root, unprivileged UID, deadline, output cap, no Docker socket, and forged-grade rejection). This run used the image built before the hidden cases of `list-remove-overload` were revised so that its starter fails without crashing. That problem was then re-run with the revised cases, and both checks passed. |
| PostgreSQL upgrade | Seeding the local database took it from 221 to 271 problems. Row digests of all 221 existing problems and all 61 existing submissions were unchanged, and IDs 222–271 follow category order. |
| Frontend | TypeScript, ESLint, and the production build passed, with the existing Monaco chunk-size warning. |
| Browser flows | 19 Playwright tests passed against the rebuilt Compose stack at `http://localhost:8080`. They cover all 14 library pages with 271 unique IDs, navigation to the final new problem, the Go filter (28 cases), the mobile layout, a new-problem repair with 1/59 edge progress, system design course progress at 1/35, and all course lessons. |
| Live submissions | Five new problems, one per language (IDs 222, 225, 226, 256, and 271), ran through the API, Celery, and the sandbox. Each starter reproduced its failure (`runtime_error` for runtime cases, `failed` otherwise) and each reference solution was accepted. Hidden feedback stayed redacted, all five solutions unlocked, and progress reported 59 runtime, 59 edge, and 35 system design cases. |

The browser and live checks ran without the optional Ollama profile, using the default lexical embeddings (`EMBEDDING_BASE_URL` blank for that run), because the configured Ollama embedding service was not started. This affects documentation retrieval only, not catalog execution. Local evidence is in `artifacts/catalog-verification-271.jsonl`, `artifacts/catalog-verification-271-list-remove.jsonl`, `artifacts/catalog-verification-full-271.jsonl`, `artifacts/catalog-upgrade-271-before.txt`, `artifacts/catalog-upgrade-271-after.txt`, `artifacts/browser-catalog-271.log`, and `artifacts/http-catalog-271.jsonl`. These artifacts are ignored by Git. Browser and live checks create named local test accounts and real submissions; the sandbox verifiers do not.

To reproduce, run `.venv/bin/pytest backend/tests -q -m 'not sandbox'` and `.venv/bin/ruff check backend`, then `npm run check && npm run build` in `frontend`. With the Compose stack running, run `docker compose exec worker python -m app.verify_catalog` and `BASE_URL=http://localhost:8080 npm run test:e2e -- --grep 'catalog filtering|new catalog problem|course'`.

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
