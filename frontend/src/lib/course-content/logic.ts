import type { Course } from '../course-types';

export const logicCourses: Course[] = [
  {
    slug: 'logic-control-flow', track: 'logic', title: 'Find logic errors in control flow', level: 'Foundations',
    description: 'Spot wrong loop boundaries, boolean groupings, and ordering rules in code that runs without crashing.',
    outcomes: ['Trace loops with an invariant', 'Turn conditions into decision tables', 'Test sorting and tie-breaking rules'],
    practice: [{ slug: 'binary-search-stall', title: 'The search that never ends' }, { slug: 'boolean-precedence', title: 'One region bypasses the age check' }, { slug: 'stable-priority-sort', title: 'Equal-priority jobs jump the queue' }],
    lessons: [
      {
        slug: 'loop-invariants', title: 'Trace boundaries and prove progress', minutes: 6,
        sections: [
          { title: 'State what the bounds mean', text: 'Write whether an interval includes its endpoints. For a half-open binary search, [lo, hi) contains all remaining candidates. Initialization, comparison, and updates must preserve that meaning. Mixing a closed-interval update with a half-open loop can skip a candidate or stall.' },
          { title: 'Make the interval strictly smaller', text: 'Inspect the smallest nonempty search interval. If an iteration can leave both bounds unchanged, termination is not guaranteed. When the midpoint is too small to be the answer, exclude it as well as everything below it. Verify empty input and insertion at either end.' },
        ],
        example: { title: 'A one-element search never advances', text: 'For [5] and target 8, lo = 0, hi = 1, and mid = 0. Setting lo = mid repeats the same state forever. A lower-bound search needs lo = mid + 1 on this branch.',
          code: { label: 'Python · lower-bound search', text: 'lo, hi = 0, len(values)\nwhile lo < hi:\n    mid = (lo + hi) // 2\n    if values[mid] < target:\n        lo = mid + 1\n    else:\n        hi = mid\nreturn lo' },
          steps: ['Trace [5], target 8; the repaired interval changes from [0, 1) to [1, 1).', 'Trace [5], target 5; the other branch changes hi to 0 and returns index 0.', 'Check [] and repeated values. If the task requires an exact-match index, validate the returned insertion point before dereferencing it.'] },
        checkpoint: { question: 'In a half-open lower-bound search, values[mid] is smaller than the target. How should lo change?', options: [
          { text: 'Set lo to mid so the midpoint stays a candidate.', feedback: 'That midpoint cannot satisfy the condition, and retaining it can stall a one-element interval.' },
          { text: 'Set lo to mid + 1 to exclude a disproven candidate.', correct: true, feedback: 'Correct. The update preserves the candidate interval and guarantees progress on this branch.' },
          { text: 'Leave both bounds unchanged and retry.', feedback: 'The same deterministic comparison will repeat indefinitely.' },
        ] }, source: { title: 'Python documentation: bisection and insertion-point semantics', url: 'https://docs.python.org/3/library/bisect.html' },
      },
      {
        slug: 'boolean-decision-tables', title: 'Expose boolean mistakes with a decision table', minutes: 5,
        sections: [
          { title: 'Translate the sentence into gates', text: 'Identify which requirements are mandatory and which are alternatives. “An adult in north or south” requires an age gate and a region gate. Parenthesize the alternatives so that every allowed region remains subject to the age requirement.' },
          { title: 'Test a single failed gate', text: 'Build rows that satisfy everything except one requirement. These near misses expose an OR that bypasses a mandatory condition. Include exact thresholds and unrecognized values. Checking only a fully eligible and a fully ineligible person misses many grouping errors.' },
        ],
        example: { title: 'The south branch skips the age check', text: 'In Python, and binds more tightly than or. Without grouping, a person in south qualifies even when younger than 18.',
          code: { label: 'Python · compare the two rules', text: '# Bug: the last alternative bypasses the age gate\nage >= 18 and region == "north" or region == "south"\n# Fix: both regions share the same mandatory age gate\nage >= 18 and (region == "north" or region == "south")' },
          steps: ['Use age 17 and south to expose the bypass: expected false, broken result true.', 'Use age 18 in both allowed regions to check the inclusive age boundary.', 'Use age 18 in west to verify that passing the age gate does not bypass the region gate.'] },
        checkpoint: { question: 'Which case specifically exposes the ungrouped south alternative?', options: [
          { text: 'An adult in north.', feedback: 'Both the correct and broken expressions accept this person, so the case does not distinguish them.' },
          { text: 'An adult in south.', feedback: 'This is also accepted by both expressions. Test a mandatory gate that should reject the person.' },
          { text: 'A 17-year-old in south.', correct: true, feedback: 'Correct. The broken OR accepts south independently of the age requirement.' },
        ] }, source: { title: 'Python reference: boolean operations and operator precedence', url: 'https://docs.python.org/3/reference/expressions.html' },
      },
      {
        slug: 'sorting-and-ties', title: 'Debug ordering and tie rules', minutes: 6,
        sections: [
          { title: 'Write the full ordering contract', text: 'Specify the primary key, direction, and behavior when keys tie. A numeric sort and a text sort answer different questions. For jobs with equal priority, preserve arrival order only if the requirement says so; do not invent an alphabetical tie-breaker.' },
          { title: 'Inspect the comparator as a relation', text: 'A comparator must handle less-than, greater-than, and equality consistently. For equal keys, return zero when they should remain tied. In JavaScript, stable sorting preserves the input order of such ties. Copy the input first when the caller’s array must remain unchanged.' },
        ],
        example: { title: 'Equal-priority work jumps the queue', text: 'Jobs arrive as b with priority 2, a with priority 2, and c with priority 5. Descending priority with arrival-order ties must produce c, b, a.',
          code: { label: 'JavaScript · preserve arrival-order ties', text: 'return [...jobs]\n  .sort((a, b) => b.priority - a.priority)\n  .map(job => job.id);' },
          steps: ['Use unequal priorities to verify the descending direction.', 'Use equal priorities with IDs deliberately out of alphabetical order to reveal an unwanted secondary sort.', 'Test the same priority on every job; the output should preserve the full input order.'] },
        checkpoint: { question: 'Equal-priority jobs must keep their arrival order. What should their comparator return?', options: [
          { text: 'Zero, using a stable sort.', correct: true, feedback: 'Correct. Equal keys remain tied, and the stable sort retains their original order.' },
          { text: 'Always one, so every comparison chooses a winner.', feedback: 'That treats equal elements inconsistently and can break the comparator contract.' },
          { text: 'An alphabetical comparison of their IDs.', feedback: 'That introduces a tie-breaker the requirement explicitly does not want.' },
        ] }, source: { title: 'MDN: Array.sort comparators and sort stability', url: 'https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/sort' },
      },
    ],
  },
  {
    slug: 'logic-state-and-algorithms', track: 'logic', title: 'Debug state and algorithm choices', level: 'Intermediate',
    description: 'Find shared-reference bugs, overwritten intermediate values, and algorithms that finalize an answer too early.',
    outcomes: ['Distinguish independent values from aliases', 'Trace old and new state in a recurrence', 'Match traversal order to the required answer'],
    practice: [{ slug: 'shared-matrix', title: 'Every row changes at once' }, { slug: 'edit-distance-diagonal', title: 'The spell checker overwrites its memory' }, { slug: 'dijkstra-early-visit', title: 'The route marked final too soon' }],
    lessons: [
      {
        slug: 'shared-references', title: 'Find accidental shared references', minutes: 5,
        sections: [
          { title: 'Draw objects, not just variable names', text: 'Two variables can point to one mutable object. Repeating a reference does not construct independent rows or records. If changing one cell affects unrelated cells, inspect object identity and the construction step before blaming the update statement.' },
          { title: 'Create independence at the right depth', text: 'A shallow copy duplicates only the outer container. Nested mutable values can still be shared. Construct each row separately when rows should be independent. Use deeper copying only when the ownership model requires it; deliberate shared state should remain shared.' },
        ],
        example: { title: 'One write changes every matrix row', text: 'A two-row board built by repeating one list contains two references to the same row. Assigning board[0][0] also changes what board[1][0] reads.',
          code: { label: 'Python · independent row construction', text: '# Shared row: [[0, 0]] * 2\nboard = [[0, 0] for _ in range(2)]\nboard[0][0] = 9\n# Expected: [[9, 0], [0, 0]]' },
          steps: ['Reproduce with just two rows and change one cell.', 'Check whether the two row references point to the same object in the broken setup.', 'Construct each row independently and assert that the untouched row retains its original values.'] },
        checkpoint: { question: 'You shallow-copy a list of mutable rows. Are the inner rows necessarily independent?', options: [
          { text: 'Yes. Every copy recursively duplicates all objects.', feedback: 'A shallow copy duplicates the outer container, leaving references to nested objects intact.' },
          { text: 'No. The new outer list can still reference the original rows.', correct: true, feedback: 'Correct. Inspect ownership at the level where mutation occurs.' },
          { text: 'Yes, provided the list has only two rows.', feedback: 'The number of rows does not change shallow-copy semantics.' },
        ] }, source: { title: 'Python documentation: shallow and deep copying', url: 'https://docs.python.org/3/library/copy.html' },
      },
      {
        slug: 'recurrence-update-order', title: 'Preserve the state a recurrence still needs', minutes: 7,
        sections: [
          { title: 'Label every dependency', text: 'Before optimizing a table into one row, write whether each dependency comes from the previous row or the current row. In edit distance, the value above and the diagonal belong to the previous row; the value to the left belongs to the current row.' },
          { title: 'Trace a tiny reference table', text: 'Use a hand-worked two-dimensional table as the reference, then compare each compressed update. Save an old value before overwriting it if the next cell still needs it. A compact algorithm is correct only when its update order preserves the original recurrence.' },
        ],
        example: { title: 'A matching letter costs an edit', text: 'Transforming a into a costs zero. With a single working row, changing row[0] to 1 before saving its old value destroys the diagonal zero needed for the matching cell.',
          code: { label: 'Python · preserve previous-row values', text: 'diagonal = row[0]\nrow[0] = i\nfor j, target_char in enumerate(target, 1):\n    above = row[j]\n    cost = 0 if source_char == target_char else 1\n    row[j] = min(above + 1, row[j - 1] + 1, diagonal + cost)\n    diagonal = above' },
          steps: ['For a → a, start from row [0, 1]; save diagonal = 0 before updating row[0].', 'The matching cell chooses min(2, 2, 0), producing distance 0.', 'Check a → b, empty → a, and a → empty; these isolate substitution, insertion, and deletion.'] },
        checkpoint: { question: 'Why save row[j] before overwriting it in a one-row edit-distance update?', options: [
          { text: 'To ensure the row always stays sorted.', feedback: 'Sorted order is not the recurrence invariant. The algorithm needs values from different logical rows.' },
          { text: 'To avoid calculating the matching-character cost.', feedback: 'The matching cost is still necessary and is independent of preserving the old cell.' },
          { text: 'Its previous-row value becomes the diagonal needed by the next cell.', correct: true, feedback: 'Correct. Saving the old value preserves a dependency that an in-place update would otherwise erase.' },
        ] }, source: { title: 'MIT OpenCourseWare: dynamic programming and edit distance', url: 'https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-fall-2011/resources/lecture-21-dp-iii-parenthesization-edit-distance-knapsack/' },
      },
      {
        slug: 'discovery-versus-finality', title: 'Do not finalize an answer at first discovery', minutes: 7,
        sections: [
          { title: 'Check the assumptions behind the algorithm', text: 'Breadth-first search minimizes the number of edges in an unweighted graph. When edges have different costs, the first discovered path need not be cheapest. For nonnegative weights, Dijkstra’s algorithm processes the smallest current distance and relaxes outgoing edges.' },
          { title: 'Keep improvements eligible', text: 'Maintain the best known distance to each node and enqueue strict improvements. An older queued distance may become stale and should be skipped. Marking a weighted node final when it is first discovered suppresses later, cheaper paths; the ordering of finalization matters.' },
        ],
        example: { title: 'A direct route costs more', text: 'Edges are A → B with cost 9, A → C with cost 2, and C → B with cost 1. The shortest path to B costs 3, even if the direct edge is inspected first.',
          steps: ['From A, record tentative distances B = 9 and C = 2.', 'Process C first and improve B to 3; B must remain eligible for that improvement.', 'Process the current distance 3 for B and ignore the stale distance 9 later. Also test an unreachable target and a target equal to the start.'] },
        checkpoint: { question: 'B is first discovered with distance 9, then a path of cost 3 is found. What should the algorithm do?', options: [
          { text: 'Update B to 3 and enqueue the improved distance.', correct: true, feedback: 'Correct. Discovery is tentative; a cheaper path must remain eligible to replace it.' },
          { text: 'Keep 9 because B was discovered first.', feedback: 'First discovery does not establish the minimum cost in a weighted graph.' },
          { text: 'Average the two path costs.', feedback: 'The requirement asks for the minimum path cost, not an average over discovered paths.' },
        ] }, source: { title: 'Princeton Algorithms: shortest paths and edge relaxation', url: 'https://algs4.cs.princeton.edu/44sp/' },
      },
    ],
  },
];
