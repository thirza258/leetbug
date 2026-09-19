import type { Course } from '../course-types';

const exceptionSource = { title: 'Python tutorial: errors and exceptions', url: 'https://docs.python.org/3/tutorial/errors.html' };

export const runtimeCourses: Course[] = [
  {
    slug: 'runtime-crash-investigation', track: 'runtime', title: 'Trace runtime errors to their cause', level: 'Foundations',
    description: 'Use the exception, input shape, and failing operation to fix crashes without hiding invalid assumptions.',
    outcomes: ['Read an exception and trace its inputs', 'Guard optional and empty values correctly', 'Contain parsing failures at the right boundary'],
    practice: [{ slug: 'empty-average', title: 'No data, big problem' }, { slug: 'optional-profile', title: 'A guest without a profile' }, { slug: 'unsafe-json', title: 'One bad payload takes down the batch' }],
    lessons: [
      {
        slug: 'read-the-crash', title: 'Read the crash from the failing operation', minutes: 5,
        sections: [
          { title: 'Use the exception as a clue', text: 'Identify the exception type, the failing expression, and the application calls that led to it. Inspect the operands at that point: a zero divisor, missing key, or out-of-range index suggests a violated precondition. The throwing line is where the failure surfaced; its cause may be earlier.' },
          { title: 'Repair the assumption', text: 'Trace the bad value back to its source and compare it with the accepted input contract. Handle a valid empty case explicitly. Reject invalid input only when the contract requires rejection. Catching every exception and returning a convenient value conceals unrelated defects.' },
        ],
        example: { title: 'An empty report divides by zero', text: 'The report averages a list and requires a zero result when there are no readings. An empty list reaches the same division as a populated list.',
          code: { label: 'Python · failing operation', text: 'average = sum(values) / len(values)\n# values = [] gives 0 / 0' },
          steps: ['Reproduce with [] and inspect len(values), which is zero.', 'Add the contract-specific empty result before division; do not invent a divisor of one.', 'Check [] → 0, [0] → 0, and [2, 4] → 3 to cover empty, zero-valued, and ordinary samples.'] },
        checkpoint: { question: 'The contract says an empty average is zero. What is the appropriate repair?', options: [
          { text: 'Replace every zero divisor with one.', feedback: 'That invents a numeric result and does not implement the specified empty behavior.' },
          { text: 'Handle the empty list explicitly before calculating the average.', correct: true, feedback: 'Correct. The guard expresses the contract and prevents the invalid division.' },
          { text: 'Catch every exception in the program and return null.', feedback: 'A broad catch also hides defects unrelated to empty input.' },
        ] }, source: exceptionSource,
      },
      {
        slug: 'optional-input-shapes', title: 'Guard each optional level', minutes: 5,
        sections: [
          { title: 'Separate missing, null, and blank', text: 'Sketch the input shape and mark each optional field. A user object, its profile, and its name can fail independently. Protect each optional dereference, then validate the final value before calling string methods. Do not assume guarding the root also protects every child.' },
          { title: 'Normalize after checking presence', text: 'Apply only the normalization the requirement allows. A blank display name may become Anonymous after trimming, while an empty identifier may be valid in another problem. Use explicit presence and type checks instead of one fallback rule for every input.' },
        ],
        example: { title: 'A guest has no profile', text: 'The exercise allows missing or null user/profile fields and uses Anonymous for a missing or blank name. JavaScript optional chaining can protect the optional levels under that stated input shape.',
          code: { label: 'JavaScript · guarded access', text: 'const name = data.user?.profile?.name;\nreturn name == null || name.trim() === ""\n  ? "Anonymous"\n  : name.trim();' },
          steps: ['Try a missing user, a null user, and a user whose profile is null.', 'Try a blank name and a name with surrounding spaces to check normalization.', 'Keep type validation separate if the contract also permits non-string names; optional chaining alone does not validate types.'] },
        checkpoint: { question: 'You checked that user exists, but user.profile can be null. What remains necessary?', options: [
          { text: 'Read profile.name immediately because the root exists.', feedback: 'Each optional level has its own precondition. A valid user does not guarantee a profile.' },
          { text: 'Convert the entire profile object into a string.', feedback: 'Coercion does not recover the required name and can invent a misleading result.' },
          { text: 'Guard profile before reading name, then normalize the name according to the contract.', correct: true, feedback: 'Correct. Protect the access path and apply the final-value rule separately.' },
        ] }, source: { title: 'MDN: optional chaining', url: 'https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Optional_chaining' },
      },
      {
        slug: 'parsing-boundaries', title: 'Contain malformed input without hiding bugs', minutes: 6,
        sections: [
          { title: 'Decode, validate shape, then use', text: 'Parsing succeeds for many values that are not the object you need. Valid JSON can be null, a number, or an array. Separate syntax errors from shape validation and from field validation. Each phase should have an explicit accepted and rejected result.' },
          { title: 'Keep exception handling narrow', text: 'Catch the expected decoding error around the decoder. Check the decoded value before indexing it, and check the field type before returning it. A broad catch around the whole workflow can turn a programming mistake into an apparently normal invalid-input response.' },
        ],
        example: { title: 'Valid JSON, wrong shape', text: 'The endpoint returns an id only when the payload is an object and id is a string. Both malformed JSON and an array must return null; an empty string id must survive unchanged.',
          code: { label: 'Python · separate decoding from validation', text: 'try:\n    value = json.loads(payload)\nexcept json.JSONDecodeError:\n    return None\nif not isinstance(value, dict):\n    return None\nidentifier = value.get("id")\nreturn identifier if isinstance(identifier, str) else None' },
          steps: ['Test malformed text to exercise only the decoder failure path.', 'Test null, [], and {"id": 7} to challenge shape and field type independently.', 'Test {"id": ""} and {"id": "a"}; both are valid string IDs and must be preserved.'] },
        checkpoint: { question: 'JSON decoding succeeds on []. Can you now safely read an object field named id?', options: [
          { text: 'No. Validate that the decoded value is an object first.', correct: true, feedback: 'Correct. Valid syntax does not establish the top-level shape or the field type.' },
          { text: 'Yes. All valid JSON values are objects.', feedback: 'JSON also permits arrays, strings, numbers, booleans, and null.' },
          { text: 'Yes, after converting every value into a string.', feedback: 'Coercion changes the input contract and does not establish that an id field exists.' },
        ] }, source: { title: 'Python documentation: JSON decoding', url: 'https://docs.python.org/3/library/json.html' },
      },
    ],
  },
  {
    slug: 'runtime-state-and-termination', track: 'runtime', title: 'Fix unsafe state and runaway execution', level: 'Intermediate',
    description: 'Diagnose collection mutation, repeated traversal, and response serialization failures that appear beyond the happy path.',
    outcomes: ['Avoid invalidating a collection while iterating', 'Make traversal terminate on cycles', 'Preserve exact values at the output boundary'],
    practice: [{ slug: 'mutation-during-iteration', title: 'Cleanup breaks halfway through' }, { slug: 'recursive-cycle', title: 'A dependency walks back to itself' }, { slug: 'bigint-json-total', title: 'The exact total that will not serialize' }],
    lessons: [
      {
        slug: 'safe-collection-updates', title: 'Separate traversal from structural changes', minutes: 5,
        sections: [
          { title: 'Identify what invalidates the traversal', text: 'Check whether the loop removes or inserts entries in the same collection it is traversing. Depending on the language and collection, this can raise an error or silently skip elements. A failure after several successful iterations often points to the first structural mutation.' },
          { title: 'Choose an explicit update strategy', text: 'Build a separate result when the task is filtering. If mutation is required, collect the keys to change first or use the collection’s documented removal mechanism. Copying keys protects iteration, but it does not by itself make a shared collection safe under concurrency.' },
        ],
        example: { title: 'Cleaning inactive sessions', text: 'A Python loop deletes inactive sessions from the dictionary it is currently iterating. The required output is just the sorted active IDs, so the mutation is unnecessary.',
          code: { label: 'Python · filter into a new result', text: 'active = [key for key, enabled in sessions.items() if enabled]\nreturn sorted(active)' },
          steps: ['Reproduce with one active and two inactive sessions so filtering must inspect both kinds.', 'Collect active IDs separately and leave the source dictionary untouched.', 'Verify empty, all-inactive, and all-active inputs, including the required output ordering.'] },
        checkpoint: { question: 'You only need a list of active IDs. Which approach avoids iterator invalidation?', options: [
          { text: 'Delete inactive keys inside the same dictionary iteration.', feedback: 'That changes the structure currently being traversed and can invalidate the iterator.' },
          { text: 'Build a separate list of active IDs.', correct: true, feedback: 'Correct. Filtering into a result avoids structural changes to the traversed dictionary.' },
          { text: 'Catch the mutation error and return the partial result.', feedback: 'A partial result omits entries and conceals the underlying traversal defect.' },
        ] }, source: { title: 'Python tutorial: data structures and looping techniques', url: 'https://docs.python.org/3/tutorial/datastructures.html' },
      },
      {
        slug: 'cycles-and-termination', title: 'Find why execution never finishes', minutes: 6,
        sections: [
          { title: 'Name the progress measure', text: 'For a loop, identify what moves toward termination: a shrinking interval, an advancing cursor, or a decreasing work count. For graph traversal, cycles can keep generating work unless visited nodes are excluded. Increasing the timeout leaves a missing progress rule unresolved.' },
          { title: 'Mark before expanding', text: 'When listing reachable nodes once, mark a node as visited before traversing its neighbors. A set used only for the final output does not stop recursive calls. If the task is to report cycles rather than merely avoid repeated visits, distinguish nodes on the active path from fully explored nodes.' },
        ],
        example: { title: 'A points to B, and B points back', text: 'The graph A → B → A is valid input for a reachability task. Recursion that adds a node to visited only after exploring its neighbors never reaches that final step.',
          code: { label: 'Python · visited check before expansion', text: 'def visit(node):\n    if node in visited:\n        return\n    visited.add(node)\n    for neighbor in graph.get(node, []):\n        visit(neighbor)' },
          steps: ['Trace A, B, A and observe the repeated state in the broken implementation.', 'Mark A before entering B so the second visit to A returns immediately.', 'Check a self-loop, a shared descendant, and a missing adjacency key; consider an explicit stack for very deep graphs.'] },
        checkpoint: { question: 'When should a node be marked visited in a reachability traversal that must tolerate cycles?', options: [
          { text: 'After recursively processing every neighbor.', feedback: 'A cycle can return to the same node before that mark is ever reached.' },
          { text: 'Only when formatting the final result.', feedback: 'Output deduplication does not prevent repeated traversal or unbounded recursion.' },
          { text: 'Before expanding its neighbors.', correct: true, feedback: 'Correct. A back edge then reaches an already visited node and stops expanding it.' },
        ] }, source: { title: 'Python documentation: graph cycles and ordering', url: 'https://docs.python.org/3/library/graphlib.html' },
      },
      {
        slug: 'serialization-boundary', title: 'Check the final serialization boundary', minutes: 6,
        sections: [
          { title: 'Correct arithmetic can still fail to return', text: 'Trace the whole path from input parsing through computation to response encoding. JavaScript BigInt supports exact integer arithmetic, but default JSON serialization cannot encode a BigInt directly. Returning an internal value is only correct if it also matches the external representation contract.' },
          { title: 'Convert at the boundary, without losing precision', text: 'When the result must be an exact decimal string, parse directly into BigInt, keep that type during arithmetic, and convert the final total to a string. Passing through Number first can round large integers. Also check what empty input must serialize to.' },
        ],
        example: { title: 'The sum is right until JSON encodes it', text: 'Two decimal strings represent 9007199254740993 and 2. The expected response is {total: "9007199254740995"}. A raw BigInt result throws during default JSON encoding.',
          code: { label: 'JavaScript · exact computation and JSON-safe output', text: 'const total = values.reduce((sum, value) => sum + BigInt(value), 0n);\nreturn { total: total.toString() };' },
          steps: ['Test a value beyond the safe integer range so a lossy Number conversion cannot pass unnoticed.', 'Check both the calculated digits and the successful serialization of the response.', 'Test the empty list and cancellation of positive and negative values; both must produce the canonical string "0".'] },
        checkpoint: { question: 'The API requires an exact integer as a decimal string. How should you return a BigInt total?', options: [
          { text: 'Convert it directly to its decimal string at the response boundary.', correct: true, feedback: 'Correct. This preserves the exact integer and provides a JSON-compatible value.' },
          { text: 'Convert it to Number and then to a string.', feedback: 'The intermediate Number may round away digits that the contract requires.' },
          { text: 'Return the raw BigInt and rely on default JSON serialization.', feedback: 'Default JSON.stringify throws when it encounters a BigInt.' },
        ] }, source: { title: 'MDN: JSON.stringify and supported values', url: 'https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/JSON/stringify' },
      },
    ],
  },
];
