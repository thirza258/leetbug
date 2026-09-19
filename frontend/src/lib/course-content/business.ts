import type { Course } from '../course-types';

const transactionSource = { title: 'Django documentation: database transactions', url: 'https://docs.djangoproject.com/en/5.2/topics/db/transactions/' };
const ruleSource = { title: 'Python reference: comparisons and boolean operations', url: 'https://docs.python.org/3/reference/expressions.html' };

export const businessCourses: Course[] = [
  {
    slug: 'business-rules-and-invariants', track: 'business', title: 'Find flaws in business rules', level: 'Foundations',
    description: 'Translate product rules into explicit checks for pricing, eligibility, and the order of calculations.',
    outcomes: ['Write business invariants before editing code', 'Keep mandatory approval gates independent', 'Check which amount a threshold applies to'],
    practice: [{ slug: 'checkout-underflow', title: 'The checkout that pays you back' }, { slug: 'expense-policy-gates', title: 'Approval substitutes for a missing receipt' }, { slug: 'shipping-after-discount', title: 'The discount keeps shipping free' }],
    lessons: [
      {
        slug: 'business-invariants', title: 'Find the rule a result must never break', minutes: 5,
        sections: [
          { title: 'Translate policy into assertions', text: 'Read the requirement as a set of input rules and output invariants. In this checkout exercise, negative prices are ignored, a negative discount becomes zero, and the final charge cannot be negative. These are separate obligations; satisfying one does not imply the others.' },
          { title: 'Challenge each stage', text: 'Trace raw inputs, normalized inputs, subtotal, discount, and final charge. Pick one counterexample per rule. A final clamp can hide a bad intermediate value while still overcharging another customer. Keep the rules tied to the stated exercise policy rather than inventing a universal pricing policy.' },
        ],
        example: { title: 'A negative discount adds a charge', text: 'Prices [1200, -200] with discount -100 should charge 1200 under this policy. Clamping only the final result instead produces 1100 and violates two input rules.',
          code: { label: 'Python · enforce each pricing rule', text: 'subtotal = sum(price for price in prices if price >= 0)\napplied_discount = max(0, discount)\nreturn {"total": max(0, subtotal - applied_discount)}' },
          steps: ['Normalize the price list to a subtotal of 1200.', 'Normalize the negative discount to zero; the charge remains 1200.', 'Separately test a discount greater than the subtotal and an empty cart; both must end at zero.'] },
        checkpoint: { question: 'Does clamping the final charge to zero enforce the rule that negative discounts are ignored?', options: [
          { text: 'Yes. Every positive result must be valid.', feedback: 'A positive result can still include an unintended surcharge from subtracting a negative discount.' },
          { text: 'No. Normalize the discount separately before calculating the charge.', correct: true, feedback: 'Correct. Input rules and output bounds must each be enforced.' },
          { text: 'Yes, if there is at least one item.', feedback: 'The presence of items does not prevent a negative discount from increasing the charge.' },
        ] }, source: ruleSource,
      },
      {
        slug: 'independent-policy-gates', title: 'Find a shortcut around a mandatory gate', minutes: 6,
        sections: [
          { title: 'Make the policy table explicit', text: 'Divide the input range at every policy threshold and list the requirements in each band. In this exercise, positive expenses up to 2,500 cents need neither document; amounts above 2,500 need a receipt, and amounts above 10,000 also need preapproval.' },
          { title: 'Approval is not a substitute for evidence', text: 'When a band requires both a receipt and preapproval, combine those gates with AND. Test each missing requirement independently. The most revealing case often passes an impressive-looking gate while failing a quieter mandatory one.' },
        ],
        example: { title: 'Preapproval bypasses a missing receipt', text: 'An expense of 12,000 cents has preapproval but no receipt. An implementation using receipt OR preapproved accepts it, even though the policy requires both.',
          code: { label: 'Python · keep each policy gate independent', text: 'return (amount > 0\n        and (amount <= 2500 or receipt)\n        and (amount <= 10000 or preapproved))' },
          steps: ['Reject 12,000 without a receipt even when preapproval is true.', 'Reject 12,000 with a receipt but without preapproval.', 'Check 2,500 versus 2,501 and 10,000 versus 10,001 to verify the inclusive thresholds.'] },
        checkpoint: { question: 'A 12,000-cent expense has preapproval but no receipt. Under this exercise policy, what happens?', options: [
          { text: 'Approve it because preapproval overrides every other rule.', feedback: 'Preapproval is an additional requirement above the higher threshold; it does not replace the receipt.' },
          { text: 'Approve half of the amount.', feedback: 'Partial approval is not part of the specified policy.' },
          { text: 'Reject it because the receipt is independently required.', correct: true, feedback: 'Correct. Every mandatory gate in that amount band must pass.' },
        ] }, source: ruleSource,
      },
      {
        slug: 'business-calculation-order', title: 'Apply rules to the right intermediate value', minutes: 5,
        sections: [
          { title: 'Name the amount at each stage', text: 'Distinguish the original subtotal, discounted subtotal, shipping charge, and final total. When a rule refers to one of these values, use that exact stage. Reusing an earlier amount because it is already available is a common source of business-flow defects.' },
          { title: 'Cross a threshold with one operation', text: 'Choose an input where applying a discount changes eligibility. A cart far above or far below the free-shipping threshold may pass even with the wrong calculation order. Include equality to decide whether the threshold uses less-than or less-than-or-equal.' },
        ],
        example: { title: 'A discount removes free-shipping eligibility', text: 'Free shipping requires a discounted subtotal of at least 5,000 cents. A subtotal of 5,500 minus a discount of 1,000 leaves 4,500, so a 600-cent shipping fee applies and the total is 5,100.',
          steps: ['Compute the payable subtotal first: 5,500 - 1,000 = 4,500.', 'Compare 4,500 with 5,000, then add the 600 fee.', 'Check a discounted subtotal exactly equal to 5,000; it qualifies for free shipping under the stated rule.'] },
        checkpoint: { question: 'The free-shipping rule uses the subtotal after discounts. Which value should be compared with its threshold?', options: [
          { text: 'The discounted subtotal, before adding shipping.', correct: true, feedback: 'Correct. That is the policy’s eligibility base and avoids counting shipping toward its own exemption.' },
          { text: 'The original subtotal before discounts.', feedback: 'A discount may move the cart below the eligibility threshold.' },
          { text: 'The total after adding the shipping fee.', feedback: 'That makes the fee influence whether it should have been charged.' },
        ] }, source: ruleSource,
      },
    ],
  },
  {
    slug: 'business-workflows-and-retries', track: 'business', title: 'Repair business workflows safely', level: 'Intermediate',
    description: 'Follow an operation through allowed transitions, partial failure, and repeated delivery while preserving business state.',
    outcomes: ['Model allowed state transitions', 'Reject a workflow without partial changes', 'Make repeated actions affect state only once'],
    practice: [{ slug: 'shipment-transitions', title: 'A delivered order goes backwards' }, { slug: 'cart-reservation-atomicity', title: 'Half the cart is reserved after rejection' }, { slug: 'cancellation-restock-once', title: 'Cancelling twice creates extra stock' }],
    lessons: [
      {
        slug: 'allowed-transitions', title: 'Find an invalid state transition', minutes: 6,
        sections: [
          { title: 'Validate the pair, not just the destination', text: 'A status name can be valid while the transition to it is invalid. Draw the allowed arrows between states and identify terminal states. A delivered order must not become paid merely because paid appears in the list of known statuses.' },
          { title: 'Preserve state after ignored events', text: 'Evaluate each event against the current accepted state. If an event is invalid or a duplicate, keep that state unchanged before evaluating the next event. Track applied and ignored counts only after deciding whether the transition is permitted.' },
        ],
        example: { title: 'A delivered shipment goes backward', text: 'Allowed transitions include paid → shipped and shipped → delivered. From paid, process shipped, delivered, paid. The final event must be ignored and the final status must remain delivered.',
          code: { label: 'Python · explicit transition table', text: 'allowed = {\n    "created": {"paid", "cancelled"},\n    "paid": {"shipped", "cancelled"},\n    "shipped": {"delivered"},\n    "delivered": set(),\n    "cancelled": set(),\n}' },
          steps: ['Accept paid → shipped and shipped → delivered, counting two applied transitions.', 'Reject delivered → paid because delivered has no outgoing transitions.', 'Replay delivered and an unknown status; neither may change state or count as an applied transition.'] },
        checkpoint: { question: 'An event names a known status, but there is no allowed arrow from the current status to it. What should happen?', options: [
          { text: 'Accept it because the destination status is known.', feedback: 'Known states and allowed transitions are different checks.' },
          { text: 'Ignore it and preserve the current state.', correct: true, feedback: 'Correct. Validate the transition pair, then mutate only if that transition is allowed.' },
          { text: 'Reset the workflow to its initial state.', feedback: 'Resetting introduces a new side effect that the invalid-event policy does not authorize.' },
        ] }, source: { title: 'Azure Architecture Center: circuit breaker state transitions', url: 'https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker' },
      },
      {
        slug: 'atomic-workflows', title: 'Find partial changes after a rejected operation', minutes: 7,
        sections: [
          { title: 'Validate the whole request before committing', text: 'A cart can contain repeated product IDs and a failing line after a valid one. Aggregate requested quantities per product, verify every product and quantity, and only then apply the staged changes. Checking each line independently can oversell repeated products or leave a partially reserved cart.' },
          { title: 'Choose the actual atomic boundary', text: 'Staging works for the single-process exercise. A real shared database also needs a transaction and suitable concurrency control around the checks and changes. A database rollback cannot undo a completed external charge; cross-service effects need explicit coordination or compensation.' },
        ],
        example: { title: 'Two affordable lines become an unaffordable cart', text: 'Stock for A is 3. A cart asks for A twice, with quantity 2 on each line. Each line appears affordable against the original stock, but the combined request of 4 must be rejected.',
          steps: ['Aggregate the two lines into requested[A] = 4.', 'Compare the aggregate with stock[A] = 3 and reject before making any change.', 'Assert stock is still 3. Then test a cart with a valid first product and an unavailable second product to catch partial commits.'] },
        checkpoint: { question: 'The second cart line fails validation after the first line was deducted. What is broken?', options: [
          { text: 'Only the error message; the inventory may remain partly reserved.', feedback: 'The all-or-nothing contract requires rejection to preserve every stock value.' },
          { text: 'Nothing, if the response says the cart failed.', feedback: 'A correct response cannot compensate for a partially changed inventory.' },
          { text: 'The operation committed before validating the complete request.', correct: true, feedback: 'Correct. Stage and validate the entire change, then commit within an appropriate atomic boundary.' },
        ] }, source: transactionSource,
      },
      {
        slug: 'duplicate-business-actions', title: 'Find side effects that happen twice', minutes: 6,
        sections: [
          { title: 'Track intent and lifecycle together', text: 'A retry or duplicate event can arrive after an operation succeeded. Keep enough state to recognize the same intent and decide whether its transition is still allowed. An order existing in storage does not mean it is still cancellable.' },
          { title: 'Tie the effect to the accepted transition', text: 'Restore stock only when an order changes from reserved to cancelled. Record that new state together with the effect so a concurrent or later duplicate cannot restore stock again. Do not delete the history if the contract says an order ID remains consumed after cancellation.' },
        ],
        example: { title: 'Cancellation is delivered twice', text: 'Order A reserved two items. Its first cancellation restores two items and records cancelled. A second cancellation must follow the duplicate policy without repeating the restock effect.',
          steps: ['Check that A exists and its current state is reserved before accepting cancellation.', 'Apply the stock increase and reserved → cancelled transition together.', 'Replay cancellation and verify both the rejection response and unchanged stock. In a concurrent service, protect that transition atomically.'] },
        checkpoint: { question: 'Why keep a cancelled order record when the ID cannot be reused?', options: [
          { text: 'To recognize duplicate actions and retain the fact that the ID is consumed.', correct: true, feedback: 'Correct. Deleting the record can make a later duplicate or reservation look like a new operation.' },
          { text: 'So every repeated cancellation can restore stock again.', feedback: 'The effect belongs to the first accepted transition only.' },
          { text: 'Because merely storing the ID prevents all concurrent races.', feedback: 'The state transition and side effect still require atomic coordination under concurrency.' },
        ] }, source: { title: 'Amazon Builders’ Library: making retries safe with idempotent APIs', url: 'https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/' },
      },
    ],
  },
];
