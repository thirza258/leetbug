"""Ten wrong-answer repairs: comparator contracts, iteration semantics, and algorithm invariants."""
from functools import partial

from ..common import make

p = partial(make, "logic")

PROBLEMS = [
    p("boolean-sort-comparator", "A true-or-false comparator leaves the list unsorted", "A JavaScript leaderboard sorts with a comparator that returns a > b, but Array.prototype.sort expects a negative, zero, or positive number rather than a boolean.",
      "Input.scores contains integers. Return them sorted in ascending numeric order, retaining duplicates.",
      '''
      function solve(data) {
        return [...data.scores].sort((a, b) => a - b);
      }
      module.exports = { solve };
      ''', ('(a, b) => a - b', '(a, b) => a > b'),
      [({"scores": [1, 2, 3]}, [1, 2, 3]), ({"scores": [3, 1, 2]}, [1, 2, 3]), ({"scores": []}, []), ({"scores": [5, -1, 5, 0]}, [-1, 0, 5, 5]), ({"scores": [10, 9, 2]}, [2, 9, 10])],
      ["What values does Array.prototype.sort expect a comparator to return?", "A boolean comparator never returns a negative number, so sort never learns that a later element belongs earlier and can leave the input unchanged.", "Return a numeric difference such as a - b so smaller values sort first."], ["javascript", "sorting", "comparators"], "easy", language="javascript"),
    p("for-in-string-index", "Item numbers come out as 01, 11, and 21", "A JavaScript checklist numbers its items inside a for...in loop, whose keys are strings, so adding one concatenates instead of adding.",
      "Input.items contains strings. Return one label per item, numbered from 1 in order, in the form '1. first', '2. second', and so on.",
      '''
      function solve(data) {
        const labels = [];
        for (const [index, item] of data.items.entries()) {
          labels.push(`${index + 1}. ${item}`);
        }
        return labels;
      }
      module.exports = { solve };
      ''', ('for (const [index, item] of data.items.entries()) {', 'for (const index in data.items) {\n    const item = data.items[index];'),
      [({"items": []}, []), ({"items": ["milk", "eggs"]}, ["1. milk", "2. eggs"]), ({"items": ["x"]}, ["1. x"]), ({"items": ["a", "b", "c"]}, ["1. a", "2. b", "3. c"]), ({"items": ["", " "]}, ["1. ", "2.  "])],
      ["What type are the keys produced by for...in?", "for...in enumerates property names as strings, so index + 1 concatenates '0' and 1 into '01'.", "Iterate with entries() or a counting loop, or convert the key with Number(index), so the label uses numeric addition."], ["javascript", "iteration", "coercion"], "easy", language="javascript"),
    p("char-shift-append", "The cipher prints numbers instead of letters", "A Java Caesar-cipher helper appends 'a' + offset to a StringBuilder, and char arithmetic produces an int, so the output contains character codes.",
      "Input.text contains lowercase ASCII letters and spaces, and input.shift is an integer from 0 through 25. Shift each letter forward by shift positions, wrapping from z to a, and keep spaces unchanged. Return the encoded string.",
      '''
      import com.google.gson.*;
      public class Solution {
        public static JsonElement solve(JsonObject data) {
          String text = data.get("text").getAsString();
          int shift = data.get("shift").getAsInt();
          StringBuilder encoded = new StringBuilder();
          for (char c : text.toCharArray()) {
            if (c == ' ') encoded.append(c);
            else encoded.append((char) ('a' + (c - 'a' + shift) % 26));
          }
          return new JsonPrimitive(encoded.toString());
        }
      }
      ''', ("encoded.append((char) ('a' + (c - 'a' + shift) % 26))", "encoded.append('a' + (c - 'a' + shift) % 26)"),
      [({"text": "", "shift": 3}, ""), ({"text": "abc", "shift": 1}, "bcd"), ({"text": "xyz", "shift": 3}, "abc"), ({"text": "hello world", "shift": 0}, "hello world"), ({"text": "a z", "shift": 25}, "z y")],
      ["What type is the expression 'a' + offset in Java?", "Adding an int to a char promotes the result to int, and StringBuilder.append(int) appends its decimal digits.", "Cast the shifted code back to char before appending it."], ["java", "char-arithmetic", "strings"], "easy", language="java"),
    p("equals-without-hashcode", "Equal points both stay in the set", "A Java map-tile deduplicator stores Point objects in a HashSet, but Point overrides equals without hashCode, so equal points land in different buckets.",
      "Input.points contains [x, y] integer pairs. Return the distinct points as [x, y] pairs in first-seen order.",
      '''
      import com.google.gson.*;
      import java.util.*;
      public class Solution {
        static final class Point {
          final int x, y;
          Point(int x, int y) { this.x = x; this.y = y; }
          @Override public boolean equals(Object other) {
            return other instanceof Point && ((Point) other).x == x && ((Point) other).y == y;
          }
          @Override public int hashCode() { return Objects.hash(x, y); }
        }

        public static JsonElement solve(JsonObject data) {
          Set<Point> seen = new LinkedHashSet<>();
          for (JsonElement raw : data.getAsJsonArray("points")) {
            JsonArray pair = raw.getAsJsonArray();
            seen.add(new Point(pair.get(0).getAsInt(), pair.get(1).getAsInt()));
          }
          JsonArray result = new JsonArray();
          for (Point point : seen) {
            JsonArray pair = new JsonArray();
            pair.add(point.x);
            pair.add(point.y);
            result.add(pair);
          }
          return result;
        }
      }
      ''', ('    @Override public int hashCode() { return Objects.hash(x, y); }\n', ''),
      [({"points": [[1, 2], [3, 4]]}, [[1, 2], [3, 4]]), ({"points": [[1, 2], [1, 2]]}, [[1, 2]]), ({"points": []}, []), ({"points": [[0, 0], [2, 1], [0, 0], [1, 2], [2, 1]]}, [[0, 0], [2, 1], [1, 2]]), ({"points": [[-1, 5], [5, -1], [-1, 5]]}, [[-1, 5], [5, -1]])],
      ["Which method does a HashSet consult before it ever calls equals?", "Equal objects must have equal hash codes; without hashCode, each Point keeps its identity hash and lands in its own bucket.", "Override hashCode consistently with equals, for example with Objects.hash(x, y)."], ["java", "hashing", "equality"], language="java"),
    p("trimleft-cutset-prefix", "Trimming the scheme eats the hostname", "A Go link normalizer removes 'https://' with strings.TrimLeft, which treats its argument as a set of characters rather than a prefix.",
      "Input.urls contains ASCII strings. Remove one leading 'https://' when present and leave every other string unchanged. Return the results in order.",
      '''
      package main

      import "strings"

      func Solve(data map[string]interface{}) interface{} {
          result := []string{}
          for _, raw := range data["urls"].([]interface{}) {
              result = append(result, strings.TrimPrefix(raw.(string), "https://"))
          }
          return result
      }
      ''', ('strings.TrimPrefix(raw.(string), "https://")', 'strings.TrimLeft(raw.(string), "https://")'),
      [({"urls": ["https://example.com"]}, ["example.com"]), ({"urls": ["https://shop.example", "https://tips.dev"]}, ["shop.example", "tips.dev"]), ({"urls": ["http://site.io"]}, ["http://site.io"]), ({"urls": ["https://https://x", "", "ftp://a"]}, ["https://x", "", "ftp://a"]), ({"urls": ["pathways/https://"]}, ["pathways/https://"])],
      ["Does strings.TrimLeft remove a prefix string or a set of characters?", "TrimLeft keeps removing leading bytes while each one appears anywhere in the cutset, so it also strips the s and h of 'shop'.", "Use strings.TrimPrefix to remove exactly one occurrence of the literal prefix."], ["go", "strings"], "easy", language="go"),
    p("remove-without-erase", "Removed tags reappear at the end", "A C++ tag filter calls std::remove but never erases the leftover tail, so the vector keeps its old size and ends with stale elements.",
      "Input.tags contains strings and input.blocked is a string. Return the tags with every occurrence of blocked removed, preserving the order of the remaining tags.",
      '''
      #include <nlohmann/json.hpp>
      #include <algorithm>
      #include <string>
      #include <vector>
      using nlohmann::json;
      json solve(const json& data) {
          std::vector<std::string> tags = data.at("tags").get<std::vector<std::string>>();
          std::string blocked = data.at("blocked").get<std::string>();
          tags.erase(std::remove(tags.begin(), tags.end(), blocked), tags.end());
          return tags;
      }
      ''', ('tags.erase(std::remove(tags.begin(), tags.end(), blocked), tags.end());', 'std::remove(tags.begin(), tags.end(), blocked);'),
      [({"tags": ["go", "api"], "blocked": "spam"}, ["go", "api"]), ({"tags": ["a", "spam", "b"], "blocked": "spam"}, ["a", "b"]), ({"tags": [], "blocked": "x"}, []), ({"tags": ["x", "x", "x"], "blocked": "x"}, []), ({"tags": ["x", "y", "x", "z", "x"], "blocked": "x"}, ["y", "z"])],
      ["Does std::remove change the size of the container?", "std::remove only shifts the kept elements to the front and returns the new logical end; the elements after it are still in the vector.", "Pass the returned iterator to erase, the erase-remove idiom, so the tail is actually removed."], ["cpp", "algorithms", "containers"], "easy", language="cpp"),
    p("exhausted-generator-pass", "The second pass over the readings finds nothing", "A normalization job parses readings with a generator expression, computes their mean in one pass, and then iterates the already exhausted generator for the deviations.",
      "Input.readings contains decimal integer strings. Parse them, compute their mean, and return each reading's deviation from the mean (reading - mean) rounded to two decimal places, in input order. An empty list returns [].",
      '''
      def solve(data):
          count = len(data["readings"])
          if count == 0:
              return []
          values = [int(text) for text in data["readings"]]
          mean = sum(values) / count
          return [round(value - mean, 2) for value in values]
      ''', ('values = [int(text) for text in data["readings"]]', 'values = (int(text) for text in data["readings"])'),
      [({"readings": []}, []), ({"readings": ["1", "2", "3"]}, [-1.0, 0.0, 1.0]), ({"readings": ["5"]}, [0.0]), ({"readings": ["10", "-10", "3"]}, [9.0, -11.0, 2.0]), ({"readings": ["1", "2"]}, [-0.5, 0.5]), ({"readings": ["0", "0", "1"]}, [-0.33, -0.33, 0.67])],
      ["Can a generator expression be iterated more than once?", "sum() consumes every value from the generator, so the later comprehension sees an exhausted iterator and produces nothing.", "Materialize the parsed readings in a list before making two passes over them."], ["iterators", "generators"]),
    p("trie-prefix-membership", "A prefix is reported as a registered word", "A username registry stores names in a trie, but its lookup succeeds whenever the path exists, so any prefix of a registered name counts as registered.",
      "Input.words contains registered names and input.queries contains names to check; both use only lowercase ASCII letters. For each query, return whether it exactly matches a registered name. The empty string is registered only if it appears in words.",
      '''
      END = "$"
      def solve(data):
          root = {}
          for word in data["words"]:
              node = root
              for char in word:
                  node = node.setdefault(char, {})
              node[END] = True
          result = []
          for query in data["queries"]:
              node = root
              for char in query:
                  node = node.get(char)
                  if node is None:
                      break
              result.append(node is not None and END in node)
          return result
      ''', ('node is not None and END in node', 'node is not None'),
      [({"words": ["car"], "queries": ["car", "cat"]}, [True, False]), ({"words": ["card"], "queries": ["car", "card"]}, [False, True]), ({"words": [], "queries": [""]}, [False]), ({"words": ["", "a"], "queries": ["", "ab", "a"]}, [True, False, True]), ({"words": ["team", "tea"], "queries": ["te", "tea", "team", "teams"]}, [False, True, True, False])],
      ["Does reaching the end of a query's path prove the query itself was inserted?", "Every prefix of a stored word also has a path in the trie; only an end-of-word marker distinguishes complete words.", "Return true only when the final node exists and carries the end marker."], ["tries", "strings", "data-structures"], "easy"),
    p("kruskal-cycle-edge", "The cheapest network pays for a redundant cable", "A network planner builds a minimum spanning tree from the cheapest edges, but it adds edges without checking whether their endpoints are already connected.",
      "Input.nodes is a positive integer n for nodes 0 through n - 1, and input.edges contains [u, v, cost] undirected edges with nonnegative integer costs; self-loops and parallel edges may appear. Build a minimum spanning forest with Kruskal's algorithm: consider edges in (cost, u, v) order and take an edge only when it joins two different components. Return {cost: total cost of the chosen edges, edges: the chosen [u, v, cost] edges in the order taken}.",
      '''
      def solve(data):
          parent = list(range(data["nodes"]))
          def find(node):
              while parent[node] != node:
                  parent[node] = parent[parent[node]]
                  node = parent[node]
              return node
          chosen, total = [], 0
          for u, v, cost in sorted(data["edges"], key=lambda edge: (edge[2], edge[0], edge[1])):
              root_u, root_v = find(u), find(v)
              if root_u == root_v:
                  continue
              parent[root_u] = root_v
              chosen.append([u, v, cost])
              total += cost
          return {"cost": total, "edges": chosen}
      ''', ('        if root_u == root_v:\n            continue\n', ''),
      [({"nodes": 2, "edges": [[0, 1, 5]]}, {"cost": 5, "edges": [[0, 1, 5]]}), ({"nodes": 3, "edges": [[0, 1, 1], [1, 2, 2], [0, 2, 3]]}, {"cost": 3, "edges": [[0, 1, 1], [1, 2, 2]]}), ({"nodes": 1, "edges": []}, {"cost": 0, "edges": []}), ({"nodes": 4, "edges": [[2, 3, 4], [0, 1, 4], [1, 2, 1], [0, 3, 9]]}, {"cost": 9, "edges": [[1, 2, 1], [0, 1, 4], [2, 3, 4]]}), ({"nodes": 4, "edges": [[0, 1, 2], [2, 3, 2], [1, 0, 1]]}, {"cost": 3, "edges": [[1, 0, 1], [2, 3, 2]]}), ({"nodes": 2, "edges": [[0, 0, 0], [0, 1, 7]]}, {"cost": 7, "edges": [[0, 1, 7]]})],
      ["When should Kruskal's algorithm reject a cheap edge?", "An edge whose endpoints already share a component would close a cycle, so it can never belong to a spanning tree.", "Compare the endpoints' union-find roots and skip the edge when they are equal; union components only for edges you take."], ["graphs", "minimum-spanning-tree", "union-find"]),
    p("run-length-multidigit", "Twelve copies decode as two", "A run-length decoder keeps only the most recent digit of each count, so counts of ten or more lose their leading digits.",
      "Input.encoded is a run-length string made of groups, each a positive decimal count without leading zeros followed by one lowercase ASCII letter. Return the decoded string, whose length is at most 1,000 characters.",
      '''
      def solve(data):
          output, count = [], ""
          for char in data["encoded"]:
              if char.isdigit():
                  count += char
              else:
                  output.append(char * int(count))
                  count = ""
          return "".join(output)
      ''', ('count += char', 'count = char'),
      [({"encoded": "3a2b"}, "aaabb"), ({"encoded": "12x"}, "x" * 12), ({"encoded": ""}, ""), ({"encoded": "1a10b1c"}, "a" + "b" * 10 + "c"), ({"encoded": "100z"}, "z" * 100)],
      ["How many digits can a run count have?", "Each new digit must extend the pending count; overwriting it keeps only the last digit of 10, 12, or 100.", "Append digits to the pending count until a letter arrives, then repeat the letter and reset the count."], ["parsing", "strings", "compression"], "easy"),
]
