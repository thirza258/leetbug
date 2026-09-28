"""Ten crash diagnoses: library contracts, API boundaries, and language-specific failures."""
from functools import partial

from ..common import make

p = partial(make, "runtime")

PROBLEMS = [
    p("null-c-string-setting", "A missing legacy setting crashes the C++ loader", "A C++ settings loader wraps a C-style lookup that returns nullptr for unknown keys, then constructs a std::string from that pointer without checking it.",
      "Input.settings contains [key, value] string pairs with unique keys, input.keys contains requested keys, and input.fallback is a string. The provided lookup returns a C string for a known key and nullptr otherwise. Return each requested key's value, or fallback when the key is unknown. Keys are case-sensitive, and empty values are valid values.",
      '''
      #include <nlohmann/json.hpp>
      #include <string>
      #include <utility>
      #include <vector>
      using nlohmann::json;

      const char* lookup(const std::vector<std::pair<std::string, std::string>>& table, const std::string& key) {
          for (const auto& entry : table) {
              if (entry.first == key) return entry.second.c_str();
          }
          return nullptr;
      }

      json solve(const json& data) {
          std::vector<std::pair<std::string, std::string>> table;
          for (const auto& setting : data.at("settings")) {
              table.emplace_back(setting.at(0).get<std::string>(), setting.at(1).get<std::string>());
          }
          std::string fallback = data.at("fallback").get<std::string>();
          json result = json::array();
          for (const auto& key : data.at("keys")) {
              const char* raw = lookup(table, key.get<std::string>());
              std::string value = raw != nullptr ? std::string(raw) : fallback;
              result.push_back(value);
          }
          return result;
      }
      ''', ('std::string value = raw != nullptr ? std::string(raw) : fallback;', 'std::string value = raw;'),
      [({"settings": [["theme", "dark"]], "keys": ["theme"], "fallback": ""}, ["dark"]), ({"settings": [["theme", "dark"]], "keys": ["locale", "theme"], "fallback": "en"}, ["en", "dark"]), ({"settings": [], "keys": [], "fallback": "x"}, []), ({"settings": [["a", ""], ["b", "2"]], "keys": ["a", "b", "c"], "fallback": "?"}, ["", "2", "?"]), ({"settings": [["Key", "v"]], "keys": ["key"], "fallback": "none"}, ["none"])],
      ["What does lookup return for a key that is not in the table?", "Constructing std::string from a null const char* is invalid, and libstdc++ throws std::logic_error instead of producing an empty string.", "Check the pointer before converting it, and use the fallback when lookup returns nullptr."], ["cpp", "null-pointers", "strings"], "easy", language="cpp"),
    p("tomap-duplicate-key", "A repeated email crashes the user index", "A Java service indexes users by email with Collectors.toMap, which throws as soon as two records share a key.",
      "Input.users contains {email: string, name: string} records in update order. The same email can appear more than once, and a later record replaces an earlier one. Emails are compared exactly. Return an object mapping each email to the name from its latest record.",
      '''
      import com.google.gson.*;
      import java.util.*;
      import java.util.stream.*;
      public class Solution {
        public static JsonElement solve(JsonObject data) {
          List<JsonObject> users = new ArrayList<>();
          for (JsonElement raw : data.getAsJsonArray("users")) users.add(raw.getAsJsonObject());
          Map<String, String> byEmail = users.stream().collect(Collectors.toMap(
              user -> user.get("email").getAsString(),
              user -> user.get("name").getAsString(),
              (earlier, later) -> later));
          JsonObject result = new JsonObject();
          for (Map.Entry<String, String> entry : byEmail.entrySet()) result.addProperty(entry.getKey(), entry.getValue());
          return result;
        }
      }
      ''', ('        user -> user.get("name").getAsString(),\n        (earlier, later) -> later));', '        user -> user.get("name").getAsString()));'),
      [({"users": [{"email": "a@x", "name": "Ann"}]}, {"a@x": "Ann"}), ({"users": [{"email": "a@x", "name": "Ann"}, {"email": "b@x", "name": "Bo"}, {"email": "a@x", "name": "Anna"}]}, {"a@x": "Anna", "b@x": "Bo"}), ({"users": []}, {}), ({"users": [{"email": "A@x", "name": "Up"}, {"email": "a@x", "name": "Low"}]}, {"A@x": "Up", "a@x": "Low"}), ({"users": [{"email": "e", "name": "1"}, {"email": "e", "name": "2"}, {"email": "e", "name": "3"}]}, {"e": "3"})],
      ["What does Collectors.toMap do when two elements produce the same key?", "Without a merge function, toMap throws IllegalStateException at the first duplicate key.", "Pass a merge function such as (earlier, later) -> later so the latest record wins."], ["java", "streams", "collections"], "easy", language="java"),
    p("gson-double-cast", "Gson turns every count into a Double", "A Java report deserializes settings into a Map<String, Object> with Gson and casts numeric values to Integer, but Gson represents untyped JSON numbers as Double.",
      "Input.settings is an object whose values are integers or strings. Return {total: the sum of the integer values, keys: the keys that hold integers, in ascending order}. String values are ignored.",
      '''
      import com.google.gson.*;
      import java.util.*;
      public class Solution {
        @SuppressWarnings("unchecked")
        public static JsonElement solve(JsonObject data) {
          Map<String, Object> settings = new Gson().fromJson(data.get("settings"), Map.class);
          long total = 0;
          List<String> keys = new ArrayList<>();
          for (Map.Entry<String, Object> entry : settings.entrySet()) {
            if (entry.getValue() instanceof Number) {
              total += ((Number) entry.getValue()).longValue();
              keys.add(entry.getKey());
            }
          }
          Collections.sort(keys);
          JsonObject result = new JsonObject();
          result.addProperty("total", total);
          result.add("keys", new Gson().toJsonTree(keys));
          return result;
        }
      }
      ''', ('((Number) entry.getValue()).longValue()', '(Integer) entry.getValue()'),
      [({"settings": {"name": "svc"}}, {"total": 0, "keys": []}), ({"settings": {"retries": 3, "name": "api", "timeout": 30}}, {"total": 33, "keys": ["retries", "timeout"]}), ({"settings": {}}, {"total": 0, "keys": []}), ({"settings": {"b": -5, "a": 5, "c": "5"}}, {"total": 0, "keys": ["a", "b"]}), ({"settings": {"x": 1000000, "y": 1000000}}, {"total": 2000000, "keys": ["x", "y"]})],
      ["Which Java type does Gson create for a JSON number when the target type is Object?", "Untyped Gson deserialization stores every number as a Double, so casting it to Integer throws ClassCastException.", "Treat the value as a Number and call longValue(), or read the JsonObject with getAsLong, instead of casting to Integer."], ["java", "gson", "casting"], language="java"),
    p("bigint-number-mixing", "A quantity multiplier crashes the exact invoice", "A JavaScript invoice keeps prices as BigInt for exactness, but multiplies them by quantities that are still ordinary Numbers.",
      "Input.lines contains {price: decimal string of a nonnegative integer amount in minor units, at most 25 digits, leading zeros allowed; quantity: integer from 0 through 1,000}. Return the exact invoice total, the sum of price × quantity, as a decimal string without leading zeros ('0' for zero).",
      '''
      function solve(data) {
        let total = 0n;
        for (const line of data.lines) {
          total += BigInt(line.price) * BigInt(line.quantity);
        }
        return total.toString();
      }
      module.exports = { solve };
      ''', ('BigInt(line.price) * BigInt(line.quantity)', 'BigInt(line.price) * line.quantity'),
      [({"lines": []}, "0"), ({"lines": [{"price": "1999", "quantity": 3}]}, "5997"), ({"lines": [{"price": "9007199254740993", "quantity": 1}]}, "9007199254740993"), ({"lines": [{"price": "123456789012345678901234", "quantity": 1000}, {"price": "1", "quantity": 0}]}, "123456789012345678901234000"), ({"lines": [{"price": "0050", "quantity": 2}, {"price": "25", "quantity": 4}]}, "200")],
      ["Which types appear on each side of the multiplication?", "JavaScript never converts implicitly between BigInt and Number, so mixing them in arithmetic throws TypeError.", "Convert the quantity with BigInt(line.quantity) before multiplying, and return the total with toString()."], ["javascript", "bigint", "money"], "easy", language="javascript"),
    p("const-running-total", "The running balance is declared constant", "A JavaScript statement builder declares its running balance with const, so the first transaction that tries to update it throws at runtime.",
      "Input.opening is an integer balance in cents, and input.changes contains integer amounts applied in order. Return the balance after each change. An empty change list returns [].",
      '''
      function solve(data) {
        let balance = data.opening;
        const history = [];
        for (const change of data.changes) {
          balance += change;
          history.push(balance);
        }
        return history;
      }
      module.exports = { solve };
      ''', ('let balance = data.opening;', 'const balance = data.opening;'),
      [({"opening": 100, "changes": []}, []), ({"opening": 100, "changes": [-30, 5]}, [70, 75]), ({"opening": 0, "changes": [0]}, [0]), ({"opening": -50, "changes": [25, 25, -1]}, [-25, 0, -1]), ({"opening": 1000000, "changes": [1000000]}, [2000000])],
      ["Which binding does the loop reassign?", "const prevents reassigning the binding itself; pushing into the const history array is fine, but balance += change is not.", "Declare balance with let, and keep const for bindings that are never reassigned."], ["javascript", "const", "scope"], "easy", language="javascript"),
    p("unbuffered-channel-deadlock", "The result channel has no room", "A Go pipeline sends results into an unbuffered channel from the same goroutine that later reads them, so the first send blocks forever.",
      "Input.values contains integers. Return each value multiplied by three, in input order, collected through the pipeline's results channel. An empty input returns [].",
      '''
      package main

      func Solve(data map[string]interface{}) interface{} {
          values := data["values"].([]interface{})
          results := make(chan int, len(values))
          for _, raw := range values {
              results <- 3 * int(raw.(float64))
          }
          close(results)
          output := []int{}
          for value := range results {
              output = append(output, value)
          }
          return output
      }
      ''', ('make(chan int, len(values))', 'make(chan int)'),
      [({"values": []}, []), ({"values": [1, 2]}, [3, 6]), ({"values": [0]}, [0]), ({"values": [-4, 5, -6]}, [-12, 15, -18]), ({"values": [333333]}, [999999])],
      ["Who is ready to receive when the loop sends its first result?", "A send on an unbuffered channel blocks until another goroutine receives, and here the only receiver runs after all the sends, so the runtime reports a deadlock.", "Give the channel room for every result, or send from a separate goroutine, before closing and draining it."], ["go", "channels", "concurrency"], language="go"),
    p("trailing-slash-empty-path", "Removing a trailing slash panics on an empty path", "A Go router normalizes paths by inspecting the last byte before checking the length, so an empty path indexes position -1.",
      "Input.paths contains ASCII strings. Remove exactly one trailing '/' from each path longer than one character; the root path '/' and the empty string are returned unchanged. Return the normalized paths in order.",
      '''
      package main

      func Solve(data map[string]interface{}) interface{} {
          result := []string{}
          for _, raw := range data["paths"].([]interface{}) {
              path := raw.(string)
              if len(path) > 1 && path[len(path)-1] == '/' {
                  path = path[:len(path)-1]
              }
              result = append(result, path)
          }
          return result
      }
      ''', ("len(path) > 1 && path[len(path)-1] == '/'", "path[len(path)-1] == '/' && len(path) > 1"),
      [({"paths": ["/users/", "/about"]}, ["/users", "/about"]), ({"paths": ["", "/docs/"]}, ["", "/docs"]), ({"paths": ["/"]}, ["/"]), ({"paths": ["//", "a/", "a//"]}, ["/", "a", "a/"]), ({"paths": []}, [])],
      ["Which index does path[len(path)-1] read when the path is empty?", "Go evaluates && from left to right, so the length guard must run before the index expression.", "Check len(path) > 1 first, then inspect the last byte and trim one slash."], ["go", "strings", "short-circuit"], "easy", language="go"),
    p("set-json-response", "Unique tags cannot be serialized", "An article service deduplicates tags into a set and returns it directly, but JSON has no set type, so serializing the response fails.",
      "Input.articles contains objects with a tags list of strings. Return the distinct tags across all articles in ascending code-point order. No articles, or no tags, return [].",
      '''
      def solve(data):
          tags = set()
          for article in data["articles"]:
              tags.update(article["tags"])
          return sorted(tags)
      ''', ('return sorted(tags)', 'return tags'),
      [({"articles": [{"tags": ["go", "api"]}]}, ["api", "go"]), ({"articles": [{"tags": ["b", "a"]}, {"tags": ["a", "c"]}]}, ["a", "b", "c"]), ({"articles": []}, []), ({"articles": [{"tags": []}, {"tags": ["Z", "a"]}]}, ["Z", "a"]), ({"articles": [{"tags": ["x", "x"]}]}, ["x"])],
      ["Which Python types can json.dumps encode?", "JSON has arrays but no sets, so returning a set makes serialization raise TypeError.", "Convert the set to a list in the required order, for example sorted(tags), before returning it."], ["json", "sets", "serialization"], "easy"),
    p("accented-slug-encoding", "An accented title crashes the slug generator", "A slug generator decomposes accented letters but then encodes the text as strict ASCII, so any remaining combining mark raises UnicodeEncodeError.",
      "Input.titles contains Unicode strings. Build each slug by applying NFKD normalization, dropping every character that is not ASCII, lowercasing, replacing each run of characters other than a-z and 0-9 with one hyphen, and trimming hyphens from both ends. Return the slugs in order.",
      '''
      import re
      import unicodedata
      def solve(data):
          slugs = []
          for title in data["titles"]:
              ascii_text = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
              slugs.append(re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-"))
          return slugs
      ''', ('.encode("ascii", "ignore")', '.encode("ascii")'),
      [({"titles": ["Hello World"]}, ["hello-world"]), ({"titles": ["Café Déjà Vu"]}, ["cafe-deja-vu"]), ({"titles": ["  --Rock & Roll--  "]}, ["rock-roll"]), ({"titles": ["ﬁnal Ω"]}, ["final"]), ({"titles": ["", "Ünïcödé 2026"]}, ["", "unicode-2026"])],
      ["What happens to combining accent marks when text is encoded as strict ASCII?", "NFKD splits é into e plus a combining accent, and that accent is still non-ASCII, so encode('ascii') raises UnicodeEncodeError.", "Encode with errors='ignore', or filter to ASCII characters, after normalizing, then build the slug."], ["unicode", "encoding", "slugs"]),
    p("naive-aware-duration", "A session with an offset crashes the duration report", "A session report subtracts parsed timestamps, but some carry a UTC offset and others do not, and Python refuses to mix naive and aware datetimes.",
      "Input.sessions contains {start, end} ISO 8601 timestamps formatted YYYY-MM-DDTHH:MM:SS, optionally followed by 'Z' or an offset ±HH:MM; a timestamp without an offset is in UTC. Every end is at or after its start. Return each session's duration in whole seconds.",
      '''
      import datetime as dt
      def parse(text):
          moment = dt.datetime.fromisoformat(text)
          return moment if moment.tzinfo is not None else moment.replace(tzinfo=dt.timezone.utc)

      def solve(data):
          return [int((parse(s["end"]) - parse(s["start"])).total_seconds()) for s in data["sessions"]]
      ''', ('moment if moment.tzinfo is not None else moment.replace(tzinfo=dt.timezone.utc)', 'moment'),
      [({"sessions": [{"start": "2026-09-28T10:00:00", "end": "2026-09-28T10:30:00"}]}, [1800]), ({"sessions": [{"start": "2026-09-28T10:00:00", "end": "2026-09-28T12:15:00+02:00"}]}, [900]), ({"sessions": []}, []), ({"sessions": [{"start": "2026-09-28T23:50:00Z", "end": "2026-09-29T00:10:00Z"}]}, [1200]), ({"sessions": [{"start": "2026-09-28T08:00:00-05:00", "end": "2026-09-28T13:00:01"}]}, [1]), ({"sessions": [{"start": "2026-03-01T00:00:00+14:00", "end": "2026-03-01T00:00:00-12:00"}]}, [93600])],
      ["Do both timestamps in each subtraction carry timezone information?", "fromisoformat returns an aware datetime when an offset or Z is present and a naive one otherwise, and aware and naive values cannot be subtracted.", "Attach UTC to naive timestamps with replace(tzinfo=timezone.utc) before computing the difference."], ["datetime", "time-zones"]),
]
