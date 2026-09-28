"""Ten crash diagnoses, including language-specific panics and exceptions."""
from functools import partial

from ..common import make

p = partial(make, "runtime")

PROBLEMS = [
    p("nil-customer-pointer", "A missing customer crashes the label printer", "A Go label printer indexes customers by pointer and dereferences every lookup, but orders can reference customers that were never loaded.",
      "Input.customers contains {id: string, name: string} objects with unique IDs, and input.orders contains customer-ID strings. Return one label per order: that customer's name, or 'unknown' when no customer has the ID. Empty names are valid names.",
      '''
      package main

      type Customer struct {
          Name string
      }

      func Solve(data map[string]interface{}) interface{} {
          index := map[string]*Customer{}
          for _, raw := range data["customers"].([]interface{}) {
              entry := raw.(map[string]interface{})
              index[entry["id"].(string)] = &Customer{Name: entry["name"].(string)}
          }
          labels := []string{}
          for _, raw := range data["orders"].([]interface{}) {
              customer, found := index[raw.(string)]
              if !found {
                  labels = append(labels, "unknown")
                  continue
              }
              labels = append(labels, customer.Name)
          }
          return labels
      }
      ''', ('customer, found := index[raw.(string)]\n        if !found {\n            labels = append(labels, "unknown")\n            continue\n        }\n', 'customer := index[raw.(string)]\n'),
      [({"customers": [{"id": "c1", "name": "Ada"}], "orders": ["c1"]}, ["Ada"]), ({"customers": [{"id": "c1", "name": "Ada"}], "orders": ["c2", "c1"]}, ["unknown", "Ada"]), ({"customers": [], "orders": []}, []), ({"customers": [{"id": "a", "name": ""}], "orders": ["a", "a"]}, ["", ""]), ({"customers": [{"id": "x", "name": "Lin"}, {"id": "y", "name": "Mo"}], "orders": ["y", "z", "x"]}, ["Mo", "unknown", "Lin"])],
      ["What does a Go map return for a key it does not contain?", "A missing key yields the element type's zero value, and the zero value of a pointer is nil.", "Use the comma-ok lookup and emit 'unknown' before dereferencing a customer that was not found."], ["go", "nil-pointers", "maps"], "easy", language="go"),
    p("podium-index-bounds", "The podium needs three finishers", "A Go leaderboard always reads three entries after sorting, so a race with fewer finishers panics.",
      "Input.times contains {runner: string, seconds: nonnegative integer} objects. Return the names of up to three runners with the lowest times, fastest first, breaking ties by runner name. Fewer than three finishers return all of them, and no finishers return [].",
      '''
      package main

      import "sort"

      type Finish struct {
          Runner  string
          Seconds int
      }

      func Solve(data map[string]interface{}) interface{} {
          finishes := []Finish{}
          for _, raw := range data["times"].([]interface{}) {
              entry := raw.(map[string]interface{})
              finishes = append(finishes, Finish{entry["runner"].(string), int(entry["seconds"].(float64))})
          }
          sort.Slice(finishes, func(i, j int) bool {
              if finishes[i].Seconds != finishes[j].Seconds {
                  return finishes[i].Seconds < finishes[j].Seconds
              }
              return finishes[i].Runner < finishes[j].Runner
          })
          count := 3
          if len(finishes) < count {
              count = len(finishes)
          }
          podium := []string{}
          for i := 0; i < count; i++ {
              podium = append(podium, finishes[i].Runner)
          }
          return podium
      }
      ''', ('    if len(finishes) < count {\n        count = len(finishes)\n    }\n', ''),
      [({"times": [{"runner": "ana", "seconds": 50}, {"runner": "bo", "seconds": 40}, {"runner": "cy", "seconds": 45}, {"runner": "di", "seconds": 60}]}, ["bo", "cy", "ana"]), ({"times": [{"runner": "ana", "seconds": 50}, {"runner": "bo", "seconds": 40}]}, ["bo", "ana"]), ({"times": []}, []), ({"times": [{"runner": "zed", "seconds": 30}, {"runner": "amy", "seconds": 30}, {"runner": "kim", "seconds": 30}]}, ["amy", "kim", "zed"]), ({"times": [{"runner": "solo", "seconds": 0}]}, ["solo"])],
      ["How many finishers does the podium loop assume exist?", "Indexing past the length of a Go slice panics instead of returning a missing value.", "Clamp the podium size to len(finishes) before reading entries; Go 1.19 has no built-in min, so compare explicitly."], ["go", "slices", "bounds"], "easy", language="go"),
    p("unboxed-missing-stock", "An unknown SKU crashes the stock check", "A Java reservation service reads counts from a Map<String, Integer> into an int, so a request for an unlisted SKU unboxes null.",
      "Input.stock maps SKU strings to nonnegative integer quantities, and input.requests contains {sku: string, quantity: positive integer} objects in arrival order. Accept a request when that SKU's remaining quantity covers it, then deduct it. SKUs are case-sensitive, and unlisted SKUs have zero stock. Return {accepted: booleans, state: {stock: remaining quantity for each originally listed SKU}}.",
      '''
      import com.google.gson.*;
      import java.util.*;
      public class Solution {
        public static JsonElement solve(JsonObject data) {
          Map<String, Integer> stock = new HashMap<>();
          for (Map.Entry<String, JsonElement> entry : data.getAsJsonObject("stock").entrySet())
            stock.put(entry.getKey(), entry.getValue().getAsInt());
          JsonArray accepted = new JsonArray();
          for (JsonElement raw : data.getAsJsonArray("requests")) {
            JsonObject request = raw.getAsJsonObject();
            String sku = request.get("sku").getAsString();
            int quantity = request.get("quantity").getAsInt();
            int available = stock.getOrDefault(sku, 0);
            boolean ok = quantity <= available;
            if (ok) stock.put(sku, available - quantity);
            accepted.add(ok);
          }
          JsonObject remaining = new JsonObject();
          for (String sku : data.getAsJsonObject("stock").keySet()) remaining.addProperty(sku, stock.get(sku));
          JsonObject state = new JsonObject();
          state.add("stock", remaining);
          JsonObject result = new JsonObject();
          result.add("accepted", accepted);
          result.add("state", state);
          return result;
        }
      }
      ''', ('stock.getOrDefault(sku, 0)', 'stock.get(sku)'),
      [({"stock": {"A": 2}, "requests": [{"sku": "A", "quantity": 1}, {"sku": "A", "quantity": 2}]}, {"accepted": [True, False], "state": {"stock": {"A": 1}}}), ({"stock": {"A": 1}, "requests": [{"sku": "B", "quantity": 1}, {"sku": "A", "quantity": 1}]}, {"accepted": [False, True], "state": {"stock": {"A": 0}}}), ({"stock": {}, "requests": []}, {"accepted": [], "state": {"stock": {}}}), ({"stock": {"A": 0, "B": 3}, "requests": [{"sku": "A", "quantity": 1}, {"sku": "B", "quantity": 3}, {"sku": "B", "quantity": 1}]}, {"accepted": [False, True, False], "state": {"stock": {"A": 0, "B": 0}}}), ({"stock": {"X": 5}, "requests": [{"sku": "x", "quantity": 1}, {"sku": "X", "quantity": 5}]}, {"accepted": [False, True], "state": {"stock": {"X": 0}}})],
      ["What does Map.get return for a key that is not present?", "Assigning a null Integer to an int triggers automatic unboxing, which throws NullPointerException.", "Treat an unlisted SKU as zero stock with getOrDefault, or an explicit null check, before comparing and deducting."], ["java", "autoboxing", "null"], "easy", language="java"),
    p("bigdecimal-even-split", "Splitting a bill three ways throws", "A Java bill splitter divides BigDecimal amounts without a rounding rule, which works for even splits but fails when the exact share never terminates.",
      "Input.amount is a nonnegative decimal string with at most seven integer digits and at most two fractional digits, and input.people is an integer from 1 through 20. Return one person's share, amount divided by people and rounded half up to exactly two decimal places, as a plain decimal string such as '3.33'.",
      '''
      import com.google.gson.*;
      import java.math.BigDecimal;
      import java.math.RoundingMode;
      public class Solution {
        public static JsonElement solve(JsonObject data) {
          BigDecimal amount = new BigDecimal(data.get("amount").getAsString());
          BigDecimal people = BigDecimal.valueOf(data.get("people").getAsInt());
          BigDecimal share = amount.divide(people, 2, RoundingMode.HALF_UP);
          return new JsonPrimitive(share.toPlainString());
        }
      }
      ''', ('amount.divide(people, 2, RoundingMode.HALF_UP)', 'amount.divide(people).setScale(2, RoundingMode.HALF_UP)'),
      [({"amount": "10.00", "people": 4}, "2.50"), ({"amount": "10.00", "people": 3}, "3.33"), ({"amount": "2.00", "people": 3}, "0.67"), ({"amount": "1.00", "people": 8}, "0.13"), ({"amount": "0", "people": 7}, "0.00")],
      ["Does every decimal quotient have a finite decimal expansion?", "BigDecimal.divide without a scale or MathContext must produce an exact result, so a repeating quotient such as 10/3 throws ArithmeticException.", "Divide with an explicit scale of two and RoundingMode.HALF_UP, then return toPlainString()."], ["java", "bigdecimal", "money"], language="java"),
    p("circular-tree-serialization", "The org chart points back at itself", "A JavaScript org-chart builder keeps a parent reference on each node to compute depths, then returns the tree with those back-references still attached.",
      "Input.people contains {id: string, manager: string or null} objects with unique IDs. When the list is nonempty, only the first person has a null manager, and every manager appears earlier in the list. Return the tree as nested {id, depth, reports} objects, where the root has depth 0 and reports keep input order. Return null for an empty list.",
      '''
      function solve(data) {
        const nodes = new Map();
        let root = null;
        for (const person of data.people) {
          const node = { id: person.id, depth: 0, reports: [] };
          if (person.manager === null) {
            root = node;
          } else {
            const manager = nodes.get(person.manager);
            node.parent = manager;
            manager.reports.push(node);
          }
          for (let above = node.parent; above; above = above.parent) node.depth += 1;
          nodes.set(person.id, node);
        }
        for (const node of nodes.values()) delete node.parent;
        return root;
      }
      module.exports = { solve };
      ''', ('  for (const node of nodes.values()) delete node.parent;\n', ''),
      [({"people": [{"id": "ceo", "manager": None}]}, {"id": "ceo", "depth": 0, "reports": []}), ({"people": [{"id": "ceo", "manager": None}, {"id": "cto", "manager": "ceo"}]}, {"id": "ceo", "depth": 0, "reports": [{"id": "cto", "depth": 1, "reports": []}]}), ({"people": []}, None), ({"people": [{"id": "a", "manager": None}, {"id": "b", "manager": "a"}, {"id": "c", "manager": "b"}, {"id": "d", "manager": "a"}]}, {"id": "a", "depth": 0, "reports": [{"id": "b", "depth": 1, "reports": [{"id": "c", "depth": 2, "reports": []}]}, {"id": "d", "depth": 1, "reports": []}]}), ({"people": [{"id": "root", "manager": None}, {"id": "x", "manager": "root"}, {"id": "y", "manager": "root"}, {"id": "z", "manager": "root"}]}, {"id": "root", "depth": 0, "reports": [{"id": "x", "depth": 1, "reports": []}, {"id": "y", "depth": 1, "reports": []}, {"id": "z", "depth": 1, "reports": []}]})],
      ["Which references are still attached to each node when the tree is serialized?", "A child's parent reference plus the parent's reports array forms a cycle, and JSON.stringify rejects circular structures.", "Remove the parent back-references before returning, or keep them in a separate Map, so only id, depth, and reports are serialized."], ["javascript", "json", "cycles"], language="javascript"),
    p("unsigned-padding-underflow", "A long label crashes the column formatter", "A C++ report right-aligns labels by subtracting their length from an unsigned column width, so a label wider than the column wraps around to an enormous padding request.",
      "Input.width is an integer from 0 through 40, and input.labels contains ASCII strings. Right-align each label in a field of that width by prefixing spaces. Labels already at least width characters long are returned unchanged. Return the formatted labels in order.",
      '''
      #include <nlohmann/json.hpp>
      #include <string>
      using nlohmann::json;
      json solve(const json& data) {
          std::size_t width = data.at("width").get<std::size_t>();
          json result = json::array();
          for (const auto& raw : data.at("labels")) {
              std::string label = raw.get<std::string>();
              std::size_t padding = label.size() < width ? width - label.size() : 0;
              result.push_back(std::string(padding, ' ') + label);
          }
          return result;
      }
      ''', ('label.size() < width ? width - label.size() : 0', 'width - label.size()'),
      [({"width": 5, "labels": ["ab", "abcde"]}, ["   ab", "abcde"]), ({"width": 3, "labels": ["abcd", "x"]}, ["abcd", "  x"]), ({"width": 0, "labels": [""]}, [""]), ({"width": 2, "labels": []}, []), ({"width": 4, "labels": ["", "toolong", "ok"]}, ["    ", "toolong", "  ok"])],
      ["What happens when an unsigned subtraction would be negative?", "size_t arithmetic wraps around, so width - label.size() becomes a huge length and std::string throws length_error.", "Compare the label length with the width before subtracting, and use no padding for labels that already fill the column."], ["cpp", "unsigned-integers", "strings"], language="cpp"),
    p("unmatched-request-id", "A log line without a request ID crashes the parser", "A log parser calls group() on the result of re.search, but some lines have no request ID and the search returns None.",
      "Input.lines contains ASCII log lines. A request ID is a maximal run of lowercase ASCII letters and digits immediately after 'rid='. Return the first request ID in each line, or null when the line has none. Matching is case-sensitive.",
      '''
      import re
      PATTERN = re.compile(r"rid=([a-z0-9]+)")
      def solve(data):
          result = []
          for line in data["lines"]:
              match = PATTERN.search(line)
              result.append(match.group(1) if match else None)
          return result
      ''', ('match.group(1) if match else None', 'match.group(1)'),
      [({"lines": ["GET /a rid=abc123 200"]}, ["abc123"]), ({"lines": ["healthcheck ok", "POST /b rid=x9 500"]}, [None, "x9"]), ({"lines": []}, []), ({"lines": ["rid= rid=q1", "RID=abc", "rid=Z"]}, ["q1", None, None]), ({"lines": ["rid=a-b", "x rid=007 y rid=8"]}, ["a", "007"])],
      ["What does re.search return when the pattern is absent?", "A failed search returns None, and None has no group method.", "Check the match object before calling group(1), and emit null for lines without an ID."], ["regex", "logging"], "easy"),
    p("sorted-in-place-none", "The ranking is None", "A leaderboard assigns the result of list.sort() to a variable and then slices what it believes is the sorted ranking.",
      "Input.scores contains integers, and input.k is an integer from 0 through 100. Return the k highest scores in descending order, or every score when fewer than k exist. Duplicate scores are retained.",
      '''
      def solve(data):
          ranking = sorted(data["scores"], reverse=True)
          return ranking[:data["k"]]
      ''', ('sorted(data["scores"], reverse=True)', 'data["scores"].sort(reverse=True)'),
      [({"scores": [3, 9, 5], "k": 2}, [9, 5]), ({"scores": [4, 4, 1], "k": 5}, [4, 4, 1]), ({"scores": [], "k": 3}, []), ({"scores": [7, -2, 7], "k": 0}, []), ({"scores": [-5, -1, -3], "k": 2}, [-1, -3])],
      ["What value does list.sort() return?", "In-place list methods such as sort, append, and reverse mutate the list and return None.", "Use sorted(..., reverse=True) to obtain a new list, or call sort first and then slice the list itself."], ["sorting", "return-values"], "easy"),
    p("softmax-exponent-range", "Confident scores crash the probability report", "A classifier report exponentiates raw scores directly, so large but legitimate scores exceed the floating-point range of math.exp.",
      "Input.scores is a nonempty list of at most 20 integers between -1,000 and 1,000. Return {top, probabilities}: top is the index of the first highest score, and probabilities are the softmax values exp(s_i) / sum(exp(s_j)) rounded to six decimal places, in input order. Probabilities that are too small to represent round to 0.0.",
      '''
      import math
      def solve(data):
          scores = data["scores"]
          peak = max(scores)
          weights = [math.exp(score - peak) for score in scores]
          total = sum(weights)
          return {"top": scores.index(peak), "probabilities": [round(weight / total, 6) for weight in weights]}
      ''', ('math.exp(score - peak)', 'math.exp(score)'),
      [({"scores": [0, 0]}, {"top": 0, "probabilities": [0.5, 0.5]}), ({"scores": [1000, 1000]}, {"top": 0, "probabilities": [0.5, 0.5]}), ({"scores": [2, 1]}, {"top": 0, "probabilities": [0.731059, 0.268941]}), ({"scores": [0, 1000]}, {"top": 1, "probabilities": [0.0, 1.0]}), ({"scores": [-1000, -1000, -1000, -1000]}, {"top": 0, "probabilities": [0.25, 0.25, 0.25, 0.25]})],
      ["What is the largest argument math.exp can represent as a float?", "Softmax is unchanged when the same constant is subtracted from every score.", "Subtract the maximum score before exponentiating so the largest weight is exp(0) = 1, then normalize and round."], ["numerical-stability", "floating-point"]),
    p("directory-key-iteration", "The user directory is keyed by ID", "A directory export loops over a mapping of user IDs as if it were a list of user records, so each iteration receives a string key.",
      "Input.users maps user-ID strings to {name: string, active: boolean} records. Return [id, name] pairs for active users, sorted by ID string in ordinary lexicographic order. An empty mapping returns [].",
      '''
      def solve(data):
          rows = []
          for user_id, user in data["users"].items():
              if user["active"]:
                  rows.append([user_id, user["name"]])
          return sorted(rows)
      ''', ('for user_id, user in data["users"].items():\n        if user["active"]:\n            rows.append([user_id, user["name"]])', 'for user in data["users"]:\n        if user["active"]:\n            rows.append([user["id"], user["name"]])'),
      [({"users": {}}, []), ({"users": {"u2": {"name": "Bo", "active": True}, "u1": {"name": "Al", "active": True}}}, [["u1", "Al"], ["u2", "Bo"]]), ({"users": {"u1": {"name": "Al", "active": False}}}, []), ({"users": {"b": {"name": "", "active": True}, "a": {"name": "Ann", "active": False}, "c": {"name": "Cy", "active": True}}}, [["b", ""], ["c", "Cy"]]), ({"users": {"10": {"name": "Ten", "active": True}, "9": {"name": "Nine", "active": True}}}, [["10", "Ten"], ["9", "Nine"]])],
      ["What does a for loop over a dictionary produce?", "Iterating a dict yields its keys, and indexing a string key with 'active' raises TypeError.", "Iterate over users.items() to receive each ID with its record, then filter active users and sort the pairs by ID."], ["dictionaries", "iteration"], "easy"),
]
