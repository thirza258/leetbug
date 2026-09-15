"""Versioned, executable case studies. Test oracles never enter the sandbox."""
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
