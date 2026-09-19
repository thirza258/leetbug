"""Twenty business-policy and workflow exercises."""
from functools import partial

from .common import make

p = partial(make, "business")

PROBLEMS = [
    p("frozen-account-withdrawal", "A frozen account still spends", "A withdrawal endpoint checks available funds but ignores the account freeze.",
      "Input.balance is nonnegative, input.frozen is boolean, and input.amount is integer cents. Accept only an unfrozen account with 0 < amount <= balance. Return {ok, state: {balance}}, preserving balance on rejection.",
      '''
      def solve(data):
          ok = not data["frozen"] and 0 < data["amount"] <= data["balance"]
          return {"ok": ok, "state": {"balance": data["balance"] - data["amount"] if ok else data["balance"]}}
      ''', ('not data["frozen"] and ', ''),
      [({"balance": 10, "frozen": False, "amount": 4}, {"ok": True, "state": {"balance": 6}}), ({"balance": 10, "frozen": True, "amount": 4}, {"ok": False, "state": {"balance": 10}}), ({"balance": 0, "frozen": False, "amount": 1}, {"ok": False, "state": {"balance": 0}}), ({"balance": 5, "frozen": False, "amount": 0}, {"ok": False, "state": {"balance": 5}}), ({"balance": 5, "frozen": False, "amount": 5}, {"ok": True, "state": {"balance": 0}})],
      ["Which account-level condition applies before the amount check?", "Sufficient funds do not override a freeze.", "Combine the unfrozen gate with the positive-amount and sufficient-balance gates before deducting."], ["accounts", "policy-gates"]),
    p("cross-currency-transfer", "A transfer silently changes currency", "A wallet transfer treats balances in different currencies as interchangeable.",
      "Input.sender and recipient contain {balance: nonnegative integer, currency: string}; amount is integer minor units. Accept only positive affordable transfers between exactly equal currencies. Return {ok, state: {sender, recipient}} with numeric balances; reject without changes.",
      '''
      def solve(data):
          a, b, amount = data["sender"], data["recipient"], data["amount"]
          ok = a["currency"] == b["currency"] and 0 < amount <= a["balance"]
          return {"ok": ok, "state": {"sender": a["balance"] - amount if ok else a["balance"], "recipient": b["balance"] + amount if ok else b["balance"]}}
      ''', ('a["currency"] == b["currency"] and ', ''),
      [({"sender": {"balance": 8, "currency": "USD"}, "recipient": {"balance": 2, "currency": "USD"}, "amount": 3}, {"ok": True, "state": {"sender": 5, "recipient": 5}}), ({"sender": {"balance": 8, "currency": "USD"}, "recipient": {"balance": 2, "currency": "EUR"}, "amount": 3}, {"ok": False, "state": {"sender": 8, "recipient": 2}}), ({"sender": {"balance": 0, "currency": "X"}, "recipient": {"balance": 0, "currency": "X"}, "amount": 0}, {"ok": False, "state": {"sender": 0, "recipient": 0}}), ({"sender": {"balance": 1, "currency": "X"}, "recipient": {"balance": 1, "currency": "X"}, "amount": 2}, {"ok": False, "state": {"sender": 1, "recipient": 1}}), ({"sender": {"balance": 2, "currency": "X"}, "recipient": {"balance": 0, "currency": "X"}, "amount": 2}, {"ok": True, "state": {"sender": 0, "recipient": 2}})],
      ["Are the two balances expressed in the same unit?", "This workflow has no currency conversion contract.", "Require equal currency codes before performing the paired debit and credit."], ["transfers", "units"]),
    p("invoice-partial-status", "A partial payment marks the invoice paid", "An invoice status changes to paid after any positive payment.",
      "Input.total is positive integer cents; input.payments contains nonnegative integer cents whose sum is at most total. Return {paid: sum, outstanding: total-sum, status: 'unpaid'|'partial'|'paid'}.",
      '''
      def solve(data):
          paid = sum(data["payments"])
          status = "paid" if paid == data["total"] else "partial" if paid > 0 else "unpaid"
          return {"paid": paid, "outstanding": data["total"] - paid, "status": status}
      ''', ('paid == data["total"]', 'paid > 0'),
      [({"total": 10, "payments": []}, {"paid": 0, "outstanding": 10, "status": "unpaid"}), ({"total": 10, "payments": [4]}, {"paid": 4, "outstanding": 6, "status": "partial"}), ({"total": 10, "payments": [4, 6]}, {"paid": 10, "outstanding": 0, "status": "paid"}), ({"total": 1, "payments": [0]}, {"paid": 0, "outstanding": 1, "status": "unpaid"}), ({"total": 9, "payments": [3, 3]}, {"paid": 6, "outstanding": 3, "status": "partial"})],
      ["What amount actually closes the invoice?", "A positive payment can still leave an outstanding balance.", "Use equality with the invoice total for paid, positive smaller amounts for partial, and zero for unpaid."], ["invoices", "state"], "easy"),
    p("percentage-discount-cap", "The percentage promotion ignores its cap", "A promotion computes a percentage discount but forgets its advertised maximum.",
      "Input.subtotal and cap are nonnegative integer cents; percent is 0 through 100. Discount is floor(subtotal*percent/100), capped at cap. Return {discount,total}.",
      '''
      def solve(data):
          discount = min(data["cap"], data["subtotal"] * data["percent"] // 100)
          return {"discount": discount, "total": data["subtotal"] - discount}
      ''', ('min(data["cap"], data["subtotal"] * data["percent"] // 100)', 'data["subtotal"] * data["percent"] // 100'),
      [({"subtotal": 100, "percent": 10, "cap": 20}, {"discount": 10, "total": 90}), ({"subtotal": 1000, "percent": 50, "cap": 100}, {"discount": 100, "total": 900}), ({"subtotal": 0, "percent": 50, "cap": 10}, {"discount": 0, "total": 0}), ({"subtotal": 99, "percent": 10, "cap": 50}, {"discount": 9, "total": 90}), ({"subtotal": 10, "percent": 100, "cap": 0}, {"discount": 0, "total": 10})],
      ["Which limit applies after the percentage calculation?", "The promotion promises the smaller of the computed discount and the cap.", "Apply min(cap, subtotal*percent//100) before subtracting the discount."], ["promotions", "pricing"], "easy"),
    p("per-line-tax-rounding", "Tax is rounded at the wrong stage", "An invoice rounds combined tax even though its exercise policy rounds each line separately.",
      "Input.lines contains nonnegative integer line totals in cents; rate_bps is 0 through 10000. Tax each line at rate_bps/10000, round half up to cents independently, then sum. Return integer total tax.",
      '''
      def solve(data):
          return sum((line * data["rate_bps"] + 5000) // 10000 for line in data["lines"])
      ''', ('sum((line * data["rate_bps"] + 5000) // 10000 for line in data["lines"])', '(sum(data["lines"]) * data["rate_bps"] + 5000) // 10000'),
      [({"lines": [100], "rate_bps": 1000}, 10), ({"lines": [5, 5], "rate_bps": 1000}, 2), ({"lines": [], "rate_bps": 1000}, 0), ({"lines": [4, 4], "rate_bps": 1000}, 0), ({"lines": [1, 2], "rate_bps": 10000}, 3)],
      ["Does this policy round before or after aggregation?", "Rounding and addition are not interchangeable operations.", "Apply integer half-up rounding to each line tax before summing."], ["billing", "rounding"]),
    p("shipping-started-blocks", "The last weight block ships for free", "A shipping quote charges only complete weight blocks, omitting a partially used block.",
      "Input.weight is nonnegative integer grams, block is positive grams, and fee is nonnegative cents per started block. Return the shipping charge; zero weight costs zero.",
      '''
      def solve(data):
          blocks = (data["weight"] + data["block"] - 1) // data["block"]
          return blocks * data["fee"]
      ''', ('(data["weight"] + data["block"] - 1)', 'data["weight"]'),
      [({"weight": 1000, "block": 500, "fee": 3}, 6), ({"weight": 501, "block": 500, "fee": 3}, 6), ({"weight": 0, "block": 500, "fee": 3}, 0), ({"weight": 1, "block": 500, "fee": 3}, 3), ({"weight": 9, "block": 2, "fee": 0}, 0)],
      ["Is a partially used block billable?", "The stated policy bills started blocks, so it needs ceiling division.", "Compute (weight+block-1)//block using integer arithmetic before multiplying by the fee."], ["shipping", "integer-arithmetic"], "easy"),
    p("prorated-unused-days", "Cancellation refunds already used days", "A subscription cancellation computes its refund from elapsed days instead of remaining days.",
      "Input.price is nonnegative cents, days is positive, and used is from 0 through days. Refund floor(price*(days-used)/days). Return integer cents.",
      '''
      def solve(data):
          return data["price"] * (data["days"] - data["used"]) // data["days"]
      ''', ('(data["days"] - data["used"])', 'data["used"]'),
      [({"price": 100, "days": 10, "used": 5}, 50), ({"price": 100, "days": 10, "used": 2}, 80), ({"price": 99, "days": 3, "used": 0}, 99), ({"price": 99, "days": 3, "used": 3}, 0), ({"price": 10, "days": 3, "used": 1}, 6)],
      ["Which days is the customer being refunded for?", "Consumed service is excluded from this exercise's refund basis.", "Multiply the price by days-used, then divide once using the specified floor rule."], ["subscriptions", "proration"]),
    p("minimum-order-eligibility", "The service fee qualifies a small order", "A delivery checkout includes its service fee when checking the minimum merchandise amount.",
      "Input.subtotal, discount, minimum, fee are nonnegative cents; discount <= subtotal. Accept when subtotal-discount >= minimum. Return {ok,total}, with total including fee only on acceptance and null on rejection.",
      '''
      def solve(data):
          merchandise = data["subtotal"] - data["discount"]
          ok = merchandise >= data["minimum"]
          return {"ok": ok, "total": merchandise + data["fee"] if ok else None}
      ''', ('ok = merchandise >=', 'ok = merchandise + data["fee"] >='),
      [({"subtotal": 100, "discount": 0, "minimum": 100, "fee": 10}, {"ok": True, "total": 110}), ({"subtotal": 90, "discount": 0, "minimum": 100, "fee": 20}, {"ok": False, "total": None}), ({"subtotal": 100, "discount": 1, "minimum": 100, "fee": 0}, {"ok": False, "total": None}), ({"subtotal": 0, "discount": 0, "minimum": 0, "fee": 5}, {"ok": True, "total": 5}), ({"subtotal": 200, "discount": 100, "minimum": 100, "fee": 0}, {"ok": True, "total": 100})],
      ["Which part of the checkout counts toward the minimum?", "The service fee does not increase eligible merchandise value.", "Evaluate the minimum on discounted merchandise before adding the fee."], ["checkout", "eligibility"]),
    p("seat-release-ownership", "One member releases another member's seat", "A seat-release endpoint checks occupancy without checking the current owner.",
      "Input.seats maps seat IDs to owner IDs; events contains {seat,user}. A release succeeds only when that user owns the seat. Return {accepted: booleans, state: {seats: remaining map}}.",
      '''
      def solve(data):
          seats = dict(data["seats"])
          accepted = []
          for event in data["events"]:
              ok = event["seat"] in seats and seats[event["seat"]] == event["user"]
              accepted.append(ok)
              if ok:
                  del seats[event["seat"]]
          return {"accepted": accepted, "state": {"seats": seats}}
      ''', (' and seats[event["seat"]] == event["user"]', ''),
      [({"seats": {"a": "u"}, "events": [{"seat": "a", "user": "u"}]}, {"accepted": [True], "state": {"seats": {}}}), ({"seats": {"a": "u"}, "events": [{"seat": "a", "user": "v"}]}, {"accepted": [False], "state": {"seats": {"a": "u"}}}), ({"seats": {}, "events": [{"seat": "a", "user": "u"}]}, {"accepted": [False], "state": {"seats": {}}}), ({"seats": {"a": ""}, "events": [{"seat": "a", "user": ""}, {"seat": "a", "user": ""}]}, {"accepted": [True, False], "state": {"seats": {}}}), ({"seats": {"a": "u"}, "events": []}, {"accepted": [], "state": {"seats": {"a": "u"}}})],
      ["Does occupancy establish permission to release?", "The resource owner must match the acting user at the time of release.", "Require both presence and owner equality before deleting the seat assignment."], ["ownership", "reservations"]),
    p("rejected-expense-budget", "A rejected expense consumes its budget", "An expense allocator subtracts requested amounts before deciding whether they fit.",
      "Input.budget is nonnegative cents; amounts is an ordered list of integer requests. Accept only positive amounts no larger than remaining budget, deducting only accepted requests. Return {accepted, state: {remaining}}.",
      '''
      def solve(data):
          remaining = data["budget"]
          accepted = []
          for amount in data["amounts"]:
              ok = 0 < amount <= remaining
              accepted.append(ok)
              if ok:
                  remaining -= amount
          return {"accepted": accepted, "state": {"remaining": remaining}}
      ''', ('if ok:\n            remaining -= amount', 'if amount > 0:\n            remaining -= amount'),
      [({"budget": 10, "amounts": [3]}, {"accepted": [True], "state": {"remaining": 7}}), ({"budget": 10, "amounts": [11, 5]}, {"accepted": [False, True], "state": {"remaining": 5}}), ({"budget": 0, "amounts": [0]}, {"accepted": [False], "state": {"remaining": 0}}), ({"budget": 5, "amounts": [-2, 5]}, {"accepted": [False, True], "state": {"remaining": 0}}), ({"budget": 8, "amounts": []}, {"accepted": [], "state": {"remaining": 8}})],
      ["What state must remain unchanged on rejection?", "An unaffordable request cannot spend any budget or block later affordable work.", "Move the deduction inside the same successful validation branch that records acceptance."], ["budgets", "atomicity"]),
    p("coupon-customer-limit", "One customer's coupon use blocks everyone", "A promotion uses one global redemption counter for a per-customer limit.",
      "Input.limit is nonnegative; users is an ordered list of user-ID strings requesting redemption. Each user may redeem at most limit times. Return {accepted, state: {uses}}; uses contains only users with successful redemptions.",
      '''
      def solve(data):
          uses, accepted = {}, []
          for user in data["users"]:
              used = uses.get(user, 0)
              ok = used < data["limit"]
              accepted.append(ok)
              if ok:
                  uses[user] = used + 1
          return {"accepted": accepted, "state": {"uses": uses}}
      ''', ('used = uses.get(user, 0)', 'used = sum(uses.values())'),
      [({"limit": 1, "users": ["a", "a"]}, {"accepted": [True, False], "state": {"uses": {"a": 1}}}), ({"limit": 1, "users": ["a", "b"]}, {"accepted": [True, True], "state": {"uses": {"a": 1, "b": 1}}}), ({"limit": 0, "users": ["a"]}, {"accepted": [False], "state": {"uses": {}}}), ({"limit": 2, "users": ["a", "b", "a"]}, {"accepted": [True, True, True], "state": {"uses": {"a": 2, "b": 1}}}), ({"limit": 1, "users": []}, {"accepted": [], "state": {"uses": {}}})],
      ["What is the scope of the redemption limit?", "A per-customer policy needs state keyed by customer identity.", "Read and increment only the current user's successful-use count."], ["promotions", "scoping"]),
    p("returned-goods-restock", "Damaged returns reappear as sellable stock", "A return processor adds every accepted return to inventory, including damaged units.",
      "Input.stock is nonnegative. Input.returns contains {quantity: positive integer, sellable: boolean}; all returns are accepted. Return {refunded_units: sum of all quantities, state: {stock: initial plus sellable quantities only}}.",
      '''
      def solve(data):
          stock, refunded = data["stock"], 0
          for item in data["returns"]:
              refunded += item["quantity"]
              if item["sellable"]:
                  stock += item["quantity"]
          return {"refunded_units": refunded, "state": {"stock": stock}}
      ''', ('if item["sellable"]:', 'if True:'),
      [({"stock": 2, "returns": [{"quantity": 1, "sellable": True}]}, {"refunded_units": 1, "state": {"stock": 3}}), ({"stock": 2, "returns": [{"quantity": 1, "sellable": False}]}, {"refunded_units": 1, "state": {"stock": 2}}), ({"stock": 0, "returns": []}, {"refunded_units": 0, "state": {"stock": 0}}), ({"stock": 1, "returns": [{"quantity": 2, "sellable": False}, {"quantity": 3, "sellable": True}]}, {"refunded_units": 5, "state": {"stock": 4}}), ({"stock": 0, "returns": [{"quantity": 2, "sellable": False}]}, {"refunded_units": 2, "state": {"stock": 0}})],
      ["Do refund eligibility and inventory eligibility mean the same thing?", "A damaged return can be refunded without becoming sellable inventory.", "Count every return toward refunded units, but restock only sellable quantities."], ["returns", "inventory"]),
    p("loyalty-redemption-blocks", "A partial reward block is redeemed", "A reward endpoint accepts arbitrary point amounts even though rewards come in fixed blocks.",
      "Input.points is nonnegative, block is positive, requested is integer. Accept only a positive affordable requested amount divisible by block. Return {ok, state: {points}}; rejection leaves points unchanged.",
      '''
      def solve(data):
          ok = 0 < data["requested"] <= data["points"] and data["requested"] % data["block"] == 0
          return {"ok": ok, "state": {"points": data["points"] - data["requested"] if ok else data["points"]}}
      ''', (' and data["requested"] % data["block"] == 0', ''),
      [({"points": 100, "block": 20, "requested": 40}, {"ok": True, "state": {"points": 60}}), ({"points": 100, "block": 20, "requested": 30}, {"ok": False, "state": {"points": 100}}), ({"points": 10, "block": 20, "requested": 20}, {"ok": False, "state": {"points": 10}}), ({"points": 0, "block": 1, "requested": 0}, {"ok": False, "state": {"points": 0}}), ({"points": 20, "block": 20, "requested": 20}, {"ok": True, "state": {"points": 0}})],
      ["Is affordability the only redemption rule?", "The requested points must represent a whole number of reward blocks.", "Combine the positive affordable amount gate with requested % block == 0."], ["loyalty", "validation"]),
    p("credit-note-balance", "Credit notes exceed the unpaid invoice", "A credit-note service checks each note against the original invoice instead of its remaining unpaid amount.",
      "Input.outstanding is nonnegative; credits is an ordered list of integers. Accept positive credits no larger than current outstanding, reducing it on success. Return {accepted, state: {outstanding}}.",
      '''
      def solve(data):
          remaining = data["outstanding"]
          accepted = []
          for credit in data["credits"]:
              ok = 0 < credit <= remaining
              accepted.append(ok)
              if ok:
                  remaining -= credit
          return {"accepted": accepted, "state": {"outstanding": remaining}}
      ''', ('credit <= remaining', 'credit <= data["outstanding"]'),
      [({"outstanding": 10, "credits": [4]}, {"accepted": [True], "state": {"outstanding": 6}}), ({"outstanding": 10, "credits": [6, 6]}, {"accepted": [True, False], "state": {"outstanding": 4}}), ({"outstanding": 0, "credits": [1]}, {"accepted": [False], "state": {"outstanding": 0}}), ({"outstanding": 5, "credits": [0, -1, 5]}, {"accepted": [False, False, True], "state": {"outstanding": 0}}), ({"outstanding": 8, "credits": []}, {"accepted": [], "state": {"outstanding": 8}})],
      ["Which balance changes after an accepted credit?", "Later notes must be checked against the remaining unpaid amount.", "Validate each positive credit against current remaining state before deducting it."], ["invoices", "credits"]),
    p("transfer-daily-allowance", "Each transfer gets the whole daily allowance", "A daily limit is enforced per request, allowing a sequence to exceed the day's total.",
      "Input.limit is nonnegative; amounts lists integer transfers for one day. Accept positive amounts when accepted total plus amount <= limit. Return {accepted, state: {used}}; rejected amounts do not consume allowance.",
      '''
      def solve(data):
          used, accepted = 0, []
          for amount in data["amounts"]:
              ok = amount > 0 and used + amount <= data["limit"]
              accepted.append(ok)
              if ok:
                  used += amount
          return {"accepted": accepted, "state": {"used": used}}
      ''', ('used + amount <=', 'amount <='),
      [({"limit": 10, "amounts": [5]}, {"accepted": [True], "state": {"used": 5}}), ({"limit": 10, "amounts": [6, 6, 4]}, {"accepted": [True, False, True], "state": {"used": 10}}), ({"limit": 0, "amounts": [1]}, {"accepted": [False], "state": {"used": 0}}), ({"limit": 5, "amounts": [-1, 0, 5]}, {"accepted": [False, False, True], "state": {"used": 5}}), ({"limit": 5, "amounts": []}, {"accepted": [], "state": {"used": 0}})],
      ["Is the limit per transfer or per day?", "The total of accepted transfers must remain within the allowance.", "Include used in the affordability check and update it only after acceptance."], ["limits", "cumulative-state"]),
    p("booking-cleanup-buffer", "Bookings overlap the cleanup period", "A room scheduler ignores required cleaning time after each meeting.",
      "Input.existing contains nonoverlapping [start,end] meetings with start < end; candidate is another such pair; buffer is nonnegative. Every meeting occupies [start,end+buffer). Return whether the candidate's occupied interval avoids every existing occupied interval.",
      '''
      def solve(data):
          start, end = data["candidate"]
          buffer = data["buffer"]
          return all(end + buffer <= a or start >= b + buffer for a, b in data["existing"])
      ''', ('start >= b + buffer', 'start >= b'),
      [({"existing": [[0, 5]], "candidate": [7, 9], "buffer": 2}, True), ({"existing": [[0, 5]], "candidate": [6, 9], "buffer": 2}, False), ({"existing": [], "candidate": [0, 1], "buffer": 4}, True), ({"existing": [[5, 8]], "candidate": [0, 4], "buffer": 2}, False), ({"existing": [[0, 5]], "candidate": [5, 8], "buffer": 0}, True)],
      ["When does the room become available after a meeting?", "The occupied interval includes cleanup, and this applies to both existing and proposed meetings.", "Use end+buffer for each meeting and allow exact nonoverlap at that occupied endpoint."], ["scheduling", "intervals"]),
    p("approval-author-exclusion", "The author approves their own release", "A release gate counts a submitter's own vote toward independent review.",
      "Input.author is a string, eligible is a list of reviewer IDs, votes is a list of reviewer IDs, and required is a positive integer. Return true if at least required distinct eligible non-author reviewers voted.",
      '''
      def solve(data):
          reviewers = set(data["votes"]) & set(data["eligible"])
          reviewers.discard(data["author"])
          return len(reviewers) >= data["required"]
      ''', ('reviewers.discard(data["author"])', 'reviewers.discard(None)'),
      [({"author": "a", "eligible": ["b"], "votes": ["b"], "required": 1}, True), ({"author": "a", "eligible": ["a", "b"], "votes": ["a"], "required": 1}, False), ({"author": "a", "eligible": ["b"], "votes": ["b", "b"], "required": 2}, False), ({"author": "a", "eligible": [], "votes": ["x"], "required": 1}, False), ({"author": "a", "eligible": ["b", "c"], "votes": ["b", "c"], "required": 2}, True)],
      ["Who is allowed to provide independent approval?", "Eligibility and distinctness still do not allow the author to approve their own work.", "Intersect votes with eligible reviewers, remove the author, then compare the distinct count."], ["approvals", "separation-of-duties"]),
    p("task-prerequisite-gates", "A task finishes with only one prerequisite", "A workflow accepts completion as soon as any prerequisite is done.",
      "Input.dependencies maps task IDs to lists of prerequisite IDs, all present as keys. Events lists task IDs attempting completion. A known unfinished task succeeds only when all its prerequisites are already completed. Return {accepted, state: {completed: sorted IDs}}; cycles remain blocked.",
      '''
      def solve(data):
          completed, accepted = set(), []
          dependencies = data["dependencies"]
          for task in data["events"]:
              ok = task in dependencies and task not in completed and all(item in completed for item in dependencies[task])
              accepted.append(ok)
              if ok:
                  completed.add(task)
          return {"accepted": accepted, "state": {"completed": sorted(completed)}}
      ''', ('all(item in completed for item in dependencies[task])', '(not dependencies[task] or any(item in completed for item in dependencies[task]))'),
      [({"dependencies": {"a": []}, "events": ["a"]}, {"accepted": [True], "state": {"completed": ["a"]}}), ({"dependencies": {"a": [], "b": [], "c": ["a", "b"]}, "events": ["a", "c"]}, {"accepted": [True, False], "state": {"completed": ["a"]}}), ({"dependencies": {"a": []}, "events": ["x", "a", "a"]}, {"accepted": [False, True, False], "state": {"completed": ["a"]}}), ({"dependencies": {"a": ["a"]}, "events": ["a"]}, {"accepted": [False], "state": {"completed": []}}), ({"dependencies": {}, "events": []}, {"accepted": [], "state": {"completed": []}})],
      ["Does one completed prerequisite satisfy every dependency?", "Each dependency is a mandatory gate and empty prerequisite lists are ready immediately.", "Require all prerequisite IDs in the completed set before recording a new completion."], ["workflows", "dependencies"], "hard"),
    p("overdue-open-invoices", "A paid invoice is marked overdue", "A collection report uses the due date without checking whether any amount remains unpaid.",
      "Input.now is an integer day; invoices contains {id: string, due: integer day, outstanding: nonnegative cents}. Return IDs in input order only when outstanding > 0 and due < now. An invoice due today is not overdue.",
      '''
      def solve(data):
          return [item["id"] for item in data["invoices"] if item["outstanding"] > 0 and item["due"] < data["now"]]
      ''', ('item["outstanding"] > 0 and ', ''),
      [({"now": 5, "invoices": [{"id": "a", "due": 4, "outstanding": 1}]}, ["a"]), ({"now": 5, "invoices": [{"id": "a", "due": 4, "outstanding": 0}]}, []), ({"now": 5, "invoices": [{"id": "a", "due": 5, "outstanding": 1}]}, []), ({"now": 0, "invoices": []}, []), ({"now": 5, "invoices": [{"id": "b", "due": 1, "outstanding": 2}, {"id": "a", "due": 2, "outstanding": 3}]}, ["b", "a"])],
      ["Can a fully paid invoice still require collection?", "Overdue status needs both an expired due date and a positive open balance.", "Filter by outstanding > 0 as well as due < now, preserving input order."], ["invoices", "reporting"], "easy"),
    p("account-closure-pending", "An account closes with unfinished transfers", "An account closure checks its balance while forgetting pending work.",
      "Input.balance and pending are nonnegative integers; closed is boolean. Close only an open account with zero balance and zero pending transfers. Return {ok, state: {closed}}. Repeated closure is rejected.",
      '''
      def solve(data):
          ok = not data["closed"] and data["balance"] == 0 and data["pending"] == 0
          return {"ok": ok, "state": {"closed": data["closed"] or ok}}
      ''', (' and data["pending"] == 0', ''),
      [({"balance": 0, "pending": 0, "closed": False}, {"ok": True, "state": {"closed": True}}), ({"balance": 0, "pending": 1, "closed": False}, {"ok": False, "state": {"closed": False}}), ({"balance": 1, "pending": 0, "closed": False}, {"ok": False, "state": {"closed": False}}), ({"balance": 0, "pending": 0, "closed": True}, {"ok": False, "state": {"closed": True}}), ({"balance": 1, "pending": 1, "closed": False}, {"ok": False, "state": {"closed": False}})],
      ["What obligations can exist beyond the displayed balance?", "Pending transfers are unfinished work even when the current balance is zero.", "Require zero pending transfers along with zero balance and an open account before closing."], ["accounts", "lifecycle"]),
]
