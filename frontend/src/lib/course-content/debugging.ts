import type { Course } from '../course-types';

const debuggerSource = { title: 'Python documentation: inspecting execution with pdb', url: 'https://docs.python.org/3/library/pdb.html' };
const testSource = { title: 'Python documentation: test cases and assertions', url: 'https://docs.python.org/3/library/unittest.html' };

export const debuggingCourses: Course[] = [
  {
    slug: 'finding-the-bug', track: 'debugging', title: 'Find the bug before changing code', level: 'Foundations',
    description: 'Turn a vague failure into a repeatable example, narrow the search, and locate the first wrong step.',
    outcomes: ['Write an expected-versus-actual comparison', 'Reduce a failing input without losing the bug', 'Trace the first broken assumption'],
    practice: [{ slug: 'missing-last-item', title: 'One item short' }, { slug: 'pagination-drift', title: 'Page two looks familiar' }],
    lessons: [
      {
        slug: 'reproduce-the-failure', title: 'Make the failure repeatable', minutes: 5,
        sections: [
          { title: 'Write the contract first', text: 'Record the exact input, expected output, actual output, and relevant starting state. Derive the expectation from the requirement. “The total looks wrong” becomes useful evidence when another person can run the same example and see the same mismatch.' },
          { title: 'Control the moving parts', text: 'Run the unmodified program first. If the result varies, capture the clock, random seed, event order, or shared state that influences it. In LeetBug, use the public input and output as your starting evidence; keep the required function signature and return format.' },
        ],
        example: { title: 'A total that is always a little low', text: 'The requirement is to sum every value. For [4, 7, 2], the expected total is 13, but the program returns 11. That mismatch is a concrete starting point.',
          code: { label: 'Python · failing implementation', text: 'total = 0\nfor i in range(len(nums) - 1):\n    total += nums[i]' },
          steps: ['Run [4, 7, 2] twice and confirm the same result of 11.', 'Record that the missing amount is the final value, 2; treat this as a hypothesis.', 'Try [4, 7, 9]. Returning 11 again supports the hypothesis that the last item is skipped.'] },
        checkpoint: { question: 'Which report gives you the strongest starting point for debugging?', options: [
          { text: 'The aggregation code feels suspicious.', feedback: 'A suspicion needs a reproducible observation before it can guide a fix.' },
          { text: 'Input [4, 7, 2] should return 13 but consistently returns 11.', correct: true, feedback: 'Correct. The input and mismatch let you reproduce the failure and test explanations.' },
          { text: 'Rewrite the entire aggregation function first.', feedback: 'A rewrite before reproduction makes it harder to explain what failed or prove it is fixed.' },
        ] }, source: testSource,
      },
      {
        slug: 'shrink-the-example', title: 'Shrink the input, keep the failure', minutes: 5,
        sections: [
          { title: 'Remove one source of noise at a time', text: 'Reduce records, fields, or actions and rerun the same assertion after each reduction. Keep a reduction only when the original kind of failure remains. Preserve validity: replacing a valid request with malformed input can reveal a different bug.' },
          { title: 'Keep the trigger in view', text: 'For sequence-dependent failures, minimize the sequence as well as each input. A duplicate cancellation needs a successful reservation and two cancellations; deleting the setup may remove the bug. The smallest useful example still explains the causal chain.' },
        ],
        example: { title: 'From a thousand readings to one', text: 'A large sum is incorrect. The final reading is nonzero, and the loop appears to skip it. Reducing the array makes the boundary easier to inspect.',
          steps: ['Reduce the input to [7, 2]; expected 9, actual 7, so the failure survives.', 'Reduce again to [2]; expected 2, actual 0, which isolates the loop boundary.', 'Keep [] as a neighboring passing case. It does not replace [2], because it no longer exposes the defect.'] },
        checkpoint: { question: 'You reduced a failing list to [] and it now passes. What should you keep as the reproducer?', options: [
          { text: 'The empty list because it is the smallest input.', feedback: 'A smaller input is useful only if it preserves the failure you are investigating.' },
          { text: 'A malformed input that raises a different error.', feedback: 'That changes the failure mechanism and no longer explains the original report.' },
          { text: 'The last valid smaller input that still failed.', correct: true, feedback: 'Correct. Preserve the triggering behavior while removing unrelated details.' },
        ] }, source: testSource,
      },
      {
        slug: 'trace-first-divergence', title: 'Find the first divergence', minutes: 6,
        sections: [
          { title: 'Trace decisions, not every line', text: 'Write a short trace of the variables that control the result: index, bounds, accumulator, state, and chosen branch. Compare each step with a hand-worked expectation. The first disagreement narrows your search more effectively than the final wrong output.' },
          { title: 'Inspect before and after the boundary', text: 'In a local debugger, pause before the suspect statement and inspect its inputs, then step over it. LeetBug returns structured output and does not provide an interactive debugger; use a hand trace or a local reproduction, and remove diagnostics before submitting.' },
        ],
        example: { title: 'Page two repeats an item', text: 'With one-based pages and a page size of three, page one starts at index 0 and page two at index 3. Multiplying the page offset by page_size - 1 starts page two at index 2.',
          code: { label: 'Python · inspect the offset', text: 'start = (page - 1) * (page_size - 1)\nreturn items[start:start + page_size]' },
          steps: ['For page 1, both the expected and actual start are 0; this case cannot distinguish the formulas.', 'For page 2, calculate expected start 3 and actual start 2. The divergence occurs before slicing.', 'Use (page - 1) * page_size, then check page 1, page 2, and a page beyond the available items.'] },
        checkpoint: { question: 'The slice returns the wrong records, and its start index is already wrong. Where should you investigate first?', options: [
          { text: 'The calculation that produced the start index.', correct: true, feedback: 'Correct. The earliest observed divergence is upstream of the slice itself.' },
          { text: 'The rendering of the returned records.', feedback: 'Rendering cannot explain an incorrect start index computed before the records are selected.' },
          { text: 'Every unrelated function in the application.', feedback: 'Follow the evidence around the first divergence before widening the search.' },
        ] }, source: debuggerSource,
      },
    ],
  },
  {
    slug: 'proving-the-fix', track: 'debugging', title: 'Prove your fix holds', level: 'Foundations',
    description: 'Choose tests that distinguish causes, prevent regressions, and catch damage hidden behind a successful response.',
    outcomes: ['Test one causal hypothesis at a time', 'Build a focused regression set', 'Check state across sequences of actions'],
    practice: [{ slug: 'negative-window', title: 'The best week is still below zero' }, { slug: 'wallet-rollback', title: 'The transfer that never arrived' }, { slug: 'cancellation-restock-once', title: 'Cancelling twice creates extra stock' }],
    lessons: [
      {
        slug: 'test-a-hypothesis', title: 'Choose a test that can disprove your guess', minutes: 6,
        sections: [
          { title: 'Predict before running', text: 'Write a causal claim and predict what you should observe if it is true. Choose an input on which competing explanations produce different results. A passing happy path often fits several explanations, so it provides little evidence about which one caused the bug.' },
          { title: 'Make one explanatory change', text: 'Change the assumption identified by your experiment, rerun the reproducer, and inspect nearby behavior. If the prediction fails, revise the explanation. Changing several unrelated rules together can hide which change mattered and introduce a second defect.' },
        ],
        example: { title: 'A maximum that refuses to be negative', text: 'The best single-day reading from [-8, -3] should be -3, but the function returns 0. Two hypotheses are an incorrect comparison and an invalid initial maximum.',
          code: { label: 'Python · suspect initialization', text: 'best = 0\nfor value in values:\n    best = max(best, value)' },
          steps: ['Predict that [5] passes but [-3] fails if zero initialization is the cause.', 'Run those cases and trace max(0, -3), which stays zero even though zero was never observed.', 'Handle empty input according to the contract, then initialize from a real candidate and retest both signs.'] },
        checkpoint: { question: 'Which input best tests whether zero is an invalid initial maximum for nonempty data?', options: [
          { text: 'A list containing only positive readings.', feedback: 'Positive readings can replace zero, so that case may pass despite the initialization bug.' },
          { text: 'A list containing only negative readings.', correct: true, feedback: 'Correct. Every valid candidate is below zero, exposing the invented initial result.' },
          { text: 'The same passing example repeated unchanged.', feedback: 'Repeating a passing case does not distinguish the competing explanations.' },
        ] }, source: debuggerSource,
      },
      {
        slug: 'regression-neighbors', title: 'Turn the failure into a regression check', minutes: 5,
        sections: [
          { title: 'Keep the original failure', text: 'A regression check records the behavior that was broken and the required result. Confirm it fails before the fix and passes afterward. Add a few neighboring cases that exercise the same rule from different directions; do not derive their expectations from the code being repaired.' },
          { title: 'Test the rule beyond one example', text: 'When exact outputs are tedious, use a property with a clear scope. For bounded integer sums, appending zero must preserve the total. Such properties supplement concrete examples; a program that always returns zero also satisfies this property, so it is not sufficient alone.' },
        ],
        example: { title: 'Guarding a loop-boundary repair', text: 'Changing a sum loop fixes [2]. A focused regression set must also verify empty input, several items, and values that do not simply increase the running total.',
          steps: ['Keep [2] → 2 as the original failing case and [] → 0 as the empty boundary.', 'Check [4, -4] → 0 and [4, 7, 2] → 13 to cover cancellation and multiple iterations.', 'Check [4, 7, 2, 0] → 13 as a supplementary property, then submit the fix to exercise hidden cases.'] },
        checkpoint: { question: 'A fix passes its original example. What gives useful additional confidence?', options: [
          { text: 'Delete the original test because it now passes.', feedback: 'Keep it so the same defect cannot quietly return.' },
          { text: 'Assume a passing public run proves every input is correct.', feedback: 'Public examples cover only part of the contract. Hidden cases and focused regression checks add evidence.' },
          { text: 'Check nearby boundaries and a scoped property derived from the requirement.', correct: true, feedback: 'Correct. Complement the reproducer with tests that challenge the same rule in different ways.' },
        ] }, source: testSource,
      },
      {
        slug: 'check-state-and-sequences', title: 'Verify state as well as the response', minutes: 6,
        sections: [
          { title: 'A rejection still has effects to check', text: 'List every field the operation can change. For a rejected operation, compare the relevant before and after state, not just the error or boolean response. A function can return false after it has already deducted funds or consumed a coupon.' },
          { title: 'Replay a short sequence', text: 'Reset the fixture between independent tests, but preserve state within a workflow test. Exercise success followed by rejection, duplicate delivery, or cancellation. Assert the invariant after each step so you can identify the first corrupting operation.' },
        ],
        example: { title: 'A second cancellation creates stock', text: 'Begin with stock 5. Reserve two items under order A, then cancel A twice. The required stock sequence is 3, 5, 5; the second cancellation must be rejected without a state change.',
          steps: ['Assert the first reservation succeeds and stock becomes 3.', 'Assert cancellation restores stock to 5 and records A as cancelled.', 'Assert the repeated cancellation fails and stock remains 5; a false response with stock 7 still indicates a bug.'] },
        checkpoint: { question: 'A repeated cancellation returns false but increases stock. Did the test pass?', options: [
          { text: 'No. The rejection must also preserve the relevant state.', correct: true, feedback: 'Correct. Responses and state are separate assertions, and both belong to the workflow contract.' },
          { text: 'Yes, because false is the expected response.', feedback: 'The response hides an unintended inventory mutation. Check the resulting state too.' },
          { text: 'Yes, because extra stock is harmless.', feedback: 'Invented stock can cause later orders to promise items that do not exist.' },
        ] }, source: testSource,
      },
    ],
  },
];
