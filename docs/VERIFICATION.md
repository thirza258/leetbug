# Verification results

Verified on September 15, 2026 against the running Docker Compose deployment at `http://localhost:8080`.

All functional PRD sections and all three roadmap phases are implemented. The local AI latency target remains unmet; measured results are recorded below rather than treating implementation of the KPI dashboard as achievement of the target.

## Completed checks

| Check | Result |
| --- | --- |
| Backend behavior and regression suite | 22 tests passed; authentication, CSRF, ownership, filtering, solution gates, job limits, queue failure, worker idempotency, grading, hints, provider contracts, document redirects, cleanup, and metrics |
| Real catalog execution | 155/155 checks passed across 40 problems: 74 buggy starters, 74 reference solutions, and seven execution-boundary probes; each starter compiles where applicable and fails a public test |
| Catalog coverage | 10 problems per category; 13 easy, 20 medium, 7 hard; 226 test cases, including 146 hidden cases; three progressive hints per problem |
| Catalog upgrade | Expanded the existing PostgreSQL library from 13 to 40 problems; repeated seeding preserved every existing problem ID and all 18 pre-expansion submissions |
| Supported languages | Python, Java 17, JavaScript, C++17, and Go all executed successfully inside the restricted Docker sandbox |
| Browser: catalog and themes | Both 20-row pages, navigation to the final new case, search resets pagination, all 11 Go cases, contextual case action, light/dark persistence, Monaco theme switching, mobile navigation |
| Browser: manual debugging | Register, fail twice, retrieve a cited hint, edit Monaco, pass all tests, unlock and share a solution, persist progress and profile changes, log out and sign back in |
| Browser: community | Register, create a discussion, reply, vote, reload persisted content, delete the author's discussion |
| Browser: live AI | Real Ollama directive, accepted generated patch, sharing, restored prompt/patch after reload, prompt-efficiency leaderboard entry |
| HTTP deployment smoke | Real API → PostgreSQL → Celery/Redis → Docker execution → feedback, including a live accepted AI fix |
| Expanded-catalog HTTP smoke | New Python, Java, Go, C++, and JavaScript problems: reproduce starter failures, submit accepted fixes, redact hidden feedback, unlock solutions, persist five solves, and report 10 cases per category in progress |
| Official documentation ingestion | 703 chunks fetched from reviewed official documentation pages; 12 bundled summaries; 715 total records in both lexical and semantic Chroma collections |
| Semantic retrieval | Actual `nomic-embed-text` embeddings; a rollback query returned official Python sqlite3 transaction documentation through `chroma-semantic` retrieval |
| TypeScript and React checks | Strict TypeScript and ESLint passed; production frontend image built successfully |
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
| Python | 24 | 256 ms |
| JavaScript | 17 | 1,113 ms |
| Java | 13 | 2,376 ms |
| C++ | 9 | 1,994 ms |
| Go | 11 | 293 ms |

The earlier, smaller-catalog submission sample recorded a manual turnaround P95 of approximately **1.49 seconds**. With the expanded catalog, the strict Java JSON case passed all 16 tests through the live queue in **2.79 seconds** end to end, including **2.68 seconds** in the sandbox; the earlier P95 should not be treated as a benchmark for the larger catalog. The latest live browser AI submission took **6.37 seconds** end to end, including **260 ms** in the sandbox, and used **223 provider-reported tokens**. An earlier AI smoke run under competing local model work took **54.56 seconds**. Consequently, the PRD's **AI P95 below five seconds is not achieved on this tested CPU setup**. A faster model service, appropriate hardware, and a representative load test are required before claiming that target. The current model is the small `qwen2.5-coder:0.5b` integration model; passing these cases does not imply it can reliably solve every challenge.

Hints bound model generation to 12 seconds and retain documentation-backed guidance when the model is slow or unavailable. This fallback was exercised against the actual deployment.

## Evidence and reproduction

- `artifacts/catalog-verification.jsonl` — every real language/case result and boundary probe.
- `artifacts/backend-tests.log` — 22 passing backend tests. Upstream deprecation notices are present under the host's Python 3.14; Compose uses Python 3.12.
- `artifacts/browser-catalog-community.log`, `artifacts/browser-workspace.log`, and `artifacts/browser-live-ai.log` — four passing browser flows.
- `artifacts/browser-expanded-catalog.log` — expanded-catalog pagination, filters, themes, mobile layout, and navigation to a new workspace.
- `artifacts/expanded-catalog-smoke.log` — new cases in all five languages through the deployed API, persistence, queue, and sandbox.
- `artifacts/live-ai-smoke.log` — persisted HTTP smoke with a real model.
- `artifacts/document-ingestion.log` and `artifacts/semantic-ingestion.log` — live official-document refresh results.
- `artifacts/library-light.png`, `artifacts/library-dark.png`, `artifacts/library-mobile-light.png`, `artifacts/library-expanded-mobile.png`, `artifacts/workspace-dark.png`, `artifacts/accepted-workspace.png`, `artifacts/progress-desktop.png`, and `artifacts/ai-workspace.png` — browser captures.

Artifacts are local and ignored by Git. Commands to reproduce these checks are in the README. Browser and HTTP tests create clearly named test accounts and real submissions; the catalog verifier does not create submission history. OpenRouter is covered by HTTP contract tests, while live provider execution was verified with Ollama. The supplied GitHub Actions workflow has not been run on a remote GitHub repository during this session.
