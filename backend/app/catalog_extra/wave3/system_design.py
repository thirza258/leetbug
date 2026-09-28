"""Thirteen executable models of limiting, probabilistic structures, streaming, and failover."""
from functools import partial

from ..common import make

p = partial(make, "system_design")

PROBLEMS = [
    p("sliding-window-counter", "The sliding window forgets the previous window", "A rate limiter meant to use the sliding-window-counter approximation counts only the current fixed window, so bursts straddling a window boundary double the allowed rate.",
      "Input.window is a positive integer, input.limit is a nonnegative integer, and input.times contains nondecreasing nonnegative integer request times. For a request at time t, let w = floor(t / window), current = accepted requests in window w, previous = accepted requests in window w - 1, and elapsed = t - w * window. Accept the request when previous * (window - elapsed) + current * window < limit * window, then count it in window w. Return the acceptance booleans.",
      '''
      def solve(data):
          window, accepted, counts = data["window"], [], {}
          for t in data["times"]:
              w = t // window
              weighted = counts.get(w - 1, 0) * (window - (t - w * window)) + counts.get(w, 0) * window
              ok = weighted < data["limit"] * window
              accepted.append(ok)
              if ok:
                  counts[w] = counts.get(w, 0) + 1
          return accepted
      ''', ('counts.get(w - 1, 0) * (window - (t - w * window)) + counts.get(w, 0) * window', 'counts.get(w, 0) * window'),
      [({"window": 10, "limit": 2, "times": [0, 1, 2]}, [True, True, False]), ({"window": 10, "limit": 2, "times": [8, 9, 10, 11]}, [True, True, False, True]), ({"window": 10, "limit": 2, "times": []}, []), ({"window": 10, "limit": 1, "times": [5, 15, 19, 25]}, [True, True, False, True]), ({"window": 5, "limit": 0, "times": [0, 100]}, [False, False]), ({"window": 4, "limit": 3, "times": [3, 3, 3, 4, 5, 7]}, [True, True, True, False, True, True])],
      ["How much of the previous window still overlaps the sliding interval that ends now?", "The sliding-window counter weights the previous window's count by the fraction of that window still inside the last window length.", "Add previous * (window - elapsed) to current * window and compare the weighted total with limit * window."], ["rate-limiting", "sliding-window"], "hard"),
    p("count-min-query-minimum", "The sketch reports its worst overestimate", "A heavy-hitter service queries a count-min sketch with the largest counter across its rows, although collisions only inflate counters and the smallest row counter is the estimate.",
      "Input.width is a positive integer, and input.hashes maps each key to a nonempty list of column indexes, one per row, each from 0 through width - 1; every key has the same number of rows. Input.adds lists keys to add once each, and input.queries lists keys to estimate; all of them appear in hashes. Each add increments the key's column in every row. Return each query's estimate: the minimum of its counters across rows.",
      '''
      def solve(data):
          rows = len(next(iter(data["hashes"].values()), []))
          table = [[0] * data["width"] for _ in range(rows)]
          for key in data["adds"]:
              for row, column in enumerate(data["hashes"][key]):
                  table[row][column] += 1
          return [min(table[row][column] for row, column in enumerate(data["hashes"][key])) for key in data["queries"]]
      ''', ('min(table[row][column]', 'max(table[row][column]'),
      [({"width": 4, "hashes": {"a": [0, 1]}, "adds": ["a", "a"], "queries": ["a"]}, [2]), ({"width": 2, "hashes": {"a": [0, 0], "b": [0, 1]}, "adds": ["a", "b", "b"], "queries": ["a", "b"]}, [1, 2]), ({"width": 3, "hashes": {"x": [2]}, "adds": [], "queries": ["x"]}, [0]), ({"width": 3, "hashes": {"p": [0, 1, 2], "q": [0, 2, 1], "r": [1, 1, 1]}, "adds": ["p", "q", "r", "r"], "queries": ["p", "q", "r"]}, [1, 1, 2]), ({"width": 1, "hashes": {"k": [0]}, "adds": ["k"], "queries": []}, [])],
      ["Can a hash collision ever make a count-min counter smaller than the true count?", "Collisions only add other keys' increments, so every row overestimates and the smallest row gives the tightest estimate.", "Estimate each query with the minimum of its counters across rows."], ["probabilistic-data-structures", "streaming"], "easy"),
    p("bloom-filter-all-bits", "The Bloom filter claims keys it never saw", "A Bloom-filter cache guard reports a key as present when any one of its bits is set, although membership requires every one of the key's bits.",
      "Input.size is a positive integer, input.positions maps each key to a nonempty list of bit indexes from 0 through size - 1, input.inserted lists keys added to the filter, and input.queries lists keys to test; all of them appear in positions. Return, for each query, whether the filter might contain it: true only when all of its bits are set.",
      '''
      def solve(data):
          bits = [False] * data["size"]
          for key in data["inserted"]:
              for index in data["positions"][key]:
                  bits[index] = True
          return [all(bits[index] for index in data["positions"][key]) for key in data["queries"]]
      ''', ('all(bits[index]', 'any(bits[index]'),
      [({"size": 8, "positions": {"a": [1, 3], "b": [5, 6]}, "inserted": ["a"], "queries": ["a", "b"]}, [True, False]), ({"size": 8, "positions": {"a": [1, 3], "c": [3, 7]}, "inserted": ["a"], "queries": ["c"]}, [False]), ({"size": 4, "positions": {"x": [0]}, "inserted": [], "queries": ["x"]}, [False]), ({"size": 6, "positions": {"a": [0, 1], "b": [2, 3], "c": [1, 2]}, "inserted": ["a", "b"], "queries": ["c", "a", "b"]}, [True, True, True]), ({"size": 5, "positions": {"k": [4, 4], "m": [0, 4]}, "inserted": ["k"], "queries": ["m", "k"]}, [False, True])],
      ["Which condition proves a key was definitely never inserted?", "If any one of a key's bits is still clear, the key was never added; only when all of its bits are set is it possibly present.", "Use all() over the key's bit positions instead of any()."], ["probabilistic-data-structures", "caching"], "easy"),
    p("snapshot-replay-boundary", "Recovery applies the snapshot's last event twice", "A Go event-sourced account rebuilds its state from a snapshot and replays events from the snapshot version onward, so the event already folded into the snapshot is applied again.",
      "Input.snapshot is {version, balance}, the state after every event with version <= snapshot.version. Input.events contains {version, delta} events with unique, increasing versions, possibly including versions the snapshot already covers. Apply each event whose version is greater than snapshot.version. Return {state: {version, balance}}, where version is the last applied event's version, or the snapshot version if none apply.",
      '''
      package main

      func Solve(data map[string]interface{}) interface{} {
          snapshot := data["snapshot"].(map[string]interface{})
          version := int(snapshot["version"].(float64))
          balance := int(snapshot["balance"].(float64))
          for _, raw := range data["events"].([]interface{}) {
              event := raw.(map[string]interface{})
              eventVersion := int(event["version"].(float64))
              if eventVersion > version {
                  balance += int(event["delta"].(float64))
                  version = eventVersion
              }
          }
          return map[string]interface{}{"state": map[string]interface{}{"version": version, "balance": balance}}
      }
      ''', ('eventVersion > version', 'eventVersion >= version'),
      [({"snapshot": {"version": 0, "balance": 0}, "events": [{"version": 1, "delta": 50}]}, {"state": {"version": 1, "balance": 50}}), ({"snapshot": {"version": 2, "balance": 70}, "events": [{"version": 1, "delta": 20}, {"version": 2, "delta": 50}, {"version": 3, "delta": -10}]}, {"state": {"version": 3, "balance": 60}}), ({"snapshot": {"version": 5, "balance": 9}, "events": []}, {"state": {"version": 5, "balance": 9}}), ({"snapshot": {"version": 3, "balance": 0}, "events": [{"version": 1, "delta": 5}, {"version": 2, "delta": 5}, {"version": 3, "delta": 5}]}, {"state": {"version": 3, "balance": 0}}), ({"snapshot": {"version": 0, "balance": 100}, "events": [{"version": 1, "delta": -100}, {"version": 2, "delta": 0}, {"version": 4, "delta": 7}]}, {"state": {"version": 4, "balance": 7}})],
      ["Which events are already reflected in the snapshot?", "A snapshot at version v already includes event v, so replay must start strictly after v.", "Apply only events whose version is greater than the snapshot version."], ["event-sourcing", "recovery", "snapshots"], "easy", language="go"),
    p("canary-sticky-bucket", "A canary user flips between versions", "A canary router picks the new version by request sequence number, so the same user bounces between versions from one request to the next.",
      "Input.percent is 0 through 100, and input.requests contains {user, bucket} objects, where bucket is the user's stable hash bucket from 0 through 99; the same user always has the same bucket. Route a request to 'canary' when its bucket is less than percent, otherwise to 'stable'. Return {routes, state: {canary_users: the sorted distinct users routed to canary}}.",
      '''
      def solve(data):
          routes = ["canary" if request["bucket"] < data["percent"] else "stable" for request in data["requests"]]
          users = sorted({request["user"] for request, route in zip(data["requests"], routes) if route == "canary"})
          return {"routes": routes, "state": {"canary_users": users}}
      ''', ('"canary" if request["bucket"] < data["percent"] else "stable" for request in data["requests"]', '"canary" if index % 100 < data["percent"] else "stable" for index, request in enumerate(data["requests"])'),
      [({"percent": 100, "requests": [{"user": "a", "bucket": 99}, {"user": "b", "bucket": 0}]}, {"routes": ["canary", "canary"], "state": {"canary_users": ["a", "b"]}}), ({"percent": 10, "requests": [{"user": "a", "bucket": 50}, {"user": "b", "bucket": 3}, {"user": "a", "bucket": 50}]}, {"routes": ["stable", "canary", "stable"], "state": {"canary_users": ["b"]}}), ({"percent": 0, "requests": []}, {"routes": [], "state": {"canary_users": []}}), ({"percent": 50, "requests": [{"user": "u1", "bucket": 49}, {"user": "u2", "bucket": 50}, {"user": "u1", "bucket": 49}]}, {"routes": ["canary", "stable", "canary"], "state": {"canary_users": ["u1"]}}), ({"percent": 0, "requests": [{"user": "x", "bucket": 0}]}, {"routes": ["stable"], "state": {"canary_users": []}})],
      ["What should stay constant for one user across many requests?", "Routing by request sequence gives each request, not each user, a bucket, so users flip between versions.", "Route every request by the user's stable bucket, bucket < percent."], ["deployments", "canary-releases", "routing"], "easy"),
    p("consumer-offset-commit", "Every restart replays the last processed message", "A stream consumer commits the offset of the last message it processed, but a committed offset names the next message to read, so each restart processes that message again.",
      "Input.committed is the partition's initial committed offset, and input.log lists messages, where message i has offset i. Input.sessions contains positive batch sizes; each session starts reading at the committed offset, processes up to that many messages in order, commits the offset of the next unread message if it processed any, and then restarts. Return {processed: the offsets processed across all sessions in order, state: {committed}}.",
      '''
      def solve(data):
          committed, processed = data["committed"], []
          for size in data["sessions"]:
              batch = list(range(committed, min(committed + size, len(data["log"]))))
              processed.extend(batch)
              if batch:
                  committed = batch[-1] + 1
          return {"processed": processed, "state": {"committed": committed}}
      ''', ('committed = batch[-1] + 1', 'committed = batch[-1]'),
      [({"committed": 1, "log": ["a", "b"], "sessions": []}, {"processed": [], "state": {"committed": 1}}), ({"committed": 0, "log": ["a", "b", "c", "d"], "sessions": [2, 2]}, {"processed": [0, 1, 2, 3], "state": {"committed": 4}}), ({"committed": 0, "log": [], "sessions": [5]}, {"processed": [], "state": {"committed": 0}}), ({"committed": 2, "log": ["a", "b", "c"], "sessions": [5, 5]}, {"processed": [2], "state": {"committed": 3}}), ({"committed": 0, "log": ["x", "y", "z"], "sessions": [1, 1, 1, 1]}, {"processed": [0, 1, 2], "state": {"committed": 3}})],
      ["Does a committed offset name the last processed message or the next message to read?", "Consumers resume at the committed offset itself, so committing the last processed offset makes every restart reprocess that message.", "Commit the offset after the last processed message, last + 1."], ["streaming", "offsets", "at-least-once"], "easy"),
    p("leader-lease-drift", "The old leader serves reads after its lease", "A leader serves local reads until its lease expiry by its own clock, ignoring the bounded clock drift the protocol requires it to subtract as a safety margin.",
      "Input.lease_end is the lease expiry time, input.max_drift is a nonnegative bound on clock drift, and input.reads contains nondecreasing local clock times. The leader may serve a read locally only when time + max_drift < lease_end; otherwise it must forward the read. Return {decisions: 'local' or 'forward' for each read, state: {last_local: the time of the last local read, or null}}.",
      '''
      def solve(data):
          decisions, last_local = [], None
          for time in data["reads"]:
              if time + data["max_drift"] < data["lease_end"]:
                  decisions.append("local")
                  last_local = time
              else:
                  decisions.append("forward")
          return {"decisions": decisions, "state": {"last_local": last_local}}
      ''', ('time + data["max_drift"] < data["lease_end"]', 'time < data["lease_end"]'),
      [({"lease_end": 100, "max_drift": 0, "reads": [50, 100]}, {"decisions": ["local", "forward"], "state": {"last_local": 50}}), ({"lease_end": 100, "max_drift": 10, "reads": [85, 95]}, {"decisions": ["local", "forward"], "state": {"last_local": 85}}), ({"lease_end": 10, "max_drift": 5, "reads": []}, {"decisions": [], "state": {"last_local": None}}), ({"lease_end": 10, "max_drift": 10, "reads": [0, 1]}, {"decisions": ["forward", "forward"], "state": {"last_local": None}}), ({"lease_end": 1000, "max_drift": 1, "reads": [998, 999]}, {"decisions": ["local", "forward"], "state": {"last_local": 998}})],
      ["Can the leader's clock be behind the rest of the cluster?", "With drift up to max_drift, another node may already consider the lease expired when the leader's clock reads lease_end - max_drift.", "Serve locally only when time + max_drift < lease_end, and forward every other read."], ["leases", "clocks", "consistency"]),
    p("retry-after-respect", "The client retries before the server's Retry-After", "A Java HTTP client schedules retries with exponential backoff alone, ignoring the Retry-After delay the server sent with its 429 or 503 response.",
      "Input.base is a positive delay in milliseconds, and input.responses contains at most 20 responses to successive attempts as {status: integer, retry_after: integer milliseconds or null}. After a 429 or 503 response to zero-based attempt i, wait max(base * 2^i, retry_after or 0) before the next attempt; stop at the first response with any other status. Return {delays: the waits in order, state: {attempts: the number of responses consumed}}.",
      '''
      import com.google.gson.*;
      public class Solution {
        public static JsonElement solve(JsonObject data) {
          long base = data.get("base").getAsLong();
          JsonArray delays = new JsonArray();
          int attempts = 0;
          for (JsonElement raw : data.getAsJsonArray("responses")) {
            JsonObject response = raw.getAsJsonObject();
            int status = response.get("status").getAsInt();
            attempts++;
            if (status != 429 && status != 503) break;
            long backoff = base << (attempts - 1);
            JsonElement hint = response.get("retry_after");
            delays.add(hint == null || hint.isJsonNull() ? backoff : Math.max(backoff, hint.getAsLong()));
          }
          JsonObject state = new JsonObject();
          state.addProperty("attempts", attempts);
          JsonObject result = new JsonObject();
          result.add("delays", delays);
          result.add("state", state);
          return result;
        }
      }
      ''', ('      JsonElement hint = response.get("retry_after");\n      delays.add(hint == null || hint.isJsonNull() ? backoff : Math.max(backoff, hint.getAsLong()));', '      delays.add(backoff);'),
      [({"base": 100, "responses": [{"status": 200, "retry_after": None}]}, {"delays": [], "state": {"attempts": 1}}), ({"base": 100, "responses": [{"status": 503, "retry_after": 1000}, {"status": 200, "retry_after": None}]}, {"delays": [1000], "state": {"attempts": 2}}), ({"base": 100, "responses": []}, {"delays": [], "state": {"attempts": 0}}), ({"base": 100, "responses": [{"status": 429, "retry_after": None}, {"status": 429, "retry_after": 50}, {"status": 503, "retry_after": 900}, {"status": 500, "retry_after": None}]}, {"delays": [100, 200, 900], "state": {"attempts": 4}}), ({"base": 1, "responses": [{"status": 429, "retry_after": 0}, {"status": 429, "retry_after": 3}]}, {"delays": [1, 3], "state": {"attempts": 2}})],
      ["Which delay does the server ask for when it rejects a request with 429 or 503?", "Retry-After is the server's minimum wait; backing off for less than that only produces another rejection.", "Wait for the larger of the exponential backoff and the Retry-After value whenever the response includes one."], ["retries", "backoff", "http"], language="java"),
    p("ring-buffer-overwrite", "The log ring returns entries out of order after wrapping", "A C++ fixed-size log ring overwrites its oldest entry when full but forgets to advance its head, so reads after wrapping start at the wrong slot.",
      "Input.capacity is a positive integer, and input.ops contains {op: 'push', value: integer} and {op: 'drain'} operations. A push appends a value, overwriting the oldest value when the ring is full and counting that value as dropped. A drain returns every buffered value from oldest to newest and empties the ring. Return {drains: the list of drained lists, state: {dropped}}.",
      '''
      #include <nlohmann/json.hpp>
      #include <string>
      #include <vector>
      using nlohmann::json;
      json solve(const json& data) {
          std::size_t capacity = data.at("capacity").get<std::size_t>();
          std::vector<long long> ring(capacity);
          std::size_t head = 0, size = 0;
          long long dropped = 0;
          json drains = json::array();
          for (const auto& op : data.at("ops")) {
              if (op.at("op").get<std::string>() == "push") {
                  ring[(head + size) % capacity] = op.at("value").get<long long>();
                  if (size == capacity) {
                      head = (head + 1) % capacity;
                      ++dropped;
                  } else {
                      ++size;
                  }
              } else {
                  json values = json::array();
                  for (std::size_t i = 0; i < size; ++i) values.push_back(ring[(head + i) % capacity]);
                  drains.push_back(values);
                  head = 0;
                  size = 0;
              }
          }
          json result;
          result["drains"] = drains;
          result["state"]["dropped"] = dropped;
          return result;
      }
      ''', ('                head = (head + 1) % capacity;\n', ''),
      [({"capacity": 3, "ops": [{"op": "push", "value": 1}, {"op": "push", "value": 2}, {"op": "drain"}]}, {"drains": [[1, 2]], "state": {"dropped": 0}}), ({"capacity": 2, "ops": [{"op": "push", "value": 1}, {"op": "push", "value": 2}, {"op": "push", "value": 3}, {"op": "drain"}]}, {"drains": [[2, 3]], "state": {"dropped": 1}}), ({"capacity": 1, "ops": [{"op": "drain"}]}, {"drains": [[]], "state": {"dropped": 0}}), ({"capacity": 2, "ops": [{"op": "push", "value": 1}, {"op": "push", "value": 2}, {"op": "push", "value": 3}, {"op": "push", "value": 4}, {"op": "push", "value": 5}, {"op": "drain"}, {"op": "push", "value": 6}, {"op": "drain"}]}, {"drains": [[4, 5], [6]], "state": {"dropped": 3}}), ({"capacity": 3, "ops": [{"op": "push", "value": -1}, {"op": "drain"}, {"op": "drain"}]}, {"drains": [[-1], []], "state": {"dropped": 0}})],
      ["After the oldest entry is overwritten, where does the oldest remaining entry live?", "When the ring is full, a push replaces the head slot, so the head must move forward to the next-oldest entry.", "Advance head by one, modulo capacity, whenever a push overwrites, and keep size at capacity."], ["ring-buffers", "logging", "data-structures"], language="cpp"),
    p("singleflight-stale-entry", "Coalesced requests keep serving the first answer", "A Node request-coalescing layer shares one backend fetch among concurrent callers but never removes the entry after it resolves, so later requests reuse the first result forever.",
      "Input.events contains {op: 'request', key} and {op: 'resolve', key, value} events in order. A request for a key with no in-flight fetch starts one, counted as a fetch, and waits; a request for a key with an in-flight fetch joins it. A resolve for an in-flight key answers every waiting request with value and ends that fetch; a resolve for any other key is ignored. Return {answers: [[key, value], ...] in the order requests are answered, with waiters of one fetch in request order, state: {fetches}}.",
      '''
      class Deferred {
        constructor() {
          this.settled = false;
          this.value = undefined;
          this.callbacks = [];
        }
        then(callback) {
          if (this.settled) callback(this.value);
          else this.callbacks.push(callback);
        }
        resolve(value) {
          if (this.settled) return;
          this.settled = true;
          this.value = value;
          for (const callback of this.callbacks) callback(value);
        }
      }

      function solve(data) {
        const pending = new Map();
        const answers = [];
        let fetches = 0;
        for (const event of data.events) {
          if (event.op === 'request') {
            if (!pending.has(event.key)) {
              fetches += 1;
              const deferred = new Deferred();
              deferred.then(() => pending.delete(event.key));
              pending.set(event.key, deferred);
            }
            pending.get(event.key).then(value => answers.push([event.key, value]));
          } else if (pending.has(event.key)) {
            pending.get(event.key).resolve(event.value);
          }
        }
        return { answers, state: { fetches } };
      }
      module.exports = { solve };
      ''', ('        deferred.then(() => pending.delete(event.key));\n', ''),
      [({"events": [{"op": "request", "key": "a"}, {"op": "resolve", "key": "a", "value": 1}]}, {"answers": [["a", 1]], "state": {"fetches": 1}}), ({"events": [{"op": "request", "key": "a"}, {"op": "resolve", "key": "a", "value": 1}, {"op": "request", "key": "a"}, {"op": "resolve", "key": "a", "value": 2}]}, {"answers": [["a", 1], ["a", 2]], "state": {"fetches": 2}}), ({"events": []}, {"answers": [], "state": {"fetches": 0}}), ({"events": [{"op": "request", "key": "a"}, {"op": "request", "key": "b"}, {"op": "request", "key": "a"}, {"op": "resolve", "key": "a", "value": "x"}, {"op": "resolve", "key": "b", "value": "y"}, {"op": "resolve", "key": "a", "value": "z"}]}, {"answers": [["a", "x"], ["a", "x"], ["b", "y"]], "state": {"fetches": 2}}), ({"events": [{"op": "resolve", "key": "k", "value": 0}, {"op": "request", "key": "k"}, {"op": "request", "key": "k"}, {"op": "resolve", "key": "k", "value": 0}, {"op": "request", "key": "k"}]}, {"answers": [["k", 0], ["k", 0]], "state": {"fetches": 2}})],
      ["What should happen to the in-flight entry once its fetch has resolved?", "Coalescing should share a fetch only while it is in flight; a settled entry left in the map becomes a permanent cache of the first result.", "Remove the key from the pending map when its fetch settles, so the next request starts a fresh fetch."], ["request-coalescing", "caching", "concurrency"], "hard", language="javascript"),
    p("graceful-drain-deadline", "Shutdown drops requests that were already running", "A Go server's graceful shutdown stops accepting new requests but also abandons in-flight requests instead of letting them finish before the drain deadline.",
      "Input.shutdown is the time shutdown begins, input.deadline is the time the drain window ends (shutdown <= deadline), and input.requests contains {id, start, end} objects with unique IDs and start < end. A request that starts at or after shutdown is rejected. A request that started before shutdown completes when end <= deadline and is aborted otherwise. Return an object mapping each ID to 'completed', 'aborted', or 'rejected'.",
      '''
      package main

      func Solve(data map[string]interface{}) interface{} {
          shutdown := int(data["shutdown"].(float64))
          outcomes := map[string]string{}
          for _, raw := range data["requests"].([]interface{}) {
              request := raw.(map[string]interface{})
              start, end := int(request["start"].(float64)), int(request["end"].(float64))
              id := request["id"].(string)
              switch {
              case start >= shutdown:
                  outcomes[id] = "rejected"
              case end <= int(data["deadline"].(float64)):
                  outcomes[id] = "completed"
              default:
                  outcomes[id] = "aborted"
              }
          }
          return outcomes
      }
      ''', ('end <= int(data["deadline"].(float64))', 'end <= shutdown'),
      [({"shutdown": 100, "deadline": 150, "requests": [{"id": "a", "start": 10, "end": 50}, {"id": "b", "start": 120, "end": 130}]}, {"a": "completed", "b": "rejected"}), ({"shutdown": 100, "deadline": 150, "requests": [{"id": "a", "start": 90, "end": 140}]}, {"a": "completed"}), ({"shutdown": 5, "deadline": 5, "requests": []}, {}), ({"shutdown": 100, "deadline": 150, "requests": [{"id": "x", "start": 99, "end": 151}, {"id": "y", "start": 100, "end": 101}, {"id": "z", "start": 0, "end": 150}]}, {"x": "aborted", "y": "rejected", "z": "completed"}), ({"shutdown": 10, "deadline": 10, "requests": [{"id": "p", "start": 0, "end": 10}, {"id": "q", "start": 5, "end": 11}]}, {"p": "completed", "q": "aborted"})],
      ["What should happen to a request that was already running when shutdown began?", "Graceful shutdown stops new work but gives in-flight requests until the drain deadline to finish.", "Compare an in-flight request's end with the drain deadline, not with the shutdown time."], ["graceful-shutdown", "deadlines", "servers"], "easy", language="go"),
    p("lww-register-tiebreak", "Two replicas disagree after the same writes", "A last-writer-wins register keeps its current value when an incoming write has the same timestamp, so replicas that receive tied writes in different orders never converge.",
      "Input.replicas maps replica names to lists of incoming writes {value, ts: integer, node: string} in delivery order, and every replica starts empty. An incoming write replaces the current one when its (ts, node) pair is greater than the current (ts, node), comparing node names as strings on ties. Return {state: {values: replica name -> final value, or null if it received no writes}, converged: whether every final value is equal}.",
      '''
      def solve(data):
          values = {}
          for name, writes in data["replicas"].items():
              current = None
              for write in writes:
                  if current is None or (write["ts"], write["node"]) > (current["ts"], current["node"]):
                      current = write
              values[name] = None if current is None else current["value"]
          finals = list(values.values())
          return {"state": {"values": values}, "converged": all(value == finals[0] for value in finals)}
      ''', ('(write["ts"], write["node"]) > (current["ts"], current["node"])', 'write["ts"] > current["ts"]'),
      [({"replicas": {"r1": [{"value": "a", "ts": 1, "node": "n1"}, {"value": "b", "ts": 2, "node": "n2"}]}}, {"state": {"values": {"r1": "b"}}, "converged": True}), ({"replicas": {"r1": [{"value": "a", "ts": 5, "node": "x"}, {"value": "b", "ts": 5, "node": "y"}], "r2": [{"value": "b", "ts": 5, "node": "y"}, {"value": "a", "ts": 5, "node": "x"}]}}, {"state": {"values": {"r1": "b", "r2": "b"}}, "converged": True}), ({"replicas": {}}, {"state": {"values": {}}, "converged": True}), ({"replicas": {"r1": [], "r2": [{"value": 7, "ts": 0, "node": "a"}]}}, {"state": {"values": {"r1": None, "r2": 7}}, "converged": False}), ({"replicas": {"p": [{"value": "v1", "ts": 3, "node": "b"}, {"value": "v2", "ts": 3, "node": "a"}, {"value": "v3", "ts": 2, "node": "z"}], "q": [{"value": "v3", "ts": 2, "node": "z"}, {"value": "v2", "ts": 3, "node": "a"}, {"value": "v1", "ts": 3, "node": "b"}]}}, {"state": {"values": {"p": "v1", "q": "v1"}}, "converged": True})],
      ["What should decide between two writes with the same timestamp?", "Keeping the current value on a tie makes the result depend on delivery order, so replicas diverge.", "Compare (ts, node) pairs so ties break deterministically by node name on every replica."], ["crdt", "replication", "conflict-resolution"]),
    p("smooth-weighted-round-robin", "Weighted round robin sends everything to the heaviest server", "A load balancer implementing smooth weighted round robin adds each server's weight every turn but never subtracts the total from the chosen server, so the heaviest server wins every time.",
      "Input.servers contains {id: string, weight: positive integer} objects in priority order and is nonempty whenever input.count is positive; input.count is 0 through 100. Each turn, add every server's weight to its current value, choose the server with the largest current value (the earliest in the list on ties), then subtract the total weight of all servers from the chosen server's current value. All current values start at 0. Return the chosen IDs for count turns.",
      '''
      def solve(data):
          servers, picks = data["servers"], []
          current = [0] * len(servers)
          for _ in range(data["count"]):
              for index, server in enumerate(servers):
                  current[index] += server["weight"]
              best = max(range(len(servers)), key=lambda index: (current[index], -index))
              current[best] -= sum(server["weight"] for server in servers)
              picks.append(servers[best]["id"])
          return picks
      ''', ('        current[best] -= sum(server["weight"] for server in servers)\n', ''),
      [({"servers": [{"id": "a", "weight": 1}], "count": 3}, ["a", "a", "a"]), ({"servers": [{"id": "a", "weight": 2}, {"id": "b", "weight": 1}], "count": 3}, ["a", "b", "a"]), ({"servers": [{"id": "x", "weight": 3}], "count": 0}, []), ({"servers": [{"id": "a", "weight": 5}, {"id": "b", "weight": 1}, {"id": "c", "weight": 1}], "count": 7}, ["a", "a", "b", "a", "c", "a", "a"]), ({"servers": [{"id": "p", "weight": 1}, {"id": "q", "weight": 1}], "count": 4}, ["p", "q", "p", "q"])],
      ["What keeps a chosen server from winning every subsequent turn?", "Smooth weighted round robin subtracts the total weight from the chosen server, so heavier servers win proportionally more often but not every time.", "After choosing the server with the largest current value, subtract the sum of all weights from its current value."], ["load-balancing", "scheduling"]),
]
