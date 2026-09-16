"""Versioned, executable case studies. Test oracles never enter the sandbox.

Append new problems: catalog order determines stable seeded database IDs.
"""
from textwrap import dedent


def code(source: str) -> str:
    return dedent(source).strip() + "\n"


def case(name, data, expected, hidden=False, assertions=None):
    return {"name": name, "input": data, "expected": expected, "hidden": hidden,
            "assertions": assertions or []}


def problem(slug, title, summary, category, difficulty, tags, requirements, starters, solutions,
            tests, explanation, hints, minutes=15):
    return dict(slug=slug, title=title, summary=summary, description=summary,
                category=category, difficulty=difficulty, tags=tags, requirements=requirements,
                starters={k: code(v) for k, v in starters.items()},
                solutions={k: code(v) for k, v in solutions.items()}, tests=tests,
                explanation=explanation, hints=hints, estimated_minutes=minutes)


CATALOG = [
    problem(
        "checkout-underflow", "The checkout that pays you back",
        "A flash-sale coupon is turning shopping carts into payouts. Customers can apply a discount larger than their subtotal, and the checkout service happily returns a negative charge. Repair the pricing rule without changing the receipt format.",
        "business", "medium", ["validation", "e-commerce", "invariants"],
        ["Input contains item prices in integer cents and a discount in cents.",
         "Ignore negative item prices. Treat a negative discount as zero.",
         "Return {total: cents}. The final total must never be negative."],
        {"python": '''
            def solve(data):
                subtotal = sum(data["prices"])
                return {"total": subtotal - data["discount"]}
        ''', "javascript": '''
            function solve(data) {
              const subtotal = data.prices.reduce((sum, price) => sum + price, 0);
              return { total: subtotal - data.discount };
            }
            module.exports = { solve };
        '''},
        {"python": '''
            def solve(data):
                subtotal = sum(max(0, price) for price in data["prices"])
                return {"total": max(0, subtotal - max(0, data["discount"]))}
        ''', "javascript": '''
            function solve(data) {
              const subtotal = data.prices.reduce((sum, price) => sum + Math.max(0, price), 0);
              return { total: Math.max(0, subtotal - Math.max(0, data.discount)) };
            }
            module.exports = { solve };
        '''},
        [case("A regular order", {"prices": [2500, 1500], "discount": 500}, {"total": 3500}),
         case("Discount exceeds subtotal", {"prices": [1200], "discount": 2000}, {"total": 0}),
         case("Empty cart", {"prices": [], "discount": 500}, {"total": 0}, True),
         case("Invalid price and discount", {"prices": [-500, 1500], "discount": -200}, {"total": 1500}, True)],
        "Validate prices and the discount independently, then clamp the final charge to zero. Clamping only the final result misses negative discounts, which would otherwise increase a customer's bill. Time O(n), extra space O(1).",
        ["Which values are allowed to cross the zero boundary? Check both the inputs and the result.",
         "A negative discount behaves like an added charge. Normalize it before calculating the total.",
         "Sum nonnegative prices, subtract a nonnegative discount, and clamp the total to zero."], 12,
    ),
    problem(
        "missing-last-item", "One item short",
        "The nightly metrics job sums a list of event counts. The dashboard always seems a little low: one event bucket disappears during aggregation. Find the boundary error and make the job work for lists of any length.",
        "logic", "easy", ["arrays", "off-by-one", "iteration"],
        ["Return the sum of every number in input.nums.", "An empty list must return 0.",
         "Numbers are integers between -1,000 and 1,000; at most 1,000 entries."],
        {"python": '''
            def solve(data):
                total = 0
                for i in range(len(data["nums"]) - 1):
                    total += data["nums"][i]
                return total
        ''', "javascript": '''
            function solve(data) {
              let total = 0;
              for (let i = 0; i < data.nums.length - 1; i++) total += data.nums[i];
              return total;
            }
            module.exports = { solve };
        ''', "java": '''
            import com.google.gson.*;
            public class Solution {
              public static JsonElement solve(JsonObject data) {
                JsonArray nums = data.getAsJsonArray("nums");
                int total = 0;
                for (int i = 0; i < nums.size() - 1; i++) total += nums.get(i).getAsInt();
                return new JsonPrimitive(total);
              }
            }
        ''', "cpp": '''
            #include <nlohmann/json.hpp>
            using nlohmann::json;
            json solve(const json& data) {
              const auto& nums = data.at("nums");
              int total = 0;
              for (int i = 0; i < static_cast<int>(nums.size()) - 1; i++) total += nums[i].get<int>();
              return total;
            }
        ''', "go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                nums := data["nums"].([]interface{})
                total := 0
                for i := 0; i < len(nums)-1; i++ { total += int(nums[i].(float64)) }
                return total
            }
        '''},
        {"python": 'def solve(data):\n    return sum(data["nums"])',
         "javascript": 'function solve(data) { return data.nums.reduce((a, b) => a + b, 0); }\nmodule.exports = { solve };',
         "java": '''
            import com.google.gson.*;
            public class Solution {
              public static JsonElement solve(JsonObject data) {
                int total = 0;
                for (JsonElement n : data.getAsJsonArray("nums")) total += n.getAsInt();
                return new JsonPrimitive(total);
              }
            }
         ''', "cpp": '''
            #include <nlohmann/json.hpp>
            using nlohmann::json;
            json solve(const json& data) {
              int total = 0;
              for (const auto& n : data.at("nums")) total += n.get<int>();
              return total;
            }
         ''', "go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                total := 0
                for _, n := range data["nums"].([]interface{}) { total += int(n.(float64)) }
                return total
            }
         '''},
        [case("Three buckets", {"nums": [2, 4, 6]}, 12), case("One bucket", {"nums": [7]}, 7),
         case("No events", {"nums": []}, 0, True), case("Negative adjustments", {"nums": [-5, 3, -8, 2]}, -8, True)],
        "The upper bound is exclusive. Stopping at length minus one skips the final element. Iterating over the values directly removes the index boundary altogether. Time O(n), space O(1).",
        ["Trace the loop for a one-element list.", "Does the loop ever visit the final valid index?",
         "Visit each value directly or use an exclusive bound equal to the list length."], 8,
    ),
    problem(
        "empty-average", "No data, big problem",
        "An analytics endpoint crashes when a new workspace has no samples. Existing workspaces should keep their average, while an empty workspace needs a meaningful default.",
        "runtime", "easy", ["division", "empty-input", "analytics"],
        ["Return the arithmetic mean of input.values.", "Return 0 when there are no values.",
         "Inputs are finite numbers; preserve fractional results."],
        {"python": 'def solve(data):\n    values = data["values"]\n    return sum(values) / len(values)',
         "javascript": 'function solve(data) { return data.values.reduce((a, b) => a + b, 0) / data.values.length; }\nmodule.exports = { solve };'},
        {"python": 'def solve(data):\n    values = data["values"]\n    return sum(values) / len(values) if values else 0',
         "javascript": 'function solve(data) { return data.values.length ? data.values.reduce((a, b) => a + b, 0) / data.values.length : 0; }\nmodule.exports = { solve };'},
        [case("Existing workspace", {"values": [2, 4, 9]}, 5), case("New workspace", {"values": []}, 0),
         case("Fractional average", {"values": [1, 2]}, 1.5, True), case("Negative samples", {"values": [-4, 0]}, -2, True)],
        "Guard the empty collection before dividing. Do not round the result or substitute the number of nonzero samples for the count. Time O(n), space O(1).",
        ["What is the denominator for an empty list?", "Check the input before performing division.",
         "Return the defined empty result early; otherwise preserve the ordinary mean calculation."], 8,
    ),
    problem(
        "wallet-rollback", "The transfer that never arrived",
        "A wallet service deducts funds before contacting its payment gateway. When the gateway fails, the customer loses money and the recipient receives nothing. Restore transaction semantics in this in-memory model.",
        "business", "hard", ["transactions", "rollback", "state"],
        ["Input has state.sender, state.recipient, an amount, and gateway_fails.",
         "Return {ok: boolean, state: {sender: cents, recipient: cents}}.",
         "Reject nonpositive amounts or insufficient funds without changing either balance.",
         "A gateway failure must leave both balances unchanged. A successful transfer must conserve total funds."],
        {"python": '''
            def solve(data):
                state = data["state"].copy()
                state["sender"] -= data["amount"]
                if data["gateway_fails"]:
                    return {"ok": False, "state": state}
                state["recipient"] += data["amount"]
                return {"ok": True, "state": state}
        '''},
        {"python": '''
            def solve(data):
                state = data["state"].copy()
                amount = data["amount"]
                if amount <= 0 or amount > state["sender"] or data["gateway_fails"]:
                    return {"ok": False, "state": state}
                state["sender"] -= amount
                state["recipient"] += amount
                return {"ok": True, "state": state}
        '''},
        [case("Successful transfer", {"state": {"sender": 100, "recipient": 20}, "amount": 40, "gateway_fails": False},
              {"ok": True, "state": {"sender": 60, "recipient": 60}}, assertions=[{"path": "state.sender", "equals": 60}]),
         case("Gateway rollback", {"state": {"sender": 100, "recipient": 20}, "amount": 40, "gateway_fails": True},
              {"ok": False, "state": {"sender": 100, "recipient": 20}}, assertions=[{"path": "state.sender", "equals": 100}, {"path": "state.recipient", "equals": 20}]),
         case("Insufficient funds", {"state": {"sender": 30, "recipient": 10}, "amount": 50, "gateway_fails": False},
              {"ok": False, "state": {"sender": 30, "recipient": 10}}, True, [{"path": "state.sender", "equals": 30}]),
         case("Invalid amount", {"state": {"sender": 30, "recipient": 10}, "amount": -5, "gateway_fails": False},
              {"ok": False, "state": {"sender": 30, "recipient": 10}}, True)],
        "Validate every precondition before committing the new state. This mock can stage changes and commit only after gateway success. A real database-backed service needs a transaction plus a suitable distributed payment strategy; a database rollback cannot undo an already-completed external payment. Time and space O(1).",
        ["What changes before the gateway can fail? Inspect the failed transaction's state.",
         "A failed operation should be observationally equivalent to no operation.",
         "Validate the amount, available funds, and gateway outcome before committing both balance changes."], 25,
    ),
    problem(
        "role-confusion", "Everyone is an administrator",
        "An internal admin action is visible only to administrators, but the API authorization check lets ordinary users through. The interface is hiding the symptom; fix the rule at the service boundary.",
        "business", "medium", ["authorization", "rbac", "conditionals"],
        ["Return true only when role is exactly 'admin' and active is true.",
         "Missing fields, unknown roles, and inactive accounts must be denied."],
        {"python": 'def solve(data):\n    return data.get("role") == "admin" or data.get("active", False)',
         "javascript": 'function solve(data) { return data.role === "admin" || data.active === true; }\nmodule.exports = { solve };'},
        {"python": 'def solve(data):\n    return data.get("role") == "admin" and data.get("active") is True',
         "javascript": 'function solve(data) { return data.role === "admin" && data.active === true; }\nmodule.exports = { solve };'},
        [case("Active admin", {"role": "admin", "active": True}, True),
         case("Active member", {"role": "member", "active": True}, False),
         case("Disabled admin", {"role": "admin", "active": False}, False, True),
         case("Missing identity", {}, False, True), case("String is not a boolean", {"role": "admin", "active": "true"}, False, True)],
        "Authorization requires both the correct role and an active account. Use an AND condition and strict boolean validation. Missing identity must fail closed. Time and space O(1).",
        ["List the two independent requirements for access.", "An active non-admin satisfies one branch of the current expression.",
         "Require both predicates and check that active is a boolean true."], 12,
    ),
    problem(
        "ordered-dedup", "A duplicate at the door",
        "An ingestion service removes repeated event identifiers while preserving the order in which they first arrived. Its sentinel value quietly drops a legitimate event ID.",
        "edge", "easy", ["sets", "sentinels", "ordering"],
        ["Return each integer from input.ids only once, preserving first-seen order.",
         "Zero and negative IDs are valid. An empty input returns an empty list."],
        {"python": '''
            def solve(data):
                seen = {0}
                result = []
                for item in data["ids"]:
                    if item not in seen:
                        seen.add(item)
                        result.append(item)
                return result
        '''},
        {"python": 'def solve(data):\n    return list(dict.fromkeys(data["ids"]))'},
        [case("Repeated IDs", {"ids": [4, 2, 4, 3]}, [4, 2, 3]), case("Zero is valid", {"ids": [0, 1, 0]}, [0, 1]),
         case("No events", {"ids": []}, [], True), case("Negative IDs", {"ids": [-1, 0, -1, 2]}, [-1, 0, 2], True)],
        "The seen set must start empty: no valid ID can double as an already-seen sentinel. Ordered dictionaries also preserve insertion order in Python. Expected time O(n), space O(n).",
        ["Which input value is considered seen before processing starts?", "Zero belongs to the valid input domain.",
         "Start with an empty seen set or use an insertion-ordered dictionary."], 10,
    ),
    problem(
        "last-character", "An index too far",
        "A notification formatter extracts the final character of an ASCII message. Every nonempty message triggers an out-of-bounds error, and empty messages need special handling too.",
        "runtime", "easy", ["strings", "bounds", "empty-input"],
        ["Return the final character of input.text as a string.", "For an empty string, return an empty string.", "Inputs contain ASCII characters."],
        {"python": 'def solve(data):\n    text = data["text"]\n    return text[len(text)]',
         "java": '''
            import com.google.gson.*;
            public class Solution {
              public static JsonElement solve(JsonObject data) {
                String text = data.get("text").getAsString();
                return new JsonPrimitive(String.valueOf(text.charAt(text.length())));
              }
            }
         '''},
        {"python": 'def solve(data):\n    return data["text"][-1:]',
         "java": '''
            import com.google.gson.*;
            public class Solution {
              public static JsonElement solve(JsonObject data) {
                String text = data.get("text").getAsString();
                return new JsonPrimitive(text.isEmpty() ? "" : text.substring(text.length() - 1));
              }
            }
         '''},
        [case("Ordinary message", {"text": "hello"}, "o"), case("Empty message", {"text": ""}, ""),
         case("One character", {"text": "A"}, "A", True), case("Trailing whitespace", {"text": "end "}, " ", True)],
        "The final valid index is length minus one. Guard an empty string before indexing, or use a safe slice. Time and extra space O(1) for the final-character operation.",
        ["What is the highest valid index in a string of length five?", "Subtracting one alone still leaves an empty-string problem.",
         "Handle empty input first, then access the last valid index."], 8,
    ),
    problem(
        "pagination-drift", "Page two looks familiar",
        "Customers scrolling an activity feed keep seeing the same entries at page boundaries. The API uses one-based page numbers but the offset calculation mixes two indexing conventions.",
        "logic", "medium", ["pagination", "offset", "api"],
        ["Return the requested slice of input.items.", "Pages are one-based; size is the number of items per page.",
         "Return [] for page < 1, size < 1, or pages beyond the collection."],
        {"python": 'def solve(data):\n    start = data["page"] - 1\n    return data["items"][start:start + data["size"]]',
         "javascript": 'function solve(data) { const start = data.page - 1; return data.items.slice(start, start + data.size); }\nmodule.exports = { solve };'},
        {"python": 'def solve(data):\n    if data["page"] < 1 or data["size"] < 1:\n        return []\n    start = (data["page"] - 1) * data["size"]\n    return data["items"][start:start + data["size"]]',
         "javascript": 'function solve(data) { if (data.page < 1 || data.size < 1) return []; const start = (data.page - 1) * data.size; return data.items.slice(start, start + data.size); }\nmodule.exports = { solve };'},
        [case("First page", {"items": [1, 2, 3, 4, 5], "page": 1, "size": 2}, [1, 2]),
         case("Second page", {"items": [1, 2, 3, 4, 5], "page": 2, "size": 2}, [3, 4]),
         case("Final partial page", {"items": [1, 2, 3, 4, 5], "page": 3, "size": 2}, [5], True),
         case("Invalid page", {"items": [1, 2, 3], "page": 0, "size": 2}, [], True),
         case("Beyond end", {"items": [1], "page": 5, "size": 2}, [], True)],
        "A page number counts groups, not individual items. Multiply the zero-based page by page size to obtain the offset. Validate both parameters first. Time and space O(size) for the returned slice.",
        ["How many items should be skipped before page two?", "The offset needs both the page number and page size.",
         "Use (page - 1) * size after rejecting invalid page and size values."], 12,
    ),
    problem(
        "inventory-retry", "Sold twice, shipped once",
        "A fulfillment webhook can be delivered more than once. The current inventory handler decrements stock on every delivery, even when the order has already been reserved. Make retries safe.",
        "business", "hard", ["idempotency", "inventory", "state"],
        ["Input has stock, processed order IDs, and an ordered list of {id, quantity} requests.",
         "Process each order ID at most once. Ignore nonpositive quantities and insufficient-stock requests.",
         "Only successful reservations add an ID to processed. Return {state: {stock, processed}} in processing order."],
        {"python": '''
            def solve(data):
                stock = data["stock"]
                processed = list(data["processed"])
                for order in data["orders"]:
                    stock -= order["quantity"]
                    processed.append(order["id"])
                return {"state": {"stock": stock, "processed": processed}}
        '''},
        {"python": '''
            def solve(data):
                stock = data["stock"]
                processed = list(data["processed"])
                seen = set(processed)
                for order in data["orders"]:
                    if order["id"] in seen or order["quantity"] <= 0 or order["quantity"] > stock:
                        continue
                    stock -= order["quantity"]
                    seen.add(order["id"])
                    processed.append(order["id"])
                return {"state": {"stock": stock, "processed": processed}}
        '''},
        [case("One reservation", {"stock": 10, "processed": [], "orders": [{"id": "a", "quantity": 3}]},
              {"state": {"stock": 7, "processed": ["a"]}}, assertions=[{"path": "state.stock", "equals": 7}]),
         case("Duplicate delivery", {"stock": 10, "processed": [], "orders": [{"id": "a", "quantity": 3}, {"id": "a", "quantity": 3}]},
              {"state": {"stock": 7, "processed": ["a"]}}, assertions=[{"path": "state.processed", "equals": ["a"]}]),
         case("Existing reservation", {"stock": 4, "processed": ["a"], "orders": [{"id": "a", "quantity": 2}, {"id": "b", "quantity": 5}]},
              {"state": {"stock": 4, "processed": ["a"]}}, True),
         case("Invalid reservation", {"stock": 4, "processed": [], "orders": [{"id": "a", "quantity": -2}, {"id": "b", "quantity": 4}]},
              {"state": {"stock": 0, "processed": ["b"]}}, True)],
        "Use the order ID as the idempotency key, validate availability, then update stock and the processed set together. A production implementation should enforce that atomicity in the database. Time O(n + p), space O(n + p).",
        ["What distinguishes a retry from a new order?", "Rejected reservations should not consume stock or the idempotency key.",
         "Check the ID and quantity first, then commit stock and processed-ID changes together."], 22,
    ),
    problem(
        "integer-overflow", "Two billion and counting",
        "A billing report adds two nonnegative 32-bit counters. Large accounts sometimes display negative usage because the addition overflows before it reaches the wider result type.",
        "edge", "medium", ["integers", "overflow", "casting"],
        ["Return the exact sum of input.a and input.b.", "Each input is between 0 and 2,147,483,647.",
         "The result may exceed the signed 32-bit range."],
        {"java": '''
            import com.google.gson.*;
            public class Solution {
              public static JsonElement solve(JsonObject data) {
                int a = data.get("a").getAsInt(), b = data.get("b").getAsInt();
                long result = a + b;
                return new JsonPrimitive(result);
              }
            }
        ''', "cpp": '''
            #include <nlohmann/json.hpp>
            using nlohmann::json;
            json solve(const json& data) {
              int a = data.at("a"), b = data.at("b");
              long long result = a + b;
              return result;
            }
        '''},
        {"java": '''
            import com.google.gson.*;
            public class Solution {
              public static JsonElement solve(JsonObject data) {
                long a = data.get("a").getAsLong(), b = data.get("b").getAsLong();
                return new JsonPrimitive(a + b);
              }
            }
        ''', "cpp": '''
            #include <nlohmann/json.hpp>
            using nlohmann::json;
            json solve(const json& data) {
              return data.at("a").get<long long>() + data.at("b").get<long long>();
            }
        '''},
        [case("Small account", {"a": 20, "b": 30}, 50), case("At the boundary", {"a": 2147483647, "b": 1}, 2147483648),
         case("Two large counters", {"a": 2147483647, "b": 2147483647}, 4294967294, True),
         case("Zero counters", {"a": 0, "b": 0}, 0, True)],
        "Widen an operand before addition, or read both values into the wider type. Assigning an already-overflowed expression to a wide variable cannot recover the lost value. Time and space O(1).",
        ["At what type does the addition happen?", "The destination type does not determine the type of the intermediate expression.",
         "Read or cast operands to 64-bit values before adding them."], 15,
    ),
    problem(
        "promises-in-parcel", "A parcel full of promises",
        "An asynchronous pricing endpoint maps item IDs to doubled prices, but its response contains empty objects instead of numbers. The outer async function has finished before its mapped work is collected.",
        "logic", "medium", ["async", "promises", "javascript"],
        ["Return an array containing each value in input.prices multiplied by two.",
         "Preserve input order and await all asynchronous operations.", "An empty list returns []."],
        {"javascript": '''
            async function solve(data) {
              return data.prices.map(async price => {
                return await Promise.resolve(price * 2);
              });
            }
            module.exports = { solve };
        '''},
        {"javascript": '''
            async function solve(data) {
              return Promise.all(data.prices.map(async price => {
                return await Promise.resolve(price * 2);
              }));
            }
            module.exports = { solve };
        '''},
        [case("Multiple prices", {"prices": [3, 7, 2]}, [6, 14, 4]), case("No prices", {"prices": []}, []),
         case("Zero and fractional", {"prices": [0, 1.5]}, [0, 3], True)],
        "An async map callback creates an array of promises. Promise.all resolves the collection while retaining input order. Time O(n), space O(n).",
        ["What is the return type of an async callback?", "Awaiting an array does not await its elements.",
         "Collect the mapped promises with Promise.all."], 15,
    ),
    problem(
        "nil-map", "A map with nowhere to write",
        "A Go service counts labels in incoming telemetry. The first write panics because declaring a map and allocating one are different operations.",
        "runtime", "easy", ["maps", "initialization", "go"],
        ["Return a JSON object mapping each string in input.labels to its frequency.",
         "An empty list returns an empty object, not null."],
        {"go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                var counts map[string]int
                for _, item := range data["labels"].([]interface{}) { counts[item.(string)]++ }
                return counts
            }
        '''},
        {"go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                counts := make(map[string]int)
                for _, item := range data["labels"].([]interface{}) { counts[item.(string)]++ }
                return counts
            }
        '''},
        [case("Repeated labels", {"labels": ["api", "web", "api"]}, {"api": 2, "web": 1}),
         case("No labels", {"labels": []}, {}), case("Empty label", {"labels": ["", "api", ""]}, {"": 2, "api": 1}, True)],
        "A nil map permits reads but panics on writes. Allocate the map with make; that also ensures the empty result serializes as an object. Time O(n), space O(k) for k unique labels.",
        ["Does declaring a map allocate its storage?", "Nil maps can be read, but not written.",
         "Initialize counts with make(map[string]int)."], 10,
    ),
]

CATALOG.append(problem(
    "wallet-race", "Two withdrawals, one balance",
    "Two payment requests arrive at the same time. Both check the same wallet balance, both see enough funds, and both withdraw. Reproduce the race with synchronized threads, then make the check and debit one atomic operation.",
    "business", "hard", ["concurrency", "locks", "state"],
    ["Input has a nonnegative balance and a list of withdrawal amounts in integer cents.",
     "Process requests concurrently, approving a request only if its amount is positive and sufficient funds remain.",
     "Return {state: {balance, approved}}. The balance must never become negative.",
     "All positive amounts in each test are identical, so the final balance and approval count do not depend on thread order."],
    {"python": '''
        import threading

        def solve(data):
            state = {"balance": data["balance"], "approved": 0}
            barrier = threading.Barrier(max(1, len(data["withdrawals"])))

            def withdraw(amount):
                allowed = amount <= state["balance"]
                barrier.wait()
                if allowed:
                    state["balance"] -= amount
                    state["approved"] += 1

            threads = [threading.Thread(target=withdraw, args=(amount,))
                       for amount in data["withdrawals"]]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            return {"state": state}
    '''},
    {"python": '''
        import threading

        def solve(data):
            state = {"balance": data["balance"], "approved": 0}
            lock = threading.Lock()
            barrier = threading.Barrier(max(1, len(data["withdrawals"])))

            def withdraw(amount):
                barrier.wait()
                with lock:
                    if 0 < amount <= state["balance"]:
                        state["balance"] -= amount
                        state["approved"] += 1

            threads = [threading.Thread(target=withdraw, args=(amount,))
                       for amount in data["withdrawals"]]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            return {"state": state}
    '''},
    [case("Enough for both", {"balance": 100, "withdrawals": [20, 20]}, {"state": {"balance": 60, "approved": 2}}),
     case("Concurrent overdraft", {"balance": 100, "withdrawals": [60, 60]}, {"state": {"balance": 40, "approved": 1}},
          assertions=[{"path": "state.balance", "equals": 40}, {"path": "state.approved", "equals": 1}]),
     case("Ten simultaneous requests", {"balance": 100, "withdrawals": [30] * 10}, {"state": {"balance": 10, "approved": 3}}, True),
     case("Invalid requests", {"balance": 100, "withdrawals": [-10, 0]}, {"state": {"balance": 100, "approved": 0}}, True),
     case("No requests", {"balance": 100, "withdrawals": []}, {"state": {"balance": 100, "approved": 0}}, True)],
    "The balance check and debit must share a critical section. Place the barrier before acquiring the lock, then validate and update under the same lock. A lock around only the debit still permits stale checks. This in-process model uses a threading lock; multiple service instances need database-level atomicity. Time O(n), thread storage O(n).",
    ["Both requests read the balance before either writes. What can change between those operations?",
     "Protect the check and the update together. Synchronizing only the debit is too late.",
     "Wait at the barrier before acquiring the lock, then validate a positive amount and update both fields while holding the lock."], 25,
))

# Append new cases so persisted problem IDs and existing submission history stay stable.
CATALOG.extend([
    problem(
        "binary-search-stall", "The search that never ends",
        "A sorted-index lookup finds middle entries quickly but hangs when the target lies near the right edge. Repair the search bounds so every iteration makes progress.",
        "logic", "medium", ["binary-search", "termination", "bounds"],
        ["Return the zero-based index of target in the strictly increasing integer list nums, or -1 if absent.",
         "The list may be empty and contains at most 1,000 elements. All values and target are between -1,000,000 and 1,000,000.", "Use a binary search with O(log n) lookup time."],
        {"python": '''
            def solve(data):
                nums, target = data["nums"], data["target"]
                left, right = 0, len(nums) - 1
                while left <= right:
                    mid = (left + right) // 2
                    if nums[mid] == target:
                        return mid
                    if nums[mid] < target:
                        left = mid
                    else:
                        right = mid - 1
                return -1
        ''', "cpp": '''
            #include <nlohmann/json.hpp>
            using nlohmann::json;
            json solve(const json& data) {
                const auto& nums = data.at("nums");
                int target = data.at("target"), left = 0, right = static_cast<int>(nums.size()) - 1;
                while (left <= right) {
                    int mid = left + (right - left) / 2;
                    if (nums[mid].get<int>() == target) return mid;
                    if (nums[mid].get<int>() < target) left = mid;
                    else right = mid - 1;
                }
                return -1;
            }
        '''},
        {"python": '''
            def solve(data):
                nums, target = data["nums"], data["target"]
                left, right = 0, len(nums) - 1
                while left <= right:
                    mid = (left + right) // 2
                    if nums[mid] == target:
                        return mid
                    if nums[mid] < target:
                        left = mid + 1
                    else:
                        right = mid - 1
                return -1
        ''', "cpp": '''
            #include <nlohmann/json.hpp>
            using nlohmann::json;
            json solve(const json& data) {
                const auto& nums = data.at("nums");
                int target = data.at("target"), left = 0, right = static_cast<int>(nums.size()) - 1;
                while (left <= right) {
                    int mid = left + (right - left) / 2;
                    if (nums[mid].get<int>() == target) return mid;
                    if (nums[mid].get<int>() < target) left = mid + 1;
                    else right = mid - 1;
                }
                return -1;
            }
        '''},
        [case("Middle entry", {"nums": [2, 4, 8], "target": 4}, 1),
         case("Rightmost entry", {"nums": [2, 4, 8], "target": 8}, 2),
         case("Empty index", {"nums": [], "target": 8}, -1, True),
         case("Missing between entries", {"nums": [2, 4, 8], "target": 3}, -1, True),
         case("Only entry", {"nums": [7], "target": 7}, 0, True),
         case("First entry", {"nums": [-9, -2, 0, 8], "target": -9}, 0, True)],
        "Once the midpoint is known to be too small, it cannot contain the answer. Move left to mid + 1 so the inclusive search interval strictly shrinks. Time O(log n), extra space O(1).",
        ["Trace the bounds when only two candidate positions remain.",
         "Can the next midpoint equal the current left boundary?",
         "Discard the checked midpoint with left = mid + 1 or right = mid - 1."], 18,
    ),
    problem(
        "numeric-sort", "Ten comes before two",
        "A report orders numeric scores using text comparison. Small samples look correct, but scores with different digit counts appear in the wrong order.",
        "logic", "easy", ["sorting", "comparators", "numbers"],
        ["Return input.scores sorted in ascending numeric order, retaining duplicates.",
         "Scores are integers from -1,000,000 to 1,000,000. Empty input returns []."],
        {"javascript": 'function solve(data) { return [...data.scores].sort(); }\nmodule.exports = { solve };',
         "java": '''
            import com.google.gson.*;
            import java.util.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    List<Integer> scores = new ArrayList<>();
                    for (JsonElement value : data.getAsJsonArray("scores")) scores.add(value.getAsInt());
                    scores.sort(Comparator.comparing(String::valueOf));
                    return new Gson().toJsonTree(scores);
                }
            }
         '''},
        {"javascript": 'function solve(data) { return [...data.scores].sort((a, b) => a - b); }\nmodule.exports = { solve };',
         "java": '''
            import com.google.gson.*;
            import java.util.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    List<Integer> scores = new ArrayList<>();
                    for (JsonElement value : data.getAsJsonArray("scores")) scores.add(value.getAsInt());
                    scores.sort(Integer::compare);
                    return new Gson().toJsonTree(scores);
                }
            }
         '''},
        [case("Single digits", {"scores": [3, 1, 2]}, [1, 2, 3]),
         case("Different widths", {"scores": [10, 2, 100, 1]}, [1, 2, 10, 100]),
         case("Negative scores", {"scores": [-2, -10, 0, 2, -2]}, [-10, -2, -2, 0, 2], True),
         case("Empty report", {"scores": []}, [], True),
         case("Large values", {"scores": [1000000, -1000000, 9]}, [-1000000, 9, 1000000], True)],
        "Text ordering compares digits rather than magnitude. Supply a numeric comparator and preserve duplicate values. Time O(n log n), O(n) space for the returned copy and sorting storage.",
        ["Compare the strings '10' and '2' one character at a time.",
         "The sort needs to compare numeric values, not their text representations.",
         "Use (a, b) => a - b in JavaScript or Integer::compare in Java."], 10,
    ),
    problem(
        "shared-matrix", "Every row changes at once",
        "A seating-plan editor writes one seat but changes the same column in every row. Its matrix contains multiple references to one shared row.",
        "logic", "medium", ["aliasing", "matrices", "mutability"],
        ["Create a rows by cols matrix of zeros, then apply writes in input order.",
         "Each write is {row, col, value}; coordinates are valid and later writes replace earlier values.",
         "Dimensions are between 0 and 30. Zero rows returns []; zero columns returns one empty list per row."],
        {"python": '''
            def solve(data):
                grid = [[0] * data["cols"]] * data["rows"]
                for write in data["writes"]:
                    grid[write["row"]][write["col"]] = write["value"]
                return grid
        '''},
        {"python": '''
            def solve(data):
                grid = [[0] * data["cols"] for _ in range(data["rows"])]
                for write in data["writes"]:
                    grid[write["row"]][write["col"]] = write["value"]
                return grid
        '''},
        [case("Blank plan", {"rows": 2, "cols": 2, "writes": []}, [[0, 0], [0, 0]]),
         case("One seat", {"rows": 2, "cols": 2, "writes": [{"row": 0, "col": 1, "value": 7}]}, [[0, 7], [0, 0]]),
         case("Independent rows", {"rows": 2, "cols": 1, "writes": [{"row": 0, "col": 0, "value": 2}, {"row": 1, "col": 0, "value": 9}, {"row": 0, "col": 0, "value": 3}]}, [[3], [9]], True),
         case("No rows", {"rows": 0, "cols": 3, "writes": []}, [], True),
         case("No columns", {"rows": 3, "cols": 0, "writes": []}, [[], [], []], True)],
        "Repeating a list repeats references to its elements. Allocate a fresh inner list for each row before applying writes. Time O(rows × cols + writes), output space O(rows × (cols + 1)).",
        ["Do the row objects have separate identities?", "Repeating an outer list does not copy the inner lists.",
         "Build the rows with a comprehension so each iteration creates a new list."], 15,
    ),
    problem(
        "nested-intervals", "A shorter meeting erases a longer one",
        "A calendar merges overlapping busy intervals, but a nested meeting shortens an existing busy block. Touching intervals also need to remain separate under the calendar's half-open convention.",
        "logic", "medium", ["intervals", "sorting", "scheduling"],
        ["Input.intervals contains integer [start, end] pairs with start < end; endpoints range from -1,000,000 to 1,000,000 and input order is arbitrary.",
         "Return sorted intervals after merging strictly overlapping ranges. Ranges that only touch must remain separate.",
         "There are at most 100 intervals. Empty input returns []."],
        {"go": '''
            package main
            import "sort"
            func Solve(data map[string]interface{}) interface{} {
                intervals := make([][]int, 0)
                for _, raw := range data["intervals"].([]interface{}) {
                    pair := raw.([]interface{})
                    intervals = append(intervals, []int{int(pair[0].(float64)), int(pair[1].(float64))})
                }
                sort.Slice(intervals, func(i, j int) bool { return intervals[i][0] < intervals[j][0] })
                result := make([][]int, 0)
                for _, next := range intervals {
                    if len(result) == 0 || next[0] >= result[len(result)-1][1] { result = append(result, next) } else {
                        result[len(result)-1][1] = next[1]
                    }
                }
                return result
            }
        ''', "cpp": '''
            #include <nlohmann/json.hpp>
            #include <algorithm>
            #include <vector>
            using nlohmann::json;
            json solve(const json& data) {
                auto intervals = data.at("intervals").get<std::vector<std::vector<int>>>();
                std::sort(intervals.begin(), intervals.end());
                std::vector<std::vector<int>> result;
                for (const auto& next : intervals) {
                    if (result.empty() || next[0] >= result.back()[1]) result.push_back(next);
                    else result.back()[1] = next[1];
                }
                return result;
            }
        '''},
        {"go": '''
            package main
            import "sort"
            func Solve(data map[string]interface{}) interface{} {
                intervals := make([][]int, 0)
                for _, raw := range data["intervals"].([]interface{}) {
                    pair := raw.([]interface{})
                    intervals = append(intervals, []int{int(pair[0].(float64)), int(pair[1].(float64))})
                }
                sort.Slice(intervals, func(i, j int) bool { return intervals[i][0] < intervals[j][0] })
                result := make([][]int, 0)
                for _, next := range intervals {
                    if len(result) == 0 || next[0] >= result[len(result)-1][1] { result = append(result, next) } else {
                        last := result[len(result)-1]
                        if next[1] > last[1] { last[1] = next[1] }
                    }
                }
                return result
            }
        ''', "cpp": '''
            #include <nlohmann/json.hpp>
            #include <algorithm>
            #include <vector>
            using nlohmann::json;
            json solve(const json& data) {
                auto intervals = data.at("intervals").get<std::vector<std::vector<int>>>();
                std::sort(intervals.begin(), intervals.end());
                std::vector<std::vector<int>> result;
                for (const auto& next : intervals) {
                    if (result.empty() || next[0] >= result.back()[1]) result.push_back(next);
                    else result.back()[1] = std::max(result.back()[1], next[1]);
                }
                return result;
            }
        '''},
        [case("Simple overlap", {"intervals": [[3, 7], [1, 4]]}, [[1, 7]]),
         case("Nested meeting", {"intervals": [[1, 10], [2, 3], [8, 12]]}, [[1, 12]]),
         case("Touching ranges", {"intervals": [[1, 3], [3, 5]]}, [[1, 3], [3, 5]], True),
         case("Same start and duplicates", {"intervals": [[0, 9], [0, 2], [0, 9], [10, 11]]}, [[0, 9], [10, 11]], True),
         case("Empty calendar", {"intervals": []}, [], True)],
        "A merged block must retain the furthest endpoint seen so far. Sort by start, merge only when next.start < current.end, and keep max(current.end, next.end). Time O(n log n), output space O(n).",
        ["Can adding a contained meeting reduce total busy time?", "The current endpoint summarizes every interval already merged.",
         "Keep the larger endpoint, and treat next.start == current.end as a new block."], 18,
    ),
    problem(
        "retry-budget", "One request too many",
        "A retry helper treats a maximum-attempts setting as a maximum-retries setting. During an outage it sends one extra request and can claim success after exhausting its budget.",
        "logic", "medium", ["retries", "off-by-one", "control-flow"],
        ["Input.outcomes is a list of booleans representing ordered request results; true means success.",
         "Make at most max_attempts attempts, stop at the first success, and never consume beyond outcomes.",
         "Return {attempts: count, success: boolean}. A nonpositive budget means zero attempts and false."],
        {"python": '''
            def solve(data):
                attempts = 0
                for outcome in data["outcomes"]:
                    if attempts > data["max_attempts"]:
                        break
                    attempts += 1
                    if outcome:
                        return {"attempts": attempts, "success": True}
                return {"attempts": attempts, "success": False}
        ''', "javascript": '''
            function solve(data) {
                let attempts = 0;
                for (const outcome of data.outcomes) {
                    if (attempts > data.max_attempts) break;
                    attempts++;
                    if (outcome) return { attempts, success: true };
                }
                return { attempts, success: false };
            }
            module.exports = { solve };
        '''},
        {"python": '''
            def solve(data):
                attempts = 0
                for outcome in data["outcomes"]:
                    if attempts >= data["max_attempts"]:
                        break
                    attempts += 1
                    if outcome:
                        return {"attempts": attempts, "success": True}
                return {"attempts": attempts, "success": False}
        ''', "javascript": '''
            function solve(data) {
                let attempts = 0;
                for (const outcome of data.outcomes) {
                    if (attempts >= data.max_attempts) break;
                    attempts++;
                    if (outcome) return { attempts, success: true };
                }
                return { attempts, success: false };
            }
            module.exports = { solve };
        '''},
        [case("Early success", {"outcomes": [False, True, False], "max_attempts": 3}, {"attempts": 2, "success": True}),
         case("Success beyond budget", {"outcomes": [False, False, True], "max_attempts": 2}, {"attempts": 2, "success": False}),
         case("Disabled retries", {"outcomes": [True], "max_attempts": 0}, {"attempts": 0, "success": False}, True),
         case("Negative budget", {"outcomes": [True], "max_attempts": -1}, {"attempts": 0, "success": False}, True),
         case("No more outcomes", {"outcomes": [False], "max_attempts": 5}, {"attempts": 1, "success": False}, True),
         case("Last allowed success", {"outcomes": [False, True], "max_attempts": 2}, {"attempts": 2, "success": True}, True)],
        "The budget counts all attempts, including the first call. Check attempts >= max_attempts before consuming another outcome, and return immediately on success. Time O(min(n, max(0, budget))), space O(1).",
        ["Does the setting count retries or total requests?", "Trace a zero budget before the first attempt.",
         "Stop before consuming an outcome when attempts is greater than or equal to the budget."], 14,
    ),
    problem(
        "frequency-ties", "A leaderboard that flips its ties",
        "A tag leaderboard ranks frequencies correctly, but equally popular tags appear in reverse alphabetical order. Make its ordering deterministic under the published tie rule.",
        "logic", "medium", ["frequency", "sorting", "tie-breaking"],
        ["Count each lowercase ASCII tag in input.tags.",
         "Return up to k distinct tags, ordered by descending frequency and then ascending alphabetical order.",
         "A nonpositive k returns []. There are at most 1,000 tags."],
        {"java": '''
            import com.google.gson.*;
            import java.util.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    Map<String, Integer> counts = new HashMap<>();
                    for (JsonElement tag : data.getAsJsonArray("tags")) counts.merge(tag.getAsString(), 1, Integer::sum);
                    List<String> tags = new ArrayList<>(counts.keySet());
                    tags.sort((a, b) -> counts.get(a).equals(counts.get(b)) ? b.compareTo(a) : Integer.compare(counts.get(b), counts.get(a)));
                    int k = Math.max(0, Math.min(data.get("k").getAsInt(), tags.size()));
                    return new Gson().toJsonTree(tags.subList(0, k));
                }
            }
        ''', "cpp": '''
            #include <nlohmann/json.hpp>
            #include <algorithm>
            #include <map>
            #include <string>
            #include <vector>
            using nlohmann::json;
            json solve(const json& data) {
                std::map<std::string, int> counts;
                for (const auto& tag : data.at("tags")) ++counts[tag.get<std::string>()];
                std::vector<std::string> tags;
                for (const auto& entry : counts) tags.push_back(entry.first);
                std::sort(tags.begin(), tags.end(), [&](const auto& a, const auto& b) {
                    return counts[a] == counts[b] ? a > b : counts[a] > counts[b];
                });
                tags.resize(std::max(0, std::min(data.at("k").get<int>(), static_cast<int>(tags.size()))));
                return tags;
            }
        '''},
        {"java": '''
            import com.google.gson.*;
            import java.util.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    Map<String, Integer> counts = new HashMap<>();
                    for (JsonElement tag : data.getAsJsonArray("tags")) counts.merge(tag.getAsString(), 1, Integer::sum);
                    List<String> tags = new ArrayList<>(counts.keySet());
                    tags.sort((a, b) -> counts.get(a).equals(counts.get(b)) ? a.compareTo(b) : Integer.compare(counts.get(b), counts.get(a)));
                    int k = Math.max(0, Math.min(data.get("k").getAsInt(), tags.size()));
                    return new Gson().toJsonTree(tags.subList(0, k));
                }
            }
        ''', "cpp": '''
            #include <nlohmann/json.hpp>
            #include <algorithm>
            #include <map>
            #include <string>
            #include <vector>
            using nlohmann::json;
            json solve(const json& data) {
                std::map<std::string, int> counts;
                for (const auto& tag : data.at("tags")) ++counts[tag.get<std::string>()];
                std::vector<std::string> tags;
                for (const auto& entry : counts) tags.push_back(entry.first);
                std::sort(tags.begin(), tags.end(), [&](const auto& a, const auto& b) {
                    return counts[a] == counts[b] ? a < b : counts[a] > counts[b];
                });
                tags.resize(std::max(0, std::min(data.at("k").get<int>(), static_cast<int>(tags.size()))));
                return tags;
            }
        '''},
        [case("Clear winner", {"tags": ["api", "web", "api"], "k": 1}, ["api"]),
         case("Tie at cutoff", {"tags": ["web", "api", "db"], "k": 2}, ["api", "db"]),
         case("Frequency before spelling", {"tags": ["a", "z", "z", "b", "b"], "k": 5}, ["b", "z", "a"], True),
         case("Zero requested", {"tags": ["a"], "k": 0}, [], True),
         case("Empty leaderboard", {"tags": [], "k": 3}, [], True)],
        "Use a two-part ordering: larger counts first, smaller tag strings first on equal counts. Clamp k to the distinct-tag count. With m distinct tags, time O(n log m + m log m) for ordered-map counting, and space O(m).",
        ["What should decide the winner when counts are equal?", "Frequency and spelling use opposite ordering directions.",
         "Compare counts descending; only when equal, compare tag strings ascending."], 18,
    ),
    problem(
        "negative-window", "The best week is still below zero",
        "A rolling-revenue report returns zero for a week where every possible window has a loss. The initial best value represents a window that was never present.",
        "logic", "medium", ["sliding-window", "initialization", "arrays"],
        ["Return the maximum sum of exactly k consecutive integers in input.values.",
         "Return null when k <= 0 or k exceeds the list length.",
         "There are at most 1,000 values, each between -10,000 and 10,000. Use O(n) time."],
        {"python": '''
            def solve(data):
                values, k = data["values"], data["k"]
                if k <= 0 or k > len(values):
                    return None
                current = sum(values[:k])
                best = max(0, current)
                for i in range(k, len(values)):
                    current += values[i] - values[i - k]
                    best = max(best, current)
                return best
        ''', "go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                values, k := data["values"].([]interface{}), int(data["k"].(float64))
                if k <= 0 || k > len(values) { return nil }
                current, best := 0, 0
                for i := 0; i < k; i++ { current += int(values[i].(float64)) }
                if current > best { best = current }
                for i := k; i < len(values); i++ {
                    current += int(values[i].(float64)) - int(values[i-k].(float64))
                    if current > best { best = current }
                }
                return best
            }
        '''},
        {"python": '''
            def solve(data):
                values, k = data["values"], data["k"]
                if k <= 0 or k > len(values):
                    return None
                current = best = sum(values[:k])
                for i in range(k, len(values)):
                    current += values[i] - values[i - k]
                    best = max(best, current)
                return best
        ''', "go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                values, k := data["values"].([]interface{}), int(data["k"].(float64))
                if k <= 0 || k > len(values) { return nil }
                current := 0
                for i := 0; i < k; i++ { current += int(values[i].(float64)) }
                best := current
                for i := k; i < len(values); i++ {
                    current += int(values[i].(float64)) - int(values[i-k].(float64))
                    if current > best { best = current }
                }
                return best
            }
        '''},
        [case("Profitable windows", {"values": [2, 5, 1, 8], "k": 2}, 9),
         case("Every window loses", {"values": [-5, -2, -7], "k": 2}, -7),
         case("Single-day window", {"values": [-8, -1, -4], "k": 1}, -1, True),
         case("Entire range", {"values": [3, -9, 2], "k": 3}, -4, True),
         case("Empty values", {"values": [], "k": 1}, None, True),
         case("Invalid length", {"values": [1, 2], "k": 0}, None, True)],
        "Initialize the best sum from the first valid window, not zero. Slide by adding the incoming value and subtracting the outgoing value. Time O(n), extra space O(1) in Go and O(k) for the Python initialization slice.",
        ["Which real window has sum zero in an all-negative input?", "The initial best value must be a valid candidate.",
         "Compute the first k-element sum and assign it to both current and best before sliding."], 16,
    ),
])

CATALOG.extend([
    problem(
        "unsafe-json", "One bad payload takes down the batch",
        "A webhook decoder assumes every payload is a valid object with a string ID. Malformed JSON and valid JSON of another shape should be rejected without crashing the caller.",
        "runtime", "medium", ["json", "parsing", "validation"],
        ["Parse the JSON text in input.payload and return its id only when the top-level value is an object and id is a string.",
         "Return null for malformed JSON, a non-object value, or a missing, null, or non-string id.",
         "Preserve string IDs exactly, including an empty string. Payloads are at most 1,000 characters."],
        {"javascript": 'function solve(data) { return JSON.parse(data.payload).id.toString(); }\nmodule.exports = { solve };',
         "java": '''
            import com.google.gson.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    JsonObject value = JsonParser.parseString(data.get("payload").getAsString()).getAsJsonObject();
                    return new JsonPrimitive(value.get("id").getAsString());
                }
            }
         '''},
        {"javascript": '''
            function solve(data) {
                try {
                    const value = JSON.parse(data.payload);
                    return value !== null && !Array.isArray(value) && typeof value === 'object'
                        && typeof value.id === 'string' ? value.id : null;
                } catch { return null; }
            }
            module.exports = { solve };
        ''', "java": r'''
            import com.google.gson.*;
            import com.google.gson.stream.*;
            import java.io.*;
            import java.util.regex.*;
            public class Solution {
                // The bundled Gson reader has legacy exceptions even with lenient mode off.
                // Validate tokens strictly, then let Gson validate the document structure.
                private static final Pattern TOKENS = Pattern.compile(
                    "\"(?:[^\"\\\\\\x00-\\x1f]|\\\\(?:[\"\\\\/bfnrt]|u[0-9a-fA-F]{4}))*\""
                    + "|-?(?:0|[1-9][0-9]*)(?:\\.[0-9]+)?(?:[eE][+-]?[0-9]+)?"
                    + "|true|false|null|[{}\\[\\]:,]|[ \\t\\r\\n]+");
                private static boolean validTokens(String source) {
                    Matcher matcher = TOKENS.matcher(source);
                    int end = 0;
                    while (matcher.find()) {
                        if (matcher.start() != end) return false;
                        end = matcher.end();
                    }
                    return end == source.length();
                }
                public static JsonElement solve(JsonObject data) {
                    try {
                        String source = data.get("payload").getAsString();
                        if (!validTokens(source)) return JsonNull.INSTANCE;
                        JsonReader reader = new JsonReader(new StringReader(source));
                        reader.setLenient(false);
                        JsonElement value = new Gson().getAdapter(JsonElement.class).read(reader);
                        if (reader.peek() != JsonToken.END_DOCUMENT || value == null || !value.isJsonObject()) return JsonNull.INSTANCE;
                        JsonElement id = value.getAsJsonObject().get("id");
                        return id != null && id.isJsonPrimitive() && id.getAsJsonPrimitive().isString() ? id : JsonNull.INSTANCE;
                    } catch (IOException | RuntimeException error) { return JsonNull.INSTANCE; }
                }
            }
        '''},
        [case("Valid event", {"payload": '{"id":"evt-7"}'}, "evt-7"),
         case("Truncated JSON", {"payload": '{"id":'}, None),
         case("JSON null", {"payload": 'null'}, None, True),
         case("Numeric ID", {"payload": '{"id":17}'}, None, True),
         case("Array payload", {"payload": '[{"id":"a"}]'}, None, True),
         case("Missing ID", {"payload": '{}'}, None, True),
         case("Empty string ID", {"payload": '{"id":""}'}, "", True),
         case("Unquoted property", {"payload": '{id:"a"}'}, None, True),
         case("Trailing document", {"payload": '{"id":"a"} {}'}, None, True),
         case("Literal newline inside a string", {"payload": '{"id":"a\nb"}'}, None, True),
         case("Uppercase keyword", {"payload": '{"id":"a","value":TRUE}'}, None, True),
         case("Unknown escape", {"payload": r'{"id":"a\q"}'}, None, True),
         case("Comments are not JSON", {"payload": '{"id":"a" /* comment */}'}, None, True),
         case("Leading zero in a number", {"payload": '{"id":"a","number":01}'}, None, True),
         case("Escaped newline remains valid", {"payload": r'{"id":"a\nb","value":true}'}, "a\nb", True),
         case("Maximum-length payload", {"payload": '{"id":"' + "x" * 991 + '"}'}, "x" * 991, True)],
        "Contain parsing failures at the decoder boundary, validate the top-level shape, then check the ID's actual type. Avoid coercion. The bundled Gson reader retains some legacy non-JSON behavior even without lenient mode, so the Java solution checks strict JSON tokens before parsing the document structure and requiring end-of-input. Escaped control characters are valid; literal control characters inside strings are not. Time and space O(payload length).",
        ["JSON can be valid without describing an object. What shapes can arrive?",
         "Calling toString or getAsString can silently turn a numeric ID into a string.",
         "Catch parsing errors, require one complete object document, and check the ID type. In Java, also reject non-JSON tokens that the bundled Gson reader accepts, such as uppercase keywords and literal newlines inside strings."], 22,
    ),
    problem(
        "queue-underflow", "The worker reads an empty queue",
        "A local job queue crashes when a consumer pops before a producer has added work. Empty reads need an explicit result while preserving FIFO behavior for later jobs.",
        "runtime", "easy", ["queues", "bounds", "state"],
        ["Process input.operations in order: {op: 'push', value: integer} appends a value; {op: 'pop'} removes the oldest value.",
         "Return {removed: [...], remaining: [...]}, recording null in removed for each pop on an empty queue.",
         "There are at most 100 operations. Only push and pop operations are supplied, with values between -1,000,000 and 1,000,000."],
        {"cpp": '''
            #include <nlohmann/json.hpp>
            #include <deque>
            using nlohmann::json;
            json solve(const json& data) {
                std::deque<int> queue;
                json removed = json::array();
                for (const auto& op : data.at("operations")) {
                    if (op.at("op") == "push") queue.push_back(op.at("value").get<int>());
                    else { removed.push_back(queue.at(0)); queue.pop_front(); }
                }
                return json{{"removed", removed}, {"remaining", queue}};
            }
        ''', "go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                queue, removed := make([]int, 0), make([]interface{}, 0)
                for _, raw := range data["operations"].([]interface{}) {
                    op := raw.(map[string]interface{})
                    if op["op"] == "push" { queue = append(queue, int(op["value"].(float64))) } else {
                        removed = append(removed, queue[0]); queue = queue[1:]
                    }
                }
                return map[string]interface{}{"removed": removed, "remaining": queue}
            }
        '''},
        {"cpp": '''
            #include <nlohmann/json.hpp>
            #include <deque>
            using nlohmann::json;
            json solve(const json& data) {
                std::deque<int> queue;
                json removed = json::array();
                for (const auto& op : data.at("operations")) {
                    if (op.at("op") == "push") queue.push_back(op.at("value").get<int>());
                    else if (queue.empty()) removed.push_back(nullptr);
                    else { removed.push_back(queue.front()); queue.pop_front(); }
                }
                return json{{"removed", removed}, {"remaining", queue}};
            }
        ''', "go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                queue, removed := make([]int, 0), make([]interface{}, 0)
                for _, raw := range data["operations"].([]interface{}) {
                    op := raw.(map[string]interface{})
                    if op["op"] == "push" { queue = append(queue, int(op["value"].(float64))) } else if len(queue) == 0 {
                        removed = append(removed, nil)
                    } else { removed = append(removed, queue[0]); queue = queue[1:] }
                }
                return map[string]interface{}{"removed": removed, "remaining": queue}
            }
        '''},
        [case("FIFO jobs", {"operations": [{"op": "push", "value": 4}, {"op": "push", "value": 9}, {"op": "pop"}]}, {"removed": [4], "remaining": [9]}),
         case("Consumer arrives first", {"operations": [{"op": "pop"}, {"op": "push", "value": 0}, {"op": "pop"}]}, {"removed": [None, 0], "remaining": []}),
         case("Repeated empty reads", {"operations": [{"op": "pop"}, {"op": "pop"}]}, {"removed": [None, None], "remaining": []}, True),
         case("Idle queue", {"operations": []}, {"removed": [], "remaining": []}, True),
         case("Drain and refill", {"operations": [{"op": "push", "value": -3}, {"op": "pop"}, {"op": "pop"}, {"op": "push", "value": 8}]}, {"removed": [-3, None], "remaining": [8]}, True)],
        "Test emptiness before reading or removing the first element. An empty pop records null and leaves the queue available for later pushes. Initialize empty output collections so they serialize as arrays. Time O(n), space O(n).",
        ["Is there always a job when pop runs?", "A failed read must not prevent later pushes from being processed.",
         "Handle an empty queue by appending null; otherwise read and remove its first value."], 12,
    ),
    problem(
        "zero-capacity", "A batch size of zero",
        "An import planner divides work into batches. A disabled or invalid capacity reaches the division before validation, causing the planning endpoint to crash.",
        "runtime", "easy", ["division", "validation", "batching"],
        ["Input contains a nonnegative integer items count and an integer capacity, each with magnitude at most 1,000,000.",
         "Return the minimum number of batches needed, rounding up partial batches.",
         "Return null for capacity <= 0. With a positive capacity, zero items requires zero batches."],
        {"python": 'def solve(data):\n    return (data["items"] + data["capacity"] - 1) // data["capacity"]',
         "go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                items, capacity := int(data["items"].(float64)), int(data["capacity"].(float64))
                return (items + capacity - 1) / capacity
            }
         '''},
        {"python": '''
            def solve(data):
                capacity = data["capacity"]
                if capacity <= 0:
                    return None
                return (data["items"] + capacity - 1) // capacity
        ''', "go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                items, capacity := int(data["items"].(float64)), int(data["capacity"].(float64))
                if capacity <= 0 { return nil }
                return (items + capacity - 1) / capacity
            }
        '''},
        [case("Partial final batch", {"items": 10, "capacity": 3}, 4),
         case("Disabled capacity", {"items": 10, "capacity": 0}, None),
         case("Negative capacity", {"items": 10, "capacity": -3}, None, True),
         case("No work", {"items": 0, "capacity": 5}, 0, True),
         case("Exact division", {"items": 12, "capacity": 4}, 3, True),
         case("No work with invalid capacity", {"items": 0, "capacity": 0}, None, True)],
        "Validate the divisor before arithmetic, including when the numerator is zero. For positive integer capacity, (items + capacity - 1) / capacity with integer division rounds up. Time and space O(1).",
        ["Which input controls whether division is defined?", "Check the capacity even when there are no items.",
         "Return null for nonpositive capacity before calculating the rounded-up batch count."], 10,
    ),
])

CATALOG.extend([
    problem(
        "mutation-during-iteration", "Cleanup breaks halfway through",
        "A session cleaner removes inactive entries while iterating over the same map. The collection changes beneath its iterator, and cleanup crashes before returning the active sessions.",
        "runtime", "medium", ["iterators", "maps", "mutation"],
        ["Input.sessions maps lowercase ASCII session IDs to booleans indicating whether each session is active.",
         "Return only active session IDs, sorted alphabetically. An empty map returns []."],
        {"python": '''
            def solve(data):
                sessions = data["sessions"].copy()
                for session in sessions:
                    if not sessions[session]:
                        del sessions[session]
                return sorted(sessions)
        ''', "java": '''
            import com.google.gson.*;
            import java.util.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    JsonObject sessions = data.getAsJsonObject("sessions").deepCopy();
                    for (Map.Entry<String, JsonElement> entry : sessions.entrySet()) {
                        if (!entry.getValue().getAsBoolean()) sessions.remove(entry.getKey());
                    }
                    List<String> active = new ArrayList<>(sessions.keySet());
                    Collections.sort(active);
                    return new Gson().toJsonTree(active);
                }
            }
        '''},
        {"python": 'def solve(data):\n    return sorted(session for session, active in data["sessions"].items() if active)',
         "java": '''
            import com.google.gson.*;
            import java.util.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    List<String> active = new ArrayList<>();
                    for (Map.Entry<String, JsonElement> entry : data.getAsJsonObject("sessions").entrySet()) {
                        if (entry.getValue().getAsBoolean()) active.add(entry.getKey());
                    }
                    Collections.sort(active);
                    return new Gson().toJsonTree(active);
                }
            }
         '''},
        [case("All active", {"sessions": {"web": True, "api": True}}, ["api", "web"]),
         case("Remove before another entry", {"sessions": {"old": False, "new": True}}, ["new"]),
         case("All expired", {"sessions": {"a": False, "b": False}}, [], True),
         case("No sessions", {"sessions": {}}, [], True),
         case("Interleaved states", {"sessions": {"z": True, "m": False, "a": True, "b": False}}, ["a", "z"], True)],
        "Structural mutation invalidates an active map iterator. Collect the desired IDs in a separate list, then sort them. This avoids both iterator invalidation and unnecessary mutation. Time O(n + a log a), space O(a) for a active sessions.",
        ["Which collection is being traversed and changed at the same time?",
         "Can you build the result without removing anything from that collection?",
         "Collect keys whose values are true into a new list, then sort that list."], 15,
    ),
    problem(
        "optional-profile", "A guest without a profile",
        "The greeting service dereferences user.profile.name even for new guests. Missing nested objects and blank names should produce the same friendly default.",
        "runtime", "easy", ["null", "optional-fields", "strings"],
        ["Return input.user.profile.name after trimming surrounding ASCII whitespace.",
         "Return 'Anonymous' if user or profile is missing or null, or name is missing, null, or blank.",
         "When present and non-null, user and profile are objects. Names contain only printable ASCII characters and ASCII whitespace."],
        {"javascript": 'function solve(data) { return data.user.profile.name.trim() || "Anonymous"; }\nmodule.exports = { solve };',
         "java": '''
            import com.google.gson.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    String name = data.getAsJsonObject("user").getAsJsonObject("profile").get("name").getAsString().trim();
                    return new JsonPrimitive(name.isEmpty() ? "Anonymous" : name);
                }
            }
         '''},
        {"javascript": 'function solve(data) { return data.user?.profile?.name?.trim() || "Anonymous"; }\nmodule.exports = { solve };',
         "java": '''
            import com.google.gson.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    JsonElement value = data;
                    for (String field : new String[]{"user", "profile", "name"}) {
                        if (value == null || !value.isJsonObject()) return new JsonPrimitive("Anonymous");
                        value = value.getAsJsonObject().get(field);
                    }
                    if (value == null || value.isJsonNull()) return new JsonPrimitive("Anonymous");
                    String name = value.getAsString().trim();
                    return new JsonPrimitive(name.isEmpty() ? "Anonymous" : name);
                }
            }
         '''},
        [case("Named member", {"user": {"profile": {"name": "  Ada  "}}}, "Ada"),
         case("Guest", {}, "Anonymous"),
         case("Null user", {"user": None}, "Anonymous", True),
         case("Missing profile", {"user": {}}, "Anonymous", True),
         case("Null profile", {"user": {"profile": None}}, "Anonymous", True),
         case("Null name", {"user": {"profile": {"name": None}}}, "Anonymous", True),
         case("Blank name", {"user": {"profile": {"name": " \t "}}}, "Anonymous", True),
         case("Missing name", {"user": {"profile": {}}}, "Anonymous", True)],
        "Protect every optional level before dereferencing it, then normalize the final string. Optional chaining handles missing and null values in JavaScript; Java can check each level explicitly. Time O(name length), space O(name length) for the trimmed result.",
        ["Does the fallback run before or after nested property access?",
         "Checking only name is too late when user or profile is absent.",
         "Guard every optional level, then trim the name and use Anonymous when the result is empty."], 12,
    ),
    problem(
        "recursive-cycle", "A dependency walks back to itself",
        "A dependency inspector recursively follows every outgoing edge. A circular dependency sends it back into an earlier node until the call stack is exhausted.",
        "runtime", "medium", ["graphs", "recursion", "cycles"],
        ["Input.graph maps lowercase ASCII node IDs to lists of neighboring IDs; input.start is a node ID.",
         "Return all nodes reachable from start, including start, once each in alphabetical order.",
         "Missing graph keys are leaves. There are at most 50 distinct nodes, and self-loops and cycles are valid."],
        {"python": '''
            def solve(data):
                seen = set()
                def visit(node):
                    seen.add(node)
                    for neighbor in data["graph"].get(node, []):
                        visit(neighbor)
                visit(data["start"])
                return sorted(seen)
        ''', "javascript": '''
            function solve(data) {
                const seen = new Set();
                function visit(node) {
                    seen.add(node);
                    for (const neighbor of data.graph[node] || []) visit(neighbor);
                }
                visit(data.start);
                return [...seen].sort();
            }
            module.exports = { solve };
        '''},
        {"python": '''
            def solve(data):
                seen = set()
                def visit(node):
                    if node in seen:
                        return
                    seen.add(node)
                    for neighbor in data["graph"].get(node, []):
                        visit(neighbor)
                visit(data["start"])
                return sorted(seen)
        ''', "javascript": '''
            function solve(data) {
                const seen = new Set();
                function visit(node) {
                    if (seen.has(node)) return;
                    seen.add(node);
                    const neighbors = Object.hasOwn(data.graph, node) ? data.graph[node] : [];
                    for (const neighbor of neighbors) visit(neighbor);
                }
                visit(data.start);
                return [...seen].sort();
            }
            module.exports = { solve };
        '''},
        [case("Simple chain", {"graph": {"a": ["b"], "b": ["c"]}, "start": "a"}, ["a", "b", "c"]),
         case("Circular dependency", {"graph": {"a": ["b"], "b": ["a"]}, "start": "a"}, ["a", "b"]),
         case("Self-loop", {"graph": {"a": ["a"]}, "start": "a"}, ["a"], True),
         case("Shared dependency and isolated node", {"graph": {"a": ["b", "c"], "b": ["d"], "c": ["d"], "z": []}, "start": "a"}, ["a", "b", "c", "d"], True),
         case("Missing start key", {"graph": {}, "start": "leaf"}, ["leaf"], True),
         case("Inherited property name", {"graph": {}, "start": "constructor"}, ["constructor"], True)],
        "Mark a node before exploring its neighbors, and return immediately when revisiting it. A set in the output alone does not prevent repeated traversal. In JavaScript, restrict adjacency lookup to own properties. Time O(V + E + V log V) including output sorting; space O(V).",
        ["Recording a node and refusing to revisit it are different operations.",
         "Marking only after visiting neighbors cannot break a cycle.",
         "Check seen at function entry, mark the new node, then traverse its own adjacency list."], 18,
    ),
    problem(
        "unhashable-coordinates", "Coordinates do not fit in a set",
        "A map service deduplicates coordinates by inserting JSON arrays into a Python set. The arrays are mutable and cannot be used as set keys.",
        "runtime", "easy", ["hashing", "tuples", "deduplication"],
        ["Input.points is a list of two-integer [x, y] coordinates, each component between -1,000,000 and 1,000,000.",
         "Return unique coordinates as arrays in first-seen order, retaining distinct ordered pairs.",
         "An empty input returns []. There are at most 1,000 points."],
        {"python": '''
            def solve(data):
                seen, result = set(), []
                for point in data["points"]:
                    if point not in seen:
                        seen.add(point)
                        result.append(point)
                return result
        '''},
        {"python": '''
            def solve(data):
                seen, result = set(), []
                for point in data["points"]:
                    key = tuple(point)
                    if key not in seen:
                        seen.add(key)
                        result.append(point)
                return result
        '''},
        [case("Repeated location", {"points": [[1, 2], [3, 4], [1, 2]]}, [[1, 2], [3, 4]]),
         case("No locations", {"points": []}, []),
         case("Coordinates are ordered", {"points": [[1, 2], [2, 1], [1, 2]]}, [[1, 2], [2, 1]], True),
         case("Zero and negative coordinates", {"points": [[0, 0], [-1, 2], [0, 0], [-1, 2]]}, [[0, 0], [-1, 2]], True),
         case("Avoid string-key collisions", {"points": [[1, 23], [12, 3]]}, [[1, 23], [12, 3]], True)],
        "Use an immutable tuple as the membership key while retaining the original array in the output. A tuple preserves coordinate order and avoids ambiguous string concatenation. Expected time O(n), space O(n).",
        ["Which Python containers can be hashed?", "The deduplication key does not have to use the output's representation.",
         "Check and store tuple(point) in seen, and append the original point to the result."], 10,
    ),
])

CATALOG.extend([
    problem(
        "unicode-count", "An emoji counts as two",
        "A text quota uses the string's storage length as its character count. Non-ASCII input exposes the difference between bytes, UTF-16 code units, and Unicode code points.",
        "edge", "medium", ["unicode", "strings", "encoding"],
        ["Return the number of Unicode code points in input.text, not bytes or UTF-16 code units.",
         "Count combining marks and zero-width joiners separately; this is not a grapheme-cluster count.",
         "Input is valid Unicode without lone surrogates and contains at most 1,000 code points."],
        {"go": 'package main\nfunc Solve(data map[string]interface{}) interface{} { return len(data["text"].(string)) }',
         "javascript": 'function solve(data) { return data.text.length; }\nmodule.exports = { solve };'},
        {"go": 'package main\nimport "unicode/utf8"\nfunc Solve(data map[string]interface{}) interface{} { return utf8.RuneCountInString(data["text"].(string)) }',
         "javascript": 'function solve(data) { return Array.from(data.text).length; }\nmodule.exports = { solve };'},
        [case("ASCII message", {"text": "hello"}, 5),
         case("Emoji message", {"text": "A😀B"}, 3),
         case("Accented text", {"text": "café"}, 4, True),
         case("Combining mark", {"text": "e\u0301"}, 2, True),
         case("Joined family emoji", {"text": "👩\u200d👩\u200d👧\u200d👦"}, 7, True),
         case("Empty text", {"text": ""}, 0, True)],
        "Go's len counts UTF-8 bytes, while JavaScript's length counts UTF-16 code units. Count runes in Go or iterate the JavaScript string by code point. Combining sequences remain multiple code points under this contract. Time O(n); Go uses O(1) extra space, Array.from uses O(n).",
        ["What unit does the language's length operation measure?", "One emoji can occupy four UTF-8 bytes or two UTF-16 code units.",
         "Use utf8.RuneCountInString in Go or the string iterator, such as Array.from, in JavaScript."], 15,
    ),
    problem(
        "minimum-sentinel", "A minimum that was never measured",
        "A sensor summary initializes its minimum to zero. Positive measurements therefore report an impossible zero reading, and an empty sample needs a separate representation.",
        "edge", "easy", ["sentinels", "empty-input", "aggregation"],
        ["Return the smallest integer in input.values, or null if there are no values.",
         "Values are between -1,000,000 and 1,000,000. Zero is a valid measurement."],
        {"cpp": '''
            #include <nlohmann/json.hpp>
            #include <algorithm>
            using nlohmann::json;
            json solve(const json& data) {
                int lowest = 0;
                for (const auto& value : data.at("values")) lowest = std::min(lowest, value.get<int>());
                return lowest;
            }
        ''', "java": '''
            import com.google.gson.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    int lowest = 0;
                    for (JsonElement value : data.getAsJsonArray("values")) lowest = Math.min(lowest, value.getAsInt());
                    return new JsonPrimitive(lowest);
                }
            }
        '''},
        {"cpp": '''
            #include <nlohmann/json.hpp>
            #include <algorithm>
            using nlohmann::json;
            json solve(const json& data) {
                const auto& values = data.at("values");
                if (values.empty()) return nullptr;
                int lowest = values.at(0).get<int>();
                for (const auto& value : values) lowest = std::min(lowest, value.get<int>());
                return lowest;
            }
        ''', "java": '''
            import com.google.gson.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    JsonArray values = data.getAsJsonArray("values");
                    if (values.isEmpty()) return JsonNull.INSTANCE;
                    int lowest = values.get(0).getAsInt();
                    for (JsonElement value : values) lowest = Math.min(lowest, value.getAsInt());
                    return new JsonPrimitive(lowest);
                }
            }
        '''},
        [case("Mixed readings", {"values": [4, -3, 2]}, -3),
         case("Only positive readings", {"values": [8, 3, 5]}, 3),
         case("No readings", {"values": []}, None, True),
         case("Zero reading", {"values": [8, 0, 2]}, 0, True),
         case("One reading", {"values": [1000000]}, 1000000, True)],
        "Handle empty input explicitly, then initialize the minimum from an actual reading. A valid measurement cannot double as the marker for no measurements. Time O(n), extra space O(1).",
        ["Was the initial minimum ever observed?", "An empty sample is different from a sample containing zero.",
         "Return null when empty; otherwise start from the first value and compare the remaining readings."], 10,
    ),
    problem(
        "cached-zero", "A cache hit becomes a miss",
        "A cache stores integer counters, including zero. The lookup falls back whenever a cached value is falsy, losing valid zero counters and confusing absent keys with stored values.",
        "edge", "easy", ["cache", "maps", "truthiness"],
        ["Return the value at input.cache[input.key] when that key is present; otherwise return input.fallback.",
         "Cache values and fallback are integers between -1,000,000,000 and 1,000,000,000. Keys are arbitrary ASCII strings, including empty strings and object-prototype names."],
        {"go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                cache := data["cache"].(map[string]interface{})
                value := cache[data["key"].(string)]
                if value == nil || value.(float64) == 0 { return data["fallback"] }
                return value
            }
        ''', "javascript": 'function solve(data) { return data.cache[data.key] || data.fallback; }\nmodule.exports = { solve };'},
        {"go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                cache := data["cache"].(map[string]interface{})
                value, exists := cache[data["key"].(string)]
                if !exists { return data["fallback"] }
                return value
            }
        ''', "javascript": 'function solve(data) { return Object.hasOwn(data.cache, data.key) ? data.cache[data.key] : data.fallback; }\nmodule.exports = { solve };'},
        [case("Stored counter", {"cache": {"hits": 8}, "key": "hits", "fallback": 99}, 8),
         case("Stored zero", {"cache": {"hits": 0}, "key": "hits", "fallback": 99}, 0),
         case("Missing counter", {"cache": {}, "key": "hits", "fallback": -1}, -1, True),
         case("Negative counter", {"cache": {"adjustment": -4}, "key": "adjustment", "fallback": 0}, -4, True),
         case("Empty key", {"cache": {"": 0}, "key": "", "fallback": 7}, 0, True),
         case("Inherited name is not stored", {"cache": {}, "key": "constructor", "fallback": 7}, 7, True),
         case("Explicit prototype-name key", {"cache": {"__proto__": 0}, "key": "__proto__", "fallback": 7}, 0, True)],
        "Check key presence independently of the cached value. Go's two-result map lookup distinguishes absence from zero. JavaScript's Object.hasOwn also excludes inherited prototype properties. Expected time and extra space O(1).",
        ["Is zero an absent counter or a stored counter?", "Value truthiness does not tell you whether a key exists.",
         "Use Go's value, exists lookup or JavaScript's Object.hasOwn before applying the fallback."], 12,
    ),
    problem(
        "negative-rotation", "The carousel takes too many steps",
        "A carousel rotation works for small positive step counts but fails for repeated full turns and large negative steps. Normalize the step count before indexing or slicing.",
        "edge", "medium", ["modulo", "arrays", "negative-values"],
        ["Rotate input.items right by input.steps; negative steps rotate left. Preserve item order within the rotation.",
         "Steps is an integer between -1,000,000 and 1,000,000. Items contains at most 100 integers in the same range.",
         "An empty list returns [], and complete turns leave the list unchanged."],
        {"python": 'def solve(data):\n    items, steps = data["items"], data["steps"]\n    return items[-steps:] + items[:-steps]',
         "cpp": '''
            #include <nlohmann/json.hpp>
            #include <vector>
            using nlohmann::json;
            json solve(const json& data) {
                auto items = data.at("items").get<std::vector<int>>();
                int n = static_cast<int>(items.size()), steps = data.at("steps");
                std::vector<int> result;
                for (int i = 0; i < n; ++i) result.push_back(items.at((i - steps + n) % n));
                return result;
            }
         '''},
        {"python": '''
            def solve(data):
                items = data["items"]
                if not items:
                    return []
                steps = data["steps"] % len(items)
                return items[-steps:] + items[:-steps]
        ''', "cpp": '''
            #include <nlohmann/json.hpp>
            #include <vector>
            using nlohmann::json;
            json solve(const json& data) {
                auto items = data.at("items").get<std::vector<int>>();
                int n = static_cast<int>(items.size());
                if (n == 0) return json::array();
                int steps = ((data.at("steps").get<int>() % n) + n) % n;
                std::vector<int> result;
                for (int i = 0; i < n; ++i) result.push_back(items[(i - steps + n) % n]);
                return result;
            }
        '''},
        [case("Two steps right", {"items": [1, 2, 3, 4, 5], "steps": 2}, [4, 5, 1, 2, 3]),
         case("More than a full turn", {"items": [1, 2, 3, 4, 5], "steps": 8}, [3, 4, 5, 1, 2]),
         case("Negative full turns", {"items": [1, 2, 3, 4, 5], "steps": -8}, [4, 5, 1, 2, 3], True),
         case("One step left", {"items": [1, 2, 3], "steps": -1}, [2, 3, 1], True),
         case("No steps", {"items": [1, 2, 3], "steps": 0}, [1, 2, 3], True),
         case("Empty carousel", {"items": [], "steps": 5}, [], True),
         case("Single item", {"items": [7], "steps": 1000000}, [7], True)],
        "Handle an empty list before modulo. Reduce steps modulo the length, normalizing negative remainders in C++, then build the rotated result with valid indices. Time and output space O(n).",
        ["How many positions does a full turn change?", "Modulo rules for negative operands differ between languages.",
         "Normalize steps into [0, n) after checking n > 0, then rotate using that reduced value."], 15,
    ),
])

CATALOG.extend([
    problem(
        "half-cent-discount", "Half a cent disappears",
        "A promotion engine always truncates fractional cents from discounts. The product rule requires rounding half a cent upward, and calculations must remain exact for large baskets.",
        "edge", "medium", ["rounding", "integer-arithmetic", "money"],
        ["Input.amount is an integer subtotal in cents from 0 to 1,000,000,000; rate_bps is from 0 to 10,000 basis points.",
         "Compute discount = amount × rate_bps / 10,000, rounded to the nearest integer cent with exact halves rounded upward.",
         "Return {discount: cents, total: amount - discount}. Apply the rounding rule once to the complete discount."],
        {"javascript": '''
            function solve(data) {
                const discount = Math.floor(data.amount * data.rate_bps / 10000);
                return { discount, total: data.amount - discount };
            }
            module.exports = { solve };
        ''', "python": '''
            def solve(data):
                discount = data["amount"] * data["rate_bps"] // 10000
                return {"discount": discount, "total": data["amount"] - discount}
        '''},
        {"javascript": '''
            function solve(data) {
                const discount = Math.floor((data.amount * data.rate_bps + 5000) / 10000);
                return { discount, total: data.amount - discount };
            }
            module.exports = { solve };
        ''', "python": '''
            def solve(data):
                discount = (data["amount"] * data["rate_bps"] + 5000) // 10000
                return {"discount": discount, "total": data["amount"] - discount}
        '''},
        [case("Whole-cent discount", {"amount": 1000, "rate_bps": 1000}, {"discount": 100, "total": 900}),
         case("Exactly half a cent", {"amount": 25, "rate_bps": 200}, {"discount": 1, "total": 24}),
         case("Below half", {"amount": 49, "rate_bps": 100}, {"discount": 0, "total": 49}, True),
         case("Above half", {"amount": 51, "rate_bps": 100}, {"discount": 1, "total": 50}, True),
         case("Fractional percentage", {"amount": 19999, "rate_bps": 3333}, {"discount": 6666, "total": 13333}, True),
         case("Full discount", {"amount": 999, "rate_bps": 10000}, {"discount": 999, "total": 0}, True),
         case("Large subtotal", {"amount": 1000000000, "rate_bps": 9999}, {"discount": 999900000, "total": 100000}, True),
         case("Empty basket", {"amount": 0, "rate_bps": 1000}, {"discount": 0, "total": 0}, True)],
        "For a nonnegative integer numerator and denominator 10,000, add 5,000 before integer division to round halves upward. This avoids binary fractional arithmetic and language-default tie rules. Products remain exact within JavaScript's safe integer range under the stated limits. Time and space O(1).",
        ["What should happen to a discount of exactly 0.5 cents?", "Default rounding functions can use different tie rules.",
         "Keep the numerator integral and calculate (amount * rate_bps + 5000) divided by 10000, rounded down."], 16,
    ),
    problem(
        "trailing-fields", "The final columns disappear",
        "An import preview splits comma-separated fields, but Java silently discards empty trailing columns. This shifts the meaning of sparse records and makes their column counts unreliable.",
        "edge", "easy", ["strings", "split", "empty-input"],
        ["Return input.line split at every comma, preserving all empty fields and whitespace exactly.",
         "This format has no quoting or escaping; every comma is a delimiter.",
         "An empty line represents one empty field and returns ['']."],
        {"java": '''
            import com.google.gson.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    return new Gson().toJsonTree(data.get("line").getAsString().split(","));
                }
            }
        '''},
        {"java": '''
            import com.google.gson.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    return new Gson().toJsonTree(data.get("line").getAsString().split(",", -1));
                }
            }
        '''},
        [case("Complete record", {"line": "name,email,role"}, ["name", "email", "role"]),
         case("Missing final column", {"line": "Ada,ada@example.com,"}, ["Ada", "ada@example.com", ""]),
         case("Only delimiters", {"line": ",,"}, ["", "", ""], True),
         case("Leading and middle gaps", {"line": ",a,,b,"}, ["", "a", "", "b", ""], True),
         case("Empty record", {"line": ""}, [""], True),
         case("Whitespace remains data", {"line": " a, ,"}, [" a", " ", ""], True)],
        "String.split with its default limit removes trailing empty strings. A negative limit preserves all fields, including those after the final delimiter. Time and output space O(n).",
        ["Are the missing fields always at the end?", "Check the meaning of split's optional limit argument.",
         "Use split(\",\", -1) to preserve trailing empty strings."], 10,
    ),
    problem(
        "negative-epoch-day", "Yesterday becomes today",
        "An archive groups timestamps into fixed UTC days from the Unix epoch. Integer division truncates toward zero, putting the seconds just before the epoch into day zero.",
        "edge", "medium", ["time", "division", "negative-values"],
        ["Return floor(input.seconds / 86400), the integer index of a fixed 86,400-second day relative to the epoch.",
         "Seconds is an integer between -1,000,000,000,000 and 1,000,000,000,000.",
         "Ignore time zones and leap seconds. The second immediately before the epoch belongs to day -1."],
        {"java": '''
            import com.google.gson.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    return new JsonPrimitive(data.get("seconds").getAsLong() / 86400L);
                }
            }
        ''', "go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                return int64(data["seconds"].(float64)) / 86400
            }
        '''},
        {"java": '''
            import com.google.gson.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    return new JsonPrimitive(Math.floorDiv(data.get("seconds").getAsLong(), 86400L));
                }
            }
        ''', "go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                seconds := int64(data["seconds"].(float64))
                day := seconds / 86400
                if seconds < 0 && seconds % 86400 != 0 { day-- }
                return day
            }
        '''},
        [case("After the epoch", {"seconds": 86401}, 1),
         case("One second before", {"seconds": -1}, -1),
         case("Exact negative boundary", {"seconds": -86400}, -1, True),
         case("Before the negative boundary", {"seconds": -86401}, -2, True),
         case("Epoch", {"seconds": 0}, 0, True),
         case("Last second in day zero", {"seconds": 86399}, 0, True),
         case("Beyond 32-bit seconds", {"seconds": -864000000001}, -10000001, True)],
        "Truncation and floor differ for negative non-integral quotients. Use Math.floorDiv in Java. In Go, decrement a negative truncated quotient only when there is a nonzero remainder. Use 64-bit arithmetic. Time and space O(1).",
        ["Which day contains the interval from -86400 through -1?", "Does integer division round toward zero or toward negative infinity?",
         "Use floor division; when implementing it manually, adjust only negative values with a nonzero remainder."], 15,
    ),
    problem(
        "finite-infinity", "A long route looks unreachable",
        "A route planner uses one million as infinity. Legitimate routes at or above that cost can never replace the sentinel, so reachable destinations disappear from its distance table.",
        "edge", "hard", ["graphs", "dijkstra", "sentinels"],
        ["Input contains n nodes numbered 0 through n-1, a valid start node, and directed edges [from, to, cost].",
         "Return an n-element list of shortest costs from start. Use null only for unreachable nodes; the start cost is zero.",
         "1 <= n <= 30; at most 200 edges; integer costs range from 0 to 1,000,000,000. Parallel edges and cycles are allowed."],
        {"cpp": '''
            #include <nlohmann/json.hpp>
            #include <vector>
            #include <algorithm>
            using nlohmann::json;
            json solve(const json& data) {
                int n = data.at("n"), start = data.at("start");
                const long long infinity = 1000000;
                std::vector<long long> distance(n, infinity);
                std::vector<bool> used(n, false);
                distance[start] = 0;
                for (int step = 0; step < n; ++step) {
                    int next = -1;
                    for (int i = 0; i < n; ++i)
                        if (!used[i] && (next == -1 || distance[i] < distance[next])) next = i;
                    if (next == -1 || distance[next] == infinity) break;
                    used[next] = true;
                    for (const auto& edge : data.at("edges")) if (edge[0].get<int>() == next) {
                        int target = edge[1].get<int>();
                        distance[target] = std::min(distance[target], distance[next] + edge[2].get<long long>());
                    }
                }
                json result = json::array();
                for (auto cost : distance) result.push_back(cost == infinity ? json(nullptr) : json(cost));
                return result;
            }
        ''', "go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                n, start := int(data["n"].(float64)), int(data["start"].(float64))
                const infinity int64 = 1000000
                distance, used := make([]int64, n), make([]bool, n)
                for i := range distance { distance[i] = infinity }; distance[start] = 0
                for step := 0; step < n; step++ {
                    next := -1
                    for i := 0; i < n; i++ {
                        if !used[i] && (next == -1 || distance[i] < distance[next]) { next = i }
                    }
                    if next == -1 || distance[next] == infinity { break }; used[next] = true
                    for _, raw := range data["edges"].([]interface{}) {
                        edge := raw.([]interface{})
                        if int(edge[0].(float64)) == next {
                            target, cost := int(edge[1].(float64)), int64(edge[2].(float64))
                            if distance[next] + cost < distance[target] { distance[target] = distance[next] + cost }
                        }
                    }
                }
                result := make([]interface{}, n)
                for i, cost := range distance { if cost != infinity { result[i] = cost } }
                return result
            }
        '''},
        {"cpp": '''
            #include <nlohmann/json.hpp>
            #include <vector>
            #include <algorithm>
            using nlohmann::json;
            json solve(const json& data) {
                int n = data.at("n"), start = data.at("start");
                const long long infinity = 1LL << 60;
                std::vector<long long> distance(n, infinity);
                std::vector<bool> used(n, false);
                distance[start] = 0;
                for (int step = 0; step < n; ++step) {
                    int next = -1;
                    for (int i = 0; i < n; ++i)
                        if (!used[i] && (next == -1 || distance[i] < distance[next])) next = i;
                    if (next == -1 || distance[next] == infinity) break;
                    used[next] = true;
                    for (const auto& edge : data.at("edges")) if (edge[0].get<int>() == next) {
                        int target = edge[1].get<int>();
                        distance[target] = std::min(distance[target], distance[next] + edge[2].get<long long>());
                    }
                }
                json result = json::array();
                for (auto cost : distance) result.push_back(cost == infinity ? json(nullptr) : json(cost));
                return result;
            }
        ''', "go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                n, start := int(data["n"].(float64)), int(data["start"].(float64))
                const infinity int64 = 1 << 60
                distance, used := make([]int64, n), make([]bool, n)
                for i := range distance { distance[i] = infinity }; distance[start] = 0
                for step := 0; step < n; step++ {
                    next := -1
                    for i := 0; i < n; i++ {
                        if !used[i] && (next == -1 || distance[i] < distance[next]) { next = i }
                    }
                    if next == -1 || distance[next] == infinity { break }; used[next] = true
                    for _, raw := range data["edges"].([]interface{}) {
                        edge := raw.([]interface{})
                        if int(edge[0].(float64)) == next {
                            target, cost := int(edge[1].(float64)), int64(edge[2].(float64))
                            if distance[next] + cost < distance[target] { distance[target] = distance[next] + cost }
                        }
                    }
                }
                result := make([]interface{}, n)
                for i, cost := range distance { if cost != infinity { result[i] = cost } }
                return result
            }
        '''},
        [case("Short route", {"n": 3, "start": 0, "edges": [[0, 1, 4], [1, 2, 3], [0, 2, 10]]}, [0, 4, 7]),
         case("At the old sentinel", {"n": 3, "start": 0, "edges": [[0, 1, 1000000], [1, 2, 5]]}, [0, 1000000, 1000005]),
         case("Long chain", {"n": 4, "start": 0, "edges": [[0, 1, 1000000000], [1, 2, 1000000000], [2, 3, 1000000000]]}, [0, 1000000000, 2000000000, 3000000000], True),
         case("Disconnected and directed", {"n": 3, "start": 1, "edges": [[0, 1, 2]]}, [None, 0, None], True),
         case("Zero cycle and parallel edges", {"n": 3, "start": 0, "edges": [[0, 1, 7], [0, 1, 0], [1, 0, 0], [1, 2, 4]]}, [0, 0, 4], True),
         case("Single node", {"n": 1, "start": 0, "edges": []}, [0], True)],
        "A finite infinity must exceed every possible shortest path while leaving room for addition. With at most 30 nodes and nonnegative costs up to 10^9, 2^60 is safely above the required range in a 64-bit integer. This simple implementation scans all edges for each settled node: O(V² + VE) time, O(V) extra space.",
        ["Can a valid shortest path equal the initial distance?", "Bounding one edge is not enough; a path can contain several edges.",
         "Use 64-bit costs and a sentinel above every possible simple-path cost, without adding to an unreachable distance."], 25,
    ),
])

CATALOG.extend([
    problem(
        "refund-limit", "Small refunds exceed the payment",
        "Each partial refund is checked against the original payment, so several individually valid refunds can return more money than was captured. Enforce the remaining refundable balance after every decision.",
        "business", "medium", ["refunds", "invariants", "state"],
        ["Input.captured and input.refunded are integer cents with 0 <= refunded <= captured <= 1,000,000,000.",
         "Process at most 100 integer amounts in input.requests in order; amounts range from -1,000,000,000 to 1,000,000,000. Accept only positive amounts no larger than the currently unrefunded balance.",
         "Return {accepted: [booleans], state: {refunded: total including earlier refunds, remaining: captured - refunded}}. Rejected requests must not change state."],
        {"python": '''
            def solve(data):
                refunded, accepted = data["refunded"], []
                for amount in data["requests"]:
                    allowed = 0 < amount <= data["captured"]
                    accepted.append(allowed)
                    if allowed:
                        refunded += amount
                return {"accepted": accepted, "state": {"refunded": refunded, "remaining": data["captured"] - refunded}}
        ''', "java": '''
            import com.google.gson.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    long captured = data.get("captured").getAsLong(), refunded = data.get("refunded").getAsLong();
                    JsonArray accepted = new JsonArray();
                    for (JsonElement request : data.getAsJsonArray("requests")) {
                        long amount = request.getAsLong();
                        boolean allowed = amount > 0 && amount <= captured;
                        accepted.add(allowed);
                        if (allowed) refunded += amount;
                    }
                    JsonObject state = new JsonObject();
                    state.addProperty("refunded", refunded); state.addProperty("remaining", captured - refunded);
                    JsonObject result = new JsonObject(); result.add("accepted", accepted); result.add("state", state);
                    return result;
                }
            }
        '''},
        {"python": '''
            def solve(data):
                refunded, accepted = data["refunded"], []
                for amount in data["requests"]:
                    allowed = 0 < amount <= data["captured"] - refunded
                    accepted.append(allowed)
                    if allowed:
                        refunded += amount
                return {"accepted": accepted, "state": {"refunded": refunded, "remaining": data["captured"] - refunded}}
        ''', "java": '''
            import com.google.gson.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    long captured = data.get("captured").getAsLong(), refunded = data.get("refunded").getAsLong();
                    JsonArray accepted = new JsonArray();
                    for (JsonElement request : data.getAsJsonArray("requests")) {
                        long amount = request.getAsLong();
                        boolean allowed = amount > 0 && amount <= captured - refunded;
                        accepted.add(allowed);
                        if (allowed) refunded += amount;
                    }
                    JsonObject state = new JsonObject();
                    state.addProperty("refunded", refunded); state.addProperty("remaining", captured - refunded);
                    JsonObject result = new JsonObject(); result.add("accepted", accepted); result.add("state", state);
                    return result;
                }
            }
        '''},
        [case("One partial refund", {"captured": 100, "refunded": 0, "requests": [30]}, {"accepted": [True], "state": {"refunded": 30, "remaining": 70}}),
         case("Cumulative limit", {"captured": 100, "refunded": 0, "requests": [60, 60, 40]}, {"accepted": [True, False, True], "state": {"refunded": 100, "remaining": 0}}, assertions=[{"path": "state.remaining", "equals": 0}]),
         case("Earlier refunds", {"captured": 100, "refunded": 80, "requests": [30, 20]}, {"accepted": [False, True], "state": {"refunded": 100, "remaining": 0}}, True),
         case("Invalid requests preserve funds", {"captured": 100, "refunded": 20, "requests": [-10, 0, 81]}, {"accepted": [False, False, False], "state": {"refunded": 20, "remaining": 80}}, True, [{"path": "state.refunded", "equals": 20}]),
         case("No captured funds", {"captured": 0, "refunded": 0, "requests": [1]}, {"accepted": [False], "state": {"refunded": 0, "remaining": 0}}, True),
         case("No new requests", {"captured": 100, "refunded": 10, "requests": []}, {"accepted": [], "state": {"refunded": 10, "remaining": 90}}, True)],
        "Validate each request against captured minus the running refunded total, then update only for accepted requests. Reusing the original limit ignores prior decisions. This sequential state model requires an atomic balance check/update when backed by a concurrent database. Time O(n), output space O(n).",
        ["Which balance changes after the first refund?", "Earlier refunds include both stored history and accepted requests from this batch.",
         "Accept only 0 < amount <= captured - refunded, then increment refunded only on success."], 18,
    ),
    problem(
        "reservation-expiry", "Expired holds still block checkout",
        "Temporary stock reservations never leave the active hold list. Once enough carts are abandoned, inventory appears sold out forever even though their hold deadlines have passed.",
        "business", "hard", ["expiration", "inventory", "state"],
        ["Input has capacity, a fixed integer now, existing holds {id, quantity, expires_at}, and requests {id, quantity, ttl}.",
         "Discard holds with expires_at <= now before processing requests. Existing hold IDs are unique, quantities are positive, and their total is at most capacity.",
         "Accept a request only if its ID is not currently held, quantity and ttl are positive, and quantity fits available capacity. New expiry is now + ttl.",
         "Return {accepted: [accepted IDs], state: {available, holds}}. Keep surviving holds in original order and append successful requests in order. All numbers are integers of magnitude at most 1,000,000."],
        {"python": '''
            def solve(data):
                holds = list(data["holds"])
                available = data["capacity"] - sum(hold["quantity"] for hold in holds)
                seen, accepted = {hold["id"] for hold in holds}, []
                for request in data["requests"]:
                    if request["id"] in seen or request["quantity"] <= 0 or request["ttl"] <= 0 or request["quantity"] > available:
                        continue
                    available -= request["quantity"]
                    seen.add(request["id"])
                    accepted.append(request["id"])
                    holds.append({"id": request["id"], "quantity": request["quantity"], "expires_at": data["now"] + request["ttl"]})
                return {"accepted": accepted, "state": {"available": available, "holds": holds}}
        ''', "javascript": '''
            function solve(data) {
                const holds = [...data.holds];
                let available = data.capacity - holds.reduce((sum, hold) => sum + hold.quantity, 0);
                const seen = new Set(holds.map(hold => hold.id)), accepted = [];
                for (const request of data.requests) {
                    if (seen.has(request.id) || request.quantity <= 0 || request.ttl <= 0 || request.quantity > available) continue;
                    available -= request.quantity; seen.add(request.id); accepted.push(request.id);
                    holds.push({ id: request.id, quantity: request.quantity, expires_at: data.now + request.ttl });
                }
                return { accepted, state: { available, holds } };
            }
            module.exports = { solve };
        '''},
        {"python": '''
            def solve(data):
                holds = [hold for hold in data["holds"] if hold["expires_at"] > data["now"]]
                available = data["capacity"] - sum(hold["quantity"] for hold in holds)
                seen, accepted = {hold["id"] for hold in holds}, []
                for request in data["requests"]:
                    if request["id"] in seen or request["quantity"] <= 0 or request["ttl"] <= 0 or request["quantity"] > available:
                        continue
                    available -= request["quantity"]
                    seen.add(request["id"])
                    accepted.append(request["id"])
                    holds.append({"id": request["id"], "quantity": request["quantity"], "expires_at": data["now"] + request["ttl"]})
                return {"accepted": accepted, "state": {"available": available, "holds": holds}}
        ''', "javascript": '''
            function solve(data) {
                const holds = data.holds.filter(hold => hold.expires_at > data.now);
                let available = data.capacity - holds.reduce((sum, hold) => sum + hold.quantity, 0);
                const seen = new Set(holds.map(hold => hold.id)), accepted = [];
                for (const request of data.requests) {
                    if (seen.has(request.id) || request.quantity <= 0 || request.ttl <= 0 || request.quantity > available) continue;
                    available -= request.quantity; seen.add(request.id); accepted.push(request.id);
                    holds.push({ id: request.id, quantity: request.quantity, expires_at: data.now + request.ttl });
                }
                return { accepted, state: { available, holds } };
            }
            module.exports = { solve };
        '''},
        [case("Space alongside an active hold", {"capacity": 10, "now": 100, "holds": [{"id": "a", "quantity": 3, "expires_at": 200}], "requests": [{"id": "b", "quantity": 2, "ttl": 50}]},
              {"accepted": ["b"], "state": {"available": 5, "holds": [{"id": "a", "quantity": 3, "expires_at": 200}, {"id": "b", "quantity": 2, "expires_at": 150}]}}),
         case("Expiry at the current instant", {"capacity": 5, "now": 100, "holds": [{"id": "a", "quantity": 4, "expires_at": 100}], "requests": [{"id": "b", "quantity": 3, "ttl": 10}]},
              {"accepted": ["b"], "state": {"available": 2, "holds": [{"id": "b", "quantity": 3, "expires_at": 110}]}}, assertions=[{"path": "state.available", "equals": 2}]),
         case("Reuse an expired ID", {"capacity": 4, "now": 100, "holds": [{"id": "a", "quantity": 4, "expires_at": 99}], "requests": [{"id": "a", "quantity": 2, "ttl": 10}]},
              {"accepted": ["a"], "state": {"available": 2, "holds": [{"id": "a", "quantity": 2, "expires_at": 110}]}}, True),
         case("Reject without consuming capacity or IDs", {"capacity": 3, "now": 0, "holds": [], "requests": [{"id": "a", "quantity": 1, "ttl": 0}, {"id": "a", "quantity": -1, "ttl": 3}, {"id": "a", "quantity": 4, "ttl": 3}, {"id": "a", "quantity": 2, "ttl": 3}, {"id": "a", "quantity": 1, "ttl": 3}]},
              {"accepted": ["a"], "state": {"available": 1, "holds": [{"id": "a", "quantity": 2, "expires_at": 3}]}}, True),
         case("Clean up without new requests", {"capacity": 5, "now": 10, "holds": [{"id": "old", "quantity": 2, "expires_at": 9}, {"id": "live", "quantity": 1, "expires_at": 11}], "requests": []},
              {"accepted": [], "state": {"available": 4, "holds": [{"id": "live", "quantity": 1, "expires_at": 11}]}}, True)],
        "Expiry affects both available stock and which IDs are active. Filter expired holds first, then derive both capacity and membership from the surviving set. Validate requests before committing any changes. A production reservation service must serialize expiry and allocation against shared stock. Time and space O(holds + requests).",
        ["At exactly expires_at, does a hold still own its inventory?", "Removing only an ID or only its quantity leaves the other state inconsistent.",
         "Keep holds with expires_at > now, derive available stock and active IDs from them, then process requests."], 25,
    ),
])

CATALOG.extend([
    problem(
        "exclusive-coupons", "One offer turns into three discounts",
        "Checkout advertises one promotion per order, but its pricing loop adds all eligible discounts together. Select the single best offer and apply the eligibility and tie rules consistently.",
        "business", "medium", ["pricing", "promotions", "selection"],
        ["Input has a nonnegative integer subtotal and coupons {code, min_spend, discount}, all amounts in integer cents.",
         "A coupon is eligible when subtotal >= min_spend. Apply at most one coupon with positive savings; its savings are min(discount, subtotal).",
         "Choose the greatest savings, breaking ties by ascending ASCII code. Codes are unique; amounts are nonnegative and at most 1,000,000.",
         "Return {coupon: code or null, discount: savings, total: subtotal - savings}. With no positive eligible savings, return null, 0, and subtotal."],
        {"python": '''
            def solve(data):
                subtotal = data["subtotal"]
                eligible = sorted((coupon for coupon in data["coupons"] if coupon["min_spend"] <= subtotal and min(coupon["discount"], subtotal) > 0),
                                  key=lambda coupon: (-min(coupon["discount"], subtotal), coupon["code"]))
                discount = min(subtotal, sum(coupon["discount"] for coupon in eligible))
                return {"coupon": eligible[0]["code"] if eligible else None, "discount": discount, "total": subtotal - discount}
        ''', "javascript": '''
            function solve(data) {
                const eligible = data.coupons.filter(coupon => coupon.min_spend <= data.subtotal && Math.min(coupon.discount, data.subtotal) > 0)
                    .sort((a, b) => Math.min(b.discount, data.subtotal) - Math.min(a.discount, data.subtotal) || (a.code < b.code ? -1 : a.code > b.code ? 1 : 0));
                const discount = Math.min(data.subtotal, eligible.reduce((sum, coupon) => sum + coupon.discount, 0));
                return { coupon: eligible[0]?.code ?? null, discount, total: data.subtotal - discount };
            }
            module.exports = { solve };
        '''},
        {"python": '''
            def solve(data):
                subtotal = data["subtotal"]
                chosen, discount = None, 0
                for coupon in data["coupons"]:
                    saving = min(coupon["discount"], subtotal)
                    if coupon["min_spend"] <= subtotal and saving > 0:
                        if saving > discount or (saving == discount and (chosen is None or coupon["code"] < chosen)):
                            chosen, discount = coupon["code"], saving
                return {"coupon": chosen, "discount": discount, "total": subtotal - discount}
        ''', "javascript": '''
            function solve(data) {
                let chosen = null, discount = 0;
                for (const coupon of data.coupons) {
                    const saving = Math.min(coupon.discount, data.subtotal);
                    if (coupon.min_spend <= data.subtotal && saving > 0 &&
                        (saving > discount || (saving === discount && (chosen === null || coupon.code < chosen)))) {
                        chosen = coupon.code; discount = saving;
                    }
                }
                return { coupon: chosen, discount, total: data.subtotal - discount };
            }
            module.exports = { solve };
        '''},
        [case("Single offer", {"subtotal": 1000, "coupons": [{"code": "SAVE", "min_spend": 500, "discount": 100}]}, {"coupon": "SAVE", "discount": 100, "total": 900}),
         case("Offers must not stack", {"subtotal": 1000, "coupons": [{"code": "A", "min_spend": 0, "discount": 200}, {"code": "B", "min_spend": 0, "discount": 300}]}, {"coupon": "B", "discount": 300, "total": 700}),
         case("Eligibility uses original subtotal", {"subtotal": 1000, "coupons": [{"code": "A", "min_spend": 1001, "discount": 800}, {"code": "B", "min_spend": 1000, "discount": 300}]}, {"coupon": "B", "discount": 300, "total": 700}, True),
         case("Tie after capping savings", {"subtotal": 100, "coupons": [{"code": "Z", "min_spend": 0, "discount": 500}, {"code": "A", "min_spend": 0, "discount": 200}]}, {"coupon": "A", "discount": 100, "total": 0}, True),
         case("No effective offer", {"subtotal": 100, "coupons": [{"code": "ZERO", "min_spend": 0, "discount": 0}, {"code": "LATER", "min_spend": 101, "discount": 80}]}, {"coupon": None, "discount": 0, "total": 100}, True),
         case("Empty basket", {"subtotal": 0, "coupons": [{"code": "FREE", "min_spend": 0, "discount": 500}]}, {"coupon": None, "discount": 0, "total": 0}, True),
         case("No offers", {"subtotal": 250, "coupons": []}, {"coupon": None, "discount": 0, "total": 250}, True)],
        "Evaluate every coupon against the unchanged subtotal, compare its capped savings, and retain only the best positive candidate. Break ties by code after capping, since different face values can produce equal savings. One pass takes O(n) time and O(1) extra space.",
        ["Does eligibility allow combining offers or only choosing one?", "Compare actual savings after capping at the subtotal.",
         "Track one best eligible coupon by savings, then code; apply only that coupon's discount."], 18,
    ),
    problem(
        "approval-quorum", "Repeated votes approve a release",
        "A release gate counts approval events rather than eligible reviewers. Retries, outsiders, and a reviewer changing their mind can all produce an approval without a real majority.",
        "business", "hard", ["authorization", "deduplication", "quorum"],
        ["Input.eligible lists unique reviewer IDs. Input.votes is an ordered list of {id, approve: boolean} events.",
         "Only eligible reviewers count, once each, using their latest vote. Missing votes are not approvals.",
         "A release needs floor(eligible count / 2) + 1 approvals. An empty eligible list can never approve.",
         "Return {approved: boolean, state: {approvals: count, required: threshold}}. There are at most 100 reviewers and 500 events."],
        {"java": '''
            import com.google.gson.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    int approvals = 0, required = data.getAsJsonArray("eligible").size() / 2 + 1;
                    for (JsonElement value : data.getAsJsonArray("votes")) if (value.getAsJsonObject().get("approve").getAsBoolean()) approvals++;
                    JsonObject state = new JsonObject(); state.addProperty("approvals", approvals); state.addProperty("required", required);
                    JsonObject result = new JsonObject(); result.addProperty("approved", approvals >= required); result.add("state", state);
                    return result;
                }
            }
        ''', "go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                approvals, required := 0, len(data["eligible"].([]interface{}))/2 + 1
                for _, raw := range data["votes"].([]interface{}) {
                    if raw.(map[string]interface{})["approve"].(bool) { approvals++ }
                }
                return map[string]interface{}{"approved": approvals >= required, "state": map[string]int{"approvals": approvals, "required": required}}
            }
        '''},
        {"java": '''
            import com.google.gson.*;
            import java.util.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    Set<String> eligible = new HashSet<>();
                    for (JsonElement id : data.getAsJsonArray("eligible")) eligible.add(id.getAsString());
                    Map<String, Boolean> latest = new HashMap<>();
                    for (JsonElement value : data.getAsJsonArray("votes")) {
                        JsonObject vote = value.getAsJsonObject();
                        String id = vote.get("id").getAsString();
                        if (eligible.contains(id)) latest.put(id, vote.get("approve").getAsBoolean());
                    }
                    int approvals = 0, required = eligible.size() / 2 + 1;
                    for (boolean vote : latest.values()) if (vote) approvals++;
                    JsonObject state = new JsonObject(); state.addProperty("approvals", approvals); state.addProperty("required", required);
                    JsonObject result = new JsonObject(); result.addProperty("approved", approvals >= required); result.add("state", state);
                    return result;
                }
            }
        ''', "go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                eligible, latest := make(map[string]bool), make(map[string]bool)
                for _, id := range data["eligible"].([]interface{}) { eligible[id.(string)] = true }
                for _, raw := range data["votes"].([]interface{}) {
                    vote := raw.(map[string]interface{}); id := vote["id"].(string)
                    if eligible[id] { latest[id] = vote["approve"].(bool) }
                }
                approvals, required := 0, len(eligible)/2 + 1
                for _, vote := range latest { if vote { approvals++ } }
                return map[string]interface{}{"approved": approvals >= required, "state": map[string]int{"approvals": approvals, "required": required}}
            }
        '''},
        [case("Actual majority", {"eligible": ["a", "b", "c"], "votes": [{"id": "a", "approve": True}, {"id": "b", "approve": True}]}, {"approved": True, "state": {"approvals": 2, "required": 2}}),
         case("Repeated approval", {"eligible": ["a", "b", "c"], "votes": [{"id": "a", "approve": True}, {"id": "a", "approve": True}]}, {"approved": False, "state": {"approvals": 1, "required": 2}}, assertions=[{"path": "state.approvals", "equals": 1}]),
         case("Outsider vote", {"eligible": ["a"], "votes": [{"id": "outsider", "approve": True}]}, {"approved": False, "state": {"approvals": 0, "required": 1}}, True),
         case("Approval withdrawn", {"eligible": ["a", "b", "c"], "votes": [{"id": "a", "approve": True}, {"id": "b", "approve": True}, {"id": "a", "approve": False}]}, {"approved": False, "state": {"approvals": 1, "required": 2}}, True),
         case("Tie is insufficient", {"eligible": ["a", "b"], "votes": [{"id": "a", "approve": True}]}, {"approved": False, "state": {"approvals": 1, "required": 2}}, True),
         case("No eligible reviewers", {"eligible": [], "votes": [{"id": "a", "approve": True}]}, {"approved": False, "state": {"approvals": 0, "required": 1}}, True),
         case("Reviewer changes to approval", {"eligible": ["a"], "votes": [{"id": "a", "approve": False}, {"id": "a", "approve": True}]}, {"approved": True, "state": {"approvals": 1, "required": 1}}, True)],
        "Filter by the eligible set and overwrite each reviewer's stored vote as events arrive. Count the final true values, then compare with a strict majority of all eligible reviewers, including those who did not vote. Expected time O(reviewers + events), space O(reviewers).",
        ["Does the current counter measure people or events?", "A later rejection must replace the same person's earlier approval.",
         "Store the latest vote keyed by eligible reviewer ID, count true values, and compare with floor(N / 2) + 1."], 25,
    ),
    problem(
        "shipment-transitions", "A delivered order goes backwards",
        "A shipment consumer assigns every incoming status directly to the order. Duplicate and out-of-order events can reopen cancelled orders or move delivered parcels back into transit.",
        "business", "hard", ["state-machine", "events", "workflow"],
        ["Input.state is created, paid, shipped, delivered, or cancelled; input.events is an ordered list of proposed status strings.",
         "Allowed transitions: created -> paid or cancelled; paid -> shipped or cancelled; shipped -> delivered. Delivered and cancelled are terminal.",
         "Ignore duplicate, unknown, and otherwise invalid transitions without changing state. Count only allowed transitions as applied.",
         "Return {state: {status}, applied: count, ignored: count}. There are at most 100 events."],
        {"python": '''
            def solve(data):
                status, applied = data["state"], 0
                for event in data["events"]:
                    status = event
                    applied += 1
                return {"state": {"status": status}, "applied": applied, "ignored": 0}
        ''', "javascript": '''
            function solve(data) {
                let status = data.state, applied = 0;
                for (const event of data.events) { status = event; applied++; }
                return { state: { status }, applied, ignored: 0 };
            }
            module.exports = { solve };
        '''},
        {"python": '''
            def solve(data):
                allowed = {"created": {"paid", "cancelled"}, "paid": {"shipped", "cancelled"},
                           "shipped": {"delivered"}, "delivered": set(), "cancelled": set()}
                status, applied = data["state"], 0
                for event in data["events"]:
                    if event in allowed[status]:
                        status = event
                        applied += 1
                return {"state": {"status": status}, "applied": applied, "ignored": len(data["events"]) - applied}
        ''', "javascript": '''
            function solve(data) {
                const allowed = { created: ['paid', 'cancelled'], paid: ['shipped', 'cancelled'],
                    shipped: ['delivered'], delivered: [], cancelled: [] };
                let status = data.state, applied = 0;
                for (const event of data.events) {
                    if (allowed[status].includes(event)) { status = event; applied++; }
                }
                return { state: { status }, applied, ignored: data.events.length - applied };
            }
            module.exports = { solve };
        '''},
        [case("Normal fulfillment", {"state": "created", "events": ["paid", "shipped", "delivered"]}, {"state": {"status": "delivered"}, "applied": 3, "ignored": 0}),
         case("Late transit event", {"state": "shipped", "events": ["delivered", "shipped"]}, {"state": {"status": "delivered"}, "applied": 1, "ignored": 1}, assertions=[{"path": "state.status", "equals": "delivered"}]),
         case("Cancelled orders stay closed", {"state": "created", "events": ["cancelled", "paid", "shipped"]}, {"state": {"status": "cancelled"}, "applied": 1, "ignored": 2}, True),
         case("Unknown and duplicate events", {"state": "paid", "events": ["paid", "unknown", "shipped", "shipped", "cancelled", "delivered"]}, {"state": {"status": "delivered"}, "applied": 2, "ignored": 4}, True),
         case("Cannot skip payment", {"state": "created", "events": ["shipped", "paid", "delivered"]}, {"state": {"status": "paid"}, "applied": 1, "ignored": 2}, True),
         case("No events", {"state": "cancelled", "events": []}, {"state": {"status": "cancelled"}, "applied": 0, "ignored": 0}, True),
         case("Cancel before shipment", {"state": "paid", "events": ["cancelled"]}, {"state": {"status": "cancelled"}, "applied": 1, "ignored": 0}, True)],
        "Represent allowed transitions explicitly and validate each event against the current status before updating it. Terminal states have no outgoing transitions. Ignoring an event also means it cannot affect the validation of the next event. Time O(events), extra space O(1) for this fixed state machine.",
        ["Does every known status make sense after every other status?", "Terminal states should have no outgoing transitions.",
         "Use an allowed-transition table, apply only matching edges from the current state, and count all other events as ignored."], 23,
    ),
])


# Problems 41–55: runtime failures.
CATALOG.extend([
    problem(
        "missing-counter-key", "The first event crashes the counter",
        "A telemetry counter increments a dictionary entry before that event type has ever been seen. Let new event types start at zero while retaining existing counts.",
        "runtime", "easy", ["dictionaries", "initialization", "events"],
        ["Input.counts maps string event types to nonnegative integer counts; input.events lists event types.",
         "Return the updated counts, adding one for each event. Preserve existing entries, including zero counts.",
         "There are at most 100 events. Event types may be empty strings."],
        {"python": '''
            def solve(data):
                counts = data["counts"].copy()
                for event in data["events"]:
                    counts[event] += 1
                return counts
        '''},
        {"python": '''
            def solve(data):
                counts = data["counts"].copy()
                for event in data["events"]:
                    counts[event] = counts.get(event, 0) + 1
                return counts
        '''},
        [case("Known event", {"counts": {"click": 2}, "events": ["click"]}, {"click": 3}),
         case("First event", {"counts": {}, "events": ["open"]}, {"open": 1}),
         case("Repeated new event", {"counts": {}, "events": ["x", "x", "x"]}, {"x": 3}, True),
         case("Preserve idle counter", {"counts": {"idle": 0}, "events": []}, {"idle": 0}, True),
         case("Mixed types", {"counts": {"a": 4}, "events": ["b", "a", "b"]}, {"a": 5, "b": 2}, True),
         case("Empty event name", {"counts": {}, "events": ["", ""]}, {"": 2}, True)],
        "Read an absent counter as zero before incrementing it. Copying the initial dictionary also retains counters with no new events. Expected time O(counts + events), space O(distinct types).",
        ["What value exists before a type's first event?", "The increment reads the key before assigning it.",
         "Use counts.get(event, 0) + 1 for the new value."], 8,
    ),
    problem(
        "empty-reduce", "An idle day breaks the report",
        "A JavaScript report uses reduce to total job durations. Busy days work, but a day without jobs throws before a report can be returned.",
        "runtime", "easy", ["reduce", "empty-input", "javascript"],
        ["Return the sum of all integer milliseconds in input.durations.",
         "An empty list returns 0. Values are nonnegative and at most 1,000,000; at most 100 values."],
        {"javascript": '''
            function solve(data) {
              return data.durations.reduce((total, duration) => total + duration);
            }
            module.exports = { solve };
        '''},
        {"javascript": '''
            function solve(data) {
              return data.durations.reduce((total, duration) => total + duration, 0);
            }
            module.exports = { solve };
        '''},
        [case("Busy day", {"durations": [20, 30, 50]}, 100),
         case("Idle day", {"durations": []}, 0),
         case("One job", {"durations": [17]}, 17, True),
         case("Zero durations", {"durations": [0, 0]}, 0, True),
         case("Mixed durations", {"durations": [0, 4, 0, 6]}, 10, True),
         case("Long jobs", {"durations": [1000000, 1000000]}, 2000000, True)],
        "Supply the additive identity, zero, as reduce's initial accumulator. The same operation then covers empty, singleton, and longer collections. Time O(n), space O(1).",
        ["How does reduce obtain its initial accumulator?", "An empty list has no first element to use.",
         "Pass zero as the second argument to reduce."], 8,
    ),
    problem(
        "unsafe-integer-token", "One bad token stops the import",
        "A Java importer assumes every field fits in an integer. A malformed or oversized field aborts the entire batch instead of producing a missing-value marker.",
        "runtime", "medium", ["parsing", "exceptions", "validation"],
        ["For every string in input.tokens, return its signed 32-bit integer value or null if invalid.",
         "Valid syntax is an optional ASCII + or - followed by one or more ASCII digits, with no whitespace. Leading zeros are allowed.",
         "Reject values outside -2147483648 through 2147483647. There are at most 100 tokens of at most 30 characters."],
        {"java": '''
            import com.google.gson.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    JsonArray result = new JsonArray();
                    for (JsonElement token : data.getAsJsonArray("tokens"))
                        result.add(Integer.parseInt(token.getAsString()));
                    return result;
                }
            }
        '''},
        {"java": '''
            import com.google.gson.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    JsonArray result = new JsonArray();
                    for (JsonElement token : data.getAsJsonArray("tokens")) {
                        String text = token.getAsString();
                        if (!text.matches("[+-]?[0-9]+")) { result.add(JsonNull.INSTANCE); continue; }
                        try { result.add(Integer.parseInt(text)); }
                        catch (NumberFormatException error) { result.add(JsonNull.INSTANCE); }
                    }
                    return result;
                }
            }
        '''},
        [case("Valid integers", {"tokens": ["12", "-3", "+4"]}, [12, -3, 4]),
         case("Bad field in a batch", {"tokens": ["1", "oops", "2"]}, [1, None, 2]),
         case("Limits", {"tokens": ["-2147483648", "2147483647", "2147483648", "-2147483649"]}, [-2147483648, 2147483647, None, None], True),
         case("Strict syntax", {"tokens": ["", "+", " 3", "3 ", "1.0", "1e2", "１２"]}, [None] * 7, True),
         case("Zeros", {"tokens": ["0009", "-0", "+000"]}, [9, 0, 0], True),
         case("No tokens", {"tokens": []}, [], True)],
        "Check the specified ASCII grammar and catch range failures for each token individually. A failed token must not discard successful values before or after it. Time O(total characters), output space O(tokens).",
        ["Which conversion failures can escape the loop?", "Syntax and numeric range are separate checks.",
         "Require [+-]?[0-9]+, parse inside a per-token try/catch, and append JSON null on failure."], 15,
    ),
    problem(
        "missing-list-target", "The search that throws on a miss",
        "A support tool looks up the first occurrence of an incident code. Its missing-code path raises an exception instead of returning the documented sentinel.",
        "runtime", "easy", ["search", "exceptions", "sentinels"],
        ["Return the first zero-based index of input.target in input.codes, or -1 when absent.",
         "Codes and target are strings; duplicates and empty strings are valid. At most 1,000 codes."],
        {"python": 'def solve(data):\n    return data["codes"].index(data["target"])'},
        {"python": '''
            def solve(data):
                for index, value in enumerate(data["codes"]):
                    if value == data["target"]:
                        return index
                return -1
        '''},
        [case("Known incident", {"codes": ["A", "B"], "target": "B"}, 1),
         case("Unknown incident", {"codes": ["A"], "target": "Z"}, -1),
         case("Empty archive", {"codes": [], "target": "A"}, -1, True),
         case("First duplicate", {"codes": ["B", "A", "B"], "target": "B"}, 0, True),
         case("Empty code", {"codes": ["A", ""], "target": ""}, 1, True),
         case("Case sensitive", {"codes": ["abc"], "target": "ABC"}, -1, True)],
        "Either catch the missing-value exception or scan with an explicit fallback. Returning on the first match preserves duplicate semantics. Time O(n), space O(1).",
        ["Does list.index return a sentinel on failure?", "A missing item is an ordinary result in this contract.",
         "Return on the first matching value and return -1 after the loop."], 8,
    ),
    problem(
        "ragged-grid-access", "A short row crashes the preview",
        "A table preview assumes every row has the same width. Sparse rows and invalid coordinates crash its cell lookup.",
        "runtime", "medium", ["bounds", "ragged-arrays", "cpp"],
        ["Input.rows is a list of integer lists of possibly different lengths. Input.queries contains [row, col] integer coordinates.",
         "Return one cell value per query, or null if either coordinate is negative or outside that particular row.",
         "There are at most 100 rows, cells per row, and queries; cell values are between -1,000,000 and 1,000,000."],
        {"cpp": '''
            #include <nlohmann/json.hpp>
            using nlohmann::json;
            json solve(const json& data) {
                json result = json::array();
                for (const auto& query : data.at("queries"))
                    result.push_back(data.at("rows").at(query.at(0).get<int>()).at(query.at(1).get<int>()));
                return result;
            }
        '''},
        {"cpp": '''
            #include <nlohmann/json.hpp>
            using nlohmann::json;
            json solve(const json& data) {
                const auto& rows = data.at("rows");
                json result = json::array();
                for (const auto& query : data.at("queries")) {
                    int r = query.at(0).get<int>(), c = query.at(1).get<int>();
                    if (r < 0 || r >= static_cast<int>(rows.size()) || c < 0 ||
                        c >= static_cast<int>(rows.at(r).size())) result.push_back(nullptr);
                    else result.push_back(rows.at(r).at(c));
                }
                return result;
            }
        '''},
        [case("Existing cells", {"rows": [[1, 2], [3]], "queries": [[0, 1], [1, 0]]}, [2, 3]),
         case("Short second row", {"rows": [[1, 2], [3]], "queries": [[1, 1]]}, [None]),
         case("Negative coordinates", {"rows": [[9]], "queries": [[-1, 0], [0, -1]]}, [None, None], True),
         case("Empty rows", {"rows": [[], [0]], "queries": [[0, 0], [1, 0], [2, 0]]}, [None, 0, None], True),
         case("No table", {"rows": [], "queries": [[0, 0]]}, [None], True),
         case("No lookups", {"rows": [[-4]], "queries": []}, [], True)],
        "Validate the row before reading its length, then validate the column against that row. Checking against the first row's width is insufficient for a ragged table. Time O(queries), output space O(queries).",
        ["Which row determines a column's valid range?", "Negative coordinates must be rejected before unsigned index conversion.",
         "Short-circuit row validation, then check the column against rows[r].size()."], 12,
    ),
    problem(
        "null-tag-list", "An untagged article breaks the feed",
        "Articles without a tag list make the feed formatter call map on null. The export still needs one formatted tag list for every article.",
        "runtime", "easy", ["null", "arrays", "formatting"],
        ["Input.articles is a list of objects whose tags field is missing, null, or an array of ASCII strings.",
         "Return an array of arrays with every tag uppercased. Missing or null tags produce an empty array.",
         "Preserve article order, tag order, duplicates, and empty tags. At most 100 articles and tags per article."],
        {"javascript": '''
            function solve(data) {
              return data.articles.map(article => article.tags.map(tag => tag.toUpperCase()));
            }
            module.exports = { solve };
        '''},
        {"javascript": '''
            function solve(data) {
              return data.articles.map(article => (article.tags ?? []).map(tag => tag.toUpperCase()));
            }
            module.exports = { solve };
        '''},
        [case("Tagged article", {"articles": [{"tags": ["news", "dev"]}]}, [["NEWS", "DEV"]]),
         case("Null tags", {"articles": [{"tags": None}]}, [[]]),
         case("Missing tags", {"articles": [{}]}, [[]], True),
         case("Mixed articles", {"articles": [{}, {"tags": ["a"]}, {"tags": []}]}, [[], ["A"], []], True),
         case("Preserve tags", {"articles": [{"tags": ["", "x", "x"]}]}, [["", "X", "X"]], True),
         case("No articles", {"articles": []}, [], True)],
        "Normalize only the optional list before mapping it. Nullish coalescing supplies an empty array for missing and null tags while keeping article positions intact. Time O(total tag characters + articles), space proportional to the output.",
        ["Which values can article.tags hold?", "Skipping an untagged article would change the output's shape.",
         "Map every article and use (article.tags ?? []) for its tag list."], 8,
    ),
    problem(
        "stale-discard", "A repeated unsubscribe crashes cleanup",
        "An unsubscribe batch can contain users who already left. Removing those users from a set raises an exception and prevents later unsubscribes from being processed.",
        "runtime", "easy", ["sets", "idempotency", "cleanup"],
        ["Input.members and input.remove are lists of lowercase ASCII user IDs.",
         "Remove every requested ID if present; missing and repeated removals are harmless.",
         "Return the remaining unique IDs sorted alphabetically. Each list contains at most 100 entries."],
        {"python": '''
            def solve(data):
                members = set(data["members"])
                for user in data["remove"]:
                    members.remove(user)
                return sorted(members)
        '''},
        {"python": '''
            def solve(data):
                members = set(data["members"])
                for user in data["remove"]:
                    members.discard(user)
                return sorted(members)
        '''},
        [case("Existing member", {"members": ["a", "b"], "remove": ["a"]}, ["b"]),
         case("Already gone", {"members": ["b"], "remove": ["a"]}, ["b"]),
         case("Repeated removal", {"members": ["a", "b"], "remove": ["a", "a"]}, ["b"], True),
         case("Empty membership", {"members": [], "remove": ["x"]}, [], True),
         case("Unique sorted output", {"members": ["c", "a", "c", "b"], "remove": []}, ["a", "b", "c"], True),
         case("Continue after a miss", {"members": ["a", "b"], "remove": ["x", "b"]}, ["a"], True)],
        "Use the set operation that tolerates absence. Handling missing IDs inside the loop preserves the rest of the batch and makes retries harmless. Expected time O(members + removals + k log k) for k surviving IDs, space O(members).",
        ["Should a second unsubscribe differ from the first?", "Set removal methods have different missing-item behavior.",
         "Use discard for each requested ID, then sort the remaining set."], 8,
    ),
    problem(
        "optional-go-count", "The optional count panics",
        "A Go endpoint directly asserts the type of an optional JSON number. Requests without the field panic instead of using the documented default.",
        "runtime", "easy", ["go", "type-assertions", "optional-fields"],
        ["Input.count is missing, null, or an integer between -1,000,000 and 1,000,000.",
         "Return twice count, using zero when count is missing or null. Negative values are valid."],
        {"go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                return int(data["count"].(float64)) * 2
            }
        '''},
        {"go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                count, ok := data["count"].(float64)
                if !ok { return 0 }
                return int(count) * 2
            }
        '''},
        [case("Present count", {"count": 7}, 14), case("Missing count", {}, 0),
         case("Null count", {"count": None}, 0, True), case("Zero count", {"count": 0}, 0, True),
         case("Negative adjustment", {"count": -9}, -18, True), case("Upper bound", {"count": 1000000}, 2000000, True)],
        "A JSON object lookup can yield a nil interface. Use the comma-ok type assertion to distinguish a number from an absent or null value before converting it. Time and space O(1).",
        ["What does the interface contain when the key is absent?", "A one-result type assertion panics when the dynamic type differs.",
         "Use count, ok := data[\"count\"].(float64), returning zero when ok is false."], 10,
    ),
])

CATALOG.extend([
    problem(
        "empty-stack-peek", "A preview with nothing on the stack",
        "A Java history preview reads the most recent item even when the stack is empty. A preview must be safe and must never consume the item it displays.",
        "runtime", "easy", ["stack", "empty-input", "java"],
        ["Process input.operations: {op: 'push', value: integer} appends to a stack; {op: 'peek'} observes its top.",
         "Return one value per peek, using null for an empty stack. Peeking does not remove an item.",
         "The stack starts empty. At most 100 operations; integer values have magnitude at most 1,000,000."],
        {"java": '''
            import com.google.gson.*;
            import java.util.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    Deque<Integer> stack = new ArrayDeque<>();
                    JsonArray result = new JsonArray();
                    for (JsonElement raw : data.getAsJsonArray("operations")) {
                        JsonObject op = raw.getAsJsonObject();
                        if (op.get("op").getAsString().equals("push")) stack.push(op.get("value").getAsInt());
                        else result.add(stack.element());
                    }
                    return result;
                }
            }
        '''},
        {"java": '''
            import com.google.gson.*;
            import java.util.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    Deque<Integer> stack = new ArrayDeque<>();
                    JsonArray result = new JsonArray();
                    for (JsonElement raw : data.getAsJsonArray("operations")) {
                        JsonObject op = raw.getAsJsonObject();
                        if (op.get("op").getAsString().equals("push")) stack.push(op.get("value").getAsInt());
                        else {
                            Integer value = stack.peek();
                            result.add(value == null ? JsonNull.INSTANCE : new JsonPrimitive(value));
                        }
                    }
                    return result;
                }
            }
        '''},
        [case("Preview a value", {"operations": [{"op": "push", "value": 3}, {"op": "peek"}]}, [3]),
         case("Empty preview", {"operations": [{"op": "peek"}]}, [None]),
         case("Non-destructive preview", {"operations": [{"op": "push", "value": 0}, {"op": "peek"}, {"op": "peek"}]}, [0, 0], True),
         case("Most recent value", {"operations": [{"op": "push", "value": 1}, {"op": "push", "value": -2}, {"op": "peek"}]}, [-2], True),
         case("Recover after empty", {"operations": [{"op": "peek"}, {"op": "push", "value": 4}, {"op": "peek"}]}, [None, 4], True),
         case("No operations", {"operations": []}, [], True)],
        "Deque.peek returns null on an empty deque, whereas element throws. Convert that null to JSON null and keep the observation separate from removal. Time O(operations), space O(pushes + peeks).",
        ["Which deque observation method tolerates an empty collection?", "Popping instead would change the next preview.",
         "Use peek and append JsonNull.INSTANCE if it returns null."], 10,
    ),
    problem(
        "damaged-utf8", "A damaged byte hides the whole message",
        "A log viewer rejects an entire byte stream when one UTF-8 sequence is damaged. It should display the readable parts and replacement characters for malformed sequences.",
        "runtime", "medium", ["unicode", "decoding", "error-handling"],
        ["Input.bytes is a list of integers from 0 to 255, with at most 1,000 entries.",
         "Return its UTF-8 decoding using Python's replacement error policy: malformed sequences become U+FFFD.",
         "Do not drop damaged bytes silently or decode the stream as a different character encoding."],
        {"python": 'def solve(data):\n    return bytes(data["bytes"]).decode("utf-8")'},
        {"python": 'def solve(data):\n    return bytes(data["bytes"]).decode("utf-8", errors="replace")'},
        [case("Valid text", {"bytes": [72, 105]}, "Hi"),
         case("Damaged byte", {"bytes": [65, 255, 66]}, "A\ufffdB"),
         case("Truncated sequence", {"bytes": [226, 130]}, "\ufffd", True),
         case("Multibyte text", {"bytes": [240, 159, 152, 128, 195, 169]}, "😀é", True),
         case("Stray continuation", {"bytes": [128, 97, 128]}, "\ufffda\ufffd", True),
         case("Empty stream", {"bytes": []}, "", True)],
        "Keep the UTF-8 decoder and change its error policy to replacement. This preserves valid multibyte characters and visible evidence of corruption without aborting the whole message. Time and output space O(bytes).",
        ["Does one malformed sequence have to abort decoding?", "Ignoring errors would lose evidence required by the contract.",
         "Decode as UTF-8 with errors='replace'."], 12,
    ),
    problem(
        "cyclic-alias-resolution", "The alias chain never reaches a value",
        "A configuration resolver recursively follows aliases. Cycles and long chains exhaust its call stack, while a missing endpoint raises a key error.",
        "runtime", "hard", ["cycles", "iteration", "configuration"],
        ["Input.values maps string names to integer values; input.aliases maps names to other names; input.start is a name.",
         "Resolve start by following aliases until a value is found. A value takes precedence if a name has both a value and an alias.",
         "Return null if a name is missing from both maps or a name is visited twice. Values may be zero or negative.",
         "There are at most 2,000 names. Resolve long chains without depending on Python's recursion limit."],
        {"python": '''
            def solve(data):
                def resolve(name):
                    if name in data["values"]:
                        return data["values"][name]
                    return resolve(data["aliases"][name])
                return resolve(data["start"])
        '''},
        {"python": '''
            def solve(data):
                name, seen = data["start"], set()
                while name not in seen:
                    if name in data["values"]:
                        return data["values"][name]
                    if name not in data["aliases"]:
                        return None
                    seen.add(name)
                    name = data["aliases"][name]
                return None
        '''},
        [case("Resolved alias", {"values": {"port": 80}, "aliases": {"web": "port"}, "start": "web"}, 80),
         case("Alias cycle", {"values": {}, "aliases": {"a": "b", "b": "a"}, "start": "a"}, None),
         case("Missing endpoint", {"values": {}, "aliases": {"a": "missing"}, "start": "a"}, None, True),
         case("Value takes precedence", {"values": {"a": 0}, "aliases": {"a": "a"}, "start": "a"}, 0, True),
         case("Long chain", {"values": {"n1500": -7}, "aliases": {f"n{i}": f"n{i + 1}" for i in range(1500)}, "start": "n0"}, -7, True),
         case("Self alias", {"values": {}, "aliases": {"x": "x"}, "start": "x"}, None, True),
         case("Empty configuration", {"values": {}, "aliases": {}, "start": ""}, None, True)],
        "Follow aliases iteratively and keep the names already visited. Test value membership before following an alias so zero values and value precedence work correctly. Expected time and space O(chain length).",
        ["What stops a chain that points back to an earlier name?", "A visited set handles cycles, but recursion still fails on sufficiently long acyclic chains.",
         "Use a loop: check for a value, reject a missing alias, record the name, and follow the next link."], 22,
    ),
    problem(
        "mixed-event-values", "One unexpected event type panics the reader",
        "A Go event reader assumes every JSON entry is an object containing a number. The feed also includes control messages, nulls, and incomplete objects.",
        "runtime", "medium", ["go", "type-assertions", "json"],
        ["Input.entries is an array of arbitrary JSON values. Any numeric value in the input is an integer with magnitude at most 1,000,000.",
         "Sum value fields only from entries that are objects and whose value field is a number.",
         "Ignore other entries and nonnumeric or missing value fields. Do not coerce strings or booleans. At most 100 entries."],
        {"go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                total := 0
                for _, raw := range data["entries"].([]interface{}) {
                    entry := raw.(map[string]interface{})
                    total += int(entry["value"].(float64))
                }
                return total
            }
        '''},
        {"go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                total := 0
                for _, raw := range data["entries"].([]interface{}) {
                    entry, ok := raw.(map[string]interface{})
                    if !ok { continue }
                    value, ok := entry["value"].(float64)
                    if ok { total += int(value) }
                }
                return total
            }
        '''},
        [case("Numeric events", {"entries": [{"value": 2}, {"value": 3}]}, 5),
         case("Control entry", {"entries": ["ping", {"value": 4}]}, 4),
         case("Missing and null", {"entries": [None, {}, {"value": None}]}, 0, True),
         case("No coercion", {"entries": [{"value": "5"}, {"value": True}, {"value": []}, 7]}, 0, True),
         case("Signed values", {"entries": [{"value": -9}, [], {"value": 0}, {"value": 4}]}, -5, True),
         case("Empty feed", {"entries": []}, 0, True)],
        "Check the dynamic type at each level independently. Successful object conversion does not guarantee that its value field is numeric. Expected time O(entries), space O(1).",
        ["There are two type assumptions inside the loop.", "Validate the entry object and its numeric field separately.",
         "Use comma-ok assertions for map[string]interface{} and float64; skip either mismatch."], 14,
    ),
    problem(
        "substring-overrun", "A stale cursor crashes the snippet",
        "A C++ snippet endpoint receives cursors from an earlier revision of a document. An offset beyond the shortened text throws instead of returning an empty snippet.",
        "runtime", "easy", ["strings", "bounds", "cpp"],
        ["Input.text is ASCII; input.start and input.length are integers of magnitude at most 1,000,000.",
         "Clamp a negative start to zero. Return up to length characters from that position, truncated at the end.",
         "Return an empty string for length <= 0 or start at or beyond the text length. Text has at most 1,000 characters."],
        {"cpp": '''
            #include <nlohmann/json.hpp>
            #include <string>
            using nlohmann::json;
            json solve(const json& data) {
                return data.at("text").get<std::string>().substr(data.at("start").get<int>(), data.at("length").get<int>());
            }
        '''},
        {"cpp": '''
            #include <nlohmann/json.hpp>
            #include <string>
            #include <algorithm>
            using nlohmann::json;
            json solve(const json& data) {
                std::string text = data.at("text").get<std::string>();
                int start = std::max(0, data.at("start").get<int>()), length = data.at("length").get<int>();
                if (length <= 0 || start >= static_cast<int>(text.size())) return "";
                return text.substr(start, length);
            }
        '''},
        [case("Ordinary snippet", {"text": "abcdef", "start": 2, "length": 3}, "cde"),
         case("Stale cursor", {"text": "abc", "start": 8, "length": 2}, ""),
         case("Negative start", {"text": "abc", "start": -2, "length": 2}, "ab", True),
         case("Negative length", {"text": "abc", "start": 1, "length": -1}, "", True),
         case("Truncated snippet", {"text": "abc", "start": 1, "length": 100}, "bc", True),
         case("Empty text", {"text": "", "start": 0, "length": 3}, "", True),
         case("At the end", {"text": "abc", "start": 3, "length": 0}, "", True)],
        "Normalize signed coordinates before passing them to an API that takes unsigned sizes. Guard the start position; substr already truncates a positive length at the end. Time and space O(snippet length).",
        ["What happens when substr's position exceeds the string length?", "Negative integers become large unsigned sizes if passed through unchecked.",
         "Clamp start to zero, reject nonpositive length or an out-of-range start, then call substr."], 10,
    ),
    problem(
        "closure-counter-scope", "The callback cannot see its counter",
        "A Python callback increments an enclosing counter. The assignment makes the name local to the callback, so its first invocation raises an unbound-local error.",
        "runtime", "medium", ["closures", "scope", "python"],
        ["Input.start is an integer of magnitude at most 1,000,000; input.steps is an integer from 0 through 100.",
         "Invoke an incrementing callback steps times and return {values: [counter after each call], final: counter}.",
         "Keep callback state across calls within one solve invocation. Zero steps returns an empty values list and the starting counter."],
        {"python": '''
            def solve(data):
                count = data["start"]
                def increment():
                    count += 1
                    return count
                values = [increment() for _ in range(data["steps"])]
                return {"values": values, "final": count}
        '''},
        {"python": '''
            def solve(data):
                count = data["start"]
                def increment():
                    nonlocal count
                    count += 1
                    return count
                values = [increment() for _ in range(data["steps"])]
                return {"values": values, "final": count}
        '''},
        [case("No callbacks", {"start": 4, "steps": 0}, {"values": [], "final": 4}),
         case("One callback", {"start": 4, "steps": 1}, {"values": [5], "final": 5}),
         case("Shared state", {"start": 0, "steps": 3}, {"values": [1, 2, 3], "final": 3}, True),
         case("Negative start", {"start": -2, "steps": 3}, {"values": [-1, 0, 1], "final": 1}, True),
         case("Large start", {"start": 1000000, "steps": 2}, {"values": [1000001, 1000002], "final": 1000002}, True),
         case("Many calls", {"start": 0, "steps": 100}, {"values": list(range(1, 101)), "final": 100}, True)],
        "Declare count nonlocal inside the callback so assignment updates the enclosing invocation's counter. A global would incorrectly share state between independent uses. Time and output space O(steps).",
        ["Assignment changes how Python resolves a name inside a function.", "The counter belongs to the enclosing solve call, not the module.",
         "Declare nonlocal count before incrementing it."], 12,
    ),
    problem(
        "literal-replace-pattern", "A bracket breaks find and replace",
        "A Java text tool treats a user's literal search text as a regular expression. A bracket can throw a syntax error, and dots or dollar signs can change the replacement's meaning.",
        "runtime", "medium", ["strings", "regex", "escaping"],
        ["Input.text, input.find, and input.replacement are ASCII strings of at most 1,000 characters.",
         "Replace all non-overlapping literal occurrences of find with the literal replacement string.",
         "If find is empty, return text unchanged. Regex operators, dollar signs, and backslashes have no special meaning."],
        {"java": '''
            import com.google.gson.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    return new JsonPrimitive(data.get("text").getAsString().replaceAll(
                        data.get("find").getAsString(), data.get("replacement").getAsString()));
                }
            }
        '''},
        {"java": '''
            import com.google.gson.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    String text = data.get("text").getAsString(), find = data.get("find").getAsString();
                    return new JsonPrimitive(find.isEmpty() ? text : text.replace(find, data.get("replacement").getAsString()));
                }
            }
        '''},
        [case("Simple replacement", {"text": "cat cat", "find": "cat", "replacement": "dog"}, "dog dog"),
         case("Literal bracket", {"text": "a[b[", "find": "[", "replacement": "("}, "a(b("),
         case("Literal dot", {"text": "a.b", "find": ".", "replacement": "!"}, "a!b", True),
         case("Literal replacement", {"text": "xx", "find": "x", "replacement": "$1\\"}, "$1\\$1\\", True),
         case("Empty search", {"text": "abc", "find": "", "replacement": "-"}, "abc", True),
         case("Non-overlapping matches", {"text": "aaaaa", "find": "aa", "replacement": "b"}, "bba", True),
         case("No match", {"text": "", "find": "x", "replacement": "y"}, "", True)],
        "Choose String.replace's literal CharSequence overload and explicitly handle an empty search. Literal replacement avoids interpreting both the search pattern and replacement text. Space O(output length); search work depends on the text and pattern lengths.",
        ["Are users entering patterns or ordinary text?", "Quoting only the pattern still leaves replacement metacharacters to consider.",
         "Guard an empty search, then use String.replace(find, replacement)."], 14,
    ),
])


# Problems 56–70: incorrect algorithms and control flow.
CATALOG.extend([
    problem(
        "two-sum-self-match", "The pair uses the same entry twice",
        "A reconciliation helper finds two amounts that match a target, but it can pair a transaction with itself because it records the current amount too early.",
        "logic", "easy", ["hash-map", "two-sum", "ordering"],
        ["Input.nums is a list of at most 1,000 integers; values and input.target have magnitude at most 1,000,000.",
         "Return [j, i] with j < i and nums[j] + nums[i] == target. Choose the smallest possible i, then the smallest j.",
         "Return null when no pair exists. Each index may be used only once. Use expected O(n) time."],
        {"python": '''
            def solve(data):
                seen = {}
                for i, value in enumerate(data["nums"]):
                    seen.setdefault(value, i)
                    complement = data["target"] - value
                    if complement in seen:
                        return [seen[complement], i]
                return None
        '''},
        {"python": '''
            def solve(data):
                seen = {}
                for i, value in enumerate(data["nums"]):
                    complement = data["target"] - value
                    if complement in seen:
                        return [seen[complement], i]
                    seen.setdefault(value, i)
                return None
        '''},
        [case("Ordinary pair", {"nums": [2, 7, 11], "target": 9}, [0, 1]),
         case("Cannot reuse one entry", {"nums": [3], "target": 6}, None),
         case("Equal values at distinct indices", {"nums": [3, 3], "target": 6}, [0, 1], True),
         case("Earliest matching partner", {"nums": [1, 1, 4], "target": 5}, [0, 2], True),
         case("Negative and zero", {"nums": [-2, 0, 2], "target": 0}, [0, 2], True),
         case("No entries", {"nums": [], "target": 0}, None, True)],
        "Look for a complement among earlier entries before inserting the current entry. Keep the first index for each value to satisfy the tie rule. Expected time and space O(n).",
        ["Which indices are already eligible when entry i is checked?", "Recording i first lets an amount match itself.",
         "Check the complement first, then store the first index for the current value."], 12,
    ),
    problem(
        "prefix-range-offset", "Every range loses its final reading",
        "A Go metrics service builds prefix sums correctly but uses the wrong endpoint when answering inclusive range queries.",
        "logic", "medium", ["prefix-sums", "ranges", "off-by-one"],
        ["Input.values contains at most 1,000 integers of magnitude at most 1,000,000. Input.queries lists valid inclusive [left, right] index pairs.",
         "Return the sum from left through right for each query. Empty values has no queries.",
         "Use O(values + queries) time, with at most 1,000 queries."],
        {"go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                values := data["values"].([]interface{})
                prefix := make([]int, len(values)+1)
                for i, raw := range values { prefix[i+1] = prefix[i] + int(raw.(float64)) }
                result := []int{}
                for _, raw := range data["queries"].([]interface{}) {
                    query := raw.([]interface{}); left, right := int(query[0].(float64)), int(query[1].(float64))
                    result = append(result, prefix[right]-prefix[left])
                }
                return result
            }
        '''},
        {"go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                values := data["values"].([]interface{})
                prefix := make([]int, len(values)+1)
                for i, raw := range values { prefix[i+1] = prefix[i] + int(raw.(float64)) }
                result := []int{}
                for _, raw := range data["queries"].([]interface{}) {
                    query := raw.([]interface{}); left, right := int(query[0].(float64)), int(query[1].(float64))
                    result = append(result, prefix[right+1]-prefix[left])
                }
                return result
            }
        '''},
        [case("Full range", {"values": [2, 4, 6], "queries": [[0, 2]]}, [12]),
         case("Single reading", {"values": [7], "queries": [[0, 0]]}, [7]),
         case("Interior range", {"values": [10, -2, 5, 9], "queries": [[1, 2], [3, 3]]}, [3, 9], True),
         case("Repeated queries", {"values": [0, 3], "queries": [[0, 1], [0, 1], [0, 0]]}, [3, 3, 0], True),
         case("Negative total", {"values": [-5, -4, 2], "queries": [[0, 1], [1, 2]]}, [-9, -2], True),
         case("No readings", {"values": [], "queries": []}, [], True)],
        "prefix[k] contains the first k values, excluding index k. An inclusive right endpoint therefore needs prefix[right + 1], then subtract prefix[left]. Time O(n + q), space O(n + q).",
        ["What exactly does prefix[k] include?", "A one-element range should return that element, not zero.",
         "Compute prefix[right + 1] - prefix[left]."], 14,
    ),
    problem(
        "stable-priority-sort", "Equal-priority jobs jump the queue",
        "A job dashboard sorts by priority but adds an ID tie-breaker that silently changes arrival order. Equal-priority work should remain first come, first served.",
        "logic", "medium", ["sorting", "stability", "queues"],
        ["Input.jobs lists {id: string, priority: integer} in arrival order. IDs are unique lowercase ASCII strings; priorities have magnitude at most 100.",
         "Return IDs ordered by descending priority, preserving arrival order for equal priorities. At most 100 jobs."],
        {"javascript": '''
            function solve(data) {
              return [...data.jobs].sort((a, b) => b.priority - a.priority || (a.id < b.id ? -1 : 1)).map(job => job.id);
            }
            module.exports = { solve };
        '''},
        {"javascript": '''
            function solve(data) {
              return [...data.jobs].sort((a, b) => b.priority - a.priority).map(job => job.id);
            }
            module.exports = { solve };
        '''},
        [case("Different priorities", {"jobs": [{"id": "a", "priority": 1}, {"id": "b", "priority": 3}]}, ["b", "a"]),
         case("Preserve arrival order", {"jobs": [{"id": "z", "priority": 2}, {"id": "a", "priority": 2}]}, ["z", "a"]),
         case("Interleaved ties", {"jobs": [{"id": "c", "priority": 1}, {"id": "z", "priority": 2}, {"id": "a", "priority": 1}, {"id": "b", "priority": 2}]}, ["z", "b", "c", "a"], True),
         case("Negative priorities", {"jobs": [{"id": "z", "priority": -1}, {"id": "a", "priority": -1}, {"id": "b", "priority": 0}]}, ["b", "z", "a"], True),
         case("One job", {"jobs": [{"id": "only", "priority": 0}]}, ["only"], True),
         case("No jobs", {"jobs": []}, [], True)],
        "Return zero from the comparator when priorities tie. JavaScript's stable sort retains the original order of equal elements. Sorting takes O(n log n) comparisons, with O(n) space for the copied array and output.",
        ["Which field defines the ordering of equal-priority jobs?", "The ID is unrelated to when a job arrived.",
         "Compare only descending priority and let the stable sort preserve ties."], 12,
    ),
    problem(
        "reversed-dependencies", "The build runs before its prerequisites",
        "A build planner reverses the meaning of each dependency edge. It produces a plausible order that starts tasks before the work they require.",
        "logic", "hard", ["graphs", "topological-sort", "dependencies"],
        ["Input.tasks lists unique lowercase ASCII task names. Each input.dependencies pair [before, after] requires before to finish first; both names exist.",
         "Return a valid task order, always choosing the alphabetically smallest currently available task. Repeated dependency pairs count only once.",
         "Return null if any cycle prevents completion; an empty task list returns []. At most 100 tasks and 500 dependency pairs."],
        {"python": '''
            import heapq
            def solve(data):
                edges = {name: set() for name in data["tasks"]}
                indegree = dict.fromkeys(data["tasks"], 0)
                for before, after in data["dependencies"]:
                    if before not in edges[after]:
                        edges[after].add(before)
                        indegree[before] += 1
                ready = [name for name in indegree if indegree[name] == 0]
                heapq.heapify(ready)
                result = []
                while ready:
                    name = heapq.heappop(ready)
                    result.append(name)
                    for next_name in edges[name]:
                        indegree[next_name] -= 1
                        if indegree[next_name] == 0:
                            heapq.heappush(ready, next_name)
                return result if len(result) == len(indegree) else None
        '''},
        {"python": '''
            import heapq
            def solve(data):
                edges = {name: set() for name in data["tasks"]}
                indegree = dict.fromkeys(data["tasks"], 0)
                for before, after in data["dependencies"]:
                    if after not in edges[before]:
                        edges[before].add(after)
                        indegree[after] += 1
                ready = [name for name in indegree if indegree[name] == 0]
                heapq.heapify(ready)
                result = []
                while ready:
                    name = heapq.heappop(ready)
                    result.append(name)
                    for next_name in edges[name]:
                        indegree[next_name] -= 1
                        if indegree[next_name] == 0:
                            heapq.heappush(ready, next_name)
                return result if len(result) == len(indegree) else None
        '''},
        [case("Independent tasks", {"tasks": ["z", "a"], "dependencies": []}, ["a", "z"]),
         case("Build before deploy", {"tasks": ["build", "deploy"], "dependencies": [["build", "deploy"]]}, ["build", "deploy"]),
         case("Newly available task wins", {"tasks": ["z", "a", "b"], "dependencies": [["a", "b"]]}, ["a", "b", "z"], True),
         case("Repeated dependency", {"tasks": ["a", "b"], "dependencies": [["a", "b"], ["a", "b"]]}, ["a", "b"], True),
         case("Cycle with isolated task", {"tasks": ["a", "b", "c"], "dependencies": [["a", "b"], ["b", "a"]]}, None, True),
         case("Self dependency", {"tasks": ["a"], "dependencies": [["a", "a"]]}, None, True),
         case("No tasks", {"tasks": [], "dependencies": []}, [], True)],
        "An edge goes from a prerequisite to its dependent, and the dependent receives the incoming-edge count. Deduplicate edges, use a min-heap for ready tasks, and reject a partial traversal. Time O(E + V log V), space O(V + E).",
        ["Which task should gain an unmet-prerequisite count for [before, after]?", "Outgoing edges should identify tasks released by completing the current task.",
         "Store after in edges[before], increment indegree[after] once, and keep the existing heap-based traversal."], 25,
    ),
    problem(
        "bfs-stack-route", "The shortest route takes a detour",
        "A network explorer marks a node when first discovered, but its LIFO work list can discover that node through a longer route first.",
        "logic", "medium", ["bfs", "graphs", "queues"],
        ["Input.n is from 1 through 50; nodes are numbered 0 through n-1. Input.edges lists undirected [a, b] links, and input.start is a valid node.",
         "Return one minimum hop count per node, using null for unreachable nodes and zero for start.",
         "Self links, repeated links, and cycles are allowed. At most 200 links; use O(n + edges) time."],
        {"cpp": '''
            #include <nlohmann/json.hpp>
            #include <vector>
            using nlohmann::json;
            json solve(const json& data) {
                int n = data.at("n"), start = data.at("start");
                std::vector<std::vector<int>> graph(n);
                for (const auto& edge : data.at("edges")) {
                    int a = edge.at(0), b = edge.at(1); graph[a].push_back(b); graph[b].push_back(a);
                }
                std::vector<int> distance(n, -1), pending{start}; distance[start] = 0;
                while (!pending.empty()) {
                    int node = pending.back(); pending.pop_back();
                    for (int next : graph[node]) if (distance[next] == -1) {
                        distance[next] = distance[node] + 1; pending.push_back(next);
                    }
                }
                json result = json::array();
                for (int value : distance) result.push_back(value < 0 ? json(nullptr) : json(value));
                return result;
            }
        '''},
        {"cpp": '''
            #include <nlohmann/json.hpp>
            #include <vector>
            #include <queue>
            using nlohmann::json;
            json solve(const json& data) {
                int n = data.at("n"), start = data.at("start");
                std::vector<std::vector<int>> graph(n);
                for (const auto& edge : data.at("edges")) {
                    int a = edge.at(0), b = edge.at(1); graph[a].push_back(b); graph[b].push_back(a);
                }
                std::vector<int> distance(n, -1); distance[start] = 0;
                std::queue<int> pending; pending.push(start);
                while (!pending.empty()) {
                    int node = pending.front(); pending.pop();
                    for (int next : graph[node]) if (distance[next] == -1) {
                        distance[next] = distance[node] + 1; pending.push(next);
                    }
                }
                json result = json::array();
                for (int value : distance) result.push_back(value < 0 ? json(nullptr) : json(value));
                return result;
            }
        '''},
        [case("A simple chain", {"n": 3, "start": 0, "edges": [[0, 1], [1, 2]]}, [0, 1, 2]),
         case("Long detour discovered first", {"n": 6, "start": 0, "edges": [[0, 1], [0, 2], [2, 3], [3, 4], [4, 5], [1, 5]]}, [0, 1, 1, 2, 3, 2]),
         case("Disconnected", {"n": 3, "start": 1, "edges": []}, [None, 0, None], True),
         case("Self and repeated links", {"n": 2, "start": 0, "edges": [[0, 0], [0, 1], [0, 1]]}, [0, 1], True),
         case("Triangle", {"n": 3, "start": 2, "edges": [[0, 1], [1, 2], [0, 2]]}, [1, 1, 0], True),
         case("One node", {"n": 1, "start": 0, "edges": []}, [0], True)],
        "A FIFO queue processes all nodes at one distance before exploring the next distance. First discovery is then a shortest path in an unweighted graph. Time O(V + E), space O(V + E).",
        ["Does the work list explore by increasing distance?", "A stack completes a deep branch before returning to shorter alternatives.",
         "Replace the LIFO work list with a queue; mark nodes when enqueuing them."], 18,
    ),
    problem(
        "reset-running-total", "The cumulative chart keeps starting over",
        "A dashboard's running total resets inside the loop, so every point shows only that day's change.",
        "logic", "easy", ["accumulators", "scope", "analytics"],
        ["Return the inclusive prefix sums of input.changes in order.",
         "Changes are integers of magnitude at most 1,000,000; at most 1,000 changes. Empty input returns []."],
        {"python": '''
            def solve(data):
                result = []
                for change in data["changes"]:
                    total = 0
                    total += change
                    result.append(total)
                return result
        '''},
        {"python": '''
            def solve(data):
                result, total = [], 0
                for change in data["changes"]:
                    total += change
                    result.append(total)
                return result
        '''},
        [case("One day", {"changes": [5]}, [5]), case("Several days", {"changes": [5, 2, 3]}, [5, 7, 10]),
         case("Negative adjustments", {"changes": [4, -6, 3]}, [4, -2, 1], True),
         case("Zero changes", {"changes": [2, 0, 0]}, [2, 2, 2], True),
         case("No days", {"changes": []}, [], True), case("All negative", {"changes": [-2, -3]}, [-2, -5], True)],
        "Initialize the accumulator once before processing changes. Each output should include the current change and all earlier ones. Time and output space O(n).",
        ["How long should the total survive?", "The initialization currently runs once per change.",
         "Move total = 0 before the loop and keep appending after each addition."], 8,
    ),
    problem(
        "binary-search-first", "The duplicate search lands in the middle",
        "A Java lookup stops at any matching record. The caller needs the first matching index so it can begin scanning the entire duplicate group.",
        "logic", "medium", ["binary-search", "duplicates", "boundaries"],
        ["Input.nums is a nondecreasing list of at most 1,000 integers; input.target is an integer. Values have magnitude at most 1,000,000.",
         "Return the first zero-based index equal to target, or -1 if absent. Use O(log n) time."],
        {"java": '''
            import com.google.gson.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    JsonArray nums = data.getAsJsonArray("nums"); int target = data.get("target").getAsInt();
                    int low = 0, high = nums.size() - 1;
                    while (low <= high) {
                        int middle = low + (high - low) / 2, value = nums.get(middle).getAsInt();
                        if (value == target) return new JsonPrimitive(middle);
                        if (value < target) low = middle + 1; else high = middle - 1;
                    }
                    return new JsonPrimitive(-1);
                }
            }
        '''},
        {"java": '''
            import com.google.gson.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    JsonArray nums = data.getAsJsonArray("nums"); int target = data.get("target").getAsInt();
                    int low = 0, high = nums.size();
                    while (low < high) {
                        int middle = low + (high - low) / 2;
                        if (nums.get(middle).getAsInt() < target) low = middle + 1; else high = middle;
                    }
                    return new JsonPrimitive(low < nums.size() && nums.get(low).getAsInt() == target ? low : -1);
                }
            }
        '''},
        [case("Unique match", {"nums": [1, 3, 5], "target": 3}, 1),
         case("Duplicate group", {"nums": [2, 2, 2, 2], "target": 2}, 0),
         case("Interior duplicates", {"nums": [-3, 0, 0, 0, 8], "target": 0}, 1, True),
         case("Missing interior value", {"nums": [1, 3, 5], "target": 4}, -1, True),
         case("After the end", {"nums": [1, 2], "target": 3}, -1, True),
         case("Empty list", {"nums": [], "target": 0}, -1, True),
         case("Last value", {"nums": [1, 2, 3], "target": 3}, 2, True)],
        "Search for the first element greater than or equal to the target instead of returning immediately on equality. Check that the resulting boundary actually contains the target. Time O(log n), space O(1).",
        ["Finding a match does not prove that no earlier match exists.", "On equality, keep searching the left half.",
         "Maintain a half-open [low, high) range, move high to middle for values >= target, then validate low."], 16,
    ),
    problem(
        "overlapping-matches", "The scanner skips overlapping alerts",
        "A text scanner jumps past the whole matched pattern. That loses valid matches that begin inside the previous match.",
        "logic", "medium", ["strings", "search", "overlap"],
        ["Return every zero-based starting index where input.needle occurs in input.text, including overlapping occurrences.",
         "Text and needle are ASCII strings of at most 1,000 characters. Return [] for an empty needle or no matches."],
        {"javascript": '''
            function solve(data) {
              if (!data.needle.length) return [];
              const result = [];
              let start = 0, index;
              while ((index = data.text.indexOf(data.needle, start)) !== -1) {
                result.push(index);
                start = index + data.needle.length;
              }
              return result;
            }
            module.exports = { solve };
        '''},
        {"javascript": '''
            function solve(data) {
              if (!data.needle.length) return [];
              const result = [];
              let start = 0, index;
              while ((index = data.text.indexOf(data.needle, start)) !== -1) {
                result.push(index);
                start = index + 1;
              }
              return result;
            }
            module.exports = { solve };
        '''},
        [case("Separate matches", {"text": "abxxab", "needle": "ab"}, [0, 4]),
         case("Overlapping pattern", {"text": "banana", "needle": "ana"}, [1, 3]),
         case("Repeated character", {"text": "aaaa", "needle": "aa"}, [0, 1, 2], True),
         case("Empty needle", {"text": "abc", "needle": ""}, [], True),
         case("Longer needle", {"text": "a", "needle": "aa"}, [], True),
         case("One-character pattern", {"text": "aba", "needle": "a"}, [0, 2], True)],
        "After each match, resume one position after its start. This guarantees progress while allowing the next occurrence to overlap. Worst-case comparison work O(text length × needle length), output space O(matches).",
        ["Can another occurrence start before the current one ends?", "The next search position needs to advance, but not by the entire pattern length.",
         "Set start = index + 1 after recording a match."], 12,
    ),
])

CATALOG.extend([
    problem(
        "palindrome-normalization", "Punctuation spoils the mirror check",
        "A text puzzle ignores spaces but leaves punctuation in the comparison. Messages that read the same forward and backward are incorrectly rejected.",
        "logic", "easy", ["strings", "normalization", "two-pointers"],
        ["Return whether input.text is a palindrome after keeping only ASCII letters and digits and ignoring letter case.",
         "Input contains at most 1,000 ASCII characters. Empty normalized text counts as a palindrome."],
        {"python": '''
            def solve(data):
                text = data["text"].replace(" ", "").lower()
                return text == text[::-1]
        '''},
        {"python": '''
            def solve(data):
                text = "".join(char.lower() for char in data["text"] if char.isalnum())
                return text == text[::-1]
        '''},
        [case("Simple palindrome", {"text": "Race car"}, True),
         case("Punctuated palindrome", {"text": "A man, a plan, a canal: Panama!"}, True),
         case("Digits matter", {"text": "0P"}, False, True),
         case("Only punctuation", {"text": "!?-"}, True, True),
         case("Not a palindrome", {"text": "debug"}, False, True),
         case("Mixed whitespace", {"text": "A\tb\na"}, True, True),
         case("Empty text", {"text": ""}, True, True)],
        "Apply the complete normalization rule before comparing: retain letters and digits, lowercase them, and compare with the reverse. The ASCII input constraint makes isalnum match the required alphabet. Time and space O(n).",
        ["Spaces are only one kind of ignored character.", "Digits must remain, while punctuation and whitespace must disappear.",
         "Filter with isalnum, lowercase the surviving characters, then compare the string with its reverse."], 10,
    ),
    problem(
        "transpose-dimensions", "The rotated table still has its old shape",
        "A Go matrix transpose allocates the original dimensions. Square examples hide the issue; rectangular tables panic or produce the wrong shape.",
        "logic", "easy", ["matrices", "dimensions", "go"],
        ["Input.matrix is a rectangular list of integer rows with at most 30 rows and 30 columns; values have magnitude at most 1,000,000.",
         "Return its transpose, whose rows are the input columns. Zero input rows or zero columns returns []."],
        {"go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                matrix := data["matrix"].([]interface{})
                if len(matrix) == 0 { return [][]int{} }
                rows, cols := len(matrix), len(matrix[0].([]interface{}))
                result := make([][]int, rows)
                for r := 0; r < rows; r++ {
                    result[r] = make([]int, cols)
                    for c := 0; c < cols; c++ { result[r][c] = int(matrix[c].([]interface{})[r].(float64)) }
                }
                return result
            }
        '''},
        {"go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                matrix := data["matrix"].([]interface{})
                if len(matrix) == 0 { return [][]int{} }
                rows, cols := len(matrix), len(matrix[0].([]interface{}))
                result := make([][]int, cols)
                for c := 0; c < cols; c++ {
                    result[c] = make([]int, rows)
                    for r := 0; r < rows; r++ { result[c][r] = int(matrix[r].([]interface{})[c].(float64)) }
                }
                return result
            }
        '''},
        [case("Square table", {"matrix": [[1, 2], [3, 4]]}, [[1, 3], [2, 4]]),
         case("Wide table", {"matrix": [[1, 2, 3], [4, 5, 6]]}, [[1, 4], [2, 5], [3, 6]]),
         case("Tall table", {"matrix": [[1], [2], [-3]]}, [[1, 2, -3]], True),
         case("One row", {"matrix": [[0, 7]]}, [[0], [7]], True),
         case("No rows", {"matrix": []}, [], True),
         case("No columns", {"matrix": [[], []]}, [], True)],
        "Swap the dimensions as well as the indices: allocate one output row per input column, each with one cell per input row. Time O(rows × columns), output space of the same order.",
        ["What shape should a two-by-three matrix have after transposition?", "Both allocation and loop bounds must follow the output shape.",
         "Allocate cols rows of length rows and assign result[c][r] = matrix[r][c]."], 12,
    ),
    problem(
        "meeting-greedy-order", "The longest meeting blocks the whole day",
        "A scheduling helper chooses meetings by start time. An early, long meeting can crowd out several shorter compatible meetings.",
        "logic", "medium", ["greedy", "scheduling", "sorting"],
        ["Input.meetings lists [start, end] integer intervals with start < end and endpoint magnitude at most 1,000,000.",
         "Return the maximum number of meetings one person can attend. Meetings occupy [start, end), so touching meetings are compatible.",
         "At most 100 meetings; repeated intervals represent separate choices but cannot overlap in the selected schedule."],
        {"java": '''
            import com.google.gson.*;
            import java.util.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    List<int[]> meetings = new ArrayList<>();
                    for (JsonElement raw : data.getAsJsonArray("meetings")) {
                        JsonArray pair = raw.getAsJsonArray(); meetings.add(new int[]{pair.get(0).getAsInt(), pair.get(1).getAsInt()});
                    }
                    meetings.sort(Comparator.comparingInt(pair -> pair[0]));
                    int count = 0, end = Integer.MIN_VALUE;
                    for (int[] pair : meetings) if (pair[0] >= end) { count++; end = pair[1]; }
                    return new JsonPrimitive(count);
                }
            }
        '''},
        {"java": '''
            import com.google.gson.*;
            import java.util.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    List<int[]> meetings = new ArrayList<>();
                    for (JsonElement raw : data.getAsJsonArray("meetings")) {
                        JsonArray pair = raw.getAsJsonArray(); meetings.add(new int[]{pair.get(0).getAsInt(), pair.get(1).getAsInt()});
                    }
                    meetings.sort(Comparator.comparingInt(pair -> pair[1]));
                    int count = 0, end = Integer.MIN_VALUE;
                    for (int[] pair : meetings) if (pair[0] >= end) { count++; end = pair[1]; }
                    return new JsonPrimitive(count);
                }
            }
        '''},
        [case("Compatible meetings", {"meetings": [[1, 2], [2, 3]]}, 2),
         case("Long early meeting", {"meetings": [[0, 10], [1, 2], [2, 3], [3, 4]]}, 3),
         case("Input is unsorted", {"meetings": [[5, 8], [0, 2], [2, 5]]}, 3, True),
         case("Negative times", {"meetings": [[-5, -2], [-2, 0], [-4, 1]]}, 2, True),
         case("Repeated interval", {"meetings": [[1, 4], [1, 4], [4, 5]]}, 2, True),
         case("Empty schedule", {"meetings": []}, 0, True)],
        "Select compatible meetings in increasing finish-time order. Finishing as early as possible leaves at least as much room for every later choice. Time O(n log n), space O(n).",
        ["Does starting earlier necessarily free the room earlier?", "The next choice benefits from the earliest possible finishing time.",
         "Sort by end time and accept a meeting when its start is at least the previous selected end."], 16,
    ),
    problem(
        "knapsack-item-reuse", "The packing list invents extra items",
        "A space-saving knapsack implementation updates capacities in ascending order. That lets one physical item be counted several times during the same iteration.",
        "logic", "hard", ["dynamic-programming", "knapsack", "iteration-order"],
        ["Input.items lists {weight, value} integers; each listed item may be chosen at most once, including separately listed identical items.",
         "Return the maximum total value with total weight at most input.capacity. Choosing no items is allowed.",
         "Capacity is 0 through 1,000; at most 40 items; weights are 1 through 1,000 and values 0 through 1,000. Use O(items × capacity) time and O(capacity) working space."],
        {"python": '''
            def solve(data):
                capacity = data["capacity"]
                best = [0] * (capacity + 1)
                for item in data["items"]:
                    for space in range(item["weight"], capacity + 1):
                        best[space] = max(best[space], best[space - item["weight"]] + item["value"])
                return best[capacity]
        '''},
        {"python": '''
            def solve(data):
                capacity = data["capacity"]
                best = [0] * (capacity + 1)
                for item in data["items"]:
                    for space in range(capacity, item["weight"] - 1, -1):
                        best[space] = max(best[space], best[space - item["weight"]] + item["value"])
                return best[capacity]
        '''},
        [case("One item fits once", {"capacity": 3, "items": [{"weight": 3, "value": 4}]}, 4),
         case("Cannot clone an item", {"capacity": 6, "items": [{"weight": 3, "value": 4}]}, 4),
         case("Two physical copies", {"capacity": 6, "items": [{"weight": 3, "value": 4}, {"weight": 3, "value": 4}]}, 8, True),
         case("Best combination", {"capacity": 7, "items": [{"weight": 3, "value": 4}, {"weight": 4, "value": 6}, {"weight": 5, "value": 7}]}, 10, True),
         case("Nothing fits", {"capacity": 2, "items": [{"weight": 3, "value": 9}]}, 0, True),
         case("Zero capacity", {"capacity": 0, "items": [{"weight": 1, "value": 3}]}, 0, True),
         case("No items", {"capacity": 5, "items": []}, 0, True)],
        "Update capacities in descending order. The smaller-capacity state then still describes choices before the current item, so the transition can add that item only once. Time O(items × capacity), working space O(capacity).",
        ["Can best[space - weight] already include the current item?", "Ascending updates reuse values written earlier in the same item iteration.",
         "Iterate space from capacity down through the item's weight."], 24,
    ),
    problem(
        "union-size-accounting", "A repeated link doubles the cluster",
        "A C++ connectivity tracker adds component sizes even when the two nodes are already connected. Duplicate and cyclic links inflate the reported cluster sizes.",
        "logic", "medium", ["union-find", "graphs", "invariants"],
        ["Input.n is 0 through 100; nodes are 0 through n-1. Input.links contains at most 500 undirected pairs of valid nodes.",
         "Return an n-element array with each node's connected-component size. Repeated links and self links must not add nodes.",
         "An empty graph returns []."],
        {"cpp": '''
            #include <nlohmann/json.hpp>
            #include <vector>
            #include <numeric>
            #include <functional>
            using nlohmann::json;
            json solve(const json& data) {
                int n = data.at("n"); std::vector<int> parent(n), size(n, 1);
                std::iota(parent.begin(), parent.end(), 0);
                std::function<int(int)> root = [&](int x) { return parent[x] == x ? x : parent[x] = root(parent[x]); };
                for (const auto& link : data.at("links")) {
                    int a = root(link.at(0).get<int>()), b = root(link.at(1).get<int>());
                    if (size[a] < size[b]) std::swap(a, b);
                    parent[b] = a; size[a] += size[b];
                }
                json result = json::array(); for (int i = 0; i < n; i++) result.push_back(size[root(i)]);
                return result;
            }
        '''},
        {"cpp": '''
            #include <nlohmann/json.hpp>
            #include <vector>
            #include <numeric>
            #include <functional>
            using nlohmann::json;
            json solve(const json& data) {
                int n = data.at("n"); std::vector<int> parent(n), size(n, 1);
                std::iota(parent.begin(), parent.end(), 0);
                std::function<int(int)> root = [&](int x) { return parent[x] == x ? x : parent[x] = root(parent[x]); };
                for (const auto& link : data.at("links")) {
                    int a = root(link.at(0).get<int>()), b = root(link.at(1).get<int>());
                    if (a == b) continue;
                    if (size[a] < size[b]) std::swap(a, b);
                    parent[b] = a; size[a] += size[b];
                }
                json result = json::array(); for (int i = 0; i < n; i++) result.push_back(size[root(i)]);
                return result;
            }
        '''},
        [case("One link", {"n": 3, "links": [[0, 1]]}, [2, 2, 1]),
         case("Repeated link", {"n": 2, "links": [[0, 1], [0, 1]]}, [2, 2]),
         case("Self link", {"n": 2, "links": [[0, 0]]}, [1, 1], True),
         case("Cycle", {"n": 4, "links": [[0, 1], [1, 2], [2, 0]]}, [3, 3, 3, 1], True),
         case("Merge two clusters", {"n": 5, "links": [[0, 1], [2, 3], [1, 3]]}, [4, 4, 4, 4, 1], True),
         case("Empty graph", {"n": 0, "links": []}, [], True)],
        "Only merge distinct roots. An edge inside an existing component changes connectivity neither for a self link nor for a cycle. Union by size and path compression give near-linear O((V + E) α(V)) time and O(V) working space; α grows extremely slowly.",
        ["Does every edge connect two different components?", "Comparing original endpoints misses distinct nodes that already share a root.",
         "Find both roots and skip the union entirely when they are equal."], 18,
    ),
    problem(
        "boolean-precedence", "One region bypasses the age check",
        "A regional eligibility rule combines AND and OR without grouping. Applicants from the second supported region bypass the minimum-age requirement.",
        "logic", "easy", ["booleans", "precedence", "validation"],
        ["Return true only when input.age >= 18 and input.region is exactly 'north' or 'south'.",
         "Age is an integer from 0 through 120; region is an ASCII string. Other regions are ineligible."],
        {"javascript": '''
            function solve(data) {
              return data.age >= 18 && data.region === 'north' || data.region === 'south';
            }
            module.exports = { solve };
        '''},
        {"javascript": '''
            function solve(data) {
              return data.age >= 18 && (data.region === 'north' || data.region === 'south');
            }
            module.exports = { solve };
        '''},
        [case("Eligible north applicant", {"age": 20, "region": "north"}, True),
         case("Underage south applicant", {"age": 17, "region": "south"}, False),
         case("Exact age threshold", {"age": 18, "region": "south"}, True, True),
         case("Underage north applicant", {"age": 0, "region": "north"}, False, True),
         case("Unsupported region", {"age": 40, "region": "east"}, False, True),
         case("Case-sensitive region", {"age": 18, "region": "South"}, False, True)],
        "AND binds more tightly than OR. Group the region alternatives so the age predicate applies to both of them. Time and space O(1).",
        ["Write down how the current expression groups without parentheses.", "The south comparison is a complete alternative to the age check.",
         "Require age >= 18 AND (region is north OR region is south)."], 8,
    ),
    problem(
        "edit-distance-diagonal", "The spell checker overwrites its memory",
        "A one-row edit-distance algorithm saves its diagonal after overwriting the cell. Later comparisons use the current row where they need the previous row.",
        "logic", "hard", ["dynamic-programming", "strings", "state"],
        ["Return the Levenshtein distance between input.source and input.target: minimum insertions, deletions, and substitutions, each costing one.",
         "Both strings contain lowercase ASCII letters and have at most 200 characters. Matching characters cost zero.",
         "Use O(source length × target length) time and O(target length) working space."],
        {"python": '''
            def solve(data):
                source, target = data["source"], data["target"]
                row = list(range(len(target) + 1))
                for i, left in enumerate(source, 1):
                    diagonal, row[0] = row[0], i
                    for j, right in enumerate(target, 1):
                        row[j] = diagonal if left == right else 1 + min(diagonal, row[j], row[j - 1])
                        diagonal = row[j]
                return row[-1]
        '''},
        {"python": '''
            def solve(data):
                source, target = data["source"], data["target"]
                row = list(range(len(target) + 1))
                for i, left in enumerate(source, 1):
                    diagonal, row[0] = row[0], i
                    for j, right in enumerate(target, 1):
                        above = row[j]
                        row[j] = diagonal if left == right else 1 + min(diagonal, above, row[j - 1])
                        diagonal = above
                return row[-1]
        '''},
        [case("One substitution", {"source": "a", "target": "b"}, 1),
         case("Identical word", {"source": "ab", "target": "ab"}, 0),
         case("Mixed edits", {"source": "kitten", "target": "sitting"}, 3, True),
         case("Insert everything", {"source": "", "target": "abc"}, 3, True),
         case("Delete everything", {"source": "abc", "target": ""}, 3, True),
         case("Repeated letters", {"source": "aaaa", "target": "aa"}, 2, True),
         case("Both empty", {"source": "", "target": ""}, 0, True)],
        "Save the previous-row value before replacing row[j]. That saved value becomes the next cell's diagonal; row[j - 1] already belongs to the current row. Time O(mn), working space O(n).",
        ["Which row should each of the three neighboring costs come from?", "The next diagonal is the old value above this cell.",
         "Save above = row[j], compute the new cell, then set diagonal = above."], 25,
    ),
])


# Problems 71–85: edge and corner cases.
CATALOG.extend([
    problem(
        "null-only-cleanup", "The cleanup deletes valid zeroes",
        "A JSON cleanup step removes all falsy values while trying to remove nulls. Valid zeroes, false flags, and empty strings disappear from the exported document.",
        "edge", "medium", ["json", "null", "recursion"],
        ["Recursively remove object fields and array elements whose value is exactly null from input.value.",
         "Preserve zero, false, empty strings, empty objects, empty arrays, and the order of remaining array elements. Root null stays null.",
         "Input.value is any JSON value, at most 10 levels deep and 1,000 nodes. Object keys are arbitrary strings; numeric values are finite."],
        {"javascript": '''
            function solve(data) {
              function clean(value) {
                if (Array.isArray(value)) return value.filter(Boolean).map(clean);
                if (value !== null && typeof value === 'object')
                  return Object.fromEntries(Object.entries(value).filter(([, child]) => Boolean(child)).map(([key, child]) => [key, clean(child)]));
                return value;
              }
              return clean(data.value);
            }
            module.exports = { solve };
        '''},
        {"javascript": '''
            function solve(data) {
              function clean(value) {
                if (Array.isArray(value)) return value.filter(child => child !== null).map(clean);
                if (value !== null && typeof value === 'object')
                  return Object.fromEntries(Object.entries(value).filter(([, child]) => child !== null).map(([key, child]) => [key, clean(child)]));
                return value;
              }
              return clean(data.value);
            }
            module.exports = { solve };
        '''},
        [case("Remove a null field", {"value": {"name": "a", "note": None}}, {"name": "a"}),
         case("Keep falsy values", {"value": [0, False, "", None, 1]}, [0, False, "", 1]),
         case("Nested values", {"value": {"a": [None, {"x": None, "y": 0}], "b": False}}, {"a": [{"y": 0}], "b": False}, True),
         case("Empty containers survive", {"value": [[], {}, [None], {"x": None}]}, [[], {}, [], {}], True),
         case("Root null", {"value": None}, None, True),
         case("Arbitrary keys", {"value": {"__proto__": {"active": False}, "constructor": 0, "": ""}}, {"__proto__": {"active": False}, "constructor": 0, "": ""}, True),
         case("Scalar root", {"value": False}, False, True)],
        "Filter by exact null equality rather than truthiness at every level. Rebuild objects with Object.fromEntries so arbitrary keys are ordinary own properties. Time and output space O(nodes), with recursion bounded by input depth.",
        ["Which values does Boolean reject besides null?", "Apply the same precise predicate to object fields and array elements.",
         "Replace truthiness filters with child !== null and retain the recursive reconstruction."], 16,
    ),
    problem(
        "numeric-version-order", "Version ten looks older than version two",
        "A release checker compares dotted versions as strings. Numeric segments and omitted trailing zeroes make that ordering disagree with the version contract.",
        "edge", "medium", ["versions", "parsing", "comparison"],
        ["Input.left and input.right are dotted version strings with one through six ASCII digit segments; each segment's value is 0 through 999.",
         "Compare segments numerically from left to right, treating missing trailing segments as zero. Leading zeroes do not matter.",
         "Return -1 if left is older, 0 if equal, or 1 if newer. There are no prerelease suffixes."],
        {"python": '''
            def solve(data):
                left, right = data["left"], data["right"]
                return (left > right) - (left < right)
        '''},
        {"python": '''
            from itertools import zip_longest
            def solve(data):
                left = map(int, data["left"].split("."))
                right = map(int, data["right"].split("."))
                for a, b in zip_longest(left, right, fillvalue=0):
                    if a != b:
                        return (a > b) - (a < b)
                return 0
        '''},
        [case("Different major versions", {"left": "2.0", "right": "1.9"}, 1),
         case("Two-digit segment", {"left": "1.10", "right": "1.2"}, 1),
         case("Implicit trailing zeros", {"left": "1", "right": "1.0.0"}, 0, True),
         case("Leading zeros", {"left": "01.002", "right": "1.2"}, 0, True),
         case("Later nonzero segment", {"left": "1.0.0", "right": "1.0.1"}, -1, True),
         case("All zero versions", {"left": "0.0", "right": "000"}, 0, True),
         case("Major version wins", {"left": "9.999", "right": "10.0"}, -1, True)],
        "Parse individual segments as integers and compare them with zero padding. Comparing complete strings or treating a version as a decimal number loses the segment ordering rule. Time and space O(total input characters).",
        ["Are segments ordered as text or as integers?", "An absent trailing segment has the same meaning as a zero segment.",
         "Zip the parsed segments with zero fill and return at the first numeric difference."], 14,
    ),
    problem(
        "intersection-initial-state", "The common labels vanish",
        "A Java label matcher starts its running intersection with an empty set. Intersecting any later group with that set can never recover common labels.",
        "edge", "easy", ["sets", "initialization", "intersection"],
        ["Input.groups is a list of lists of lowercase ASCII label strings, with at most 100 groups and 100 labels per group.",
         "Return the unique labels present in every group, sorted alphabetically. Duplicate labels inside one group count once.",
         "If there are no groups, return []. An empty group makes the intersection empty."],
        {"java": '''
            import com.google.gson.*;
            import java.util.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    Set<String> common = new TreeSet<>();
                    for (JsonElement raw : data.getAsJsonArray("groups")) {
                        Set<String> group = new HashSet<>();
                        for (JsonElement label : raw.getAsJsonArray()) group.add(label.getAsString());
                        common.retainAll(group);
                    }
                    return new Gson().toJsonTree(common);
                }
            }
        '''},
        {"java": '''
            import com.google.gson.*;
            import java.util.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    Set<String> common = new TreeSet<>(); boolean first = true;
                    for (JsonElement raw : data.getAsJsonArray("groups")) {
                        Set<String> group = new HashSet<>();
                        for (JsonElement label : raw.getAsJsonArray()) group.add(label.getAsString());
                        if (first) { common.addAll(group); first = false; }
                        else common.retainAll(group);
                    }
                    return new Gson().toJsonTree(common);
                }
            }
        '''},
        [case("Disjoint groups", {"groups": [["a"], ["b"]]}, []),
         case("A shared label", {"groups": [["a", "b"], ["b", "c"]]}, ["b"]),
         case("Single group", {"groups": [["z", "a", "a"]]}, ["a", "z"], True),
         case("Empty first group", {"groups": [[], ["a"]]}, [], True),
         case("Empty later group", {"groups": [["a"], []]}, [], True),
         case("No groups", {"groups": []}, [], True),
         case("Several shared labels", {"groups": [["b", "a", "c"], ["b", "a"], ["a", "b", "d"]]}, ["a", "b"], True)],
        "Initialize from the first actual group, even if that group is empty. Track whether a group was processed separately from whether the current intersection is empty. Time O(total labels × log distinct labels) with a sorted set, space O(distinct labels).",
        ["What happens when any set is intersected with the empty set?", "An empty first group is different from having no group yet.",
         "Copy the first group into the running set; only intersect subsequent groups."], 12,
    ),
    problem(
        "chunk-remainder", "The final partial batch disappears",
        "A Go batcher emits only full chunks. When the item count is not a multiple of the batch size, the last few items never reach the worker.",
        "edge", "easy", ["batching", "slices", "remainders"],
        ["Split input.items into consecutive chunks of at most input.size items, preserving order and keeping the final partial chunk.",
         "Return [] for size <= 0 or no items. Size has magnitude at most 1,000; items contains at most 100 integers of magnitude at most 1,000,000."],
        {"go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                items, size := data["items"].([]interface{}), int(data["size"].(float64))
                result := [][]int{}
                if size <= 0 { return result }
                for start := 0; start+size <= len(items); start += size {
                    chunk := []int{}
                    for _, raw := range items[start:start+size] { chunk = append(chunk, int(raw.(float64))) }
                    result = append(result, chunk)
                }
                return result
            }
        '''},
        {"go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                items, size := data["items"].([]interface{}), int(data["size"].(float64))
                result := [][]int{}
                if size <= 0 { return result }
                for start := 0; start < len(items); start += size {
                    end := start + size
                    if end > len(items) { end = len(items) }
                    chunk := []int{}
                    for _, raw := range items[start:end] { chunk = append(chunk, int(raw.(float64))) }
                    result = append(result, chunk)
                }
                return result
            }
        '''},
        [case("Full chunks", {"items": [1, 2, 3, 4], "size": 2}, [[1, 2], [3, 4]]),
         case("Partial final chunk", {"items": [1, 2, 3], "size": 2}, [[1, 2], [3]]),
         case("Less than one full chunk", {"items": [0, -1], "size": 9}, [[0, -1]], True),
         case("Individual items", {"items": [2, 2], "size": 1}, [[2], [2]], True),
         case("Empty input", {"items": [], "size": 3}, [], True),
         case("Zero size", {"items": [1], "size": 0}, [], True),
         case("Negative size", {"items": [1], "size": -2}, [], True)],
        "Continue while the next chunk has any starting item, then clamp its end to the collection length. Validate the size before using it as the loop increment. Time and output space O(n).",
        ["Does a chunk need to be full to be valid?", "The loop condition should test whether any items remain.",
         "Loop while start < len(items) and use min(start + size, len(items)) as the slice end."], 10,
    ),
    problem(
        "radix-zero-sign", "Zero has no representation",
        "A JavaScript radix formatter extracts digits only while the number is positive. It emits an empty string for zero and every negative number.",
        "edge", "medium", ["number-bases", "zero", "signs"],
        ["Convert input.number, an integer from -1,000,000,000 through 1,000,000,000, to base input.base (2 through 16).",
         "Use lowercase digits 0–9 and a–f, a leading minus sign only for negative numbers, and no leading zeroes.",
         "Zero must return '0'. Return a string."],
        {"javascript": '''
            function solve(data) {
              const digits = '0123456789abcdef';
              let number = data.number, result = '';
              while (number > 0) {
                result = digits[number % data.base] + result;
                number = Math.floor(number / data.base);
              }
              return result;
            }
            module.exports = { solve };
        '''},
        {"javascript": '''
            function solve(data) {
              const digits = '0123456789abcdef';
              let number = Math.abs(data.number), result = '';
              do {
                result = digits[number % data.base] + result;
                number = Math.floor(number / data.base);
              } while (number > 0);
              return (data.number < 0 ? '-' : '') + result;
            }
            module.exports = { solve };
        '''},
        [case("Positive binary", {"number": 10, "base": 2}, "1010"),
         case("Zero", {"number": 0, "base": 16}, "0"),
         case("Negative hexadecimal", {"number": -255, "base": 16}, "-ff", True),
         case("Base three", {"number": 10, "base": 3}, "101", True),
         case("Negative one", {"number": -1, "base": 2}, "-1", True),
         case("Large decimal", {"number": 1000000000, "base": 10}, "1000000000", True)],
        "Extract at least one digit from the absolute magnitude, then prepend a minus sign if needed. Separating sign handling also keeps remainders valid digit indices. There are O(log_base(|number| + 1)) digits; repeated string prepending may take quadratic time in that small digit count.",
        ["How many digits should zero produce?", "Use the magnitude for digit extraction and handle the sign separately.",
         "Use a do/while loop on Math.abs(number), then prepend '-' only for an original negative value."], 14,
    ),
    problem(
        "century-leap-day", "The calendar invents a leap day",
        "A calendar validator assumes every year divisible by four is a leap year. Century years reveal the missing Gregorian exception.",
        "edge", "medium", ["dates", "leap-years", "validation"],
        ["Return whether input.year, input.month, and input.day form a valid date in the proleptic Gregorian calendar.",
         "Year is 1 through 9999. Month and day are integers from -100 through 100; reject out-of-range values.",
         "Leap years are divisible by 4, except years divisible by 100 unless also divisible by 400."],
        {"python": '''
            def solve(data):
                year, month, day = data["year"], data["month"], data["day"]
                lengths = [31, 29 if year % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
                return 1 <= month <= 12 and 1 <= day <= lengths[month - 1]
        '''},
        {"python": '''
            def solve(data):
                year, month, day = data["year"], data["month"], data["day"]
                leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
                lengths = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
                return 1 <= month <= 12 and 1 <= day <= lengths[month - 1]
        '''},
        [case("Ordinary leap year", {"year": 2024, "month": 2, "day": 29}, True),
         case("Century exception", {"year": 1900, "month": 2, "day": 29}, False),
         case("Four-century exception", {"year": 2000, "month": 2, "day": 29}, True, True),
         case("Ordinary February", {"year": 2023, "month": 2, "day": 29}, False, True),
         case("Short month", {"year": 2026, "month": 4, "day": 31}, False, True),
         case("Invalid month", {"year": 2026, "month": 0, "day": 1}, False, True),
         case("Invalid day", {"year": 2026, "month": 12, "day": 0}, False, True),
         case("Last date of year", {"year": 9999, "month": 12, "day": 31}, True, True)],
        "Encode all three divisibility rules before choosing February's length. Validate the month before indexing the month-length table and include both day boundaries. Time and space O(1).",
        ["Do 1900 and 2000 follow the same century rule?", "Divisibility by 400 restores the leap day removed by divisibility by 100.",
         "Use year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)."], 12,
    ),
    problem(
        "closed-interval-touch", "A shared endpoint disappears",
        "A range-intersection tool uses the test for open intervals even though its endpoints are included. Two ranges meeting at one point are reported as disjoint.",
        "edge", "easy", ["intervals", "boundaries", "cpp"],
        ["Input.a and input.b are closed integer intervals [start, end], with start <= end and endpoint magnitude at most 1,000,000.",
         "Return their intersection as [start, end], or null if disjoint. A single shared endpoint is a valid one-point interval."],
        {"cpp": '''
            #include <nlohmann/json.hpp>
            #include <algorithm>
            using nlohmann::json;
            json solve(const json& data) {
                int left = std::max(data.at("a").at(0).get<int>(), data.at("b").at(0).get<int>());
                int right = std::min(data.at("a").at(1).get<int>(), data.at("b").at(1).get<int>());
                return left < right ? json::array({left, right}) : json(nullptr);
            }
        '''},
        {"cpp": '''
            #include <nlohmann/json.hpp>
            #include <algorithm>
            using nlohmann::json;
            json solve(const json& data) {
                int left = std::max(data.at("a").at(0).get<int>(), data.at("b").at(0).get<int>());
                int right = std::min(data.at("a").at(1).get<int>(), data.at("b").at(1).get<int>());
                return left <= right ? json::array({left, right}) : json(nullptr);
            }
        '''},
        [case("Ordinary overlap", {"a": [1, 5], "b": [3, 7]}, [3, 5]),
         case("Touching endpoints", {"a": [1, 3], "b": [3, 8]}, [3, 3]),
         case("Disjoint ranges", {"a": [1, 2], "b": [3, 4]}, None, True),
         case("One-point input", {"a": [0, 0], "b": [-2, 2]}, [0, 0], True),
         case("Contained range", {"a": [-9, 9], "b": [-2, 4]}, [-2, 4], True),
         case("Equal points", {"a": [-1, -1], "b": [-1, -1]}, [-1, -1], True)],
        "Compute the larger start and smaller end, then accept equality as well as a positive width. Closed ranges contain their endpoints. Time and space O(1).",
        ["Is the endpoint itself part of each range?", "An intersection can contain exactly one value.",
         "Return the candidate interval when left <= right."], 8,
    ),
    problem(
        "query-parameter-lists", "The URL loses half its filters",
        "A query-string reader keeps only the last value for each key and drops blank fields. Repeated filters and explicit empty selections cannot survive a round trip.",
        "edge", "medium", ["parsing", "urls", "duplicates"],
        ["Input.query is an application/x-www-form-urlencoded query string without a leading '?', at most 1,000 characters.",
         "Return an object mapping decoded keys to lists of all decoded values in arrival order. Keep blank values, bare keys as empty values, and blank keys.",
         "Split fields at '&' and each field at its first '='; ignore empty fields. Decode percent escapes and '+' as a space. Percent escapes are valid and decode to ASCII."],
        {"python": '''
            from urllib.parse import parse_qsl
            def solve(data):
                result = {}
                for key, value in parse_qsl(data["query"]):
                    result[key] = [value]
                return result
        '''},
        {"python": '''
            from urllib.parse import parse_qsl
            def solve(data):
                result = {}
                for key, value in parse_qsl(data["query"], keep_blank_values=True):
                    result.setdefault(key, []).append(value)
                return result
        '''},
        [case("One filter", {"query": "tag=python"}, {"tag": ["python"]}),
         case("Repeated filter", {"query": "tag=python&tag=go"}, {"tag": ["python", "go"]}),
         case("Blank and bare values", {"query": "q=&debug&tag=x"}, {"q": [""], "debug": [""], "tag": ["x"]}, True),
         case("Escaped separators", {"query": "q=a%26b%3Dc&plus=%2B+x"}, {"q": ["a&b=c"], "plus": ["+ x"]}, True),
         case("Empty fields and keys", {"query": "&=one&&=two&"}, {"": ["one", "two"]}, True),
         case("First equals only", {"query": "token=a=b=c"}, {"token": ["a=b=c"]}, True),
         case("Empty query", {"query": ""}, {}, True)],
        "Ask the form parser to keep blank values and accumulate a list per decoded key. Split before decoding so escaped separators remain part of their original value. Time and output space O(query length).",
        ["Can one key legitimately appear more than once?", "The parser's default treatment of blank values loses another kind of field.",
         "Use parse_qsl(..., keep_blank_values=True) and append each value with setdefault(key, [])."], 16,
    ),
])

CATALOG.extend([
    problem(
        "strict-decimal-cents", "A decimal amount loses a cent",
        "A Java import converts decimal strings through binary floating point and truncates the result. Some valid amounts lose a cent, while unsupported number formats are accepted.",
        "edge", "medium", ["decimals", "precision", "parsing"],
        ["For each string in input.amounts, return its exact integer cents or null if invalid.",
         "Valid syntax is an optional minus sign, 1–9 ASCII digits, and optionally a dot followed by 1–2 ASCII digits. Leading zeroes and negative zero are allowed.",
         "Reject whitespace, a plus sign, exponents, missing integer digits, and extra fractional digits. At most 100 strings of at most 30 characters; use a result type large enough for 99,999,999,999 cents."],
        {"java": '''
            import com.google.gson.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    JsonArray result = new JsonArray();
                    for (JsonElement raw : data.getAsJsonArray("amounts")) {
                        try { result.add((long)(Double.parseDouble(raw.getAsString()) * 100)); }
                        catch (NumberFormatException error) { result.add(JsonNull.INSTANCE); }
                    }
                    return result;
                }
            }
        '''},
        {"java": '''
            import com.google.gson.*;
            import java.math.BigDecimal;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    JsonArray result = new JsonArray();
                    for (JsonElement raw : data.getAsJsonArray("amounts")) {
                        String text = raw.getAsString();
                        if (!text.matches("-?[0-9]{1,9}([.][0-9]{1,2})?")) result.add(JsonNull.INSTANCE);
                        else result.add(new BigDecimal(text).movePointRight(2).longValueExact());
                    }
                    return result;
                }
            }
        '''},
        [case("Whole and fractional units", {"amounts": ["12", "1.50", "0.5"]}, [1200, 150, 50]),
         case("Binary rounding trap", {"amounts": ["0.29", "-0.29"]}, [29, -29]),
         case("Unsupported syntax", {"amounts": ["1e2", "+1", " 2", "2 ", ".5", "1.", "1.234"]}, [None] * 7, True),
         case("Exact large amount", {"amounts": ["999999999.99", "-999999999.99"]}, [99999999999, -99999999999], True),
         case("Leading and signed zero", {"amounts": ["0001.20", "-0.00", "0"]}, [120, 0, 0], True),
         case("Invalid fields", {"amounts": ["", "NaN", "Infinity", "1000000000", "１２"]}, [None] * 5, True),
         case("Empty import", {"amounts": []}, [], True)],
        "Validate the exact accepted grammar, then parse the original decimal text with BigDecimal and shift by two decimal places. Converting through double first cannot recover the lost decimal precision. Time O(total characters), output space O(amounts).",
        ["Is every two-decimal value represented exactly by a double?", "Rounding a double alone would still accept forbidden syntax.",
         "Validate the grammar, construct BigDecimal from the string, and use movePointRight(2).longValueExact()."], 18,
    ),
    problem(
        "median-even-pair", "The median drops its fractional half",
        "A C++ median calculation correctly finds the middle values but averages them with integer division. Even-sized samples can lose a half unit.",
        "edge", "medium", ["median", "integer-division", "sorting"],
        ["Return the median of input.values after numeric sorting. For an even count, return the arithmetic mean of the two middle values.",
         "An empty list returns null. There are at most 1,000 integers, each with magnitude at most 1,000,000. Preserve fractional and negative medians."],
        {"cpp": '''
            #include <nlohmann/json.hpp>
            #include <vector>
            #include <algorithm>
            using nlohmann::json;
            json solve(const json& data) {
                auto values = data.at("values").get<std::vector<int>>();
                if (values.empty()) return nullptr;
                std::sort(values.begin(), values.end()); int middle = values.size() / 2;
                if (values.size() % 2) return values[middle];
                return (values[middle - 1] + values[middle]) / 2;
            }
        '''},
        {"cpp": '''
            #include <nlohmann/json.hpp>
            #include <vector>
            #include <algorithm>
            using nlohmann::json;
            json solve(const json& data) {
                auto values = data.at("values").get<std::vector<int>>();
                if (values.empty()) return nullptr;
                std::sort(values.begin(), values.end()); int middle = values.size() / 2;
                if (values.size() % 2) return values[middle];
                return (values[middle - 1] + values[middle]) / 2.0;
            }
        '''},
        [case("Odd sample", {"values": [9, 1, 3]}, 3), case("Fractional median", {"values": [1, 2]}, 1.5),
         case("Negative median", {"values": [-4, -1]}, -2.5, True),
         case("Middle values only", {"values": [100, 2, 3, -100]}, 2.5, True),
         case("Repeated values", {"values": [5, 5, 5, 5]}, 5, True),
         case("Empty sample", {"values": []}, None, True)],
        "Use floating-point division for the even-count average. The given input bounds keep the integer addition safe; changing only the denominator preserves the half-unit result. Time O(n log n), space O(n) for the copied values.",
        ["What type is the division when both operands are integers?", "Converting the result after division is too late.",
         "Divide the middle-value sum by 2.0."], 12,
    ),
    problem(
        "descending-range-step", "The countdown never starts",
        "A range builder rejects start values above the stop before considering the step. That check discards every valid descending range.",
        "edge", "easy", ["ranges", "negative-step", "boundaries"],
        ["Return the integers starting at input.start and repeatedly adding input.step, excluding input.stop and stopping before crossing it.",
         "A positive step requires start < stop; a negative step requires start > stop. A zero step returns [].",
         "Start and stop are integers from -100 through 100; step is from -20 through 20."],
        {"python": '''
            def solve(data):
                if data["step"] == 0 or data["start"] >= data["stop"]:
                    return []
                return list(range(data["start"], data["stop"], data["step"]))
        '''},
        {"python": '''
            def solve(data):
                if data["step"] == 0:
                    return []
                return list(range(data["start"], data["stop"], data["step"]))
        '''},
        [case("Count upward", {"start": 1, "stop": 5, "step": 2}, [1, 3]),
         case("Count downward", {"start": 5, "stop": 0, "step": -2}, [5, 3, 1]),
         case("Wrong direction", {"start": 1, "stop": 5, "step": -1}, [], True),
         case("Equal endpoints", {"start": 3, "stop": 3, "step": -1}, [], True),
         case("Zero step", {"start": 0, "stop": 5, "step": 0}, [], True),
         case("Across zero", {"start": 2, "stop": -3, "step": -1}, [2, 1, 0, -1, -2], True),
         case("Step passes endpoint", {"start": 1, "stop": 0, "step": -20}, [1], True)],
        "The valid direction depends on the step's sign. Python's range already handles both directions and exclusive endpoints, so only the zero-step case needs an explicit guard. Time and output space O(number of emitted values).",
        ["Which direction does a negative step move?", "The start-versus-stop check assumes an ascending sequence.",
         "Keep the zero-step guard and let range handle direction and stopping."], 10,
    ),
    problem(
        "anagram-multiplicity", "The anagram key forgets repeated letters",
        "A Java word grouper uses a set of letters as its signature. Words with the same distinct letters but different letter counts are merged into one group.",
        "edge", "medium", ["anagrams", "multiplicity", "hash-map"],
        ["Group input.words by anagram equivalence: every letter must occur the same number of times.",
         "Preserve group order by first appearance and word order inside each group. Keep duplicate and empty words.",
         "There are at most 100 lowercase ASCII words, each at most 100 characters."],
        {"java": '''
            import com.google.gson.*;
            import java.util.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    Map<String, JsonArray> groups = new LinkedHashMap<>();
                    for (JsonElement raw : data.getAsJsonArray("words")) {
                        String word = raw.getAsString(); Set<Character> letters = new TreeSet<>();
                        for (char letter : word.toCharArray()) letters.add(letter);
                        String key = letters.toString();
                        groups.computeIfAbsent(key, ignored -> new JsonArray()).add(word);
                    }
                    JsonArray result = new JsonArray(); for (JsonArray group : groups.values()) result.add(group);
                    return result;
                }
            }
        '''},
        {"java": '''
            import com.google.gson.*;
            import java.util.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    Map<String, JsonArray> groups = new LinkedHashMap<>();
                    for (JsonElement raw : data.getAsJsonArray("words")) {
                        String word = raw.getAsString(); char[] letters = word.toCharArray();
                        Arrays.sort(letters); String key = new String(letters);
                        groups.computeIfAbsent(key, ignored -> new JsonArray()).add(word);
                    }
                    JsonArray result = new JsonArray(); for (JsonArray group : groups.values()) result.add(group);
                    return result;
                }
            }
        '''},
        [case("Ordinary anagrams", {"words": ["eat", "tea", "tan", "ate"]}, [["eat", "tea", "ate"], ["tan"]]),
         case("Repeated letters matter", {"words": ["ab", "aab", "ba", "aba"]}, [["ab", "ba"], ["aab", "aba"]]),
         case("Empty words", {"words": ["", "a", ""]}, [["", ""], ["a"]], True),
         case("Preserve duplicate words", {"words": ["aa", "aa", "a"]}, [["aa", "aa"], ["a"]], True),
         case("Group arrival order", {"words": ["z", "xy", "yx", "zz", "z"]}, [["z", "z"], ["xy", "yx"], ["zz"]], True),
         case("No words", {"words": []}, [], True)],
        "A sorted character sequence preserves multiplicity while providing a shared key for anagrams. LinkedHashMap retains the first-seen order of groups. Time O(sum of word length × log word length), space proportional to the input and output.",
        ["What information does a set discard?", "The signature needs letter counts as well as letter identities.",
         "Sort each word's complete character array and use the resulting string as the key."], 16,
    ),
    problem(
        "polynomial-zero-coefficients", "Removing zeroes changes the polynomial",
        "A polynomial multiplier normalizes its output by removing every zero coefficient. Interior zeroes encode missing powers and must stay in place.",
        "edge", "medium", ["polynomials", "arrays", "normalization"],
        ["Input.a and input.b list integer coefficients in ascending power order: [2, 0, 3] means 2 + 3x².",
         "Return coefficients of the product in the same order. Remove only trailing zero coefficients; represent the zero polynomial as [0].",
         "An empty input array represents zero. Each array has at most 30 coefficients of magnitude at most 100."],
        {"python": '''
            def solve(data):
                a, b = data["a"], data["b"]
                if not a or not b:
                    return [0]
                result = [0] * (len(a) + len(b) - 1)
                for i, left in enumerate(a):
                    for j, right in enumerate(b):
                        result[i + j] += left * right
                return [value for value in result if value != 0] or [0]
        '''},
        {"python": '''
            def solve(data):
                a, b = data["a"], data["b"]
                if not a or not b:
                    return [0]
                result = [0] * (len(a) + len(b) - 1)
                for i, left in enumerate(a):
                    for j, right in enumerate(b):
                        result[i + j] += left * right
                while len(result) > 1 and result[-1] == 0:
                    result.pop()
                return result
        '''},
        [case("Ordinary product", {"a": [1, 1], "b": [1, 1]}, [1, 2, 1]),
         case("Interior zero", {"a": [1, 1], "b": [1, -1]}, [1, 0, -1]),
         case("Leading zero powers", {"a": [0, 1], "b": [0, 1]}, [0, 0, 1], True),
         case("Trailing zero normalization", {"a": [2, 0], "b": [3, 0]}, [6], True),
         case("Zero polynomial", {"a": [0, 0], "b": [1, 2]}, [0], True),
         case("Empty polynomial", {"a": [], "b": [1]}, [0], True),
         case("Constant product", {"a": [-3], "b": [2]}, [-6], True)],
        "A coefficient's index encodes its power, so removing an interior entry changes every later power. Pop only zeroes at the highest-power end while retaining one coefficient for zero. Time O(len(a) × len(b)), space O(len(a) + len(b)).",
        ["What does an array index mean in this representation?", "A zero coefficient can be structurally necessary.",
         "Keep the product array intact and pop from its end while the last value is zero and more than one coefficient remains."], 16,
    ),
    problem(
        "lossy-id-comparison", "Distinct identifiers become the same number",
        "A JavaScript synchronizer converts decimal identifier strings to Number before comparing them. Large consecutive IDs round to the same value and appear equal.",
        "edge", "medium", ["precision", "big-integers", "comparison"],
        ["Input.left and input.right are nonempty strings of 1–100 ASCII digits representing nonnegative integers. Leading zeroes are allowed.",
         "Return -1, 0, or 1 for exact numeric comparison of left with right. Do not lose precision for large identifiers."],
        {"javascript": '''
            function solve(data) {
              const left = Number(data.left), right = Number(data.right);
              return Number(left > right) - Number(left < right);
            }
            module.exports = { solve };
        '''},
        {"javascript": '''
            function solve(data) {
              const left = data.left.replace(/^0+/, '') || '0';
              const right = data.right.replace(/^0+/, '') || '0';
              if (left.length !== right.length) return left.length < right.length ? -1 : 1;
              return Number(left > right) - Number(left < right);
            }
            module.exports = { solve };
        '''},
        [case("Small identifiers", {"left": "12", "right": "9"}, 1),
         case("Adjacent large identifiers", {"left": "9007199254740993", "right": "9007199254740992"}, 1),
         case("Leading zeroes", {"left": "00042", "right": "42"}, 0, True),
         case("Zero representations", {"left": "000", "right": "0"}, 0, True),
         case("Long common prefix", {"left": "1" + "0" * 98 + "1", "right": "1" + "0" * 98 + "2"}, -1, True),
         case("Different lengths", {"left": "9" * 99, "right": "1" + "0" * 99}, -1, True),
         case("Equal large identifiers", {"left": "7" * 100, "right": "7" * 100}, 0, True)],
        "Strip leading zeroes, compare digit counts, then compare equal-length strings lexicographically. This compares nonnegative integers exactly without converting them to a limited-precision numeric type. Time and space O(digits).",
        ["Can Number distinguish every integer with this many digits?", "After removing leading zeroes, the longer digit string is larger.",
         "Normalize zero, compare lengths, and compare the strings directly only when their lengths match."], 16,
    ),
    problem(
        "second-distinct-maximum", "Second place is still first place",
        "A Go leaderboard takes the penultimate sorted score as the runner-up. Repeated maximum scores mean that position can still contain the highest score.",
        "edge", "medium", ["duplicates", "extrema", "sorting"],
        ["Return the second-largest distinct integer in input.values, or null if fewer than two distinct values exist.",
         "There are at most 1,000 values with magnitude at most 1,000,000. Negative numbers and zero are valid."],
        {"go": '''
            package main
            import "sort"
            func Solve(data map[string]interface{}) interface{} {
                values := []int{}
                for _, raw := range data["values"].([]interface{}) { values = append(values, int(raw.(float64))) }
                sort.Ints(values)
                if len(values) < 2 { return nil }
                return values[len(values)-2]
            }
        '''},
        {"go": '''
            package main
            import "sort"
            func Solve(data map[string]interface{}) interface{} {
                values := []int{}
                for _, raw := range data["values"].([]interface{}) { values = append(values, int(raw.(float64))) }
                sort.Ints(values)
                for i := len(values)-2; i >= 0; i-- {
                    if values[i] != values[len(values)-1] { return values[i] }
                }
                return nil
            }
        '''},
        [case("Distinct scores", {"values": [2, 9, 5]}, 5),
         case("Tied maximum", {"values": [5, 9, 9]}, 5),
         case("All equal", {"values": [3, 3, 3]}, None, True),
         case("Negative scores", {"values": [-8, -2, -2, -5]}, -5, True),
         case("Zero is runner-up", {"values": [0, 1, 1]}, 0, True),
         case("Single value", {"values": [7]}, None, True),
         case("No scores", {"values": []}, None, True)],
        "After sorting, skip every copy of the maximum and return the first smaller value. If no such value exists, return null rather than a duplicate or numeric sentinel. Time O(n log n), space O(n) for the copied values.",
        ["Does the second position always represent the second distinct score?", "There may be several copies of the maximum, or no smaller value at all.",
         "Scan backward past all values equal to the maximum; return null if the scan finds none."], 12,
    ),
])


# Problems 86–100: business rules and stateful workflows.
CATALOG.extend([
    problem(
        "tiered-usage-billing", "Crossing a tier makes the bill shrink",
        "A usage bill applies the final pricing tier to every unit. Crossing a threshold retroactively discounts earlier units, instead of charging each tier separately.",
        "business", "medium", ["pricing", "tiers", "arithmetic"],
        ["Input.units is an integer from 0 through 1,000,000.",
         "Charge 5 cents for each of the first 100 units, 3 cents for each of the next 900 units, and 1 cent for each remaining unit.",
         "Return the total integer cents. These are graduated tiers, with no minimum fee or rounding."],
        {"python": '''
            def solve(data):
                units = data["units"]
                rate = 5 if units <= 100 else 3 if units <= 1000 else 1
                return units * rate
        '''},
        {"python": '''
            def solve(data):
                units = data["units"]
                return min(units, 100) * 5 + min(max(units - 100, 0), 900) * 3 + max(units - 1000, 0)
        '''},
        [case("First tier", {"units": 50}, 250), case("Enter second tier", {"units": 101}, 503),
         case("First boundary", {"units": 100}, 500, True), case("Second boundary", {"units": 1000}, 3200, True),
         case("Enter last tier", {"units": 1001}, 3201, True), case("No usage", {"units": 0}, 0, True),
         case("Maximum usage", {"units": 1000000}, 1002200, True)],
        "Allocate usage to each band before multiplying by that band's price. Earlier units keep their original rates when later units enter a cheaper tier. Time and space O(1).",
        ["Should the 101st unit change the price of the first 100?", "Calculate how many units belong to each band separately.",
         "Charge min(units, 100) at 5, the next at most 900 at 3, and the remainder at 1."], 14,
    ),
    problem(
        "shipping-after-discount", "The discount keeps shipping free",
        "A checkout decides free-shipping eligibility before subtracting the discount. Orders below the required payable subtotal still receive free delivery.",
        "business", "easy", ["checkout", "thresholds", "ordering"],
        ["Input.subtotal, discount, threshold, and fee are nonnegative integer cents at most 1,000,000; discount <= subtotal.",
         "Shipping is free when subtotal minus discount is at least threshold; otherwise charge fee.",
         "Return {shipping: shipping charge, total: discounted subtotal plus shipping}. Apply this rule even to a zero subtotal."],
        {"javascript": '''
            function solve(data) {
              const shipping = data.subtotal >= data.threshold ? 0 : data.fee;
              return { shipping, total: data.subtotal - data.discount + shipping };
            }
            module.exports = { solve };
        '''},
        {"javascript": '''
            function solve(data) {
              const payable = data.subtotal - data.discount;
              const shipping = payable >= data.threshold ? 0 : data.fee;
              return { shipping, total: payable + shipping };
            }
            module.exports = { solve };
        '''},
        [case("Free delivery", {"subtotal": 120, "discount": 10, "threshold": 100, "fee": 15}, {"shipping": 0, "total": 110}),
         case("Discount drops below threshold", {"subtotal": 100, "discount": 20, "threshold": 90, "fee": 10}, {"shipping": 10, "total": 90}),
         case("Exact payable threshold", {"subtotal": 120, "discount": 20, "threshold": 100, "fee": 15}, {"shipping": 0, "total": 100}, True),
         case("Zero threshold", {"subtotal": 0, "discount": 0, "threshold": 0, "fee": 15}, {"shipping": 0, "total": 0}, True),
         case("Fully discounted order", {"subtotal": 50, "discount": 50, "threshold": 10, "fee": 7}, {"shipping": 7, "total": 7}, True),
         case("No discount", {"subtotal": 40, "discount": 0, "threshold": 100, "fee": 5}, {"shipping": 5, "total": 45}, True)],
        "Compute the payable subtotal first and use that same amount for both threshold eligibility and the final charge. Equality qualifies for free shipping. Time and space O(1).",
        ["Which subtotal does the shipping policy use?", "The discounted amount can fall on the other side of the threshold.",
         "Calculate payable = subtotal - discount before choosing the shipping charge."], 10,
    ),
    problem(
        "loyalty-threshold-carry", "The reward wipes out leftover points",
        "A rewards service issues one voucher and resets points to zero after crossing a threshold. It loses leftover points and misses multiple vouchers earned in one purchase.",
        "business", "medium", ["rewards", "remainders", "state"],
        ["Input.points is an integer from 0 through 99. Input.earned lists 0 through 100 nonnegative integer point awards, each at most 1,000.",
         "After each award, issue one voucher per complete 100 points and carry the remainder to the next award.",
         "Return {vouchers: [vouchers issued per award], state: {points: unspent remainder}}."],
        {"python": '''
            def solve(data):
                points, vouchers = data["points"], []
                for earned in data["earned"]:
                    points += earned
                    if points >= 100:
                        vouchers.append(1)
                        points = 0
                    else:
                        vouchers.append(0)
                return {"vouchers": vouchers, "state": {"points": points}}
        '''},
        {"python": '''
            def solve(data):
                points, vouchers = data["points"], []
                for earned in data["earned"]:
                    issued, points = divmod(points + earned, 100)
                    vouchers.append(issued)
                return {"vouchers": vouchers, "state": {"points": points}}
        '''},
        [case("Exact reward", {"points": 80, "earned": [20]}, {"vouchers": [1], "state": {"points": 0}}),
         case("Carry to next award", {"points": 80, "earned": [30, 90]}, {"vouchers": [1, 1], "state": {"points": 0}}),
         case("Several vouchers at once", {"points": 0, "earned": [250]}, {"vouchers": [2], "state": {"points": 50}}, True, [{"path": "state.points", "equals": 50}]),
         case("No award", {"points": 67, "earned": []}, {"vouchers": [], "state": {"points": 67}}, True),
         case("Zero award", {"points": 99, "earned": [0]}, {"vouchers": [0], "state": {"points": 99}}, True),
         case("Several purchases", {"points": 0, "earned": [60, 60, 90]}, {"vouchers": [0, 1, 1], "state": {"points": 10}}, True)],
        "Divide the accumulated points by 100 after each award. The quotient is the number of new vouchers and the remainder is the state carried forward. Time O(awards), working space O(1) excluding the output.",
        ["Which points have actually been redeemed?", "One award can cross the threshold more than once.",
         "Use divmod(points + earned, 100) for issued vouchers and the next points balance."], 14,
    ),
    problem(
        "seat-downgrade-capacity", "The plan shrinks below its active users",
        "A subscription update accepts every nonnegative seat limit, including limits below the number of active users. Available seats become negative after a downgrade.",
        "business", "medium", ["subscriptions", "capacity", "invariants"],
        ["Input.users lists unique active user IDs; input.limit is a nonnegative seat limit at least as large as the user count.",
         "Process integer input.requests in order. Accept a new seat limit only when it is nonnegative and at least the active user count; rejected requests leave the current limit unchanged.",
         "Return {accepted: [booleans], state: {limit, available: limit - active users}}. Users do not change. At most 100 users and requests; limits have magnitude at most 1,000."],
        {"python": '''
            def solve(data):
                limit, accepted = data["limit"], []
                for requested in data["requests"]:
                    ok = requested >= 0
                    accepted.append(ok)
                    if ok:
                        limit = requested
                return {"accepted": accepted, "state": {"limit": limit, "available": limit - len(data["users"])}}
        '''},
        {"python": '''
            def solve(data):
                limit, accepted = data["limit"], []
                for requested in data["requests"]:
                    ok = requested >= len(data["users"])
                    accepted.append(ok)
                    if ok:
                        limit = requested
                return {"accepted": accepted, "state": {"limit": limit, "available": limit - len(data["users"])}}
        '''},
        [case("Safe downgrade", {"limit": 5, "users": ["a", "b"], "requests": [3]}, {"accepted": [True], "state": {"limit": 3, "available": 1}}),
         case("Below active usage", {"limit": 5, "users": ["a", "b", "c"], "requests": [2]}, {"accepted": [False], "state": {"limit": 5, "available": 2}}, assertions=[{"path": "state.limit", "equals": 5}]),
         case("Exact usage", {"limit": 4, "users": ["a", "b"], "requests": [2]}, {"accepted": [True], "state": {"limit": 2, "available": 0}}, True),
         case("Rejected update preserves previous success", {"limit": 5, "users": ["a", "b"], "requests": [4, 1]}, {"accepted": [True, False], "state": {"limit": 4, "available": 2}}, True),
         case("Empty workspace", {"limit": 1, "users": [], "requests": [0, -1]}, {"accepted": [True, False], "state": {"limit": 0, "available": 0}}, True),
         case("No changes", {"limit": 2, "users": ["a"], "requests": []}, {"accepted": [], "state": {"limit": 2, "available": 1}}, True)],
        "Validate the proposed limit against committed usage before changing state. Since user count is nonnegative, requiring limit >= user count also rejects negative limits. Time O(requests), output space O(requests).",
        ["A nonnegative capacity can still be too small.", "The available-seat count should never go below zero.",
         "Accept only requested limits at least len(users), then update the current limit."], 14,
    ),
    problem(
        "daily-usage-reset", "An old request rewinds the quota clock",
        "A Go quota meter resets usage whenever the incoming day differs from its current day. A delayed request from yesterday resets today's quota and can be accepted incorrectly.",
        "business", "medium", ["quotas", "events", "state"],
        ["Input.limit is nonnegative. Input.state contains integer day and used, with 0 <= used <= limit. Input.requests lists {day, amount} in processing order.",
         "Reject older-day requests without changing state. For a newer day, advance state.day and reset used to zero before validating the amount, even if that request is rejected.",
         "Accept only positive amounts whose addition would not exceed limit. Rejections on the current day do not consume quota.",
         "Return {accepted: [booleans], state: {day, used}}. At most 100 requests; all integers have magnitude at most 1,000,000."],
        {"go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                state := data["state"].(map[string]interface{})
                day, used, limit := int(state["day"].(float64)), int(state["used"].(float64)), int(data["limit"].(float64))
                accepted := []bool{}
                for _, raw := range data["requests"].([]interface{}) {
                    request := raw.(map[string]interface{}); next, amount := int(request["day"].(float64)), int(request["amount"].(float64))
                    if next != day { day, used = next, 0 }
                    ok := amount > 0 && used+amount <= limit
                    accepted = append(accepted, ok)
                    if ok { used += amount }
                }
                return map[string]interface{}{"accepted": accepted, "state": map[string]int{"day": day, "used": used}}
            }
        '''},
        {"go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                state := data["state"].(map[string]interface{})
                day, used, limit := int(state["day"].(float64)), int(state["used"].(float64)), int(data["limit"].(float64))
                accepted := []bool{}
                for _, raw := range data["requests"].([]interface{}) {
                    request := raw.(map[string]interface{}); next, amount := int(request["day"].(float64)), int(request["amount"].(float64))
                    if next < day { accepted = append(accepted, false); continue }
                    if next > day { day, used = next, 0 }
                    ok := amount > 0 && used+amount <= limit
                    accepted = append(accepted, ok)
                    if ok { used += amount }
                }
                return map[string]interface{}{"accepted": accepted, "state": map[string]int{"day": day, "used": used}}
            }
        '''},
        [case("Current-day usage", {"limit": 5, "state": {"day": 10, "used": 2}, "requests": [{"day": 10, "amount": 3}]}, {"accepted": [True], "state": {"day": 10, "used": 5}}),
         case("Late request", {"limit": 5, "state": {"day": 10, "used": 4}, "requests": [{"day": 9, "amount": 1}]}, {"accepted": [False], "state": {"day": 10, "used": 4}}, assertions=[{"path": "state.used", "equals": 4}]),
         case("New day resets quota", {"limit": 5, "state": {"day": 10, "used": 5}, "requests": [{"day": 11, "amount": 2}]}, {"accepted": [True], "state": {"day": 11, "used": 2}}, True),
         case("New day with rejected amount", {"limit": 3, "state": {"day": 10, "used": 2}, "requests": [{"day": 11, "amount": 4}]}, {"accepted": [False], "state": {"day": 11, "used": 0}}, True),
         case("Rejected amounts do not consume", {"limit": 3, "state": {"day": 1, "used": 1}, "requests": [{"day": 1, "amount": 3}, {"day": 1, "amount": 0}, {"day": 1, "amount": -1}, {"day": 1, "amount": 2}]}, {"accepted": [False, False, False, True], "state": {"day": 1, "used": 3}}, True),
         case("Old event after reset", {"limit": 2, "state": {"day": 1, "used": 0}, "requests": [{"day": 2, "amount": 1}, {"day": 1, "amount": 1}]}, {"accepted": [True, False], "state": {"day": 2, "used": 1}}, True),
         case("No requests", {"limit": 0, "state": {"day": 0, "used": 0}, "requests": []}, {"accepted": [], "state": {"day": 0, "used": 0}}, True)],
        "Keep the meter's day monotonic: reject past days and reset only on future days. Then validate the amount against the current day's available quota. Time O(requests), working space O(1) excluding feedback.",
        ["Does a different day always mean a newer day?", "Handle older, equal, and newer days as three separate cases.",
         "Reject next < day, reset only for next > day, then validate positive usage against the limit."], 18,
    ),
    problem(
        "contiguous-event-replay", "An early event skips the missing update",
        "A projection consumer advances directly to any newer version. When events arrive out of order, it skips missing deltas and treats their later arrival as stale.",
        "business", "hard", ["events", "ordering", "buffering"],
        ["Input.state contains a nonnegative version and integer total. Input.events lists {version: positive integer, delta: integer}; the pending buffer starts empty.",
         "Ignore versions <= the current applied version. Buffer higher versions; the first received event wins if a pending version repeats.",
         "After each event, apply and remove every consecutively available version starting at current version + 1, adding each delta to total.",
         "Return {applied: [versions in application order], state: {version, total, pending: [buffered {version, delta} sorted by version]}}. At most 100 events; integer magnitudes at most 1,000,000."],
        {"javascript": '''
            function solve(data) {
              let { version, total } = data.state;
              const applied = [];
              for (const event of data.events) {
                if (event.version <= version) continue;
                version = event.version;
                total += event.delta;
                applied.push(version);
              }
              return { applied, state: { version, total, pending: [] } };
            }
            module.exports = { solve };
        '''},
        {"javascript": '''
            function solve(data) {
              let { version, total } = data.state;
              const applied = [], pending = new Map();
              for (const event of data.events) {
                if (event.version <= version) continue;
                if (!pending.has(event.version)) pending.set(event.version, event.delta);
                while (pending.has(version + 1)) {
                  version++;
                  total += pending.get(version);
                  pending.delete(version);
                  applied.push(version);
                }
              }
              const buffered = [...pending].sort((a, b) => a[0] - b[0]).map(([version, delta]) => ({ version, delta }));
              return { applied, state: { version, total, pending: buffered } };
            }
            module.exports = { solve };
        '''},
        [case("In-order events", {"state": {"version": 0, "total": 0}, "events": [{"version": 1, "delta": 2}, {"version": 2, "delta": 3}]}, {"applied": [1, 2], "state": {"version": 2, "total": 5, "pending": []}}),
         case("Gap later filled", {"state": {"version": 0, "total": 10}, "events": [{"version": 2, "delta": 5}, {"version": 1, "delta": 3}]}, {"applied": [1, 2], "state": {"version": 2, "total": 18, "pending": []}}, assertions=[{"path": "state.total", "equals": 18}]),
         case("Unfilled gap", {"state": {"version": 0, "total": 0}, "events": [{"version": 3, "delta": 9}]}, {"applied": [], "state": {"version": 0, "total": 0, "pending": [{"version": 3, "delta": 9}]}}, True),
         case("First buffered event wins", {"state": {"version": 0, "total": 0}, "events": [{"version": 2, "delta": 5}, {"version": 2, "delta": 99}, {"version": 1, "delta": 1}]}, {"applied": [1, 2], "state": {"version": 2, "total": 6, "pending": []}}, True),
         case("Stale versions", {"state": {"version": 5, "total": 20}, "events": [{"version": 4, "delta": 100}, {"version": 5, "delta": 100}, {"version": 6, "delta": -2}]}, {"applied": [6], "state": {"version": 6, "total": 18, "pending": []}}, True),
         case("Drain only a contiguous prefix", {"state": {"version": 0, "total": 0}, "events": [{"version": 4, "delta": 4}, {"version": 2, "delta": 2}, {"version": 1, "delta": 1}]}, {"applied": [1, 2], "state": {"version": 2, "total": 3, "pending": [{"version": 4, "delta": 4}]}}, True),
         case("Sorted pending output", {"state": {"version": 0, "total": 7}, "events": [{"version": 5, "delta": 0}, {"version": 3, "delta": -1}]}, {"applied": [], "state": {"version": 0, "total": 7, "pending": [{"version": 3, "delta": -1}, {"version": 5, "delta": 0}]}}, True),
         case("No events", {"state": {"version": 2, "total": 7}, "events": []}, {"applied": [], "state": {"version": 2, "total": 7, "pending": []}}, True)],
        "Separate received versions from committed versions. Buffer each future version once, then drain only a contiguous sequence so every delta is applied exactly once and in order. Expected processing time O(events), plus O(pending log pending) for output ordering; space O(events).",
        ["A newer version may still have a missing predecessor.", "The highest received version is not necessarily the highest safely applied version.",
         "Buffer by version, retain the first duplicate, and repeatedly apply current + 1 while it is present."], 28,
    ),
    problem(
        "cart-reservation-atomicity", "Half the cart is reserved after rejection",
        "An inventory service reserves cart lines one by one. A later invalid line rejects the order after earlier products have already lost stock.",
        "business", "hard", ["transactions", "inventory", "atomicity"],
        ["Input.stock maps product IDs to nonnegative quantities. Input.items is an ordered list of {sku, quantity}; a SKU may repeat.",
         "Accept only a nonempty cart where every quantity is positive, every SKU exists, and each SKU's combined quantity fits its stock.",
         "Return {ok: boolean, state: {stock: updated inventory}}. Rejecting a cart must preserve all original quantities; success deducts all lines together.",
         "At most 100 products and cart lines. Stock and quantities are integers with magnitude at most 1,000,000."],
        {"python": '''
            def solve(data):
                stock = data["stock"].copy()
                if not data["items"]:
                    return {"ok": False, "state": {"stock": stock}}
                for item in data["items"]:
                    sku, quantity = item["sku"], item["quantity"]
                    if quantity <= 0 or sku not in stock or quantity > stock[sku]:
                        return {"ok": False, "state": {"stock": stock}}
                    stock[sku] -= quantity
                return {"ok": True, "state": {"stock": stock}}
        '''},
        {"python": '''
            def solve(data):
                stock, required = data["stock"].copy(), {}
                if not data["items"]:
                    return {"ok": False, "state": {"stock": stock}}
                for item in data["items"]:
                    sku, quantity = item["sku"], item["quantity"]
                    if quantity <= 0 or sku not in stock:
                        return {"ok": False, "state": {"stock": stock}}
                    required[sku] = required.get(sku, 0) + quantity
                if any(quantity > stock[sku] for sku, quantity in required.items()):
                    return {"ok": False, "state": {"stock": stock}}
                for sku, quantity in required.items():
                    stock[sku] -= quantity
                return {"ok": True, "state": {"stock": stock}}
        '''},
        [case("Complete reservation", {"stock": {"a": 5, "b": 3}, "items": [{"sku": "a", "quantity": 2}, {"sku": "b", "quantity": 1}]}, {"ok": True, "state": {"stock": {"a": 3, "b": 2}}}),
         case("Later line cannot fit", {"stock": {"a": 5, "b": 3}, "items": [{"sku": "a", "quantity": 2}, {"sku": "b", "quantity": 4}]}, {"ok": False, "state": {"stock": {"a": 5, "b": 3}}}, assertions=[{"path": "state.stock.a", "equals": 5}]),
         case("Repeated SKU exceeds stock", {"stock": {"a": 3}, "items": [{"sku": "a", "quantity": 2}, {"sku": "a", "quantity": 2}]}, {"ok": False, "state": {"stock": {"a": 3}}}, True),
         case("Invalid later quantity", {"stock": {"a": 3}, "items": [{"sku": "a", "quantity": 1}, {"sku": "a", "quantity": 0}]}, {"ok": False, "state": {"stock": {"a": 3}}}, True),
         case("Unknown later product", {"stock": {"a": 3}, "items": [{"sku": "a", "quantity": 1}, {"sku": "x", "quantity": 1}]}, {"ok": False, "state": {"stock": {"a": 3}}}, True),
         case("Empty cart", {"stock": {"a": 3}, "items": []}, {"ok": False, "state": {"stock": {"a": 3}}}, True),
         case("Combined exact stock", {"stock": {"a": 3, "idle": 2}, "items": [{"sku": "a", "quantity": 1}, {"sku": "a", "quantity": 2}]}, {"ok": True, "state": {"stock": {"a": 0, "idle": 2}}}, True)],
        "Stage requested totals per SKU and validate the entire cart before changing inventory. Aggregate repeated SKUs so individually affordable lines cannot over-reserve the same product. Expected time O(products + lines), space O(products + distinct requested SKUs).",
        ["What inventory is returned if the last cart line fails?", "Every line must be validated before any deduction becomes visible.",
         "Aggregate quantities per SKU, validate all totals, then commit all deductions in a separate loop."], 25,
    ),
])

CATALOG.extend([
    problem(
        "gift-card-expiry-order", "The oldest credit is spent last",
        "A Java checkout spends gift cards in input order. Credit that expires soon is left untouched while later-expiring credit is consumed first.",
        "business", "medium", ["payments", "expiry", "ordering"],
        ["Input.cards lists {id, balance, expires_at} with unique IDs and nonnegative integer-cent balances. Input.amount is a nonnegative purchase amount; input.now is fixed.",
         "Spend only cards with expires_at > now, in ascending expiry order, breaking ties by their original input order. Spend up to each balance until the purchase is covered.",
         "Return {charge: amount still payable, state: {cards: all cards in original order with updated balances}}. Preserve expired cards and their balances.",
         "At most 100 cards; integer magnitudes are at most 1,000,000."],
        {"java": '''
            import com.google.gson.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    JsonArray cards = data.getAsJsonArray("cards").deepCopy();
                    int charge = data.get("amount").getAsInt(), now = data.get("now").getAsInt();
                    for (JsonElement raw : cards) {
                        JsonObject card = raw.getAsJsonObject();
                        if (card.get("expires_at").getAsInt() <= now) continue;
                        int balance = card.get("balance").getAsInt(), spent = Math.min(charge, balance);
                        card.addProperty("balance", balance - spent); charge -= spent;
                    }
                    JsonObject state = new JsonObject(); state.add("cards", cards);
                    JsonObject result = new JsonObject(); result.addProperty("charge", charge); result.add("state", state);
                    return result;
                }
            }
        '''},
        {"java": '''
            import com.google.gson.*;
            import java.util.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    JsonArray cards = data.getAsJsonArray("cards").deepCopy();
                    int charge = data.get("amount").getAsInt(), now = data.get("now").getAsInt();
                    List<Integer> order = new ArrayList<>();
                    for (int i = 0; i < cards.size(); i++) order.add(i);
                    order.sort(Comparator.comparingInt(i -> cards.get(i).getAsJsonObject().get("expires_at").getAsInt()));
                    for (int index : order) {
                        JsonObject card = cards.get(index).getAsJsonObject();
                        if (card.get("expires_at").getAsInt() <= now) continue;
                        int balance = card.get("balance").getAsInt(), spent = Math.min(charge, balance);
                        card.addProperty("balance", balance - spent); charge -= spent;
                    }
                    JsonObject state = new JsonObject(); state.add("cards", cards);
                    JsonObject result = new JsonObject(); result.addProperty("charge", charge); result.add("state", state);
                    return result;
                }
            }
        '''},
        [case("One card", {"now": 0, "amount": 30, "cards": [{"id": "a", "balance": 50, "expires_at": 10}]}, {"charge": 0, "state": {"cards": [{"id": "a", "balance": 20, "expires_at": 10}]}}),
         case("Earlier expiry comes second", {"now": 0, "amount": 50, "cards": [{"id": "late", "balance": 50, "expires_at": 20}, {"id": "soon", "balance": 40, "expires_at": 10}]}, {"charge": 0, "state": {"cards": [{"id": "late", "balance": 40, "expires_at": 20}, {"id": "soon", "balance": 0, "expires_at": 10}]}}, assertions=[{"path": "state.cards.0.balance", "equals": 40}]),
         case("Expiry is exclusive", {"now": 10, "amount": 20, "cards": [{"id": "old", "balance": 99, "expires_at": 10}, {"id": "live", "balance": 5, "expires_at": 11}]}, {"charge": 15, "state": {"cards": [{"id": "old", "balance": 99, "expires_at": 10}, {"id": "live", "balance": 0, "expires_at": 11}]}}, True),
         case("Stable expiry ties", {"now": 0, "amount": 7, "cards": [{"id": "z", "balance": 5, "expires_at": 10}, {"id": "a", "balance": 5, "expires_at": 10}]}, {"charge": 0, "state": {"cards": [{"id": "z", "balance": 0, "expires_at": 10}, {"id": "a", "balance": 3, "expires_at": 10}]}}, True),
         case("No cards", {"now": 5, "amount": 12, "cards": []}, {"charge": 12, "state": {"cards": []}}, True),
         case("Zero purchase", {"now": 0, "amount": 0, "cards": [{"id": "a", "balance": 5, "expires_at": 10}]}, {"charge": 0, "state": {"cards": [{"id": "a", "balance": 5, "expires_at": 10}]}}, True),
         case("Exhaust all valid credit", {"now": 0, "amount": 20, "cards": [{"id": "a", "balance": 0, "expires_at": 1}, {"id": "b", "balance": 3, "expires_at": 2}]}, {"charge": 17, "state": {"cards": [{"id": "a", "balance": 0, "expires_at": 1}, {"id": "b", "balance": 0, "expires_at": 2}]}}, True)],
        "Sort card indices by expiry while keeping the cards themselves in their original order. Stable tie ordering preserves the input policy, and each deduction is capped by both the card balance and the remaining charge. Time O(n log n), space O(n).",
        ["Is input order the same as spending priority?", "Changing the processing order must not reorder the returned card records.",
         "Sort an index list by expires_at, skip expired cards, and update the original-position copies."], 18,
    ),
    problem(
        "appointment-touching-slots", "Back-to-back appointments are rejected",
        "A booking service treats an appointment's end as occupied time. It rejects requests that start exactly when the previous appointment finishes.",
        "business", "medium", ["booking", "intervals", "state"],
        ["Input.schedule contains existing non-overlapping [start, end] appointments with start < end. Input.requests lists proposed [start, end] pairs in processing order.",
         "Appointments occupy half-open [start, end) intervals. Accept a request only when start < end and it overlaps neither existing nor previously accepted appointments.",
         "Return {accepted: [booleans], state: {schedule: original appointments followed by accepted requests in processing order}}.",
         "There are at most 100 existing appointments and 100 requests; endpoints are integers with magnitude at most 1,000,000."],
        {"cpp": '''
            #include <nlohmann/json.hpp>
            using nlohmann::json;
            json solve(const json& data) {
                json schedule = data.at("schedule"), accepted = json::array();
                for (const auto& request : data.at("requests")) {
                    int start = request.at(0), end = request.at(1); bool ok = start < end;
                    for (const auto& old : schedule)
                        if (start <= old.at(1).get<int>() && old.at(0).get<int>() <= end) ok = false;
                    accepted.push_back(ok); if (ok) schedule.push_back(request);
                }
                return json{{"accepted", accepted}, {"state", {{"schedule", schedule}}}};
            }
        '''},
        {"cpp": '''
            #include <nlohmann/json.hpp>
            using nlohmann::json;
            json solve(const json& data) {
                json schedule = data.at("schedule"), accepted = json::array();
                for (const auto& request : data.at("requests")) {
                    int start = request.at(0), end = request.at(1); bool ok = start < end;
                    for (const auto& old : schedule)
                        if (start < old.at(1).get<int>() && old.at(0).get<int>() < end) ok = false;
                    accepted.push_back(ok); if (ok) schedule.push_back(request);
                }
                return json{{"accepted", accepted}, {"state", {{"schedule", schedule}}}};
            }
        '''},
        [case("Separate appointments", {"schedule": [[1, 2]], "requests": [[4, 5]]}, {"accepted": [True], "state": {"schedule": [[1, 2], [4, 5]]}}),
         case("Back-to-back slot", {"schedule": [[1, 3]], "requests": [[3, 5]]}, {"accepted": [True], "state": {"schedule": [[1, 3], [3, 5]]}}, assertions=[{"path": "state.schedule", "equals": [[1, 3], [3, 5]]}]),
         case("Earlier touching slot", {"schedule": [[3, 5]], "requests": [[1, 3]]}, {"accepted": [True], "state": {"schedule": [[3, 5], [1, 3]]}}, True),
         case("Accepted request blocks later overlap", {"schedule": [], "requests": [[1, 4], [2, 3], [4, 6]]}, {"accepted": [True, False, True], "state": {"schedule": [[1, 4], [4, 6]]}}, True),
         case("Invalid intervals", {"schedule": [], "requests": [[2, 2], [4, 1]]}, {"accepted": [False, False], "state": {"schedule": []}}, True),
         case("Enclosing request", {"schedule": [[2, 3]], "requests": [[1, 4]]}, {"accepted": [False], "state": {"schedule": [[2, 3]]}}, True),
         case("No requests", {"schedule": [[-2, 0]], "requests": []}, {"accepted": [], "state": {"schedule": [[-2, 0]]}}, True)],
        "Two half-open intervals overlap only when each starts strictly before the other ends. Validate each request against the updated schedule and append only accepted intervals. Time O(requests × (existing + requests)), space O(existing + requests).",
        ["Is the ending instant still reserved by the previous appointment?", "Touching endpoints need strict inequalities in the overlap test.",
         "Use start < old_end and old_start < end, while separately requiring start < end."], 16,
    ),
    problem(
        "rejected-rate-limit-slots", "Denied requests keep the limiter full",
        "A sliding-window limiter records rejected requests as if they consumed capacity. A burst of denied attempts keeps blocking traffic even after earlier accepted requests expire.",
        "business", "hard", ["rate-limiting", "sliding-window", "queues"],
        ["Input.times lists request timestamps in nondecreasing integer order. Input.limit is 0 through 100 and input.window is a positive integer.",
         "Before each request at time t, expire accepted timestamps <= t - window. Accept the request only if fewer than limit accepted timestamps remain.",
         "Only accepted requests enter the window. Return {accepted: [booleans], state: {admitted: active accepted timestamps after the final request}}.",
         "At most 1,000 requests; times and window are at most 1,000,000 and nonnegative except window must be positive. No requests means an empty admitted list."],
        {"python": '''
            from collections import deque
            def solve(data):
                admitted, accepted = deque(), []
                for time in data["times"]:
                    while admitted and admitted[0] <= time - data["window"]:
                        admitted.popleft()
                    ok = len(admitted) < data["limit"]
                    accepted.append(ok)
                    admitted.append(time)
                return {"accepted": accepted, "state": {"admitted": list(admitted)}}
        '''},
        {"python": '''
            from collections import deque
            def solve(data):
                admitted, accepted = deque(), []
                for time in data["times"]:
                    while admitted and admitted[0] <= time - data["window"]:
                        admitted.popleft()
                    ok = len(admitted) < data["limit"]
                    accepted.append(ok)
                    if ok:
                        admitted.append(time)
                return {"accepted": accepted, "state": {"admitted": list(admitted)}}
        '''},
        [case("Within quota", {"times": [0, 1], "limit": 2, "window": 10}, {"accepted": [True, True], "state": {"admitted": [0, 1]}}),
         case("Rejected traffic does not extend usage", {"times": [0, 1, 2, 10, 11], "limit": 2, "window": 10}, {"accepted": [True, True, False, True, True], "state": {"admitted": [10, 11]}}, assertions=[{"path": "state.admitted", "equals": [10, 11]}]),
         case("Exact expiry boundary", {"times": [0, 10], "limit": 1, "window": 10}, {"accepted": [True, True], "state": {"admitted": [10]}}, True),
         case("Simultaneous requests", {"times": [5, 5, 5], "limit": 2, "window": 10}, {"accepted": [True, True, False], "state": {"admitted": [5, 5]}}, True),
         case("Zero capacity", {"times": [0, 1], "limit": 0, "window": 10}, {"accepted": [False, False], "state": {"admitted": []}}, True),
         case("Long idle gap", {"times": [1, 100, 101], "limit": 1, "window": 10}, {"accepted": [True, True, False], "state": {"admitted": [100]}}, True),
         case("No requests", {"times": [], "limit": 3, "window": 10}, {"accepted": [], "state": {"admitted": []}}, True)],
        "Maintain a deque containing accepted requests only. Expire its old prefix before checking capacity, and append the current timestamp only after approval. Each timestamp enters and leaves once, giving O(requests) time and O(limit) working space.",
        ["Does a denied attempt consume any of the documented quota?", "The stored timestamps are both the capacity counter and the future expiry schedule.",
         "Move admitted.append(time) inside an if ok block after the decision."], 22,
    ),
    problem(
        "expense-policy-gates", "Approval substitutes for a missing receipt",
        "An expense checker treats receipt and preapproval as interchangeable permissions. Larger expenses need both applicable checks, with precise amount thresholds.",
        "business", "medium", ["approvals", "thresholds", "booleans"],
        ["Input.amount is integer cents with magnitude at most 1,000,000; input.receipt and input.preapproved are booleans.",
         "Approve only positive amounts. Amounts up to and including 2,500 need neither receipt nor preapproval.",
         "Amounts above 2,500 require a receipt. Amounts above 10,000 additionally require preapproval. Return a boolean under this exercise's policy."],
        {"java": '''
            import com.google.gson.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    int amount = data.get("amount").getAsInt();
                    boolean receipt = data.get("receipt").getAsBoolean(), approved = data.get("preapproved").getAsBoolean();
                    return new JsonPrimitive(amount > 0 && (amount <= 2500 || receipt || approved));
                }
            }
        '''},
        {"java": '''
            import com.google.gson.*;
            public class Solution {
                public static JsonElement solve(JsonObject data) {
                    int amount = data.get("amount").getAsInt();
                    boolean receipt = data.get("receipt").getAsBoolean(), approved = data.get("preapproved").getAsBoolean();
                    return new JsonPrimitive(amount > 0 && (amount <= 2500 || receipt) && (amount <= 10000 || approved));
                }
            }
        '''},
        [case("Small expense", {"amount": 2500, "receipt": False, "preapproved": False}, True),
         case("Large expense lacks preapproval", {"amount": 10001, "receipt": True, "preapproved": False}, False),
         case("Approval does not replace receipt", {"amount": 2501, "receipt": False, "preapproved": True}, False, True),
         case("Exact approval threshold", {"amount": 10000, "receipt": True, "preapproved": False}, True, True),
         case("Both conditions met", {"amount": 10001, "receipt": True, "preapproved": True}, True, True),
         case("Zero is invalid", {"amount": 0, "receipt": True, "preapproved": True}, False, True),
         case("Negative is invalid", {"amount": -1, "receipt": True, "preapproved": True}, False, True),
         case("Missing receipt above threshold", {"amount": 2501, "receipt": False, "preapproved": False}, False, True)],
        "Express each requirement as an independent gate: positive amount, receipt when required, and preapproval when required. Combine the gates with AND, preserving inclusive amount thresholds. Time and space O(1).",
        ["Which requirements accumulate as the amount increases?", "Preapproval does not waive the receipt requirement.",
         "Require amount > 0 AND (amount <= 2500 OR receipt) AND (amount <= 10000 OR preapproved)."], 14,
    ),
    problem(
        "split-payment-remainder", "The split leaves cents unassigned",
        "A group-payment helper divides an integer-cent total equally and discards the remainder. The assigned shares no longer add up to the original charge.",
        "business", "medium", ["allocation", "rounding", "conservation"],
        ["Input.amount is 0 through 1,000,000 integer cents and input.people is 1 through 100.",
         "Return one nonnegative integer-cent share per person, in person order. Shares must sum exactly to amount and differ by at most one cent.",
         "Assign any extra cents one each to the earliest people."],
        {"python": 'def solve(data):\n    return [data["amount"] // data["people"]] * data["people"]'},
        {"python": '''
            def solve(data):
                base, extra = divmod(data["amount"], data["people"])
                return [base + (index < extra) for index in range(data["people"])]
        '''},
        [case("Even split", {"amount": 12, "people": 3}, [4, 4, 4]),
         case("One leftover cent", {"amount": 10, "people": 3}, [4, 3, 3]),
         case("Less than one cent each", {"amount": 1, "people": 3}, [1, 0, 0], True),
         case("Several extra cents", {"amount": 13, "people": 5}, [3, 3, 3, 2, 2], True),
         case("Zero amount", {"amount": 0, "people": 3}, [0, 0, 0], True),
         case("Single person", {"amount": 1000000, "people": 1}, [1000000], True)],
        "Use integer quotient and remainder. Give everyone the quotient, then add one cent to the first remainder people. This preserves the total and makes the largest difference one cent. Time and output space O(people).",
        ["Where do cents left over from integer division go?", "The remainder tells you exactly how many people need one extra cent.",
         "Use divmod(amount, people) and add one when index < remainder."], 14,
    ),
    problem(
        "cancellation-restock-once", "Cancelling twice creates extra stock",
        "A reservation workflow restores stock whenever it sees a cancellation. Replayed cancellations restock an order that has already been released.",
        "business", "hard", ["idempotency", "cancellation", "state-machine"],
        ["Input.stock is a nonnegative integer; no orders exist initially. Input.events contains {op: 'reserve', id, quantity} or {op: 'cancel', id}.",
         "Reserve only a never-successfully-used ID with a positive quantity no larger than available stock. Failed reserves do not claim their IDs.",
         "Cancel only an active reserved order, restoring its quantity exactly once. A cancelled ID cannot be reserved again; missing or repeated cancellations are rejected.",
         "Return {accepted: [booleans], state: {stock, orders: [{id, quantity, status: 'reserved' or 'cancelled'}]}} in successful reservation order. IDs are arbitrary strings. At most 100 events; integer magnitudes at most 1,000,000."],
        {"javascript": '''
            function solve(data) {
              let stock = data.stock;
              const orders = new Map(), accepted = [];
              for (const event of data.events) {
                let ok = false;
                if (event.op === 'reserve') {
                  if (!orders.has(event.id) && event.quantity > 0 && event.quantity <= stock) {
                    stock -= event.quantity;
                    orders.set(event.id, { id: event.id, quantity: event.quantity, status: 'reserved' });
                    ok = true;
                  }
                } else if (orders.has(event.id)) {
                  const order = orders.get(event.id);
                  stock += order.quantity;
                  order.status = 'cancelled';
                  ok = true;
                }
                accepted.push(ok);
              }
              return { accepted, state: { stock, orders: [...orders.values()] } };
            }
            module.exports = { solve };
        '''},
        {"javascript": '''
            function solve(data) {
              let stock = data.stock;
              const orders = new Map(), accepted = [];
              for (const event of data.events) {
                let ok = false;
                if (event.op === 'reserve') {
                  if (!orders.has(event.id) && event.quantity > 0 && event.quantity <= stock) {
                    stock -= event.quantity;
                    orders.set(event.id, { id: event.id, quantity: event.quantity, status: 'reserved' });
                    ok = true;
                  }
                } else if (orders.has(event.id) && orders.get(event.id).status === 'reserved') {
                  const order = orders.get(event.id);
                  stock += order.quantity;
                  order.status = 'cancelled';
                  ok = true;
                }
                accepted.push(ok);
              }
              return { accepted, state: { stock, orders: [...orders.values()] } };
            }
            module.exports = { solve };
        '''},
        [case("Reserve then cancel", {"stock": 5, "events": [{"op": "reserve", "id": "a", "quantity": 3}, {"op": "cancel", "id": "a"}]}, {"accepted": [True, True], "state": {"stock": 5, "orders": [{"id": "a", "quantity": 3, "status": "cancelled"}]}}),
         case("Repeated cancellation", {"stock": 5, "events": [{"op": "reserve", "id": "a", "quantity": 3}, {"op": "cancel", "id": "a"}, {"op": "cancel", "id": "a"}]}, {"accepted": [True, True, False], "state": {"stock": 5, "orders": [{"id": "a", "quantity": 3, "status": "cancelled"}]}}, assertions=[{"path": "state.stock", "equals": 5}]),
         case("Unknown cancellation", {"stock": 0, "events": [{"op": "cancel", "id": "x"}]}, {"accepted": [False], "state": {"stock": 0, "orders": []}}, True),
         case("Failed reserve can retry", {"stock": 3, "events": [{"op": "reserve", "id": "a", "quantity": 4}, {"op": "reserve", "id": "a", "quantity": 2}]}, {"accepted": [False, True], "state": {"stock": 1, "orders": [{"id": "a", "quantity": 2, "status": "reserved"}]}}, True),
         case("Cannot reuse cancelled ID", {"stock": 3, "events": [{"op": "reserve", "id": "a", "quantity": 1}, {"op": "cancel", "id": "a"}, {"op": "reserve", "id": "a", "quantity": 2}]}, {"accepted": [True, True, False], "state": {"stock": 3, "orders": [{"id": "a", "quantity": 1, "status": "cancelled"}]}}, True),
         case("Invalid quantities", {"stock": 3, "events": [{"op": "reserve", "id": "a", "quantity": 0}, {"op": "reserve", "id": "a", "quantity": -1}]}, {"accepted": [False, False], "state": {"stock": 3, "orders": []}}, True),
         case("Prototype-like ID and duplicate reserve", {"stock": 5, "events": [{"op": "reserve", "id": "__proto__", "quantity": 2}, {"op": "reserve", "id": "__proto__", "quantity": 1}]}, {"accepted": [True, False], "state": {"stock": 3, "orders": [{"id": "__proto__", "quantity": 2, "status": "reserved"}]}}, True),
         case("No events", {"stock": 7, "events": []}, {"accepted": [], "state": {"stock": 7, "orders": []}}, True)],
        "An existing order is not necessarily still cancellable. Permit only the reserved-to-cancelled transition and restore stock inside that transition. Keep cancelled records so their IDs remain consumed. Expected time and space O(events).",
        ["Does finding an order prove its stock is still reserved?", "A successful cancellation changes which operations remain valid for that ID.",
         "Require status === 'reserved' before restoring stock and changing status to 'cancelled'."], 22,
    ),
    problem(
        "campaign-end-exclusive", "The promotion lives one instant too long",
        "A promotion checker includes its ending instant, allowing a campaign after the configured exclusive deadline.",
        "business", "easy", ["campaigns", "time-windows", "eligibility"],
        ["Input.start, end, and now are integer timestamps of magnitude at most 1,000,000, with start < end. The active interval is [start, end).",
         "Input.quantity is a nonnegative integer and input.minimum is positive, each at most 100. Input.member and input.members_only are booleans.",
         "Return true only while the campaign is active, quantity >= minimum, and membership is present when members_only is true."],
        {"python": '''
            def solve(data):
                return (data["start"] <= data["now"] <= data["end"]
                        and data["quantity"] >= data["minimum"]
                        and (not data["members_only"] or data["member"]))
        '''},
        {"python": '''
            def solve(data):
                return (data["start"] <= data["now"] < data["end"]
                        and data["quantity"] >= data["minimum"]
                        and (not data["members_only"] or data["member"]))
        '''},
        [case("At opening", {"start": 10, "end": 20, "now": 10, "quantity": 2, "minimum": 2, "member": False, "members_only": False}, True),
         case("At closing", {"start": 10, "end": 20, "now": 20, "quantity": 2, "minimum": 2, "member": True, "members_only": True}, False),
         case("Before opening", {"start": 10, "end": 20, "now": 9, "quantity": 2, "minimum": 2, "member": True, "members_only": False}, False, True),
         case("Last active timestamp", {"start": 10, "end": 20, "now": 19, "quantity": 2, "minimum": 2, "member": True, "members_only": True}, True, True),
         case("Insufficient quantity", {"start": 10, "end": 20, "now": 15, "quantity": 1, "minimum": 2, "member": True, "members_only": False}, False, True),
         case("Membership required", {"start": 10, "end": 20, "now": 15, "quantity": 2, "minimum": 2, "member": False, "members_only": True}, False, True)],
        "Use an inclusive start and exclusive end, then combine the quantity and membership gates. Keeping all gates independent prevents a valid membership from bypassing time or quantity rules. Time and space O(1).",
        ["Is the campaign still active at exactly its end timestamp?", "The two ends of a half-open interval use different comparisons.",
         "Require start <= now < end and retain the quantity and membership conditions."], 10,
    ),
    problem(
        "waitlist-promotion", "The waitlist that skips its turn",
        "A membership service queues people when capacity is full but fails to promote them when a seat opens. A new arrival can take a seat ahead of everyone already waiting.",
        "business", "hard", ["queues", "fairness", "state-machine"],
        ["Input.capacity is 0 through 100; input.members lists unique current user IDs with length <= capacity. The waiting queue starts empty.",
         "Process input.events as {op: 'join' or 'leave', user: string}. Joining an existing member or waiting user has no effect; otherwise take a free seat or append to the waitlist.",
         "Leaving removes the user from either members or waiting, if present. Immediately fill any freed seats from the front of the waiting queue before the next event.",
         "Return {state: {members, waiting}}. Keep member order, appending newly seated users; keep FIFO waiting order. At most 200 events. IDs are arbitrary ASCII strings."],
        {"python": '''
            def solve(data):
                members, waiting = list(data["members"]), []
                for event in data["events"]:
                    user = event["user"]
                    if event["op"] == "join":
                        if user in members or user in waiting:
                            continue
                        if len(members) < data["capacity"]:
                            members.append(user)
                        else:
                            waiting.append(user)
                    elif user in members:
                        members.remove(user)
                    elif user in waiting:
                        waiting.remove(user)
                return {"state": {"members": members, "waiting": waiting}}
        '''},
        {"python": '''
            from collections import deque
            def solve(data):
                members, waiting = list(data["members"]), deque()
                for event in data["events"]:
                    user = event["user"]
                    if event["op"] == "join":
                        if user in members or user in waiting:
                            continue
                        if len(members) < data["capacity"]:
                            members.append(user)
                        else:
                            waiting.append(user)
                    elif user in members:
                        members.remove(user)
                    elif user in waiting:
                        waiting.remove(user)
                    while waiting and len(members) < data["capacity"]:
                        members.append(waiting.popleft())
                return {"state": {"members": members, "waiting": list(waiting)}}
        '''},
        [case("Seat available", {"capacity": 2, "members": ["a"], "events": [{"op": "join", "user": "b"}]}, {"state": {"members": ["a", "b"], "waiting": []}}),
         case("Promote immediately", {"capacity": 1, "members": ["a"], "events": [{"op": "join", "user": "b"}, {"op": "join", "user": "c"}, {"op": "leave", "user": "a"}]}, {"state": {"members": ["b"], "waiting": ["c"]}}, assertions=[{"path": "state.members", "equals": ["b"]}]),
         case("New arrival cannot jump queue", {"capacity": 1, "members": ["a"], "events": [{"op": "join", "user": "b"}, {"op": "leave", "user": "a"}, {"op": "join", "user": "c"}]}, {"state": {"members": ["b"], "waiting": ["c"]}}, True),
         case("Waiting user withdraws", {"capacity": 1, "members": ["a"], "events": [{"op": "join", "user": "b"}, {"op": "join", "user": "c"}, {"op": "leave", "user": "b"}, {"op": "leave", "user": "a"}]}, {"state": {"members": ["c"], "waiting": []}}, True),
         case("Duplicate joins", {"capacity": 1, "members": ["a"], "events": [{"op": "join", "user": "a"}, {"op": "join", "user": "b"}, {"op": "join", "user": "b"}, {"op": "leave", "user": "a"}]}, {"state": {"members": ["b"], "waiting": []}}, True),
         case("Zero capacity", {"capacity": 0, "members": [], "events": [{"op": "join", "user": "b"}, {"op": "leave", "user": "b"}, {"op": "join", "user": "c"}]}, {"state": {"members": [], "waiting": ["c"]}}, True),
         case("Preserve member and queue order", {"capacity": 2, "members": ["a", "b"], "events": [{"op": "join", "user": "c"}, {"op": "join", "user": "d"}, {"op": "leave", "user": "a"}, {"op": "leave", "user": "b"}]}, {"state": {"members": ["c", "d"], "waiting": []}}, True),
         case("Unknown departure", {"capacity": 1, "members": ["a"], "events": [{"op": "leave", "user": "x"}]}, {"state": {"members": ["a"], "waiting": []}}, True),
         case("No events", {"capacity": 1, "members": [], "events": []}, {"state": {"members": [], "waiting": []}}, True)],
        "Restore the capacity invariant immediately after each event: if a seat is free and anyone is waiting, seat the earliest waiting user. Handle waiting-list departures and duplicate joins so promotion never reintroduces a withdrawn or already-seated user. With linear membership checks, time O(events × (capacity + events)), space O(capacity + events).",
        ["What must happen as soon as a current member leaves?", "Promotion must happen before another join can claim the vacant seat.",
         "After processing an event, repeatedly move the front waiting user into members while capacity remains."], 25,
    ),
])


def _design_option(identifier, *, capacity=1000, latency=100, cost=300, ops=2, strong=True):
    return {"id": identifier, "capacity_rps": capacity, "latency_ms": latency,
            "monthly_cost": cost, "ops": ops, "strong_consistency": strong}


def _design_input(designs, **requirements):
    return {"requirements": {"peak_rps": 1000, "max_latency_ms": 100, "monthly_budget": 500,
                             "max_ops": 3, "needs_strong_consistency": True, **requirements},
            "designs": designs}


CATALOG.append(problem(
    "choosing-the-right-system-design", "Choosing the right system design",
    "A team's architecture selector always recommends the design with the highest throughput. "
    "It keeps proposing systems the team cannot afford or operate, and sometimes sacrifices required consistency. "
    "Repair the selector so every recommendation fits the workload before comparing cost. "
    "The supplied estimates describe these hypothetical deployments, not universal properties of an architecture style.",
    "system_design", "medium", ["system-design", "architecture", "trade-offs", "constraints"],
    ["Input.requirements contains peak_rps, max_latency_ms, monthly_budget, max_ops, and needs_strong_consistency (a boolean).",
     "Input.designs contains up to 1,000 candidates, each with a unique id (1 to 50 lowercase ASCII letters or hyphens), capacity_rps, latency_ms, monthly_cost, ops, and strong_consistency (a boolean). Numeric fields are integers from 0 to 1,000,000. ops is the staffing effort required; max_ops is the team's available effort in the same units.",
     "A design is feasible only when capacity_rps >= peak_rps, latency_ms <= max_latency_ms, monthly_cost <= monthly_budget, and ops <= max_ops. Equality is allowed for every limit.",
     "When needs_strong_consistency is true, strong_consistency must also be true. When it is false, either consistency option is allowed.",
     "Among feasible designs, choose the lowest monthly_cost, then the lowest ops, then the alphabetically smallest id. Return {design: id}, or {design: null} when none is feasible. Do not change the input.",
     "These ranking rules are this team's stated policy. In a real review, validate estimates under representative load and document the trade-offs before choosing."],
    {"python": '''
        def solve(data):
            if not data["designs"]:
                return {"design": None}
            best = max(data["designs"], key=lambda design: design["capacity_rps"])
            return {"design": best["id"]}
    ''', "javascript": '''
        function solve(data) {
          let best = null;
          for (const design of data.designs) {
            if (!best || design.capacity_rps > best.capacity_rps) best = design;
          }
          return { design: best ? best.id : null };
        }
        module.exports = { solve };
    '''},
    {"python": '''
        def solve(data):
            requirements = data["requirements"]
            best = None
            for design in data["designs"]:
                if (design["capacity_rps"] < requirements["peak_rps"]
                        or design["latency_ms"] > requirements["max_latency_ms"]
                        or design["monthly_cost"] > requirements["monthly_budget"]
                        or design["ops"] > requirements["max_ops"]
                        or (requirements["needs_strong_consistency"]
                            and not design["strong_consistency"])):
                    continue
                rank = (design["monthly_cost"], design["ops"], design["id"])
                if best is None or rank < best:
                    best = rank
            return {"design": best[2] if best is not None else None}
    ''', "javascript": '''
        function solve(data) {
          const r = data.requirements;
          let best = null;
          for (const d of data.designs) {
            if (d.capacity_rps < r.peak_rps || d.latency_ms > r.max_latency_ms ||
                d.monthly_cost > r.monthly_budget || d.ops > r.max_ops ||
                (r.needs_strong_consistency && !d.strong_consistency)) continue;
            if (!best || d.monthly_cost < best.monthly_cost ||
                (d.monthly_cost === best.monthly_cost && (d.ops < best.ops ||
                  (d.ops === best.ops && d.id < best.id)))) best = d;
          }
          return { design: best ? best.id : null };
        }
        module.exports = { solve };
    '''},
    [case("Fit a small team's workload", _design_input([
        _design_option("microservices", capacity=20000, cost=450, ops=8),
        _design_option("modular-monolith", capacity=2000),
        _design_option("managed-workers", capacity=3000, cost=400),
    ]), {"design": "modular-monolith"}),
     case("Consistency is a requirement", _design_input([
         _design_option("replica-reads", capacity=8000, cost=100, strong=False),
         _design_option("primary-reads", capacity=2000),
     ]), {"design": "primary-reads"}),
     case("Exact limits are feasible", _design_input([
         _design_option("at-the-limits", cost=500, ops=3),
     ]), {"design": "at-the-limits"}, True),
     case("Reject insufficient capacity", _design_input([
         _design_option("undersized", capacity=999, cost=100), _design_option("sized"),
     ]), {"design": "sized"}, True),
     case("Reject excessive latency", _design_input([
         _design_option("slow", latency=101, cost=100), _design_option("responsive"),
     ]), {"design": "responsive"}, True),
     case("Budget cannot be exceeded", _design_input([
         _design_option("over-budget", cost=501),
     ]), {"design": None}, True),
     case("Staffing cannot be exceeded", _design_input([
         _design_option("too-much-ops", ops=4),
     ]), {"design": None}, True),
     case("Choose lowest feasible cost", _design_input([
         _design_option("expensive", capacity=9000, cost=400, ops=1),
         _design_option("affordable", cost=200, ops=3),
     ]), {"design": "affordable"}, True),
     case("Break cost ties by effort", _design_input([
         _design_option("aaa", ops=3), _design_option("zzz", ops=1),
     ]), {"design": "zzz"}, True),
     case("Break remaining ties by ID", _design_input([
         _design_option("zeta"), _design_option("alpha"),
     ]), {"design": "alpha"}, True),
     case("Stale reads are acceptable here", _design_input([
         _design_option("strong"), _design_option("eventual", cost=100, strong=False),
     ], needs_strong_consistency=False), {"design": "eventual"}, True),
     case("Strong consistency is also allowed when optional", _design_input([
         _design_option("strong"),
     ], needs_strong_consistency=False), {"design": "strong"}, True),
     case("No candidates", _design_input([]), {"design": None}, True),
     case("No consistent candidate", _design_input([
         _design_option("eventual-only", strong=False),
     ]), {"design": None}, True),
     case("Zero is a valid limit", _design_input([
         _design_option("zero", capacity=0, latency=0, cost=0, ops=0),
         _design_option("paid", capacity=100, latency=0, cost=1, ops=0),
     ], peak_rps=0, max_latency_ms=0, monthly_budget=0, max_ops=0), {"design": "zero"}, True)],
    "Separate feasibility from preference: a cheap or fast design still fails if any mandatory requirement is missing. "
    "Filter using all five gates, then compare (monthly_cost, ops, id) in that order. A single pass keeps the best "
    "feasible candidate without sorting or changing the input. Return null when the team must revise its candidates "
    "or requirements. Time O(n), extra space O(1), treating bounded IDs as constant size.",
    ["Does the highest-throughput option meet every requirement, including the team's operating capacity?",
     "Check feasibility before ranking. Strong consistency is a one-way requirement: it is allowed even when optional.",
     "Skip any candidate that misses a limit, then retain the smallest (monthly_cost, ops, id) tuple. Handle an empty feasible set."],
    20,
))


# Append-only expansion: IDs 102–121 preserve every previously seeded case.
CATALOG.extend([
    problem(
        "empty-iterator-fallback", "The search with no next result",
        "An alert service returns the first reading above a threshold. A quiet interval crashes the service instead of reporting that no reading qualified.",
        "runtime", "easy", ["iterators", "defaults", "monitoring"],
        ["Input.readings is a list of at most 200 integers; input.threshold is an integer. Values have magnitude at most 10,000.",
         "Return the first reading strictly greater than threshold, in input order. Return null if none qualifies.",
         "Zero and negative readings are valid results; do not use truthiness to detect a missing result."],
        {"python": '''
            def solve(data):
                matches = (value for value in data["readings"] if value > data["threshold"])
                return next(matches)
        '''},
        {"python": '''
            def solve(data):
                matches = (value for value in data["readings"] if value > data["threshold"])
                return next(matches, None)
        '''},
        [case("An alert is present", {"readings": [2, 9, 7], "threshold": 5}, 9),
         case("Quiet interval", {"readings": [1, 2, 3], "threshold": 5}, None),
         case("No readings", {"readings": [], "threshold": 0}, None, True),
         case("Equality is not an alert", {"readings": [5, 5], "threshold": 5}, None, True),
         case("Zero qualifies", {"readings": [-3, 0, 2], "threshold": -1}, 0, True),
         case("Negative result", {"readings": [-9, -3, -1], "threshold": -5}, -3, True),
         case("Last reading qualifies", {"readings": [1, 1, 2], "threshold": 1}, 2, True)],
        "next() raises StopIteration when the filtered iterator is exhausted. Supply None as its default to distinguish absence from valid values such as zero. The generator stops at the first match. Time O(n), extra space O(1).",
        ["What happens when the filter yields no values?", "An iterator can finish normally without producing a result.",
         "Use next(matches, None) so exhaustion returns the required null result."], 8,
    ),
    problem(
        "fixed-size-roster", "The roster that cannot grow",
        "A roster loads correctly from an array, but adding the first arrival throws an exception. Repair the collection choice while preserving arrival order.",
        "runtime", "easy", ["collections", "mutability", "java"],
        ["Input.initial and input.arrivals are lists of strings, at most 100 entries each.",
         "Return one list containing all initial entries followed by every arrival in order.",
         "Keep duplicates and empty strings. Each string has at most 30 characters."],
        {"java": '''
            import com.google.gson.*;
            import java.util.*;
            public class Solution {
              public static JsonElement solve(JsonObject data) {
                String[] initial = new Gson().fromJson(data.get("initial"), String[].class);
                List<String> roster = Arrays.asList(initial);
                for (JsonElement arrival : data.getAsJsonArray("arrivals")) roster.add(arrival.getAsString());
                return new Gson().toJsonTree(roster);
              }
            }
        '''},
        {"java": '''
            import com.google.gson.*;
            import java.util.*;
            public class Solution {
              public static JsonElement solve(JsonObject data) {
                String[] initial = new Gson().fromJson(data.get("initial"), String[].class);
                List<String> roster = new ArrayList<>(Arrays.asList(initial));
                for (JsonElement arrival : data.getAsJsonArray("arrivals")) roster.add(arrival.getAsString());
                return new Gson().toJsonTree(roster);
              }
            }
        '''},
        [case("No new arrivals", {"initial": ["ana", "bo"], "arrivals": []}, ["ana", "bo"]),
         case("A new arrival", {"initial": ["ana"], "arrivals": ["bo"]}, ["ana", "bo"]),
         case("Start empty", {"initial": [], "arrivals": ["a", "b"]}, ["a", "b"], True),
         case("Both empty", {"initial": [], "arrivals": []}, [], True),
         case("Keep duplicate entries", {"initial": ["a", "a"], "arrivals": ["a"]}, ["a", "a", "a"], True),
         case("Keep empty strings", {"initial": [""], "arrivals": ["b", ""]}, ["", "b", ""], True),
         case("Preserve order", {"initial": ["z", "a"], "arrivals": ["y", "b"]}, ["z", "a", "y", "b"], True)],
        "Arrays.asList returns a fixed-size list backed by its array. Replacing entries is allowed, but adding entries is not. Copy into an ArrayList before appending arrivals. Time and output space O(n + m).",
        ["The initial entries load successfully. Which operation first changes the list's size?",
         "Not every List implementation supports add, even when its entries can be replaced.",
         "Construct new ArrayList<>(Arrays.asList(initial)) before appending."], 10,
    ),
    problem(
        "go-slice-growth", "Reserved space, missing elements",
        "A sensor converter reserves enough slice capacity but panics when writing the first doubled reading. Empty batches appear to work, hiding the mistake.",
        "runtime", "easy", ["slices", "allocation", "go"],
        ["Input.readings contains at most 200 integers of magnitude at most 10,000.",
         "Return an array with every reading multiplied by two, preserving order.",
         "An empty batch must return [], not null."],
        {"go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                readings := data["readings"].([]interface{})
                result := make([]int, 0, len(readings))
                for i, reading := range readings { result[i] = 2 * int(reading.(float64)) }
                return result
            }
        '''},
        {"go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                readings := data["readings"].([]interface{})
                result := make([]int, len(readings))
                for i, reading := range readings { result[i] = 2 * int(reading.(float64)) }
                return result
            }
        '''},
        [case("Empty batch", {"readings": []}, []),
         case("One reading", {"readings": [3]}, [6]),
         case("Several readings", {"readings": [2, 4, 1]}, [4, 8, 2], True),
         case("Negative readings", {"readings": [-3, -1]}, [-6, -2], True),
         case("Zero is retained", {"readings": [0, 2, 0]}, [0, 4, 0], True),
         case("Mixed signs", {"readings": [-10000, 10000, -1]}, [-20000, 20000, -2], True),
         case("Maximum batch", {"readings": [1] * 200}, [2] * 200, True)],
        "Capacity reserves backing storage; length determines valid indices. Allocate a slice whose length equals the input length, or append into a zero-length slice. make with length zero also preserves the required empty JSON array. Time and output space O(n).",
        ["What are len(result) and cap(result) before the first assignment?",
         "Indexing is bounded by length, even when backing storage has spare capacity.",
         "Use make([]int, len(readings)) for indexed writes, or append each result."], 10,
    ),
    problem(
        "bigint-json-total", "The exact total that will not serialize",
        "A counter service computes large totals exactly with BigInt, then fails while returning JSON. Keep the exact arithmetic and repair the response representation.",
        "runtime", "medium", ["bigint", "serialization", "precision"],
        ["Input.values contains at most 100 canonical decimal integer strings of magnitude at most 10^30; no leading plus signs or leading zeros except '0'.",
         "Return {total: string}, where total is the exact sum as a canonical decimal integer string.",
         "An empty list returns {total: '0'}. Do not convert values through Number."],
        {"javascript": '''
            function solve(data) {
              let total = 0n;
              for (const value of data.values) total += BigInt(value);
              return { total };
            }
            module.exports = { solve };
        '''},
        {"javascript": '''
            function solve(data) {
              let total = 0n;
              for (const value of data.values) total += BigInt(value);
              return { total: total.toString() };
            }
            module.exports = { solve };
        '''},
        [case("Small total", {"values": ["12", "8"]}, {"total": "20"}),
         case("Beyond exact Number integers", {"values": ["9007199254740992", "1"]}, {"total": "9007199254740993"}),
         case("Empty sum", {"values": []}, {"total": "0"}, True),
         case("Negative total", {"values": ["-9", "2"]}, {"total": "-7"}, True),
         case("Exact cancellation", {"values": ["999999999999999999999999999999", "-999999999999999999999999999999"]}, {"total": "0"}, True),
         case("Carry into another digit", {"values": ["999999999999999999999999999999", "1"]}, {"total": "1000000000000000000000000000000"}, True),
         case("Zero and a large negative", {"values": ["0", "-9007199254740993"]}, {"total": "-9007199254740993"}, True)],
        "JSON.stringify cannot serialize a BigInt directly. Keep BigInt throughout the sum, then convert the final value to a decimal string at the response boundary. Converting to Number first would silently lose integer precision. Time O(n × d), extra space O(d), where d bounds the sum's digits.",
        ["The addition succeeds. What type is handed to the JSON serializer?",
         "The response contract asks for a string so large totals remain exact across clients.",
         "Return {total: total.toString()} after summing with BigInt."], 12,
    ),
    problem(
        "dijkstra-early-visit", "The route marked final too soon",
        "A routing service locks in a destination as soon as it discovers a path. A cheaper route found moments later is ignored, so the reported shortest distance can be wrong.",
        "logic", "hard", ["graphs", "shortest-path", "priority-queue"],
        ["Input.n is 1 through 100. Nodes are integers 0 through n-1. Input.edges contains at most 500 directed [from, to, weight] edges with integer weights 0 through 1,000.",
         "Parallel edges, self-edges, and cycles are allowed. Input.start and input.target are valid nodes.",
         "Return the minimum total weight from start to target, or null when unreachable. The distance from a node to itself is zero."],
        {"python": '''
            import heapq
            def solve(data):
                graph = [[] for _ in range(data["n"])]
                for source, target, weight in data["edges"]:
                    graph[source].append((target, weight))
                pending = [(0, data["start"])]
                visited = {data["start"]}
                while pending:
                    distance, node = heapq.heappop(pending)
                    if node == data["target"]:
                        return distance
                    for neighbor, weight in graph[node]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            heapq.heappush(pending, (distance + weight, neighbor))
                return None
        '''},
        {"python": '''
            import heapq
            def solve(data):
                graph = [[] for _ in range(data["n"])]
                for source, target, weight in data["edges"]:
                    graph[source].append((target, weight))
                distances = [float("inf")] * data["n"]
                distances[data["start"]] = 0
                pending = [(0, data["start"])]
                while pending:
                    distance, node = heapq.heappop(pending)
                    if distance != distances[node]:
                        continue
                    if node == data["target"]:
                        return distance
                    for neighbor, weight in graph[node]:
                        candidate = distance + weight
                        if candidate < distances[neighbor]:
                            distances[neighbor] = candidate
                            heapq.heappush(pending, (candidate, neighbor))
                return None
        '''},
        [case("One route", {"n": 2, "edges": [[0, 1, 4]], "start": 0, "target": 1}, 4),
         case("Cheaper route discovered later", {"n": 3, "edges": [[0, 1, 9], [0, 2, 1], [2, 1, 1]], "start": 0, "target": 1}, 2),
         case("Unreachable node", {"n": 3, "edges": [[0, 1, 2]], "start": 0, "target": 2}, None, True),
         case("Already at the target", {"n": 1, "edges": [[0, 0, 7]], "start": 0, "target": 0}, 0, True),
         case("Parallel edges", {"n": 2, "edges": [[0, 1, 8], [0, 1, 3]], "start": 0, "target": 1}, 3, True),
         case("Zero-weight cycle", {"n": 3, "edges": [[0, 1, 0], [1, 0, 0], [1, 2, 2], [0, 2, 5]], "start": 0, "target": 2}, 2, True),
         case("Direction matters", {"n": 2, "edges": [[1, 0, 4]], "start": 0, "target": 1}, None, True),
         case("Several improvements", {"n": 4, "edges": [[0, 1, 10], [0, 2, 2], [2, 1, 1], [1, 3, 2], [2, 3, 20]], "start": 0, "target": 3}, 5, True)],
        "Discovery does not finalize a weighted shortest path. Track the best known distance, enqueue every strict improvement, and discard stale heap entries. With nonnegative edges, a current minimum-distance entry for the target is final. Time O(V + E log(E + 1)), space O(V + E).",
        ["Can a node's first discovered path be more expensive than a path through another pending node?",
         "Keep a tentative distance and allow it to improve before the node is removed from the priority queue.",
         "Relax an edge only when distance + weight improves its target; skip heap entries whose distance is stale."], 30,
    ),
    problem(
        "longest-window-rewind", "The window that moves backward",
        "A text analyzer finds the longest substring without repeated characters. Its left boundary sometimes moves backward, bringing an old duplicate into a supposedly unique window.",
        "logic", "medium", ["sliding-window", "strings", "invariants"],
        ["Input.text contains at most 500 printable ASCII characters. Comparisons are case-sensitive and spaces count as characters.",
         "Return the length of the longest contiguous substring whose characters are all distinct.",
         "Return 0 for an empty string."],
        {"python": '''
            def solve(data):
                last = {}
                left = best = 0
                for right, char in enumerate(data["text"]):
                    if char in last:
                        left = last[char] + 1
                    last[char] = right
                    best = max(best, right - left + 1)
                return best
        ''', "javascript": '''
            function solve(data) {
              const last = new Map();
              let left = 0, best = 0;
              for (let right = 0; right < data.text.length; right++) {
                const char = data.text[right];
                if (last.has(char)) left = last.get(char) + 1;
                last.set(char, right);
                best = Math.max(best, right - left + 1);
              }
              return best;
            }
            module.exports = { solve };
        '''},
        {"python": '''
            def solve(data):
                last = {}
                left = best = 0
                for right, char in enumerate(data["text"]):
                    if char in last:
                        left = max(left, last[char] + 1)
                    last[char] = right
                    best = max(best, right - left + 1)
                return best
        ''', "javascript": '''
            function solve(data) {
              const last = new Map();
              let left = 0, best = 0;
              for (let right = 0; right < data.text.length; right++) {
                const char = data.text[right];
                if (last.has(char)) left = Math.max(left, last.get(char) + 1);
                last.set(char, right);
                best = Math.max(best, right - left + 1);
              }
              return best;
            }
            module.exports = { solve };
        '''},
        [case("Repeated prefix", {"text": "abcabcbb"}, 3),
         case("Old occurrence outside the window", {"text": "abba"}, 2),
         case("Empty text", {"text": ""}, 0, True),
         case("One repeated character", {"text": "aaaa"}, 1, True),
         case("Late stale occurrence", {"text": "tmmzuxt"}, 5, True),
         case("Overlapping windows", {"text": "dvdf"}, 3, True),
         case("Spaces and case", {"text": "a A!a"}, 4, True),
         case("All unique", {"text": "abcde"}, 5, True)],
        "The left boundary is monotonic. A prior occurrence only constrains the current window if it lies inside that window, so take the maximum of the existing boundary and the position after the prior occurrence. Time O(n), extra space O(alphabet size).",
        ["Trace both occurrences of 'a' in 'abba'. Where is the left boundary after the second 'b'?",
         "An occurrence before the current left boundary cannot introduce a duplicate into this window.",
         "Update left with max(left, last[char] + 1), then measure the window."], 18,
    ),
    problem(
        "product-except-self-update", "The product includes itself",
        "A statistics helper uses prefix and suffix products to exclude each position, but updates its prefix too early. Every result accidentally includes the value it was meant to omit.",
        "logic", "medium", ["prefix-products", "arrays", "update-order"],
        ["Input.nums has at most 10 integers, each between -5 and 5.",
         "Return an array where position i is the product of all values except nums[i]. Do not use division.",
         "An empty input returns []; a single value returns [1]. Zeros and negative values are valid."],
        {"cpp": '''
            #include <nlohmann/json.hpp>
            #include <vector>
            using nlohmann::json;
            json solve(const json& data) {
              auto nums = data.at("nums").get<std::vector<long long>>();
              int n = static_cast<int>(nums.size());
              std::vector<long long> result(n, 1);
              long long prefix = 1, suffix = 1;
              for (int i = 0; i < n; ++i) {
                prefix *= nums[i];
                result[i] = prefix;
              }
              for (int i = n - 1; i >= 0; --i) {
                result[i] *= suffix;
                suffix *= nums[i];
              }
              return result;
            }
        '''},
        {"cpp": '''
            #include <nlohmann/json.hpp>
            #include <vector>
            using nlohmann::json;
            json solve(const json& data) {
              auto nums = data.at("nums").get<std::vector<long long>>();
              int n = static_cast<int>(nums.size());
              std::vector<long long> result(n, 1);
              long long prefix = 1, suffix = 1;
              for (int i = 0; i < n; ++i) {
                result[i] = prefix;
                prefix *= nums[i];
              }
              for (int i = n - 1; i >= 0; --i) {
                result[i] *= suffix;
                suffix *= nums[i];
              }
              return result;
            }
        '''},
        [case("Unit values", {"nums": [1, 1, 1]}, [1, 1, 1]),
         case("Exclude each value", {"nums": [2, 3, 4]}, [12, 8, 6]),
         case("One zero", {"nums": [2, 0, 3]}, [0, 6, 0], True),
         case("Two zeros", {"nums": [0, 4, 0]}, [0, 0, 0], True),
         case("Negative values", {"nums": [-2, 3, -4]}, [-12, 8, -6], True),
         case("Single value", {"nums": [5]}, [1], True),
         case("Empty input", {"nums": []}, [], True),
         case("Largest product", {"nums": [5] * 10}, [1953125] * 10, True)],
        "Before visiting i, prefix must contain only values strictly before i. Store it before multiplying by nums[i], then apply a suffix containing only values strictly after i. This handles zeros without division. Time O(n), extra space O(1) beyond the output and input copy.",
        ["What exactly should prefix contain when assigned to result[i]?",
         "The suffix pass stores its contribution before consuming the current value. Compare the prefix pass.",
         "Assign result[i] = prefix before prefix *= nums[i]."], 18,
    ),
    problem(
        "run-length-final-flush", "The last run goes missing",
        "A compact event log emits a run whenever its letter changes. The final run disappears because no next letter arrives to trigger the flush.",
        "logic", "easy", ["strings", "compression", "streaming"],
        ["Input.text contains at most 500 uppercase ASCII letters A through Z.",
         "Return an array of {char: string, count: integer} for each maximal adjacent run, preserving order.",
         "Separate runs of the same letter must stay separate. Empty text returns []."],
        {"go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                text := data["text"].(string)
                result := make([]map[string]interface{}, 0)
                count := 0
                for i := 0; i < len(text); i++ {
                    if i > 0 && text[i] != text[i-1] {
                        result = append(result, map[string]interface{}{"char": string(text[i-1]), "count": count})
                        count = 0
                    }
                    count++
                }
                return result
            }
        '''},
        {"go": '''
            package main
            func Solve(data map[string]interface{}) interface{} {
                text := data["text"].(string)
                result := make([]map[string]interface{}, 0)
                count := 0
                for i := 0; i < len(text); i++ {
                    if i > 0 && text[i] != text[i-1] {
                        result = append(result, map[string]interface{}{"char": string(text[i-1]), "count": count})
                        count = 0
                    }
                    count++
                }
                if count > 0 {
                    result = append(result, map[string]interface{}{"char": string(text[len(text)-1]), "count": count})
                }
                return result
            }
        '''},
        [case("Empty log", {"text": ""}, []),
         case("Several runs", {"text": "AAABCC"}, [{"char": "A", "count": 3}, {"char": "B", "count": 1}, {"char": "C", "count": 2}]),
         case("One letter", {"text": "Z"}, [{"char": "Z", "count": 1}], True),
         case("One long run", {"text": "B" * 500}, [{"char": "B", "count": 500}], True),
         case("Letter returns later", {"text": "ABA"}, [{"char": "A", "count": 1}, {"char": "B", "count": 1}, {"char": "A", "count": 1}], True),
         case("Single final letter", {"text": "AAB"}, [{"char": "A", "count": 2}, {"char": "B", "count": 1}], True),
         case("Two equal runs", {"text": "XXYY"}, [{"char": "X", "count": 2}, {"char": "Y", "count": 2}], True)],
        "A change of letter flushes the preceding run, but end-of-input is also a boundary. Append the pending run after the loop when count is positive; that guard keeps empty input safe. Time O(n), output space O(number of runs).",
        ["What event flushes a run when the input never changes letter?",
         "The last run is still pending when iteration ends.",
         "After the loop, append the final letter and count only when count > 0."], 10,
    ),
    problem(
        "literal-search-offset", "The match at position zero",
        "A search badge hides matches at the beginning of a title and lights up when the text is absent. A position is being mistaken for a boolean.",
        "edge", "easy", ["strings", "truthiness", "sentinels"],
        ["Input.text and input.query are ASCII strings of at most 200 characters.",
         "Return true if query occurs as a contiguous substring of text, otherwise false. Matching is case-sensitive.",
         "An empty query is always present, including in empty text."],
        {"javascript": '''
            function solve(data) {
              return Boolean(data.text.indexOf(data.query));
            }
            module.exports = { solve };
        '''},
        {"javascript": '''
            function solve(data) {
              return data.text.indexOf(data.query) !== -1;
            }
            module.exports = { solve };
        '''},
        [case("Match in the middle", {"text": "debugging", "query": "bug"}, True),
         case("Match at the beginning", {"text": "debugging", "query": "debug"}, True),
         case("No match", {"text": "debugging", "query": "patch"}, False, True),
         case("Empty query", {"text": "abc", "query": ""}, True, True),
         case("Both empty", {"text": "", "query": ""}, True, True),
         case("Query longer than text", {"text": "a", "query": "ab"}, False, True),
         case("Case-sensitive search", {"text": "Bug", "query": "bug"}, False, True),
         case("Match at the end", {"text": "abc", "query": "c"}, True, True)],
        "indexOf returns zero for a match at the start and -1 for absence. Zero is falsy while -1 is truthy, so boolean coercion reverses these important cases. Compare with -1 explicitly or use includes. Worst-case time O(n × m) for a direct substring search, extra space O(1).",
        ["What numeric value represents a match at the first character?",
         "The missing-value sentinel is -1, and -1 is truthy in JavaScript.",
         "Return indexOf(query) !== -1, or use text.includes(query)."], 8,
    ),
    problem(
        "timestamp-offset-order", "The timeline sorted by local clocks",
        "A global incident feed sorts timestamp strings. Events with different UTC offsets appear out of order even though every timestamp is valid.",
        "edge", "medium", ["timestamps", "time-zones", "sorting"],
        ["Input.events contains at most 100 objects with unique string id values and a timestamp.",
         "Timestamps are valid Gregorian dates in years 2000 through 2099, formatted YYYY-MM-DDTHH:MM:SS followed by Z or an explicit offset ±HH:MM of magnitude at most 14 hours. There are no fractional seconds or leap seconds.",
         "Return event IDs from earliest to latest actual instant. Preserve input order for timestamps representing the same instant.",
         "An empty event list returns []."],
        {"python": '''
            def solve(data):
                events = sorted(data["events"], key=lambda event: event["timestamp"])
                return [event["id"] for event in events]
        '''},
        {"python": '''
            from datetime import datetime
            def solve(data):
                events = sorted(data["events"], key=lambda event: datetime.fromisoformat(event["timestamp"]))
                return [event["id"] for event in events]
        '''},
        [case("Same offset", {"events": [{"id": "b", "timestamp": "2026-01-01T09:00:00Z"}, {"id": "a", "timestamp": "2026-01-01T08:00:00Z"}]}, ["a", "b"]),
         case("Different local clocks", {"events": [{"id": "a", "timestamp": "2026-01-01T08:00:00+02:00"}, {"id": "b", "timestamp": "2026-01-01T07:30:00Z"}]}, ["a", "b"]),
         case("Crossing midnight", {"events": [{"id": "later", "timestamp": "2026-01-01T23:30:00-02:00"}, {"id": "earlier", "timestamp": "2026-01-02T00:30:00Z"}]}, ["earlier", "later"], True),
         case("Equal instants stay stable", {"events": [{"id": "z", "timestamp": "2026-02-01T10:00:00+02:00"}, {"id": "a", "timestamp": "2026-02-01T08:00:00Z"}, {"id": "m", "timestamp": "2026-02-01T03:00:00-05:00"}]}, ["z", "a", "m"], True),
         case("Half-hour offset", {"events": [{"id": "x", "timestamp": "2026-01-01T12:00:00+05:30"}, {"id": "y", "timestamp": "2026-01-01T07:00:00Z"}]}, ["x", "y"], True),
         case("Negative offset", {"events": [{"id": "x", "timestamp": "2026-01-01T00:00:00-03:00"}, {"id": "y", "timestamp": "2026-01-01T01:00:00Z"}]}, ["y", "x"], True),
         case("One event", {"events": [{"id": "only", "timestamp": "2000-01-01T00:00:00+14:00"}]}, ["only"], True),
         case("No events", {"events": []}, [], True)],
        "A timestamp's wall-clock fields cannot be compared independently of its offset. Parse each value as an aware datetime and use Python's stable sort to compare actual instants while keeping equal instants in input order. Time O(n log n), extra space O(n).",
        ["Does 08:00 at UTC+02 occur before or after 07:30 UTC?",
         "The offset is part of the value, not a suffix that can be ignored during sorting.",
         "Sort by datetime.fromisoformat(timestamp); keep the stable input order for equal keys."], 18,
    ),
    problem(
        "escaped-delimiter-fields", "The separator inside the field",
        "A log importer splits on every pipe, including escaped pipes that belong inside a field. Repair the parser without dropping empty fields or literal backslashes.",
        "edge", "medium", ["parsing", "escaping", "state-machine"],
        ["Input.text is an ASCII string of at most 500 characters. An unescaped | separates fields.",
         "A backslash escapes exactly the next character, removing that backslash and keeping the next character literally, even when it is a pipe or another backslash.",
         "A final backslash with no following character is kept literally. Preserve all empty fields and whitespace.",
         "Return the array of decoded fields. Empty text contains one empty field."],
        {"java": r'''
            import com.google.gson.*;
            public class Solution {
              public static JsonElement solve(JsonObject data) {
                return new Gson().toJsonTree(data.get("text").getAsString().split("\\|", -1));
              }
            }
        '''},
        {"java": r'''
            import com.google.gson.*;
            public class Solution {
              public static JsonElement solve(JsonObject data) {
                String text = data.get("text").getAsString();
                JsonArray fields = new JsonArray();
                StringBuilder field = new StringBuilder();
                for (int i = 0; i < text.length(); i++) {
                  char ch = text.charAt(i);
                  if (ch == '\\' && i + 1 < text.length()) {
                    field.append(text.charAt(++i));
                  } else if (ch == '|') {
                    fields.add(field.toString());
                    field.setLength(0);
                  } else {
                    field.append(ch);
                  }
                }
                fields.add(field.toString());
                return fields;
              }
            }
        '''},
        [case("Plain fields", {"text": "a|b|"}, ["a", "b", ""]),
         case("Escaped pipe", {"text": r"a\|b|c"}, ["a|b", "c"]),
         case("Escaped backslash before separator", {"text": r"a\\|b"}, ["a\\", "b"], True),
         case("Trailing backslash", {"text": "a|b\\"}, ["a", "b\\"], True),
         case("Empty fields", {"text": "||"}, ["", "", ""], True),
         case("Empty text", {"text": ""}, [""], True),
         case("Escape an ordinary character", {"text": r"\a|\z"}, ["a", "z"], True),
         case("Whitespace is data", {"text": r" a | \| "}, [" a ", " | "], True),
         case("Backslash then escaped pipe", {"text": r"\\\|"}, ["\\|"], True)],
        "Scan left to right and consume an escaped character together with its backslash. Only a pipe encountered outside an escape ends a field. Append the pending field at end-of-input even when empty, and retain a trailing unpaired backslash. Time and output space O(n).",
        ["Can a plain split distinguish a separator from a literal pipe?",
         "After a backslash, consume the next character as data before checking for separators.",
         "Scan once: consume escapes, flush on an unescaped pipe, and always append the final field."], 22,
    ),
    problem(
        "ipv4-leading-zero", "The address with an ambiguous octet",
        "A strict IPv4 form accepts octets with leading zeros because it validates only their numeric values. Repair validation so each accepted address has the required decimal spelling.",
        "edge", "medium", ["validation", "parsing", "network-addresses"],
        ["Input.address is a string of at most 30 characters. Return a boolean.",
         "Accept exactly four dot-separated octets. Each octet must contain only ASCII digits and have a decimal value from 0 through 255.",
         "An octet is either '0' or begins with 1 through 9. Leading zeros, signs, whitespace, and empty octets are invalid.",
         "This is a strict dotted-decimal exercise; do not accept alternative address representations."],
        {"python": '''
            def solve(data):
                parts = data["address"].split(".")
                return len(parts) == 4 and all(
                    part and all("0" <= char <= "9" for char in part) and int(part) <= 255
                    for part in parts
                )
        '''},
        {"python": '''
            def solve(data):
                parts = data["address"].split(".")
                return len(parts) == 4 and all(
                    1 <= len(part) <= 3
                    and all("0" <= char <= "9" for char in part)
                    and (len(part) == 1 or part[0] != "0")
                    and int(part) <= 255
                    for part in parts
                )
        '''},
        [case("Ordinary address", {"address": "192.168.1.1"}, True),
         case("Leading zero", {"address": "01.2.3.4"}, False),
         case("All zeros", {"address": "0.0.0.0"}, True, True),
         case("Largest octets", {"address": "255.255.255.255"}, True, True),
         case("Out of range", {"address": "256.1.2.3"}, False, True),
         case("Empty octet", {"address": "1..2.3"}, False, True),
         case("Too few octets", {"address": "1.2.3"}, False, True),
         case("Too many octets", {"address": "1.2.3.4.5"}, False, True),
         case("Signed octet", {"address": "+1.2.3.4"}, False, True),
         case("Whitespace", {"address": "1.2.3.4 "}, False, True),
         case("Non-ASCII digit", {"address": "١.2.3.4"}, False, True),
         case("Zero padding", {"address": "000.0.0.0"}, False, True),
         case("Empty address", {"address": ""}, False, True)],
        "Numeric conversion loses the spelling that distinguishes '1' from '01'. Validate each octet's length, ASCII characters, and leading-zero rule before converting it for the range check. Time O(n), space O(n) for the split fields.",
        ["What information is lost when an octet is converted to an integer?",
         "Zero is valid by itself, but a longer octet must not begin with zero.",
         "Require one to three ASCII digits, reject leading zeros in multi-character octets, then check the value is at most 255."], 16,
    ),
    problem(
        "transfer-fee-affordability", "Enough for the transfer, short on the fee",
        "A wallet checks that the transfer amount is affordable but forgets its fixed fee. An accepted transfer can leave the wallet with a negative balance.",
        "business", "medium", ["wallets", "validation", "state"],
        ["Input.balance and input.fee are nonnegative integer units, at most 100,000. Input.amounts contains at most 100 integer transfer requests of magnitude at most 100,000.",
         "Process requests in order. Accept only a positive amount for which balance covers amount + fee. An accepted request debits both, adding amount to sent and fee to fees.",
         "Rejected requests have no effect. Return {accepted: boolean[], state: {balance, sent, fees}}, with sent and fees initially zero."],
        {"python": '''
            def solve(data):
                balance, sent, fees = data["balance"], 0, 0
                accepted = []
                for amount in data["amounts"]:
                    ok = amount > 0 and balance >= amount
                    if ok:
                        balance -= amount + data["fee"]
                        sent += amount
                        fees += data["fee"]
                    accepted.append(ok)
                return {"accepted": accepted, "state": {"balance": balance, "sent": sent, "fees": fees}}
        '''},
        {"python": '''
            def solve(data):
                balance, sent, fees = data["balance"], 0, 0
                accepted = []
                for amount in data["amounts"]:
                    ok = amount > 0 and balance >= amount + data["fee"]
                    if ok:
                        balance -= amount + data["fee"]
                        sent += amount
                        fees += data["fee"]
                    accepted.append(ok)
                return {"accepted": accepted, "state": {"balance": balance, "sent": sent, "fees": fees}}
        '''},
        [case("Both transfers affordable", {"balance": 100, "fee": 5, "amounts": [20, 30]}, {"accepted": [True, True], "state": {"balance": 40, "sent": 50, "fees": 10}}),
         case("Fee makes the second transfer unaffordable", {"balance": 100, "fee": 10, "amounts": [40, 50]}, {"accepted": [True, False], "state": {"balance": 50, "sent": 40, "fees": 10}}, assertions=[{"path": "state.balance", "equals": 50}]),
         case("Exact balance", {"balance": 100, "fee": 10, "amounts": [90]}, {"accepted": [True], "state": {"balance": 0, "sent": 90, "fees": 10}}, True),
         case("Invalid amounts do not charge fees", {"balance": 100, "fee": 5, "amounts": [0, -10, 20]}, {"accepted": [False, False, True], "state": {"balance": 75, "sent": 20, "fees": 5}}, True),
         case("No fee", {"balance": 100, "fee": 0, "amounts": [100, 1]}, {"accepted": [True, False], "state": {"balance": 0, "sent": 100, "fees": 0}}, True),
         case("Rejection preserves funds", {"balance": 50, "fee": 2, "amounts": [1000, 10]}, {"accepted": [False, True], "state": {"balance": 38, "sent": 10, "fees": 2}}, True),
         case("No transfers", {"balance": 5, "fee": 10, "amounts": []}, {"accepted": [], "state": {"balance": 5, "sent": 0, "fees": 0}}, True),
         case("Empty wallet", {"balance": 0, "fee": 0, "amounts": [1]}, {"accepted": [False], "state": {"balance": 0, "sent": 0, "fees": 0}}, True)],
        "The affordability check must cover the full debit, including the fee. Validate the amount and total cost before mutating any ledger field so a rejection preserves all state. The final balance plus sent plus fees equals the initial balance. Time O(n), output space O(n), bookkeeping space O(1).",
        ["Which values are subtracted after acceptance, and which were checked beforehand?",
         "A transfer can cover the amount while still being unable to cover amount plus fee.",
         "Require amount > 0 and balance >= amount + fee before changing balance, sent, or fees."], 16,
    ),
    problem(
        "review-revision-reset", "Approval for yesterday's document",
        "A publishing workflow keeps approvals after a document is edited. A new revision can be published using reviews that only covered old content.",
        "business", "hard", ["approvals", "versioning", "state-machine"],
        ["Input.quorum is 1 through 5. Start at revision 1 with no approvals and no published revision.",
         "Process at most 200 input.events. An {op: 'edit'} increments revision and clears all approvals. An {op: 'approve', reviewer: string} adds that reviewer once to the current revision.",
         "An {op: 'publish'} publishes the current revision only if at least quorum distinct reviewers approved it and it has not already been published. Failed publications have no effect.",
         "Editing does not remove the previous publication. Return {published: integer[], state: {revision, approvals, published_revision}}. List successful publication revisions in order, sort the current reviewer IDs lexicographically, and use null when nothing has been published. IDs contain lowercase ASCII letters."],
        {"python": '''
            def solve(data):
                revision, published_revision = 1, None
                approvals, published = set(), []
                for event in data["events"]:
                    if event["op"] == "edit":
                        revision += 1
                    elif event["op"] == "approve":
                        approvals.add(event["reviewer"])
                    elif len(approvals) >= data["quorum"] and published_revision != revision:
                        published_revision = revision
                        published.append(revision)
                return {"published": published, "state": {"revision": revision,
                        "approvals": sorted(approvals), "published_revision": published_revision}}
        '''},
        {"python": '''
            def solve(data):
                revision, published_revision = 1, None
                approvals, published = set(), []
                for event in data["events"]:
                    if event["op"] == "edit":
                        revision += 1
                        approvals.clear()
                    elif event["op"] == "approve":
                        approvals.add(event["reviewer"])
                    elif len(approvals) >= data["quorum"] and published_revision != revision:
                        published_revision = revision
                        published.append(revision)
                return {"published": published, "state": {"revision": revision,
                        "approvals": sorted(approvals), "published_revision": published_revision}}
        '''},
        [case("Approved revision", {"quorum": 2, "events": [{"op": "approve", "reviewer": "b"}, {"op": "approve", "reviewer": "a"}, {"op": "publish"}]}, {"published": [1], "state": {"revision": 1, "approvals": ["a", "b"], "published_revision": 1}}),
         case("Reviews cannot cross revisions", {"quorum": 2, "events": [{"op": "approve", "reviewer": "a"}, {"op": "edit"}, {"op": "approve", "reviewer": "b"}, {"op": "publish"}]}, {"published": [], "state": {"revision": 2, "approvals": ["b"], "published_revision": None}}, assertions=[{"path": "state.approvals", "equals": ["b"]}]),
         case("Duplicate approval is one vote", {"quorum": 2, "events": [{"op": "approve", "reviewer": "a"}, {"op": "approve", "reviewer": "a"}, {"op": "publish"}]}, {"published": [], "state": {"revision": 1, "approvals": ["a"], "published_revision": None}}, True),
         case("Publish each revision once", {"quorum": 1, "events": [{"op": "approve", "reviewer": "a"}, {"op": "publish"}, {"op": "publish"}]}, {"published": [1], "state": {"revision": 1, "approvals": ["a"], "published_revision": 1}}, True),
         case("Edit keeps the last publication", {"quorum": 1, "events": [{"op": "approve", "reviewer": "a"}, {"op": "publish"}, {"op": "edit"}, {"op": "publish"}]}, {"published": [1], "state": {"revision": 2, "approvals": [], "published_revision": 1}}, True),
         case("Fresh review can publish again", {"quorum": 1, "events": [{"op": "approve", "reviewer": "a"}, {"op": "publish"}, {"op": "edit"}, {"op": "approve", "reviewer": "a"}, {"op": "publish"}]}, {"published": [1, 2], "state": {"revision": 2, "approvals": ["a"], "published_revision": 2}}, True),
         case("Multiple edits", {"quorum": 1, "events": [{"op": "approve", "reviewer": "a"}, {"op": "edit"}, {"op": "edit"}]}, {"published": [], "state": {"revision": 3, "approvals": [], "published_revision": None}}, True),
         case("No events", {"quorum": 1, "events": []}, {"published": [], "state": {"revision": 1, "approvals": [], "published_revision": None}}, True)],
        "An approval belongs to a particular revision. Clear the current approval set on every edit while retaining the last published revision. A set prevents duplicate votes, and recording the published revision prevents duplicate publication. Time O(events + reviewers log reviewers), space O(events + reviewers), treating bounded IDs as constant size.",
        ["What content did an approval cover before an edit?",
         "Separate the last published revision from approvals for the current draft.",
         "On edit, increment revision and clear approvals; keep published_revision unchanged until a fresh quorum publishes."], 25,
    ),
    problem(
        "partial-backorder-fulfillment", "The small order jumps the queue",
        "A warehouse skips an order it cannot fill completely and uses the remaining stock for later orders. Its policy actually requires partial fulfillment in arrival order.",
        "business", "medium", ["inventory", "fifo", "allocation"],
        ["Input.stock is a nonnegative integer at most 1,000,000. Input.orders contains at most 100 orders in arrival order with unique string id values and integer quantity from 1 through 10,000.",
         "Allocate as much stock as possible to each order before considering the next. A partially filled order consumes all remaining stock.",
         "Return {allocations: [{id, quantity}], state: {stock}}. Include every order in its original order, including allocations of zero. Never allocate more than requested or more than available."],
        {"cpp": '''
            #include <nlohmann/json.hpp>
            using nlohmann::json;
            json solve(const json& data) {
              int stock = data.at("stock").get<int>();
              json allocations = json::array();
              for (const auto& order : data.at("orders")) {
                int requested = order.at("quantity").get<int>();
                int allocated = stock >= requested ? requested : 0;
                stock -= allocated;
                allocations.push_back({{"id", order.at("id")}, {"quantity", allocated}});
              }
              return {{"allocations", allocations}, {"state", {{"stock", stock}}}};
            }
        '''},
        {"cpp": '''
            #include <nlohmann/json.hpp>
            #include <algorithm>
            using nlohmann::json;
            json solve(const json& data) {
              int stock = data.at("stock").get<int>();
              json allocations = json::array();
              for (const auto& order : data.at("orders")) {
                int requested = order.at("quantity").get<int>();
                int allocated = std::min(stock, requested);
                stock -= allocated;
                allocations.push_back({{"id", order.at("id")}, {"quantity", allocated}});
              }
              return {{"allocations", allocations}, {"state", {{"stock", stock}}}};
            }
        '''},
        [case("Enough for everyone", {"stock": 8, "orders": [{"id": "a", "quantity": 3}, {"id": "b", "quantity": 2}]}, {"allocations": [{"id": "a", "quantity": 3}, {"id": "b", "quantity": 2}], "state": {"stock": 3}}),
         case("Partial order before a smaller order", {"stock": 4, "orders": [{"id": "a", "quantity": 6}, {"id": "b", "quantity": 2}]}, {"allocations": [{"id": "a", "quantity": 4}, {"id": "b", "quantity": 0}], "state": {"stock": 0}}, assertions=[{"path": "allocations.0.quantity", "equals": 4}]),
         case("Stock runs out midway", {"stock": 5, "orders": [{"id": "a", "quantity": 3}, {"id": "b", "quantity": 4}, {"id": "c", "quantity": 1}]}, {"allocations": [{"id": "a", "quantity": 3}, {"id": "b", "quantity": 2}, {"id": "c", "quantity": 0}], "state": {"stock": 0}}, True),
         case("No stock", {"stock": 0, "orders": [{"id": "a", "quantity": 2}]}, {"allocations": [{"id": "a", "quantity": 0}], "state": {"stock": 0}}, True),
         case("No orders", {"stock": 7, "orders": []}, {"allocations": [], "state": {"stock": 7}}, True),
         case("Exact stock", {"stock": 3, "orders": [{"id": "z", "quantity": 3}, {"id": "a", "quantity": 1}]}, {"allocations": [{"id": "z", "quantity": 3}, {"id": "a", "quantity": 0}], "state": {"stock": 0}}, True),
         case("Large excess stock", {"stock": 1000000, "orders": [{"id": "a", "quantity": 10000}]}, {"allocations": [{"id": "a", "quantity": 10000}], "state": {"stock": 990000}}, True)],
        "FIFO partial fulfillment means the earlier order receives min(remaining stock, requested quantity), even when it cannot be completed. Decrement stock immediately and retain zero allocations for later orders. This preserves both priority and stock conservation. Time O(n), output space O(n).",
        ["Does insufficient stock mean an earlier order should receive nothing?",
         "A partial allocation must happen before the next order is considered.",
         "Allocate min(stock, requested), deduct it, and include the order even when that allocation is zero."], 18,
    ),
    problem(
        "coupon-use-after-rejection", "The coupon spent on an ineligible cart",
        "A limited-use promotion spends one redemption whenever it is attempted. An ineligible cart can exhaust the coupon before a qualifying cart reaches checkout.",
        "business", "medium", ["coupons", "eligibility", "state"],
        ["Input.uses is a nonnegative integer at most 100. Input.minimum and input.discount are nonnegative integer units at most 10,000.",
         "Input.subtotals contains at most 100 nonnegative integer cart totals at most 10,000. Process them in order.",
         "Apply the coupon only if uses remain and subtotal >= minimum. Successful use consumes exactly one redemption and charges max(0, subtotal - discount); otherwise charge the original subtotal and consume nothing.",
         "A qualifying use still counts when discount is zero. Return {totals: integer[], applied: boolean[], state: {uses_left}}."],
        {"python": '''
            def solve(data):
                remaining = data["uses"]
                totals, applied = [], []
                for subtotal in data["subtotals"]:
                    ok = False
                    if remaining > 0:
                        remaining -= 1
                        ok = subtotal >= data["minimum"]
                    totals.append(max(0, subtotal - data["discount"]) if ok else subtotal)
                    applied.append(ok)
                return {"totals": totals, "applied": applied, "state": {"uses_left": remaining}}
        ''', "javascript": '''
            function solve(data) {
              let remaining = data.uses;
              const totals = [], applied = [];
              for (const subtotal of data.subtotals) {
                let ok = false;
                if (remaining > 0) {
                  remaining--;
                  ok = subtotal >= data.minimum;
                }
                totals.push(ok ? Math.max(0, subtotal - data.discount) : subtotal);
                applied.push(ok);
              }
              return { totals, applied, state: { uses_left: remaining } };
            }
            module.exports = { solve };
        '''},
        {"python": '''
            def solve(data):
                remaining = data["uses"]
                totals, applied = [], []
                for subtotal in data["subtotals"]:
                    ok = remaining > 0 and subtotal >= data["minimum"]
                    if ok:
                        remaining -= 1
                    totals.append(max(0, subtotal - data["discount"]) if ok else subtotal)
                    applied.append(ok)
                return {"totals": totals, "applied": applied, "state": {"uses_left": remaining}}
        ''', "javascript": '''
            function solve(data) {
              let remaining = data.uses;
              const totals = [], applied = [];
              for (const subtotal of data.subtotals) {
                const ok = remaining > 0 && subtotal >= data.minimum;
                if (ok) remaining--;
                totals.push(ok ? Math.max(0, subtotal - data.discount) : subtotal);
                applied.push(ok);
              }
              return { totals, applied, state: { uses_left: remaining } };
            }
            module.exports = { solve };
        '''},
        [case("Qualifying carts", {"uses": 2, "minimum": 100, "discount": 20, "subtotals": [100, 200]}, {"totals": [80, 180], "applied": [True, True], "state": {"uses_left": 0}}),
         case("Rejected cart before an eligible one", {"uses": 1, "minimum": 100, "discount": 20, "subtotals": [50, 100]}, {"totals": [50, 80], "applied": [False, True], "state": {"uses_left": 0}}),
         case("All carts rejected", {"uses": 2, "minimum": 100, "discount": 20, "subtotals": [0, 99]}, {"totals": [0, 99], "applied": [False, False], "state": {"uses_left": 2}}, True, [{"path": "state.uses_left", "equals": 2}]),
         case("Coupon exhausted", {"uses": 1, "minimum": 100, "discount": 20, "subtotals": [100, 200]}, {"totals": [80, 200], "applied": [True, False], "state": {"uses_left": 0}}, True),
         case("No redemptions available", {"uses": 0, "minimum": 0, "discount": 20, "subtotals": [10]}, {"totals": [10], "applied": [False], "state": {"uses_left": 0}}, True),
         case("Discount is capped at the subtotal", {"uses": 1, "minimum": 0, "discount": 20, "subtotals": [5]}, {"totals": [0], "applied": [True], "state": {"uses_left": 0}}, True),
         case("Zero discount still consumes a use", {"uses": 1, "minimum": 0, "discount": 0, "subtotals": [0, 1]}, {"totals": [0, 1], "applied": [True, False], "state": {"uses_left": 0}}, True),
         case("No carts", {"uses": 3, "minimum": 5, "discount": 2, "subtotals": []}, {"totals": [], "applied": [], "state": {"uses_left": 3}}, True)],
        "Check all eligibility conditions before consuming a redemption. Commit the discount and decrement together only for an eligible cart; a rejected attempt leaves the counter unchanged. Eligibility is independent of whether the numeric discount changes the total. Time O(n), output space O(n), bookkeeping space O(1).",
        ["Which event should spend a redemption: an attempted coupon or an accepted one?",
         "Check both remaining uses and the minimum subtotal before changing the counter.",
         "Compute eligibility first; decrement remaining only when eligibility is true."], 18,
    ),
    problem(
        "cache-write-invalidation", "The cache remembers an old value",
        "A cache-aside simulation serves repeated reads efficiently, but writes and deletes leave cached entries untouched. Even a previously missing key stays missing after it is created.",
        "system_design", "medium", ["caching", "consistency", "invalidation"],
        ["Input.store maps arbitrary ASCII string keys to integers of magnitude at most 10,000. The cache starts empty.",
         "Process at most 200 events in order: {op: 'get', key}, {op: 'put', key, value}, or {op: 'delete', key}. Put values are integers with the same bound.",
         "A get reads from cache when the key is present; otherwise read the store and cache the result, using null for an absent key. A put changes the store and invalidates that key in cache. A delete removes the store entry if present and invalidates that key.",
         "Return {reads: (integer or null)[], state: {store, cache}}. Only get events append to reads. Preserve unrelated cached entries. This is a sequential simulation with no concurrent requests."],
        {"python": '''
            def solve(data):
                store, cache, reads = dict(data["store"]), {}, []
                for event in data["events"]:
                    key = event["key"]
                    if event["op"] == "get":
                        if key not in cache:
                            cache[key] = store.get(key)
                        reads.append(cache[key])
                    elif event["op"] == "put":
                        store[key] = event["value"]
                    else:
                        store.pop(key, None)
                return {"reads": reads, "state": {"store": store, "cache": cache}}
        ''', "javascript": '''
            function solve(data) {
              const store = new Map(Object.entries(data.store)), cache = new Map(), reads = [];
              for (const event of data.events) {
                const key = event.key;
                if (event.op === 'get') {
                  if (!cache.has(key)) cache.set(key, store.has(key) ? store.get(key) : null);
                  reads.push(cache.get(key));
                } else if (event.op === 'put') {
                  store.set(key, event.value);
                } else {
                  store.delete(key);
                }
              }
              return { reads, state: { store: Object.fromEntries(store), cache: Object.fromEntries(cache) } };
            }
            module.exports = { solve };
        '''},
        {"python": '''
            def solve(data):
                store, cache, reads = dict(data["store"]), {}, []
                for event in data["events"]:
                    key = event["key"]
                    if event["op"] == "get":
                        if key not in cache:
                            cache[key] = store.get(key)
                        reads.append(cache[key])
                    else:
                        if event["op"] == "put":
                            store[key] = event["value"]
                        else:
                            store.pop(key, None)
                        cache.pop(key, None)
                return {"reads": reads, "state": {"store": store, "cache": cache}}
        ''', "javascript": '''
            function solve(data) {
              const store = new Map(Object.entries(data.store)), cache = new Map(), reads = [];
              for (const event of data.events) {
                const key = event.key;
                if (event.op === 'get') {
                  if (!cache.has(key)) cache.set(key, store.has(key) ? store.get(key) : null);
                  reads.push(cache.get(key));
                } else {
                  if (event.op === 'put') store.set(key, event.value);
                  else store.delete(key);
                  cache.delete(key);
                }
              }
              return { reads, state: { store: Object.fromEntries(store), cache: Object.fromEntries(cache) } };
            }
            module.exports = { solve };
        '''},
        [case("Repeated read", {"store": {"x": 1}, "events": [{"op": "get", "key": "x"}, {"op": "get", "key": "x"}]}, {"reads": [1, 1], "state": {"store": {"x": 1}, "cache": {"x": 1}}}),
         case("Read after write", {"store": {"x": 1}, "events": [{"op": "get", "key": "x"}, {"op": "put", "key": "x", "value": 2}, {"op": "get", "key": "x"}]}, {"reads": [1, 2], "state": {"store": {"x": 2}, "cache": {"x": 2}}}),
         case("Cached miss then creation", {"store": {}, "events": [{"op": "get", "key": "x"}, {"op": "put", "key": "x", "value": 0}, {"op": "get", "key": "x"}]}, {"reads": [None, 0], "state": {"store": {"x": 0}, "cache": {"x": 0}}}, True),
         case("Read after delete", {"store": {"x": 1}, "events": [{"op": "get", "key": "x"}, {"op": "delete", "key": "x"}, {"op": "get", "key": "x"}]}, {"reads": [1, None], "state": {"store": {}, "cache": {"x": None}}}, True),
         case("Invalidate without refilling", {"store": {"x": 1}, "events": [{"op": "get", "key": "x"}, {"op": "put", "key": "x", "value": 2}]}, {"reads": [1], "state": {"store": {"x": 2}, "cache": {}}}, True, [{"path": "state.cache", "equals": {}}]),
         case("Keep unrelated cached entries", {"store": {"x": 1, "y": 2}, "events": [{"op": "get", "key": "x"}, {"op": "get", "key": "y"}, {"op": "put", "key": "x", "value": 5}]}, {"reads": [1, 2], "state": {"store": {"x": 5, "y": 2}, "cache": {"y": 2}}}, True),
         case("Prototype-like key", {"store": {"__proto__": -1}, "events": [{"op": "get", "key": "__proto__"}, {"op": "put", "key": "__proto__", "value": 0}, {"op": "get", "key": "__proto__"}]}, {"reads": [-1, 0], "state": {"store": {"__proto__": 0}, "cache": {"__proto__": 0}}}, True),
         case("Delete a cached missing key", {"store": {}, "events": [{"op": "get", "key": "missing"}, {"op": "delete", "key": "missing"}]}, {"reads": [None], "state": {"store": {}, "cache": {}}}, True),
         case("No events", {"store": {"x": 0}, "events": []}, {"reads": [], "state": {"store": {"x": 0}, "cache": {}}}, True)],
        "The cache is a derived copy. Invalidate the affected key after every store mutation, including a delete of a missing key because its absence may be cached. Test presence independently of value, and use Map for arbitrary JavaScript keys. This sequential exercise does not model concurrent cache-fill races. Expected time O(initial keys + events), space O(initial keys + events).",
        ["Which copy does a get use after the authoritative store changes?",
         "Both cached values and cached misses become stale after a mutation.",
         "After each put or delete, remove just that key from cache; let the next get refill it."], 22,
    ),
    problem(
        "queue-visibility-redelivery", "The job lost after a worker disappears",
        "A queue simulator hides leased jobs while a worker processes them, but never makes them visible again. A crashed worker can leave a job stranded forever.",
        "system_design", "hard", ["queues", "leases", "redelivery"],
        ["Input.jobs contains at most 50 unique lowercase ASCII job IDs in queue order. Input.visibility is an integer from 1 through 100.",
         "Process at most 200 events with nondecreasing integer now values from 0 through 10,000. A {op: 'receive', now} leases the first unfinished job in original queue order that has no lease or whose lease deadline <= now. Return {id, token}, or null if none is visible.",
         "A successful receive uses the next integer token starting at 1 and sets that job's deadline to now + visibility. Empty receives do not consume tokens. Redelivery replaces the previous token.",
         "An {op: 'ack', now, token} returns true and completes a job only when token matches its current lease, the job is unfinished, and now is strictly before its deadline. Otherwise return false without changing state.",
         "Return {results: array, state: {pending: string[], done: string[]}}, with one result per event and both state lists in original job order. This is a deterministic lease simulation."],
        {"python": '''
            def solve(data):
                jobs = [{"id": job, "deadline": None, "token": None, "done": False} for job in data["jobs"]]
                results, next_token = [], 1
                for event in data["events"]:
                    now = event["now"]
                    if event["op"] == "receive":
                        job = next((job for job in jobs if not job["done"]
                                    and job["deadline"] is None), None)
                        if job is None:
                            results.append(None)
                        else:
                            job["deadline"] = now + data["visibility"]
                            job["token"] = next_token
                            results.append({"id": job["id"], "token": next_token})
                            next_token += 1
                    else:
                        job = next((job for job in jobs if not job["done"]
                                    and job["token"] == event["token"] and now < job["deadline"]), None)
                        if job is not None:
                            job["done"] = True
                        results.append(job is not None)
                return {"results": results, "state": {
                    "pending": [job["id"] for job in jobs if not job["done"]],
                    "done": [job["id"] for job in jobs if job["done"]]}}
        '''},
        {"python": '''
            def solve(data):
                jobs = [{"id": job, "deadline": None, "token": None, "done": False} for job in data["jobs"]]
                results, next_token = [], 1
                for event in data["events"]:
                    now = event["now"]
                    if event["op"] == "receive":
                        job = next((job for job in jobs if not job["done"]
                                    and (job["deadline"] is None or job["deadline"] <= now)), None)
                        if job is None:
                            results.append(None)
                        else:
                            job["deadline"] = now + data["visibility"]
                            job["token"] = next_token
                            results.append({"id": job["id"], "token": next_token})
                            next_token += 1
                    else:
                        job = next((job for job in jobs if not job["done"]
                                    and job["token"] == event["token"] and now < job["deadline"]), None)
                        if job is not None:
                            job["done"] = True
                        results.append(job is not None)
                return {"results": results, "state": {
                    "pending": [job["id"] for job in jobs if not job["done"]],
                    "done": [job["id"] for job in jobs if job["done"]]}}
        '''},
        [case("Receive and acknowledge", {"jobs": ["a"], "visibility": 5, "events": [{"op": "receive", "now": 0}, {"op": "ack", "now": 1, "token": 1}]}, {"results": [{"id": "a", "token": 1}, True], "state": {"pending": [], "done": ["a"]}}),
         case("Worker disappears until expiry", {"jobs": ["a"], "visibility": 5, "events": [{"op": "receive", "now": 0}, {"op": "receive", "now": 5}]}, {"results": [{"id": "a", "token": 1}, {"id": "a", "token": 2}], "state": {"pending": ["a"], "done": []}}),
         case("Lease still active", {"jobs": ["a"], "visibility": 5, "events": [{"op": "receive", "now": 0}, {"op": "receive", "now": 4}]}, {"results": [{"id": "a", "token": 1}, None], "state": {"pending": ["a"], "done": []}}, True),
         case("Old acknowledgement cannot finish a new lease", {"jobs": ["a"], "visibility": 5, "events": [{"op": "receive", "now": 0}, {"op": "receive", "now": 5}, {"op": "ack", "now": 6, "token": 1}, {"op": "ack", "now": 6, "token": 2}]}, {"results": [{"id": "a", "token": 1}, {"id": "a", "token": 2}, False, True], "state": {"pending": [], "done": ["a"]}}, True),
         case("Expiry prioritizes original queue order", {"jobs": ["a", "b"], "visibility": 5, "events": [{"op": "receive", "now": 0}, {"op": "receive", "now": 1}, {"op": "receive", "now": 5}]}, {"results": [{"id": "a", "token": 1}, {"id": "b", "token": 2}, {"id": "a", "token": 3}], "state": {"pending": ["a", "b"], "done": []}}, True),
         case("Acknowledgement at the deadline is too late", {"jobs": ["a"], "visibility": 5, "events": [{"op": "receive", "now": 0}, {"op": "ack", "now": 5, "token": 1}, {"op": "receive", "now": 5}]}, {"results": [{"id": "a", "token": 1}, False, {"id": "a", "token": 2}], "state": {"pending": ["a"], "done": []}}, True),
         case("Empty receives preserve token sequence", {"jobs": ["a", "b"], "visibility": 5, "events": [{"op": "receive", "now": 0}, {"op": "receive", "now": 0}, {"op": "receive", "now": 1}, {"op": "ack", "now": 1, "token": 1}, {"op": "receive", "now": 5}]}, {"results": [{"id": "a", "token": 1}, {"id": "b", "token": 2}, None, True, {"id": "b", "token": 3}], "state": {"pending": ["b"], "done": ["a"]}}, True),
         case("Completed jobs never return", {"jobs": ["a"], "visibility": 5, "events": [{"op": "receive", "now": 0}, {"op": "ack", "now": 1, "token": 1}, {"op": "ack", "now": 2, "token": 1}, {"op": "receive", "now": 10}]}, {"results": [{"id": "a", "token": 1}, True, False, None], "state": {"pending": [], "done": ["a"]}}, True),
         case("Empty queue and unknown acknowledgement", {"jobs": [], "visibility": 5, "events": [{"op": "receive", "now": 0}, {"op": "ack", "now": 0, "token": 99}]}, {"results": [None, False], "state": {"pending": [], "done": []}}, True),
         case("No events", {"jobs": ["b", "a"], "visibility": 1, "events": []}, {"results": [], "state": {"pending": ["b", "a"], "done": []}}, True)],
        "A lease is temporary ownership, not permanent removal. An unfinished job becomes visible at its deadline. Assign a new token on redelivery and accept acknowledgements only for the current, unexpired lease, so an old worker cannot complete a newer delivery. Time O(events × jobs), space O(events + jobs).",
        ["What makes an unfinished leased job eligible after its worker disappears?",
         "The lease interval ends at deadline, so equality belongs to the next delivery.",
         "Receive jobs with no lease or deadline <= now; retain the current-token and now < deadline checks for acknowledgements."], 30,
    ),
    problem(
        "consistent-hash-wraparound", "The missing end of the hash ring",
        "A shard router searches clockwise for the next token but forgets that the token space is a ring. Keys beyond the largest token lose their owner.",
        "system_design", "medium", ["sharding", "consistent-hashing", "binary-search"],
        ["Input.nodes contains at most 100 {position, owner} objects. Positions are unique integers from 0 through 9,999; owners are strings and may repeat for virtual nodes. Input order is arbitrary.",
         "Input.hashes contains at most 200 precomputed integer hashes from 0 through 9,999.",
         "For each hash, return the owner of the smallest position >= hash. If there is no such position, wrap to the smallest position on the ring.",
         "Return an array in hash input order. An empty ring returns null for every hash; no hashes returns []."],
        {"go": '''
            package main
            import "sort"
            type ringNode struct { position int; owner string }
            func Solve(data map[string]interface{}) interface{} {
                nodes := make([]ringNode, 0)
                for _, raw := range data["nodes"].([]interface{}) {
                    node := raw.(map[string]interface{})
                    nodes = append(nodes, ringNode{int(node["position"].(float64)), node["owner"].(string)})
                }
                sort.Slice(nodes, func(i, j int) bool { return nodes[i].position < nodes[j].position })
                result := make([]interface{}, 0)
                for _, raw := range data["hashes"].([]interface{}) {
                    hash := int(raw.(float64))
                    i := sort.Search(len(nodes), func(i int) bool { return nodes[i].position >= hash })
                    if i == len(nodes) { result = append(result, nil) } else { result = append(result, nodes[i].owner) }
                }
                return result
            }
        '''},
        {"go": '''
            package main
            import "sort"
            type ringNode struct { position int; owner string }
            func Solve(data map[string]interface{}) interface{} {
                nodes := make([]ringNode, 0)
                for _, raw := range data["nodes"].([]interface{}) {
                    node := raw.(map[string]interface{})
                    nodes = append(nodes, ringNode{int(node["position"].(float64)), node["owner"].(string)})
                }
                sort.Slice(nodes, func(i, j int) bool { return nodes[i].position < nodes[j].position })
                result := make([]interface{}, 0)
                for _, raw := range data["hashes"].([]interface{}) {
                    if len(nodes) == 0 { result = append(result, nil); continue }
                    hash := int(raw.(float64))
                    i := sort.Search(len(nodes), func(i int) bool { return nodes[i].position >= hash })
                    if i == len(nodes) { i = 0 }
                    result = append(result, nodes[i].owner)
                }
                return result
            }
        '''},
        [case("Clockwise successor", {"nodes": [{"position": 10, "owner": "a"}, {"position": 20, "owner": "b"}], "hashes": [0, 12]}, ["a", "b"]),
         case("Wrap past the last token", {"nodes": [{"position": 10, "owner": "a"}, {"position": 20, "owner": "b"}], "hashes": [90]}, ["a"]),
         case("Exact token belongs to that owner", {"nodes": [{"position": 10, "owner": "a"}, {"position": 20, "owner": "b"}], "hashes": [10, 11, 20, 21]}, ["a", "b", "b", "a"], True),
         case("Unsorted tokens", {"nodes": [{"position": 70, "owner": "c"}, {"position": 10, "owner": "a"}, {"position": 40, "owner": "b"}], "hashes": [0, 20, 50, 99]}, ["a", "b", "c", "a"], True),
         case("One owner covers the ring", {"nodes": [{"position": 500, "owner": "only"}], "hashes": [0, 500, 9999]}, ["only", "only", "only"], True),
         case("Empty ring", {"nodes": [], "hashes": [0, 9999]}, [None, None], True),
         case("No lookups", {"nodes": [{"position": 0, "owner": "a"}], "hashes": []}, [], True),
         case("Virtual nodes share an owner", {"nodes": [{"position": 0, "owner": "a"}, {"position": 40, "owner": "b"}, {"position": 80, "owner": "a"}], "hashes": [0, 1, 41, 81]}, ["a", "b", "a", "a"], True)],
        "Sort ring tokens and find the first position at least as large as the hash. A search result just past the array means wrap to index zero, provided the ring is not empty. Repeated owner names represent valid virtual nodes and must not be deduplicated. Time O(n log n + q log(n + 1)), space O(n + q).",
        ["Where should a clockwise walk go after passing the largest token?",
         "An out-of-range search result means wraparound for a nonempty ring, but absence for an empty ring.",
         "Handle an empty ring first, then replace a search result equal to len(nodes) with index zero."], 20,
    ),
    problem(
        "circuit-breaker-cooldown", "The circuit that never closes",
        "A dependency circuit opens after repeated failures and blocks every later call, even after its cooldown. Repair recovery so a probe can restore service or start a fresh cooldown.",
        "system_design", "hard", ["resilience", "circuit-breaker", "state-machine"],
        ["Input.threshold is 1 through 5 and input.cooldown is 1 through 100. Start closed with zero consecutive failures.",
         "Input.calls contains at most 200 {at, ok} objects with nondecreasing integer times from 0 through 10,000 and boolean outcomes. Every allowed call completes immediately.",
         "While closed, success resets failures to zero; failure increments failures. Reaching threshold opens the circuit until at + cooldown.",
         "While open and at < retry_at, return 'blocked' and ignore the supplied outcome without extending the cooldown. At or after retry_at, allow one synchronous probe: success closes and resets failures; failure immediately reopens until at + cooldown with failures set to threshold.",
         "Return {results: ('ok', 'error', or 'blocked')[], state: {status: 'open' or 'closed', failures, retry_at}}. Use 0 for retry_at when closed. Merely reaching the deadline does not close the circuit without a successful probe."],
        {"java": '''
            import com.google.gson.*;
            public class Solution {
              public static JsonElement solve(JsonObject data) {
                int threshold = data.get("threshold").getAsInt(), cooldown = data.get("cooldown").getAsInt();
                int failures = 0;
                Integer retryAt = null;
                JsonArray results = new JsonArray();
                for (JsonElement raw : data.getAsJsonArray("calls")) {
                  JsonObject call = raw.getAsJsonObject();
                  int at = call.get("at").getAsInt();
                  if (retryAt != null) {
                    results.add("blocked");
                    continue;
                  }
                  boolean probe = retryAt != null;
                  if (call.get("ok").getAsBoolean()) {
                    failures = 0;
                    retryAt = null;
                    results.add("ok");
                  } else {
                    failures = probe ? threshold : failures + 1;
                    if (failures >= threshold) retryAt = at + cooldown;
                    results.add("error");
                  }
                }
                JsonObject state = new JsonObject(), result = new JsonObject();
                state.addProperty("status", retryAt == null ? "closed" : "open");
                state.addProperty("failures", failures);
                state.addProperty("retry_at", retryAt == null ? 0 : retryAt);
                result.add("results", results);
                result.add("state", state);
                return result;
              }
            }
        '''},
        {"java": '''
            import com.google.gson.*;
            public class Solution {
              public static JsonElement solve(JsonObject data) {
                int threshold = data.get("threshold").getAsInt(), cooldown = data.get("cooldown").getAsInt();
                int failures = 0;
                Integer retryAt = null;
                JsonArray results = new JsonArray();
                for (JsonElement raw : data.getAsJsonArray("calls")) {
                  JsonObject call = raw.getAsJsonObject();
                  int at = call.get("at").getAsInt();
                  if (retryAt != null && at < retryAt) {
                    results.add("blocked");
                    continue;
                  }
                  boolean probe = retryAt != null;
                  if (call.get("ok").getAsBoolean()) {
                    failures = 0;
                    retryAt = null;
                    results.add("ok");
                  } else {
                    failures = probe ? threshold : failures + 1;
                    if (failures >= threshold) retryAt = at + cooldown;
                    results.add("error");
                  }
                }
                JsonObject state = new JsonObject(), result = new JsonObject();
                state.addProperty("status", retryAt == null ? "closed" : "open");
                state.addProperty("failures", failures);
                state.addProperty("retry_at", retryAt == null ? 0 : retryAt);
                result.add("results", results);
                result.add("state", state);
                return result;
              }
            }
        '''},
        [case("Success resets consecutive failures", {"threshold": 2, "cooldown": 5, "calls": [{"at": 0, "ok": False}, {"at": 1, "ok": True}, {"at": 2, "ok": False}]}, {"results": ["error", "ok", "error"], "state": {"status": "closed", "failures": 1, "retry_at": 0}}),
         case("Recover at the deadline", {"threshold": 2, "cooldown": 5, "calls": [{"at": 0, "ok": False}, {"at": 1, "ok": False}, {"at": 5, "ok": True}, {"at": 6, "ok": True}]}, {"results": ["error", "error", "blocked", "ok"], "state": {"status": "closed", "failures": 0, "retry_at": 0}}),
         case("Failed probe restarts the cooldown", {"threshold": 1, "cooldown": 5, "calls": [{"at": 0, "ok": False}, {"at": 5, "ok": False}]}, {"results": ["error", "error"], "state": {"status": "open", "failures": 1, "retry_at": 10}}, True, [{"path": "state.retry_at", "equals": 10}]),
         case("Probe failure reopens immediately at a higher threshold", {"threshold": 3, "cooldown": 5, "calls": [{"at": 0, "ok": False}, {"at": 1, "ok": False}, {"at": 2, "ok": False}, {"at": 7, "ok": False}, {"at": 8, "ok": True}, {"at": 12, "ok": True}]}, {"results": ["error", "error", "error", "error", "blocked", "ok"], "state": {"status": "closed", "failures": 0, "retry_at": 0}}, True),
         case("Blocked failure does not extend the deadline", {"threshold": 1, "cooldown": 5, "calls": [{"at": 0, "ok": False}, {"at": 4, "ok": False}, {"at": 5, "ok": True}]}, {"results": ["error", "blocked", "ok"], "state": {"status": "closed", "failures": 0, "retry_at": 0}}, True),
         case("Same-time call is blocked", {"threshold": 1, "cooldown": 5, "calls": [{"at": 0, "ok": False}, {"at": 0, "ok": True}]}, {"results": ["error", "blocked"], "state": {"status": "open", "failures": 1, "retry_at": 5}}, True),
         case("Late recovery", {"threshold": 1, "cooldown": 1, "calls": [{"at": 0, "ok": False}, {"at": 10000, "ok": True}]}, {"results": ["error", "ok"], "state": {"status": "closed", "failures": 0, "retry_at": 0}}, True),
         case("No calls", {"threshold": 2, "cooldown": 5, "calls": []}, {"results": [], "state": {"status": "closed", "failures": 0, "retry_at": 0}}, True)],
        "An open circuit rejects calls only before its retry deadline. Once the deadline is reached, the next allowed call is a probe: success clears the failure history, while failure immediately starts another cooldown. Blocked outcomes never affect state. This synchronous model has no overlapping probes. Time O(n), output space O(n), bookkeeping space O(1).",
        ["Is 'open' permanent, or does its deadline permit a recovery attempt?",
         "Distinguish calls before retry_at from calls at or after it; blocked calls must not move the deadline.",
         "Block only when retryAt != null and at < retryAt. Preserve the existing probe success and failure transitions."], 28,
    ),
])
