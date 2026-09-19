import type { Course } from '../course-types';

export const appliedSystemDesignCourses: Course[] = [
  {
    slug: 'system-design-failure-analysis', track: 'system_design', title: 'Test a system design against failure', level: 'Intermediate',
    description: 'Challenge a design with stale reads, disappearing workers, and failing dependencies, then choose the guarantees it needs.',
    outcomes: ['Trace a cache through reads and writes', 'Choose recovery semantics for queued jobs', 'Verify circuit-breaker recovery at its boundary'],
    practice: [{ slug: 'cache-write-invalidation', title: 'The cache remembers an old value' }, { slug: 'queue-visibility-redelivery', title: 'The job lost after a worker disappears' }, { slug: 'circuit-breaker-cooldown', title: 'The circuit that never closes' }],
    lessons: [
      {
        slug: 'cache-read-write-traces', title: 'Choose a consistency policy with a read-write trace', minutes: 6,
        sections: [
          { title: 'Make freshness a requirement', text: 'Decide which reads may lag and which decisions need authoritative data. A product page may tolerate an old stock display; reserving the last unit cannot trust it. Trace the cache and store as separate copies so an update to one does not imply an update to the other.' },
          { title: 'Test the write path and its limits', text: 'In a sequential cache-aside exercise, updating the store and invalidating the key prevents later reads from reusing the old entry. In a concurrent system, an in-flight read can refill stale data after invalidation. Stronger freshness requirements need an appropriate coordination or authoritative-read strategy.' },
        ],
        example: { title: 'A successful write leaves an old cached value', text: 'Read item A at value 4 to populate the cache, write A = 9, then read A again. If the final read returns 4, the write path left the cached copy valid.',
          code: { label: 'Sequential trace · store and cache', text: 'read A    → store 4, cache 4, result 4\nwrite A=9 → store 9, cache entry invalidated\nread A    → cache miss, load 9, result 9' },
          steps: ['Reproduce read → write → read on one key and assert the final value is 9.', 'Invalidate that key after the authoritative write, and check that unrelated cached keys remain available.', 'For a concurrent design, also consider a stale read finishing after invalidation; document whether that staleness is allowed.'] },
        checkpoint: { question: 'Stock reservation requires an authoritative decision. A display cache may be stale. Which path should decide the reservation?', options: [
          { text: 'The cache, because it responds fastest.', feedback: 'Speed does not satisfy the freshness and atomic-update requirements of the reservation decision.' },
          { text: 'An authoritative atomic stock check and update.', correct: true, feedback: 'Correct. Choose the data path whose guarantees match the decision, while keeping display caching separate.' },
          { text: 'Whichever cached replica reports the most stock.', feedback: 'Selecting a favorable stale value does not establish that the stock can actually be reserved.' },
        ] }, source: { title: 'Azure Architecture Center: cache-aside consistency considerations', url: 'https://learn.microsoft.com/en-us/azure/architecture/patterns/cache-aside' },
      },
      {
        slug: 'worker-loss-and-leases', title: 'Recover work when a worker disappears', minutes: 7,
        sections: [
          { title: 'Distinguish delivery from completion', text: 'Deleting a job when a worker receives it loses work if the worker crashes before finishing. A visibility lease temporarily hides the job; acknowledgement records completion. If the lease expires without a valid acknowledgement, the unfinished job becomes eligible for another delivery.' },
          { title: 'Expect duplicates and stale owners', text: 'Redelivery can happen after an effect already occurred, so handlers need idempotency. In the linked exercise, every delivery has a new token and only the current unexpired token can acknowledge it. Set lease durations or renewal policies around measured job duration and recovery needs.' },
        ],
        example: { title: 'An old worker acknowledges a new lease', text: 'At time 0, job A is leased with token 1 until time 5. The worker disappears. At time 5, A is redelivered with token 2. Token 1 must no longer be able to finish the job.',
          steps: ['Advance to the exact deadline and verify that A becomes available again.', 'Send an acknowledgement using token 1 after redelivery; it must be rejected without completing A.', 'Acknowledge the current token before its deadline and confirm A is completed once. Separately test duplicate business effects in the handler.'] },
        checkpoint: { question: 'A worker dies after receiving a job but before acknowledging it. What should a recoverable queue do?', options: [
          { text: 'Forget the job because delivery means completion.', feedback: 'Receiving work does not prove its processing or effects completed.' },
          { text: 'Hold the job forever for the missing worker.', feedback: 'A permanent lease prevents the remaining workers from recovering unfinished work.' },
          { text: 'Make it eligible for redelivery after the visibility lease expires.', correct: true, feedback: 'Correct. Recovery requires redelivery, and handlers must account for possible duplicate execution.' },
        ] }, source: { title: 'Amazon SQS documentation: visibility timeout and redelivery', url: 'https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html' },
      },
      {
        slug: 'circuit-recovery-boundaries', title: 'Verify a failing dependency can recover', minutes: 6,
        sections: [
          { title: 'Trace the breaker as a state machine', text: 'A closed breaker permits calls and counts failures. Reaching a threshold opens it and blocks calls until a cooldown expires. Recovery needs a probe: success closes the breaker, while failure starts another cooldown. Blocked requests are not dependency failures because no call was made.' },
          { title: 'Check the deadline and probe ownership', text: 'Test just before, exactly at, and after the retry deadline. Merely reaching the deadline must not erase failure history before a probe succeeds. The exercise processes calls synchronously; a concurrent production design also needs a limit on simultaneous recovery probes.' },
        ],
        example: { title: 'Blocked traffic postpones recovery forever', text: 'A breaker opens at time 10 with a cooldown of 5, so its retry deadline is 15. If a blocked call at time 14 moves that deadline to 19, regular traffic can keep the circuit open forever.',
          steps: ['At time 14, block the call and leave the retry deadline at 15.', 'At time 15, permit a probe. On success, close the breaker and clear failures.', 'Repeat with a failed probe: reopen until time 20. Do not interpret the supplied outcome of a blocked call as a real dependency result.'] },
        checkpoint: { question: 'A request is blocked before the cooldown ends. Should it extend the cooldown?', options: [
          { text: 'No. Preserve the deadline because no dependency call occurred.', correct: true, feedback: 'Correct. Extending the cooldown on blocked traffic can prevent recovery indefinitely.' },
          { text: 'Yes. Every arriving request proves the dependency is still failing.', feedback: 'A blocked request provides no new evidence about the dependency’s health.' },
          { text: 'Close the breaker immediately without a probe.', feedback: 'The design requires a successful probe before declaring recovery.' },
        ] }, source: { title: 'Azure Architecture Center: circuit breaker recovery', url: 'https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker' },
      },
    ],
  },
];
