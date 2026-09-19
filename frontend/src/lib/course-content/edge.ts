import type { Course } from '../course-types';

const valueSource = { title: 'Python documentation: truth values and sequence operations', url: 'https://docs.python.org/3/library/stdtypes.html' };

export const edgeCourses: Course[] = [
  {
    slug: 'edge-case-discovery', track: 'edge', title: 'Find edge and corner cases', level: 'Foundations',
    description: 'Build a deliberate test matrix for empty inputs, exact boundaries, valid zeroes, duplicates, and interacting conditions.',
    outcomes: ['Partition inputs and combine risky boundaries', 'Distinguish absent data from valid falsy values', 'Test identity, multiplicity, and ordering separately'],
    practice: [{ slug: 'chunk-remainder', title: 'The final partial batch disappears' }, { slug: 'cached-zero', title: 'A cache hit becomes a miss' }, { slug: 'ordered-dedup', title: 'A duplicate at the door' }],
    lessons: [
      {
        slug: 'boundary-test-matrix', title: 'Build a boundary and corner-case matrix', minutes: 6,
        sections: [
          { title: 'Partition before guessing', text: 'List the input dimensions: length, value range, ordering, optional fields, and state. For each dimension, choose representatives such as empty, one, many; below, equal, above; missing, null, present. Include invalid inputs only when the contract defines their handling.' },
          { title: 'Combine conditions that interact', text: 'An edge case sits at one boundary; a corner case combines boundaries that may interact. Do not enumerate every possible combination blindly. Choose pairs that influence the same calculation, such as a short list and an oversized batch, or a duplicate ID and a rejected operation.' },
        ],
        example: { title: 'The final partial batch disappears', text: 'A batching function with size 3 should preserve every item, including a remainder. Testing only lengths divisible by three lets a floor-division loop appear correct.',
          code: { label: 'Boundary matrix · batch size 3', text: 'length 0 → []\nlength 1 → [[a]]\nlength 3 → [[a, b, c]]\nlength 4 → [[a, b, c], [d]]\nlength 6 → [[a, b, c], [d, e, f]]' },
          steps: ['Use length 3 as the exact-boundary case, then length 4 to expose the dropped remainder.', 'Combine a one-item list with batch size 10 to test an oversized batch.', 'Check that flattening the batches reproduces the original list in order and that no output batch exceeds the size.'] },
        checkpoint: { question: 'A batcher passes all inputs whose lengths are multiples of its batch size. Which test is most revealing next?', options: [
          { text: 'Another larger exact multiple.', feedback: 'That repeats the same partition and may still avoid the remainder-handling branch.' },
          { text: 'A length one greater than the batch size.', correct: true, feedback: 'Correct. It requires a full batch followed by a one-item remainder.' },
          { text: 'Only a faster machine.', feedback: 'A dropped remainder is a correctness issue, not a processing-capacity issue.' },
        ] }, source: { title: 'Python documentation: subtests for parameterized cases', url: 'https://docs.python.org/3/library/unittest.html#distinguishing-test-iterations-using-subtests' },
      },
      {
        slug: 'absence-versus-zero', title: 'Keep absence separate from zero and false', minutes: 5,
        sections: [
          { title: 'Ask presence and value separately', text: 'Zero, false, and an empty string can be valid data even when a language treats them as falsy. A cache hit asks whether an entry exists; a stock check asks whether its value is positive. Combining these questions in one truthiness test can change the meaning of the program.' },
          { title: 'Choose an unambiguous missing marker', text: 'Use a membership test or a sentinel that cannot be confused with a legitimate value. If null is a valid cached result, checking only for null is not enough. The same distinction applies to a search result at index zero and an empty measurement set.' },
        ],
        example: { title: 'Zero stock becomes a cache miss', text: 'The cache contains item-a with value 0. The program checks if cache.get(key) and unnecessarily reloads the database because the cached value is falsy.',
          code: { label: 'Python · distinguish presence from truthiness', text: 'if key in cache:\n    return cache[key]\nvalue = load_from_store(key)\ncache[key] = value\nreturn value' },
          steps: ['Test an absent key and confirm that it triggers a load.', 'Test a present key with value 0 and confirm that it returns zero without loading.', 'Repeat with false or null only if those are permitted cached values; the membership rule still distinguishes them from absence.'] },
        checkpoint: { question: 'A search returns index 0 for a successful match. What does a truthiness check risk?', options: [
          { text: 'Treating the first-position match as if no match existed.', correct: true, feedback: 'Correct. Compare with the API’s actual missing marker instead of using truthiness.' },
          { text: 'Automatically moving the match to index 1.', feedback: 'Truthiness does not change the index; it chooses the wrong branch for a valid zero.' },
          { text: 'Nothing, because successful results are always positive.', feedback: 'Zero is a valid index and can represent a successful match.' },
        ] }, source: valueSource,
      },
      {
        slug: 'duplicates-and-order', title: 'Test duplicates without losing meaning', minutes: 6,
        sections: [
          { title: 'Separate identity, count, and order', text: 'Decide whether duplicates should be removed, counted, grouped, or rejected. Then specify the order of the output. A set may answer membership correctly while losing required order or multiplicity. Two equal values can also belong to distinct records that must remain separate.' },
          { title: 'Make accidental sorting visible', text: 'Use input deliberately out of sorted order with a duplicate in the middle and another at the end. If first-occurrence order is required, add a value to the output only when it is first seen. Never infer the tie rule from the data structure you happened to choose.' },
        ],
        example: { title: 'Deduplication rearranges the input', text: 'For [b, a, b, c, a], retaining the first occurrence of each value requires [b, a, c]. Sorting a set produces [a, b, c], which has the right members but the wrong order.',
          code: { label: 'Python · membership and output order have separate roles', text: 'seen = set()\nresult = []\nfor value in values:\n    if value not in seen:\n        seen.add(value)\n        result.append(value)' },
          steps: ['Use b before a to ensure alphabetical sorting cannot accidentally pass.', 'Trace both occurrences of b; only the first appends to result.', 'Check all-identical values, no duplicates, and empty input, asserting the sequence rather than just its set of members.'] },
        checkpoint: { question: 'The output has the correct unique values but a different order from the required first occurrences. Is it correct?', options: [
          { text: 'Yes. A matching set always proves sequence equality.', feedback: 'Sets discard ordering information that the requirement explicitly preserves.' },
          { text: 'Yes, if the output happens to be sorted.', feedback: 'Sorted order is a different policy from first-occurrence order.' },
          { text: 'No. Membership and order are independent parts of the contract.', correct: true, feedback: 'Correct. Assert the full ordered result when order is observable behavior.' },
        ] }, source: valueSource,
      },
    ],
  },
  {
    slug: 'boundaries-and-representation', track: 'edge', title: 'Solve numeric, text, and time boundaries', level: 'Intermediate',
    description: 'Find failures caused by representation: decimal precision, Unicode counting, and timestamps with different offsets.',
    outcomes: ['Keep decimal values exact from parsing onward', 'Choose the correct unit for text operations', 'Compare timestamps as actual instants'],
    practice: [{ slug: 'strict-decimal-cents', title: 'A decimal amount loses a cent' }, { slug: 'unicode-count', title: 'An emoji counts as two' }, { slug: 'timestamp-offset-order', title: 'The timeline sorted by local clocks' }],
    lessons: [
      {
        slug: 'exact-numeric-representations', title: 'Keep exact values exact from the input', minutes: 6,
        sections: [
          { title: 'Separate syntax, arithmetic, and rounding', text: 'A decimal amount may require a restricted grammar, exact arithmetic, and a specific rounding policy. Validate the original text before parsing. If only one or two fractional digits are permitted, accepting an exponent or silently rounding a third digit changes the contract.' },
          { title: 'Do not pass through an inexact representation', text: 'Use a decimal type constructed from the original string, or parse whole and fractional digits directly into integer minor units. Creating a decimal from an already rounded binary float cannot recover the original text’s exact value. Choose an output integer type wide enough for the maximum amount.' },
        ],
        example: { title: 'Converting 1.15 into cents', text: 'The accepted decimal string 1.15 must become exactly 115 cents. A binary floating-point intermediate can fall slightly below the intended value before truncation.',
          steps: ['Validate the required grammar first: optional minus, integer digits, and at most two fractional digits.', 'Parse "1.15" directly into decimal arithmetic or split it into 1 whole unit and 15 cents.', 'Check "0.01", "-0.01", the maximum accepted amount, and invalid "1.005". Invalid syntax should not be quietly rounded.'] },
        checkpoint: { question: 'Why construct an exact decimal from the original input string instead of from a float?', options: [
          { text: 'A decimal type automatically accepts only your application’s grammar.', feedback: 'Grammar validation remains a separate step; decimal parsers may accept additional syntax.' },
          { text: 'The float may already have rounded away information from the original value.', correct: true, feedback: 'Correct. Preserve the source representation until you choose an exact numeric interpretation.' },
          { text: 'Every decimal operation is guaranteed to need no rounding policy.', feedback: 'Operations can still require explicit precision and rounding. Exact input conversion is only the first step.' },
        ] }, source: { title: 'Python documentation: decimal arithmetic and construction', url: 'https://docs.python.org/3/library/decimal.html' },
      },
      {
        slug: 'unicode-units', title: 'Choose the right unit when counting text', minutes: 6,
        sections: [
          { title: 'Define what one character means', text: 'Bytes, UTF-16 code units, Unicode code points, and user-perceived characters are different units. Ask which one the requirement wants before choosing a length operation. ASCII-only examples cannot reveal the difference because these counts often coincide there.' },
          { title: 'Use examples that separate the units', text: 'A supplementary-plane emoji occupies two UTF-16 code units but one code point. A letter plus a combining mark contains two code points even when displayed as one grapheme. For the linked code-point exercise, do not normalize or combine these values unless the requirement asks for it.' },
        ],
        example: { title: 'An emoji counts as two', text: 'For A😀, JavaScript string.length is 3 but the required code-point count is 2. String iteration advances by code point, which matches this exercise’s contract.',
          code: { label: 'JavaScript · count code points', text: 'let count = 0;\nfor (const codePoint of text) {\n  count += 1;\n}\nreturn count;' },
          steps: ['Test A😀 to separate UTF-16 length from code-point length.', 'Test e followed by a combining acute accent; the expected code-point count is 2, even if it displays as one letter.', 'Check empty text and a joined emoji sequence. Use grapheme segmentation only for a contract that asks for user-perceived characters.'] },
        checkpoint: { question: 'The contract counts code points. How many are in e followed by one combining accent?', options: [
          { text: 'Two, regardless of whether the display combines them into one grapheme.', correct: true, feedback: 'Correct. The requested unit is code points, not display width or grapheme clusters.' },
          { text: 'Always one because it looks like one letter.', feedback: 'Visual appearance does not determine the number of code points.' },
          { text: 'The number of bytes used by the file encoding.', feedback: 'Byte length is another unit and varies with the encoding.' },
        ] }, source: { title: 'MDN: string iteration by Unicode code point', url: 'https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/Symbol.iterator' },
      },
      {
        slug: 'time-offset-boundaries', title: 'Compare instants, not wall-clock labels', minutes: 6,
        sections: [
          { title: 'Keep the offset attached to the time', text: 'An offset tells you how a local timestamp relates to UTC. Sorting local text fields across different offsets can reverse the actual timeline. Parse valid timestamps into offset-aware values and compare their instants. Do not discard the offset during normalization.' },
          { title: 'Test ties and day crossings', text: 'Choose examples whose local ordering differs from UTC ordering, including a date boundary. Specify how equal instants should be ordered; the linked problem preserves input order. Local times without an offset require a separate timezone policy and cannot be resolved by guessing one.' },
        ],
        example: { title: '09:00 happened before 08:30', text: 'A is 2026-01-01T09:00:00+02:00, which is 07:00 UTC. B is 2026-01-01T08:30:00Z. Although A looks later by its clock label, it happened 90 minutes before B.',
          steps: ['Convert both values to a shared instant representation: A = 07:00 UTC and B = 08:30 UTC.', 'Sort A before B using the parsed aware values.', 'Add C = 2026-01-01T07:00:00Z. A and C are equal instants, so keep their original relative order.'] },
        checkpoint: { question: 'Two timestamp strings have different offsets but represent the same instant. What should a stable chronological sort do?', options: [
          { text: 'Put the larger displayed hour first.', feedback: 'Displayed hours are not comparable independently of their offsets.' },
          { text: 'Drop one event as a duplicate automatically.', feedback: 'Equal timestamps do not imply that two distinct events are duplicates.' },
          { text: 'Treat them as tied and preserve their input order.', correct: true, feedback: 'Correct. Compare instants and apply the specified tie policy to distinct events.' },
        ] }, source: { title: 'Python documentation: aware and naive datetime objects', url: 'https://docs.python.org/3/library/datetime.html' },
      },
    ],
  },
];
