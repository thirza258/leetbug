"""Ten executable models of replication, recovery, and capacity decisions."""
from functools import partial

from ..common import make

p = partial(make, "system_design")

PROBLEMS = [
    p("gcounter-merge-idempotence", "Merging the same replica twice doubles the count", "A grow-only counter merges replica states by adding per-replica counts, so re-delivered gossip inflates the total.",
      "A G-counter state maps replica IDs to nonnegative integer counts. Input.local is the starting state, and input.incoming lists states received by gossip, which may be repeated or stale. Merge each incoming state into local with the CRDT join. Return {total: sum of the merged counts, state: {counts: merged map}}.",
      '''
      def solve(data):
          counts = dict(data["local"])
          for remote in data["incoming"]:
              for replica, value in remote.items():
                  counts[replica] = max(counts.get(replica, 0), value)
          return {"total": sum(counts.values()), "state": {"counts": counts}}
      ''', ('max(counts.get(replica, 0), value)', 'counts.get(replica, 0) + value'),
      [({"local": {"a": 2}, "incoming": [{"b": 3}]}, {"total": 5, "state": {"counts": {"a": 2, "b": 3}}}), ({"local": {"a": 2}, "incoming": [{"a": 2, "b": 1}, {"a": 2, "b": 1}]}, {"total": 3, "state": {"counts": {"a": 2, "b": 1}}}), ({"local": {}, "incoming": []}, {"total": 0, "state": {"counts": {}}}), ({"local": {"a": 5, "b": 1}, "incoming": [{"a": 3}, {"b": 4, "c": 0}]}, {"total": 9, "state": {"counts": {"a": 5, "b": 4, "c": 0}}}), ({"local": {"x": 1}, "incoming": [{"x": 1}]}, {"total": 1, "state": {"counts": {"x": 1}}})],
      ["What must happen when the same gossip message is delivered twice?", "A CRDT merge must be idempotent, commutative, and associative; per-replica addition double-counts repeated or stale states.", "Join states by taking the per-replica maximum, then sum the merged counts."], ["crdt", "replication", "idempotency"]),
    p("idempotency-key-conflict", "A reused idempotency key hides a different request", "A Node payment API replays the stored response for any repeated idempotency key without checking that the new request has the same payload.",
      "Input.requests contains {key: string, amount: integer} payment requests in arrival order. The first request with a key creates a charge with the next charge number (1, 2, ...) and remembers its amount, returning {status: 'created', charge}. A later request with the same key and amount returns {status: 'replayed', charge} for the original charge. The same key with a different amount returns {status: 'conflict'} and creates nothing. Return {responses, state: {charges: number of charges created}}.",
      '''
      function solve(data) {
        const stored = new Map();
        const responses = [];
        let charges = 0;
        for (const request of data.requests) {
          const previous = stored.get(request.key);
          if (previous === undefined) {
            charges += 1;
            stored.set(request.key, { charge: charges, amount: request.amount });
            responses.push({ status: 'created', charge: charges });
          } else if (previous.amount !== request.amount) {
            responses.push({ status: 'conflict' });
          } else {
            responses.push({ status: 'replayed', charge: previous.charge });
          }
        }
        return { responses, state: { charges } };
      }
      module.exports = { solve };
      ''', ("    } else if (previous.amount !== request.amount) {\n      responses.push({ status: 'conflict' });\n", ''),
      [({"requests": [{"key": "k1", "amount": 500}, {"key": "k1", "amount": 500}]}, {"responses": [{"status": "created", "charge": 1}, {"status": "replayed", "charge": 1}], "state": {"charges": 1}}), ({"requests": [{"key": "k1", "amount": 500}, {"key": "k1", "amount": 900}]}, {"responses": [{"status": "created", "charge": 1}, {"status": "conflict"}], "state": {"charges": 1}}), ({"requests": []}, {"responses": [], "state": {"charges": 0}}), ({"requests": [{"key": "a", "amount": 1}, {"key": "b", "amount": 1}, {"key": "a", "amount": 2}, {"key": "a", "amount": 1}]}, {"responses": [{"status": "created", "charge": 1}, {"status": "created", "charge": 2}, {"status": "conflict"}, {"status": "replayed", "charge": 1}], "state": {"charges": 2}}), ({"requests": [{"key": "", "amount": 0}, {"key": "", "amount": 0}]}, {"responses": [{"status": "created", "charge": 1}, {"status": "replayed", "charge": 1}], "state": {"charges": 1}})],
      ["Does an idempotency key alone prove that two requests are the same?", "A retry must carry the identical payload; reusing a key with a different amount is a client error, not a replay.", "Store the original amount with the key and return a conflict, without creating a charge, when a repeated key arrives with a different amount."], ["idempotency", "payments", "api-design"], language="javascript"),
    p("wal-uncommitted-replay", "Recovery replays an uncommitted transaction", "A key-value store's crash recovery skips aborted transactions but still applies writes from transactions that never reached a commit record.",
      "Input.log contains records in write order: {op: 'begin', tx}, {op: 'set', tx, key, value}, {op: 'commit', tx}, or {op: 'abort', tx}. Every set belongs to a transaction that began earlier and has not yet ended. Rebuild the store by applying, in log order, only the sets of transactions that have a commit record. Return {state: {store: the resulting key-value map}}.",
      '''
      def solve(data):
          ended = {record["tx"]: record["op"] for record in data["log"] if record["op"] in ("commit", "abort")}
          store = {}
          for record in data["log"]:
              if record["op"] == "set" and ended.get(record["tx"]) == "commit":
                  store[record["key"]] = record["value"]
          return {"state": {"store": store}}
      ''', ('ended.get(record["tx"]) == "commit"', 'ended.get(record["tx"]) != "abort"'),
      [({"log": [{"op": "begin", "tx": 1}, {"op": "set", "tx": 1, "key": "a", "value": 1}, {"op": "commit", "tx": 1}]}, {"state": {"store": {"a": 1}}}), ({"log": [{"op": "begin", "tx": 1}, {"op": "set", "tx": 1, "key": "a", "value": 1}, {"op": "commit", "tx": 1}, {"op": "begin", "tx": 2}, {"op": "set", "tx": 2, "key": "a", "value": 9}]}, {"state": {"store": {"a": 1}}}), ({"log": []}, {"state": {"store": {}}}), ({"log": [{"op": "begin", "tx": 1}, {"op": "begin", "tx": 2}, {"op": "set", "tx": 1, "key": "x", "value": 1}, {"op": "set", "tx": 2, "key": "x", "value": 2}, {"op": "set", "tx": 2, "key": "y", "value": 5}, {"op": "abort", "tx": 2}, {"op": "commit", "tx": 1}]}, {"state": {"store": {"x": 1}}}), ({"log": [{"op": "begin", "tx": 7}, {"op": "set", "tx": 7, "key": "k", "value": "v"}, {"op": "begin", "tx": 8}, {"op": "set", "tx": 8, "key": "m", "value": "w"}, {"op": "commit", "tx": 8}, {"op": "set", "tx": 7, "key": "z", "value": 0}]}, {"state": {"store": {"m": "w"}}}), ({"log": [{"op": "begin", "tx": 1}, {"op": "set", "tx": 1, "key": "a", "value": 1}, {"op": "begin", "tx": 2}, {"op": "set", "tx": 2, "key": "b", "value": 2}, {"op": "commit", "tx": 2}, {"op": "commit", "tx": 1}]}, {"state": {"store": {"a": 1, "b": 2}}})],
      ["Which transactions are durable after a crash?", "Only a commit record makes a transaction's writes durable; a transaction with neither commit nor abort was still in flight at the crash.", "Apply a set during replay only when its transaction has a commit record, keeping log order for committed writes."], ["write-ahead-log", "recovery", "transactions"], "hard"),
    p("raft-log-freshness-vote", "A stale log wins the election", "A consensus node grants votes by comparing only log length, so a candidate with a longer log from an older term can defeat a node holding newer entries.",
      "Input.voter and each item in input.candidates are {last_term, last_index} positions of nonnegative integers. Under Raft's election restriction, a candidate's log is at least as up to date as the voter's when its last_term is greater, or when the terms are equal and its last_index is greater than or equal to the voter's. Return one boolean per candidate saying whether log freshness permits the vote.",
      '''
      def solve(data):
          voter = data["voter"]
          return [(c["last_term"], c["last_index"]) >= (voter["last_term"], voter["last_index"]) for c in data["candidates"]]
      ''', ('(c["last_term"], c["last_index"]) >= (voter["last_term"], voter["last_index"])', 'c["last_index"] >= voter["last_index"]'),
      [({"voter": {"last_term": 2, "last_index": 5}, "candidates": [{"last_term": 2, "last_index": 5}, {"last_term": 2, "last_index": 4}]}, [True, False]), ({"voter": {"last_term": 3, "last_index": 4}, "candidates": [{"last_term": 2, "last_index": 9}, {"last_term": 4, "last_index": 1}]}, [False, True]), ({"voter": {"last_term": 0, "last_index": 0}, "candidates": []}, []), ({"voter": {"last_term": 0, "last_index": 0}, "candidates": [{"last_term": 0, "last_index": 0}]}, [True]), ({"voter": {"last_term": 5, "last_index": 10}, "candidates": [{"last_term": 5, "last_index": 11}, {"last_term": 6, "last_index": 0}, {"last_term": 4, "last_index": 100}, {"last_term": 5, "last_index": 9}]}, [True, True, False, False])],
      ["Which part of a log position reflects newer leadership?", "Raft compares last log terms first; only when the terms tie does the longer log win.", "Compare (last_term, last_index) pairs lexicographically instead of comparing indexes alone."], ["consensus", "raft", "leader-election"], "hard"),
    p("quorum-read-latest-version", "A quorum read returns a stale replica", "A replicated store answers a quorum read with the first replica response instead of the response that carries the highest version.",
      "Input.quorum is a positive integer, and input.responses contains replica replies {replica: string, version: nonnegative integer, value} in arrival order. Use only the first quorum replies; if fewer arrived, return {ok: false}. Otherwise return {ok: true, value, version, repair}: take the value with the highest version, with ties going to the earliest reply, and list in arrival order the replicas within the quorum whose version is lower.",
      '''
      def solve(data):
          replies = data["responses"][:data["quorum"]]
          if len(replies) < data["quorum"]:
              return {"ok": False}
          best = max(replies, key=lambda reply: reply["version"])
          repair = [reply["replica"] for reply in replies if reply["version"] < best["version"]]
          return {"ok": True, "value": best["value"], "version": best["version"], "repair": repair}
      ''', ('best = max(replies, key=lambda reply: reply["version"])', 'best = replies[0]'),
      [({"quorum": 2, "responses": [{"replica": "r1", "version": 3, "value": "new"}, {"replica": "r2", "version": 2, "value": "old"}]}, {"ok": True, "value": "new", "version": 3, "repair": ["r2"]}), ({"quorum": 2, "responses": [{"replica": "r1", "version": 1, "value": "old"}, {"replica": "r2", "version": 4, "value": "new"}, {"replica": "r3", "version": 9, "value": "newest"}]}, {"ok": True, "value": "new", "version": 4, "repair": ["r1"]}), ({"quorum": 3, "responses": [{"replica": "a", "version": 1, "value": "x"}]}, {"ok": False}), ({"quorum": 3, "responses": [{"replica": "a", "version": 2, "value": "p"}, {"replica": "b", "version": 2, "value": "q"}, {"replica": "c", "version": 0, "value": None}]}, {"ok": True, "value": "p", "version": 2, "repair": ["c"]}), ({"quorum": 3, "responses": [{"replica": "a", "version": 1, "value": "v1"}, {"replica": "b", "version": 3, "value": "v3"}, {"replica": "c", "version": 2, "value": "v2"}]}, {"ok": True, "value": "v3", "version": 3, "repair": ["a", "c"]})],
      ["Which reply in a quorum reflects the latest write?", "Replicas in a quorum can lag, so versions, not arrival order, identify the newest value.", "Pick the reply with the highest version among the first quorum replies, the earliest on ties, and mark lower-version replicas for read repair."], ["replication", "quorums", "read-repair"]),
    p("two-phase-commit-unanimity", "One participant's no vote is outvoted", "A two-phase-commit coordinator commits when most participants vote yes, even though a single no vote or missing vote must abort the transaction.",
      "Input.participants lists participant IDs, and input.votes maps some of those IDs to true (prepared) or false (cannot commit). Commit only if every participant voted true; any false or missing vote aborts, and an empty participant list commits. Return {decision: 'commit'|'abort', blockers: IDs that voted false or did not vote, in participant order}.",
      '''
      def solve(data):
          blockers = [pid for pid in data["participants"] if data["votes"].get(pid) is not True]
          decision = "commit" if not blockers else "abort"
          return {"decision": decision, "blockers": blockers}
      ''', ('not blockers', 'len(blockers) * 2 < len(data["participants"])'),
      [({"participants": ["a", "b"], "votes": {"a": True, "b": True}}, {"decision": "commit", "blockers": []}), ({"participants": ["a", "b", "c"], "votes": {"a": True, "b": False, "c": True}}, {"decision": "abort", "blockers": ["b"]}), ({"participants": ["a", "b", "c"], "votes": {"a": True, "c": True}}, {"decision": "abort", "blockers": ["b"]}), ({"participants": [], "votes": {}}, {"decision": "commit", "blockers": []}), ({"participants": ["x", "y"], "votes": {"x": False, "y": False}}, {"decision": "abort", "blockers": ["x", "y"]})],
      ["How many participants can veto a two-phase commit?", "Atomic commit requires unanimity: every participant must be prepared, and one no vote or missing vote forces an abort.", "Commit only when the blocker list is empty; an empty participant list has no blockers."], ["transactions", "two-phase-commit", "atomicity"], "easy"),
    p("saga-compensation-order", "The saga undoes its steps in the wrong order", "An order saga runs its compensating actions in the same order as the original steps instead of unwinding the most recent step first.",
      "Input.steps lists saga step names in execution order, and input.failed_at is the index of the step that failed, or null if every step succeeded. After a failure, compensate every step that completed before the failed one, most recent first; the failed step itself is not compensated. Return {status: 'completed'|'compensated', compensations: ['undo:' + step name, ...]}.",
      '''
      def solve(data):
          if data["failed_at"] is None:
              return {"status": "completed", "compensations": []}
          done = data["steps"][:data["failed_at"]]
          return {"status": "compensated", "compensations": ["undo:" + step for step in reversed(done)]}
      ''', ('reversed(done)', 'done'),
      [({"steps": ["reserve", "charge"], "failed_at": 1}, {"status": "compensated", "compensations": ["undo:reserve"]}), ({"steps": ["reserve", "charge", "ship"], "failed_at": 2}, {"status": "compensated", "compensations": ["undo:charge", "undo:reserve"]}), ({"steps": ["a"], "failed_at": None}, {"status": "completed", "compensations": []}), ({"steps": ["a", "b"], "failed_at": 0}, {"status": "compensated", "compensations": []}), ({"steps": ["hold", "debit", "notify", "ship"], "failed_at": 3}, {"status": "compensated", "compensations": ["undo:notify", "undo:debit", "undo:hold"]})],
      ["In what order should completed saga steps be undone?", "Compensation unwinds a saga like a stack: later steps may depend on earlier ones, so the most recent step is undone first.", "Compensate the steps before failed_at in reverse execution order, excluding the failed step."], ["sagas", "compensation", "workflows"], "easy"),
    p("heartbeat-last-seen", "A node that keeps heartbeating is declared dead", "A failure detector records each node's first heartbeat with setdefault and never refreshes it, so healthy nodes eventually look silent.",
      "Input.timeout is a positive integer, input.now is an integer time, and input.heartbeats contains {node, at} events in nondecreasing time order, none after now. A node is suspected when now - (its latest heartbeat time) > timeout. Return the suspected node IDs in ascending order; nodes that never sent a heartbeat are not listed.",
      '''
      def solve(data):
          last_seen = {}
          for beat in data["heartbeats"]:
              last_seen[beat["node"]] = beat["at"]
          return sorted(node for node, at in last_seen.items() if data["now"] - at > data["timeout"])
      ''', ('last_seen[beat["node"]] = beat["at"]', 'last_seen.setdefault(beat["node"], beat["at"])'),
      [({"timeout": 10, "now": 20, "heartbeats": [{"node": "a", "at": 5}, {"node": "b", "at": 15}]}, ["a"]), ({"timeout": 10, "now": 30, "heartbeats": [{"node": "a", "at": 0}, {"node": "a", "at": 25}]}, []), ({"timeout": 1, "now": 0, "heartbeats": []}, []), ({"timeout": 5, "now": 10, "heartbeats": [{"node": "y", "at": 4}, {"node": "x", "at": 5}, {"node": "x", "at": 6}]}, ["y"]), ({"timeout": 3, "now": 100, "heartbeats": [{"node": "a", "at": 50}, {"node": "b", "at": 90}, {"node": "b", "at": 98}, {"node": "c", "at": 99}]}, ["a"])],
      ["Which heartbeat determines whether a node is still alive?", "setdefault keeps the first value it stored, so later heartbeats never refresh a node's last-seen time.", "Overwrite the node's entry on every heartbeat and compare the latest time with the timeout."], ["failure-detection", "heartbeats"]),
    p("deadline-budget-propagation", "The downstream call outlives its caller's deadline", "A Go gateway gives every downstream call its full configured timeout, ignoring how much of the caller's deadline has already been spent.",
      "Input.deadline is the caller's absolute deadline in milliseconds. Input.calls contains downstream calls {start, timeout, duration} in nondecreasing start order. A call whose start is at or after the caller's deadline is skipped. Otherwise its limit is the earlier of start + timeout and the caller's deadline; it succeeds when start + duration <= limit and otherwise times out at the limit. Return {statuses: 'ok'|'timeout'|'skipped' per call, state: {busy_until: the time the most recently attempted call stopped, or null if none ran}}.",
      '''
      package main

      func Solve(data map[string]interface{}) interface{} {
          callerDeadline := int(data["deadline"].(float64))
          statuses := []string{}
          var busyUntil interface{}
          for _, raw := range data["calls"].([]interface{}) {
              call := raw.(map[string]interface{})
              start := int(call["start"].(float64))
              if start >= callerDeadline {
                  statuses = append(statuses, "skipped")
                  continue
              }
              limit := start + int(call["timeout"].(float64))
              if limit > callerDeadline {
                  limit = callerDeadline
              }
              end := start + int(call["duration"].(float64))
              if end <= limit {
                  statuses = append(statuses, "ok")
              } else {
                  statuses = append(statuses, "timeout")
                  end = limit
              }
              busyUntil = end
          }
          return map[string]interface{}{"statuses": statuses, "state": map[string]interface{}{"busy_until": busyUntil}}
      }
      ''', ('        if limit > callerDeadline {\n            limit = callerDeadline\n        }\n', ''),
      [({"deadline": 1000, "calls": [{"start": 0, "timeout": 300, "duration": 100}]}, {"statuses": ["ok"], "state": {"busy_until": 100}}), ({"deadline": 500, "calls": [{"start": 0, "timeout": 300, "duration": 200}, {"start": 200, "timeout": 400, "duration": 350}]}, {"statuses": ["ok", "timeout"], "state": {"busy_until": 500}}), ({"deadline": 100, "calls": [{"start": 100, "timeout": 50, "duration": 1}]}, {"statuses": ["skipped"], "state": {"busy_until": None}}), ({"deadline": 1000, "calls": [{"start": 0, "timeout": 100, "duration": 150}, {"start": 100, "timeout": 2000, "duration": 950}, {"start": 1050, "timeout": 10, "duration": 1}]}, {"statuses": ["timeout", "timeout", "skipped"], "state": {"busy_until": 1000}}), ({"deadline": 50, "calls": []}, {"statuses": [], "state": {"busy_until": None}})],
      ["Can a downstream call usefully keep running after its caller has given up?", "Each call's deadline must be capped by the remaining budget of the request that made it.", "Take the earlier of start + timeout and the caller's deadline as the call's limit; compare explicitly, since Go 1.19 has no built-in min."], ["deadlines", "timeouts", "resilience"], language="go"),
    p("autoscaler-ceiling-replicas", "The autoscaler rounds away the last replica", "A horizontal autoscaler computes the desired replica count with floor division, so demand just above the replicas' target capacity is under-provisioned.",
      "Input.current is a positive replica count, input.target is the positive target utilization per replica, and input.min_replicas <= input.max_replicas are positive bounds. Input.samples contains nonnegative integer average utilizations for successive scaling decisions. For each sample, desired = ceil(current * sample / target), clamped to [min_replicas, max_replicas], and the result becomes current for the next sample. Return the replica count after each decision.",
      '''
      def solve(data):
          current, low, high = data["current"], data["min_replicas"], data["max_replicas"]
          history = []
          for sample in data["samples"]:
              desired = -(-current * sample // data["target"])
              current = max(low, min(high, desired))
              history.append(current)
          return history
      ''', ('-(-current * sample // data["target"])', 'current * sample // data["target"]'),
      [({"current": 2, "target": 50, "min_replicas": 1, "max_replicas": 10, "samples": [50]}, [2]), ({"current": 4, "target": 60, "min_replicas": 1, "max_replicas": 10, "samples": [70]}, [5]), ({"current": 3, "target": 50, "min_replicas": 1, "max_replicas": 10, "samples": []}, []), ({"current": 2, "target": 50, "min_replicas": 1, "max_replicas": 5, "samples": [200, 200, 10]}, [5, 5, 1]), ({"current": 10, "target": 80, "min_replicas": 2, "max_replicas": 20, "samples": [81, 0, 40]}, [11, 2, 2]), ({"current": 1, "target": 100, "min_replicas": 1, "max_replicas": 3, "samples": [101, 101]}, [2, 3])],
      ["Which rounding direction keeps every replica at or below its target utilization?", "Floor division drops fractional replicas, so load slightly above target capacity never adds the replica it needs.", "Round the desired replica count up with integer ceiling division before applying the min/max clamp."], ["autoscaling", "capacity-planning"], "easy"),
]
