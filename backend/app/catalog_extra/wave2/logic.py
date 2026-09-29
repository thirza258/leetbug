"""Ten wrong-answer repairs, including language-specific semantics traps."""
from functools import partial

from ..common import make

p = partial(make, "logic")

PROBLEMS = [
    p("map-parseint-radix", "Parsing with map mangles later values", "A JavaScript importer passes parseInt directly to Array.map, which silently supplies each element's index as the radix.",
      "Input.tokens contains canonical decimal strings of nonnegative integers: ASCII digits only, at most 15 digits, leading zeros allowed. Return their numeric values in order.",
      '''
      function solve(data) {
        return data.tokens.map(token => Number.parseInt(token, 10));
      }
      module.exports = { solve };
      ''', ('data.tokens.map(token => Number.parseInt(token, 10))', 'data.tokens.map(Number.parseInt)'),
      [({"tokens": ["42"]}, [42]), ({"tokens": ["10", "10", "10"]}, [10, 10, 10]), ({"tokens": []}, []), ({"tokens": ["7", "8", "9", "10"]}, [7, 8, 9, 10]), ({"tokens": ["0", "007", "123456789012345"]}, [0, 7, 123456789012345])],
      ["Which arguments does Array.prototype.map pass to its callback?", "map calls the callback with (element, index, array), and parseInt treats its second argument as the radix.", "Wrap the call so every token is parsed with radix 10, for example token => Number.parseInt(token, 10)."], ["javascript", "callbacks", "parsing"], "easy", language="javascript"),
    p("var-loop-handlers", "Every button reports the last position", "A JavaScript toolbar registers click handlers in a loop declared with var, so every handler reads the counter after the loop has finished.",
      "Input.buttons contains button labels, and input.clicks contains valid button indexes in click order. Each click produces 'index:label' for the button that was clicked. Return the click results in order.",
      '''
      function solve(data) {
        const handlers = [];
        for (let index = 0; index < data.buttons.length; index++) {
          handlers.push(() => `${index}:${data.buttons[index]}`);
        }
        return data.clicks.map(position => handlers[position]());
      }
      module.exports = { solve };
      ''', ('for (let index = 0;', 'for (var index = 0;'),
      [({"buttons": ["save"], "clicks": []}, []), ({"buttons": ["save", "open"], "clicks": [0, 1]}, ["0:save", "1:open"]), ({"buttons": [], "clicks": []}, []), ({"buttons": ["a", "b", "c"], "clicks": [2, 2, 0]}, ["2:c", "2:c", "0:a"]), ({"buttons": ["", "x"], "clicks": [0]}, ["0:"])],
      ["Which variable does each handler read when it finally runs?", "A var declaration is function-scoped, so every closure shares one index that already equals buttons.length.", "Declare the loop variable with let so each iteration gets its own binding."], ["javascript", "closures", "scope"], language="javascript"),
    p("list-remove-overload", "Cancelling ticket 1 removes the second guest", "A Java waitlist calls remove with a primitive ticket number, which Java resolves to the index-based overload instead of removing that ticket.",
      "Input.waitlist contains distinct nonnegative integer ticket numbers in queue order, and input.cancel contains ticket numbers to cancel in order. Remove each cancelled ticket if it is still waiting, and ignore tickets that are absent. Return the remaining waitlist.",
      '''
      import com.google.gson.*;
      import java.util.*;
      public class Solution {
        public static JsonElement solve(JsonObject data) {
          List<Integer> waitlist = new ArrayList<>();
          for (JsonElement ticket : data.getAsJsonArray("waitlist")) waitlist.add(ticket.getAsInt());
          for (JsonElement raw : data.getAsJsonArray("cancel")) {
            int ticket = raw.getAsInt();
            waitlist.remove(Integer.valueOf(ticket));
          }
          return new Gson().toJsonTree(waitlist);
        }
      }
      ''', ('waitlist.remove(Integer.valueOf(ticket))', 'waitlist.remove(ticket)'),
      [({"waitlist": [0, 1, 2], "cancel": [0]}, [1, 2]), ({"waitlist": [4, 7, 1], "cancel": [1]}, [4, 7]), ({"waitlist": [3, 5, 9], "cancel": [2]}, [3, 5, 9]), ({"waitlist": [2, 0, 1, 5], "cancel": [0, 2]}, [1, 5]), ({"waitlist": [0, 1, 2, 3], "cancel": [1, 1]}, [0, 2, 3])],
      ["Which remove overload does Java choose for a primitive int argument?", "List<Integer>.remove(int) removes by position; only remove(Object) removes a matching value.", "Pass a boxed value, for example waitlist.remove(Integer.valueOf(ticket)), so present tickets are removed by value and absent tickets are ignored."], ["java", "collections", "overloading"], language="java"),
    p("range-copy-interest", "Interest is credited to a copy", "A Go batch job applies interest inside a range loop, but it updates a copy of each account struct instead of the account stored in the slice.",
      "Input.accounts contains {id: string, balance: nonnegative integer cents} objects, and input.rate_bps is 0 through 10,000. Add floor(balance * rate_bps / 10,000) to each balance. Return [{id, balance}] in input order.",
      '''
      package main

      type Account struct {
          ID      string `json:"id"`
          Balance int    `json:"balance"`
      }

      func Solve(data map[string]interface{}) interface{} {
          rate := int(data["rate_bps"].(float64))
          accounts := []Account{}
          for _, raw := range data["accounts"].([]interface{}) {
              entry := raw.(map[string]interface{})
              accounts = append(accounts, Account{entry["id"].(string), int(entry["balance"].(float64))})
          }
          for i := range accounts {
              account := &accounts[i]
              account.Balance += account.Balance * rate / 10000
          }
          return accounts
      }
      ''', ('    for i := range accounts {\n        account := &accounts[i]\n', '    for _, account := range accounts {\n'),
      [({"accounts": [], "rate_bps": 100}, []), ({"accounts": [{"id": "a", "balance": 10000}], "rate_bps": 150}, [{"id": "a", "balance": 10150}]), ({"accounts": [{"id": "a", "balance": 99}, {"id": "b", "balance": 0}], "rate_bps": 100}, [{"id": "a", "balance": 99}, {"id": "b", "balance": 0}]), ({"accounts": [{"id": "x", "balance": 2500}, {"id": "y", "balance": 12345}], "rate_bps": 10000}, [{"id": "x", "balance": 5000}, {"id": "y", "balance": 24690}]), ({"accounts": [{"id": "z", "balance": 1000000}], "rate_bps": 1}, [{"id": "z", "balance": 1000100}])],
      ["Which value does the range loop variable refer to?", "range copies each struct element into the loop variable, so changing that copy leaves the slice unchanged.", "Iterate by index and update accounts[i], or a pointer to it, so the new balance is stored in the slice."], ["go", "structs", "iteration"], "easy", language="go"),
    p("append-shared-path", "Recorded routes rewrite themselves", "A Go route finder appends its shared path slice to the results without copying it, so later branches overwrite paths that were already recorded.",
      "Input.children maps node IDs to ordered lists of child IDs, and input.root is the root ID. The graph is a tree with at most 30 nodes; nodes missing from children, or with empty child lists, are leaves. Return every root-to-leaf path in depth-first order, visiting children in their listed order.",
      '''
      package main

      func Solve(data map[string]interface{}) interface{} {
          children := data["children"].(map[string]interface{})
          paths := [][]string{}
          path := make([]string, 0, 32)
          var visit func(node string)
          visit = func(node string) {
              path = append(path, node)
              next, _ := children[node].([]interface{})
              if len(next) == 0 {
                  paths = append(paths, append([]string(nil), path...))
              }
              for _, child := range next {
                  visit(child.(string))
              }
              path = path[:len(path)-1]
          }
          visit(data["root"].(string))
          return paths
      }
      ''', ('paths = append(paths, append([]string(nil), path...))', 'paths = append(paths, path)'),
      [({"children": {}, "root": "a"}, [["a"]]), ({"children": {"a": ["b", "c"]}, "root": "a"}, [["a", "b"], ["a", "c"]]), ({"children": {"r": ["x"], "x": ["y", "z"], "y": [], "z": []}, "root": "r"}, [["r", "x", "y"], ["r", "x", "z"]]), ({"children": {"a": ["b", "d"], "b": ["c"]}, "root": "a"}, [["a", "b", "c"], ["a", "d"]]), ({"children": {"root": ["l1", "l2", "l3"]}, "root": "root"}, [["root", "l1"], ["root", "l2"], ["root", "l3"]])],
      ["Do the recorded path slices own their elements, or do they share storage with path?", "A slice is a view of a backing array; after backtracking, appending to the shared path overwrites positions that earlier recorded slices still reference.", "Record a copy of the current path, for example append([]string(nil), path...), before continuing the search."], ["go", "slices", "backtracking"], "hard", language="go"),
    p("accumulate-integer-seed", "The receipt total drops every cent", "A C++ receipt sums decimal prices with std::accumulate seeded by the integer literal 0, so every partial sum is truncated to an int.",
      "Input.prices contains up to 50 numbers from 0 through 10,000 with at most two decimal places. Return their sum rounded to two decimal places. An empty receipt totals 0.",
      '''
      #include <nlohmann/json.hpp>
      #include <cmath>
      #include <numeric>
      #include <vector>
      using nlohmann::json;
      json solve(const json& data) {
          std::vector<double> prices = data.at("prices").get<std::vector<double>>();
          double total = std::accumulate(prices.begin(), prices.end(), 0.0);
          return std::round(total * 100) / 100;
      }
      ''', ('std::accumulate(prices.begin(), prices.end(), 0.0)', 'std::accumulate(prices.begin(), prices.end(), 0)'),
      [({"prices": [2, 3]}, 5), ({"prices": [1.5, 2.25]}, 3.75), ({"prices": []}, 0), ({"prices": [0.1, 0.2, 0.3]}, 0.6), ({"prices": [9999.99, 0.01, 10000]}, 20000)],
      ["Which type does std::accumulate use for its running total?", "The accumulator has the type of the initial value; the literal 0 is an int, so each partial sum is truncated.", "Seed the accumulation with 0.0, a double, and round only the final total to cents."], ["cpp", "type-deduction", "floating-point"], "easy", language="cpp"),
    p("shared-default-warnings", "Every record inherits earlier warnings", "A validation helper collects warnings in a list default argument, so records validated later report problems found in earlier records.",
      "Input.records contains objects whose present values are strings. A field is missing when its key is absent or its value is an empty string. Check 'email' first, then 'name'. Return one list per record containing 'missing email' and/or 'missing name' in that order.",
      '''
      def validate(record, warnings=None):
          warnings = [] if warnings is None else warnings
          for field in ("email", "name"):
              if not record.get(field):
                  warnings.append(f"missing {field}")
          return warnings

      def solve(data):
          return [validate(record) for record in data["records"]]
      ''', ('warnings=None):\n    warnings = [] if warnings is None else warnings\n', 'warnings=[]):\n'),
      [({"records": [{"email": "a@x", "name": ""}]}, [["missing name"]]), ({"records": [{"email": "", "name": "Al"}, {"email": "b@x", "name": "Bo"}]}, [["missing email"], []]), ({"records": []}, []), ({"records": [{}, {"name": "x"}, {"email": "e"}]}, [["missing email", "missing name"], ["missing email"], ["missing name"]]), ({"records": [{"email": "a", "name": "b", "extra": ""}]}, [[]])],
      ["When is a default argument value created?", "Python evaluates a default once, when the function is defined, so every call that omits warnings appends to the same list.", "Use None as the default and create a fresh list inside the function when the caller does not supply one."], ["functions", "mutable-defaults"]),
    p("diamond-false-cycle", "A diamond dependency is reported as a cycle", "A dependency checker treats every previously visited package as part of the current path, so reaching a shared dependency by a second route looks like a cycle.",
      "Input.graph maps package names to lists of dependency names, and every dependency is also a key. Return true exactly when the directed graph contains a cycle, including a package that depends on itself. There are at most 50 packages.",
      '''
      def solve(data):
          graph = data["graph"]
          state = {}
          def visit(node):
              state[node] = "active"
              for child in graph[node]:
                  mark = state.get(child)
                  if mark == "active":
                      return True
                  if mark is None and visit(child):
                      return True
              state[node] = "done"
              return False
          return any(state.get(node) is None and visit(node) for node in graph)
      ''', ('if mark == "active":', 'if mark is not None:'),
      [({"graph": {"a": ["b"], "b": []}}, False), ({"graph": {"app": ["log", "http"], "http": ["log"], "log": []}}, False), ({"graph": {"a": ["a"]}}, True), ({"graph": {"a": ["b"], "b": ["c"], "c": ["a"], "d": []}}, True), ({"graph": {"x": [], "y": ["x"]}}, False), ({"graph": {}}, False)],
      ["Does reaching a finished package again prove there is a cycle?", "Only an edge back to a package on the current depth-first path closes a cycle; finished packages are safe to reach again.", "Track three states (unvisited, active, done) and report a cycle only when a dependency is still active."], ["graphs", "cycle-detection", "dfs"], "hard"),
    p("two-stack-queue-transfer", "The two-stack queue serves out of order", "A queue built from two stacks moves every inbox item to the outbox on each dequeue, even while older items are still waiting in the outbox.",
      "Input.ops contains {op: 'push', value: integer} and {op: 'pop'} operations applied to an initially empty first-in, first-out queue. A pop returns the oldest queued value, or null when the queue is empty. Return the pop results in order.",
      '''
      def solve(data):
          inbox, outbox, results = [], [], []
          for op in data["ops"]:
              if op["op"] == "push":
                  inbox.append(op["value"])
                  continue
              if not outbox:
                  while inbox:
                      outbox.append(inbox.pop())
              results.append(outbox.pop() if outbox else None)
          return results
      ''', ('        if not outbox:\n            while inbox:\n                outbox.append(inbox.pop())\n', '        while inbox:\n            outbox.append(inbox.pop())\n'),
      [({"ops": [{"op": "push", "value": 1}, {"op": "push", "value": 2}, {"op": "pop"}, {"op": "pop"}]}, [1, 2]), ({"ops": [{"op": "push", "value": 1}, {"op": "push", "value": 2}, {"op": "pop"}, {"op": "push", "value": 3}, {"op": "pop"}, {"op": "pop"}]}, [1, 2, 3]), ({"ops": [{"op": "pop"}]}, [None]), ({"ops": [{"op": "push", "value": 5}, {"op": "pop"}, {"op": "pop"}, {"op": "push", "value": 6}, {"op": "push", "value": 7}, {"op": "pop"}, {"op": "push", "value": 8}, {"op": "pop"}, {"op": "pop"}]}, [5, None, 6, 7, 8]), ({"ops": []}, [])],
      ["When may items move from the inbox stack to the outbox stack?", "Older items already in the outbox must be served before any newer inbox item is reversed on top of them.", "Transfer the inbox only when the outbox is empty, then pop from the outbox."], ["queues", "stacks", "data-structures"]),
    p("rectangle-corner-overlap", "A cross-shaped overlap goes unnoticed", "A floor-plan checker detects overlapping rooms by testing whether a corner of one room lies inside the other, which misses rooms that cross like a plus sign.",
      "Input.a and input.b are axis-aligned rectangles [x1, y1, x2, y2] with integer coordinates, x1 < x2, and y1 < y2. Return true when their interiors overlap with positive area. Rectangles that only touch along an edge or at a corner do not overlap.",
      '''
      def solve(data):
          ax1, ay1, ax2, ay2 = data["a"]
          bx1, by1, bx2, by2 = data["b"]
          return ax1 < bx2 and bx1 < ax2 and ay1 < by2 and by1 < ay2
      ''', ('ax1 < bx2 and bx1 < ax2 and ay1 < by2 and by1 < ay2', 'any(bx1 < x < bx2 and by1 < y < by2 for x in (ax1, ax2) for y in (ay1, ay2)) or any(ax1 < x < ax2 and ay1 < y < ay2 for x in (bx1, bx2) for y in (by1, by2))'),
      [({"a": [0, 0, 4, 4], "b": [2, 2, 6, 6]}, True), ({"a": [0, 2, 6, 4], "b": [2, 0, 4, 6]}, True), ({"a": [0, 0, 2, 2], "b": [2, 0, 4, 2]}, False), ({"a": [1, 1, 3, 3], "b": [1, 1, 3, 3]}, True), ({"a": [0, 0, 10, 10], "b": [2, 2, 3, 3]}, True), ({"a": [-5, -5, -1, -1], "b": [-1, -5, 3, -1]}, False)],
      ["Can two rectangles overlap even though no corner of either lies inside the other?", "Axis-aligned rectangles overlap exactly when their x-intervals overlap and their y-intervals overlap.", "Compare the open intervals on both axes with strict inequalities instead of testing corner containment."], ["geometry", "intervals"]),
]
