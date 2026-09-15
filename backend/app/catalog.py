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
