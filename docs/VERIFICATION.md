# Verification results

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

The catalog now contains **101 problems, 136 language variants, and 636 test cases**. New execution checks cover the added problem; the complete 100-problem execution results below describe the earlier run. The browser tests create named local test accounts and real submissions. Local captures are saved under `artifacts/system-design-*.png`.

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
