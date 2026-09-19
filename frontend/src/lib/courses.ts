import type { Course, CourseTrack, Lesson } from './course-types';
import { debuggingCourses } from './course-content/debugging';
import { runtimeCourses } from './course-content/runtime';
import { logicCourses } from './course-content/logic';
import { businessCourses } from './course-content/business';
import { edgeCourses } from './course-content/edge';
import { appliedSystemDesignCourses } from './course-content/system-design';

export type { Course, CourseTrack, Lesson } from './course-types';

export const courseTracks: { id: CourseTrack; title: string; description: string }[] = [
  { id: 'debugging', title: 'Debugging fundamentals', description: 'Start here: reproduce a failure, follow the evidence, and prove the fix.' },
  { id: 'runtime', title: 'Runtime errors', description: 'Trace crashes, unsafe operations, and execution that never finishes.' },
  { id: 'logic', title: 'Logic errors', description: 'Find the wrong decision in code that runs but gives the wrong answer.' },
  { id: 'business', title: 'Business flow', description: 'Protect business rules through validation, state changes, and retries.' },
  { id: 'edge', title: 'Edge & corner cases', description: 'Test the boundaries, representations, and combinations the happy path misses.' },
  { id: 'system_design', title: 'System design', description: 'Choose a design from requirements, then test its behavior under failure.' },
];

export const courses: Course[] = [
  ...debuggingCourses,
  ...runtimeCourses,
  ...logicCourses,
  ...businessCourses,
  ...edgeCourses,
  {
    slug: 'choosing-an-architecture',
    track: 'system_design',
    title: 'Choosing the right architecture',
    description: 'Turn a vague brief into requirements, compare designs, and explain the trade-offs behind your choice.',
    level: 'Foundations',
    outcomes: ['Separate requirements from preferences', 'Compare a modular monolith, services, and workers', 'Make a decision you can revisit'],
    practice: [{ slug: 'choosing-the-right-system-design', title: 'Choosing the right system design' }],
    lessons: [
      {
        slug: 'requirements-first', title: 'Start with the requirements', minutes: 5,
        sections: [
          { title: 'Describe the workload', text: 'List the actions the system must support, then put numbers on its limits: peak requests per second, response time, acceptable data staleness, monthly budget, and available operating effort. Record where each estimate came from. A guess is something to test.' },
          { title: 'Reject before you rank', text: 'A mandatory requirement is a gate. A preference helps compare options that pass every gate. Agree on priorities before scoring candidates so a cheap design cannot quietly compensate for missing a critical requirement.' },
        ],
        example: { title: 'A booking service brief', text: 'A three-person team needs 1,000 requests per second, responses within 100 ms, and no stale availability decisions. A candidate that handles 20,000 requests per second but needs eight people to operate fails the staffing requirement. Extra capacity does not fix that mismatch.' },
        checkpoint: { question: 'The fastest candidate exceeds a mandatory monthly budget. What should you do?', options: [
          { text: 'Choose it because throughput is the highest.', feedback: 'Throughput is only one requirement. Exceeding a mandatory budget makes this candidate infeasible.' },
          { text: 'Exclude it, then compare the candidates that meet every requirement.', correct: true, feedback: 'Correct. Establish feasibility first. If nothing qualifies, revisit the brief or the candidate designs explicitly.' },
          { text: 'Average the budget and throughput scores.', feedback: 'A weighted average can hide a broken requirement. Use scores only after mandatory gates pass.' },
        ] },
        source: { title: 'Azure Architecture Center: architecture fundamentals', url: 'https://learn.microsoft.com/en-us/azure/architecture/guide/' },
      },
      {
        slug: 'architecture-styles', title: 'Compare architecture styles', minutes: 6,
        sections: [
          { title: 'Choose boundaries for a reason', text: 'A modular monolith keeps distinct business modules in one deployable application. Separate services add independent deployment and scaling boundaries, along with network calls and more operational work. Those benefits matter when teams and workloads actually need them.' },
          { title: 'Separate slow work', text: 'A web application with a queue and workers can move long jobs out of the request path. Users receive a job identifier and check its status. Decide what must finish immediately and what can complete later; one system can combine these approaches.' },
        ],
        example: { title: 'An image-processing product', text: 'Profiles and billing have modest traffic, but image conversion takes 30 seconds and has large bursts. Keep the initial application modular and give conversion its own worker pool. Reassess separate services when ownership or scaling requirements justify the added boundaries.' },
        checkpoint: { question: 'Users accept delayed image conversion. Which change directly addresses the long request?', options: [
          { text: 'Split every feature into a service immediately.', feedback: 'That introduces many boundaries without targeting the slow work. Start with the workload that needs a different execution model.' },
          { text: 'Increase the HTTP timeout indefinitely.', feedback: 'Longer timeouts keep requests occupied and leave burst handling unresolved.' },
          { text: 'Enqueue conversion work and expose job status.', correct: true, feedback: 'Correct. A queue and workers separate request handling from long processing and let that workload scale independently.' },
        ] },
        source: { title: 'Azure Architecture Center: architecture styles', url: 'https://learn.microsoft.com/en-us/azure/architecture/guide/architecture-styles/' },
      },
      {
        slug: 'defend-the-decision', title: 'Defend and revisit the decision', minutes: 5,
        sections: [
          { title: 'Make the comparison reproducible', text: 'Write down the context, candidates, mandatory gates, ranking policy, chosen option, and accepted drawbacks. Include rejected alternatives and the assumptions that ruled them out. Another engineer should be able to follow the decision from the same evidence.' },
          { title: 'Define a reason to revisit', text: 'A decision has a useful lifetime. Set a review trigger such as a measured latency breach, a change in team ownership, or a new consistency requirement. Load-test the actual request mix and failure behavior before treating a capacity estimate as a guarantee.' },
        ],
        example: { title: 'Two feasible designs', text: 'Design A costs 300 units per month and needs two units of operating effort. Design B costs 400 and needs one. Under a cost-first policy A wins; under an effort-first policy B wins. Both decisions need an explicit policy. These are exercise estimates, not vendor prices.' },
        checkpoint: { question: 'No candidate passes every mandatory gate. What is the most defensible result?', options: [
          { text: 'Report no feasible design and revisit candidates or requirements.', correct: true, feedback: 'Correct. An explicit gap is more useful than silently relaxing a mandatory constraint.' },
          { text: 'Choose the option that fails the fewest gates.', feedback: 'Even one missing mandatory property can invalidate a design. Changing a gate requires a documented decision.' },
          { text: 'Always choose the most complex design.', feedback: 'Complexity does not establish feasibility. Compare evidence against the requirements.' },
        ] },
        source: { title: 'Azure Architecture Center: choosing an application architecture', url: 'https://learn.microsoft.com/en-us/azure/architecture/guide/' },
      },
    ],
  },
  {
    slug: 'data-consistency-and-caching',
    track: 'system_design',
    title: 'Data, consistency, and caching',
    description: 'Choose storage around access patterns, protect concurrent updates, and decide when stale data is acceptable.',
    level: 'Intermediate',
    outcomes: ['Map queries to storage models', 'Protect data invariants under concurrency', 'Design a cache with a freshness policy'],
    practice: [{ slug: 'wallet-race', title: 'Two withdrawals, one balance' }, { slug: 'cached-zero', title: 'A cache hit becomes a miss' }],
    lessons: [
      {
        slug: 'access-patterns', title: 'Choose storage from access patterns', minutes: 5,
        sections: [
          { title: 'Start with queries and updates', text: 'Describe how records are looked up, joined, updated, and retained. Relational stores are useful for related records and transactions; key-value access fits direct lookups; object storage fits large files. Check a particular product’s guarantees and limits before choosing it.' },
          { title: 'Give each copy a purpose', text: 'Keep an authoritative store for each record. Add a search index or other derived copy when a concrete access pattern calls for it. Every extra copy needs an update path and a policy for lag and rebuilding.' },
        ],
        example: { title: 'A photo library', text: 'Store the image bytes in object storage and ownership, captions, and file references in a database. A search index can support caption search if needed. The index is a derived view; an outdated search result must not grant access to a private image.' },
        checkpoint: { question: 'An order update must atomically change several related records. What should drive storage selection?', options: [
          { text: 'Whether the database is described as NoSQL.', feedback: 'A category label does not establish transaction guarantees. Check the actual operations and boundaries.' },
          { text: 'The required transaction boundary and query patterns.', correct: true, feedback: 'Correct. Evaluate transaction support, integrity rules, and access patterns together.' },
          { text: 'The number of database products in the design.', feedback: 'More stores add synchronization work. Each one needs a specific role.' },
        ] },
        source: { title: 'Azure Architecture Center: understand data models', url: 'https://learn.microsoft.com/en-us/azure/architecture/data-guide/technology-choices/understand-data-store-models' },
      },
      {
        slug: 'concurrent-updates', title: 'Protect concurrent updates', minutes: 6,
        sections: [
          { title: 'Name the invariant', text: 'An invariant is a condition that must remain true, such as “a wallet balance cannot become negative.” Two requests can each read an apparently valid balance and then conflict. A correct result with one request does not prove correctness with concurrent requests.' },
          { title: 'Choose an atomic boundary', text: 'Use a conditional update, appropriate locking, or a transaction isolation level that protects the invariant. A transaction by itself does not prevent every race. Serializable transactions can abort on conflicts, so callers must handle a retry of the whole transaction.' },
        ],
        example: { title: 'Two withdrawals', text: 'A wallet contains 100 units. Two requests each want 80 and both read 100 before either writes. The check and debit must share an atomic boundary so only one succeeds. A stale display balance can be acceptable; the debit decision needs authoritative state.' },
        checkpoint: { question: 'Which operation protects a single wallet from concurrent overdrafts?', options: [
          { text: 'Read the balance from a cache, then write the new value.', feedback: 'Another withdrawal can happen between the read and write, and the cache can already be stale.' },
          { text: 'Add a delay before saving the balance.', feedback: 'Timing changes do not make the check and debit atomic.' },
          { text: 'Atomically debit only when the stored balance is sufficient, and check whether it succeeded.', correct: true, feedback: 'Correct. The condition and update belong in one atomic operation. Broader invariants may require a larger transaction boundary.' },
        ] },
        source: { title: 'PostgreSQL documentation: transaction isolation', url: 'https://www.postgresql.org/docs/current/transaction-iso.html' },
      },
      {
        slug: 'cache-freshness', title: 'Make freshness part of the cache design', minutes: 5,
        sections: [
          { title: 'Understand cache-aside', text: 'Look for a key in the cache; on a miss, read the authoritative store and populate the cache. On a write, update the store and invalidate the cached value. Distinguish an absent entry from cached values such as zero or false.' },
          { title: 'Plan for stale data', text: 'Cache-aside does not guarantee consistency with the store. Expiration limits an entry’s lifetime, but concurrent fills and lagging replicas can still return old values. Decide which reads may be stale and keep correctness-sensitive decisions on an authoritative path.' },
        ],
        example: { title: 'Browse versus reserve', text: 'A product page can show an approximate stock count. Reserving the final item must check and update authoritative stock atomically. If the cache is unavailable, protect the database from a sudden wave of misses using bounded concurrency or admission limits.' },
        checkpoint: { question: 'A cached inventory count is zero. Is that necessarily a cache miss?', options: [
          { text: 'No. Check whether the key exists independently of its value.', correct: true, feedback: 'Correct. Zero is a valid cached result. A truthiness check can cause needless database reads.' },
          { text: 'Yes. Only positive counts should be cached.', feedback: 'An out-of-stock result can still be useful cached data. Presence and value answer different questions.' },
          { text: 'Yes. A zero value proves the cache is unavailable.', feedback: 'A valid response containing zero says nothing about availability. Handle connection failures separately.' },
        ] },
        source: { title: 'Azure Architecture Center: cache-aside pattern', url: 'https://learn.microsoft.com/en-us/azure/architecture/patterns/cache-aside' },
      },
    ],
  },
  {
    slug: 'queues-and-reliability',
    track: 'system_design',
    title: 'Queues, retries, and reliability',
    description: 'Handle bursts and partial failures without creating duplicate work or overwhelming a dependency.',
    level: 'Intermediate',
    outcomes: ['Separate acceptance from completion', 'Make repeated requests safe', 'Bound retries and observe recovery'],
    practice: [{ slug: 'inventory-retry', title: 'Sold twice, shipped once' }, { slug: 'retry-budget', title: 'One request too many' }],
    lessons: [
      {
        slug: 'queues-and-bursts', title: 'Use queues to absorb bursts', minutes: 5,
        sections: [
          { title: 'Accept work durably', text: 'A queue decouples incoming requests from processing. Acknowledge acceptance only after work is durably recorded, and expose pending, completed, and failed states. Being accepted into a queue does not mean the requested operation has finished.' },
          { title: 'A buffer is not infinite capacity', text: 'Watch queue depth and the age of the oldest job. Workers must eventually drain the backlog. Bound admission when sustained arrival exceeds processing, and define how jobs that repeatedly fail are isolated and reviewed.' },
        ],
        example: { title: 'A report-generation burst', text: 'For ten seconds, 100 jobs per second arrive while workers finish 40 per second. The simplified backlog grows by 600 jobs. If arrivals stop, it takes another 15 seconds to drain at that rate. A queue absorbs this burst, but sustained overload still needs a capacity or admission change.' },
        checkpoint: { question: 'Arrival rate stays above processing rate indefinitely. What happens?', options: [
          { text: 'The queue automatically makes workers faster.', feedback: 'A queue buffers demand; it does not create processing capacity.' },
          { text: 'The backlog grows unless capacity or admission changes.', correct: true, feedback: 'Correct. Measure job age as well as depth, and keep admission and processing capacity within a sustainable envelope.' },
          { text: 'Every accepted job has already completed.', feedback: 'Acceptance and completion are separate states. The user needs a way to distinguish them.' },
        ] },
        source: { title: 'Azure Architecture Center: queue-based load leveling', url: 'https://learn.microsoft.com/en-us/azure/architecture/patterns/queue-based-load-leveling' },
      },
      {
        slug: 'safe-retries', title: 'Make retries safe with idempotency', minutes: 6,
        sections: [
          { title: 'A timeout leaves uncertainty', text: 'A server may commit a change before its response is lost. A retry then risks applying the change again. An idempotency key identifies one intended operation so repeated delivery can return the recorded outcome without repeating its effect.' },
          { title: 'Make deduplication atomic', text: 'Scope keys to the caller and operation, verify that a repeated key has the same payload, and atomically coordinate the recorded outcome with the state change. For effects in another service, that service needs its own deduplication contract. Define key retention and behavior for concurrent or late retries.' },
        ],
        example: { title: 'A lost reservation response', text: 'Reservation request order-a reduces stock from five to four, but the response times out. Sending order-a again must return the original result. A new order-b is a different intent and may reserve another item. Generating a new key for each retry defeats deduplication.' },
        checkpoint: { question: 'A reservation times out after it may have committed. Which key should its retry use?', options: [
          { text: 'A new random key for every attempt.', feedback: 'A new key describes a new operation, so the service cannot recognize the retry.' },
          { text: 'One shared key for all customers.', feedback: 'Unrelated operations must not be treated as duplicates. Scope the key to a specific intent and caller.' },
          { text: 'The same key and payload for the same intended reservation.', correct: true, feedback: 'Correct. Reuse the operation identity so the server can safely replay its outcome.' },
        ] },
        source: { title: 'Amazon Builders’ Library: making retries safe with idempotent APIs', url: 'https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/' },
      },
      {
        slug: 'bounded-recovery', title: 'Bound retries and measure recovery', minutes: 6,
        sections: [
          { title: 'Keep retries within a budget', text: 'Retry only eligible failures and safe operations. Set an overall deadline and a maximum number of attempts, including the first call. Exponential backoff spaces out attempts; jitter varies their timing so clients do not all retry together. Honor server retry guidance within your deadline.' },
          { title: 'Avoid multiplying traffic', text: 'Choose where retries are owned. Three layers making up to three attempts each can turn one user action into 27 calls to a failing dependency. Track latency, errors, retry volume, and recovery so the policy can be adjusted from evidence.' },
        ],
        example: { title: 'A dependency outage', text: 'An operation allows three total attempts within two seconds. After the first timeout, retry only if the operation is safe and another attempt fits the remaining deadline. Stop after the third attempt or the deadline, whichever comes first, and expose a useful failure state.' },
        checkpoint: { question: 'A policy permits three total attempts. How many retries can follow the first call?', options: [
          { text: 'Two retries, subject to the overall deadline.', correct: true, feedback: 'Correct. The initial call consumes one attempt. A deadline may allow fewer than two retries.' },
          { text: 'Three retries plus the first call.', feedback: 'That makes four attempts. Specify whether a budget counts retries or all attempts.' },
          { text: 'Unlimited retries while the server fails.', feedback: 'Unbounded retries can amplify overload and keep users waiting indefinitely.' },
        ] },
        source: { title: 'AWS Well-Architected: control and limit retry calls', url: 'https://docs.aws.amazon.com/wellarchitected/latest/framework/rel_mitigate_interaction_failure_limit_retries.html' },
      },
    ],
  },
  ...appliedSystemDesignCourses,
];

export const lessonKey = (course: Course, lesson: Lesson) => `${course.slug}/${lesson.slug}`;
export const courseMinutes = (course: Course) => course.lessons.reduce((total, lesson) => total + lesson.minutes, 0);
