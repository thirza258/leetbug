"""Twenty executable models of distributed-system decisions and failure recovery."""
from functools import partial

from .common import make

p = partial(make, "system_design")

PROBLEMS = [
    p("token-bucket-capacity", "Idle time creates an unlimited burst", "A token bucket refills forever while idle, ignoring its burst capacity.",
      "Input.capacity and rate are positive integers. Start full at time 0. Input.times contains nondecreasing nonnegative integer request times. Refill rate tokens per elapsed unit, capped at capacity; each accepted request spends one token. Return {accepted, state: {tokens}}.",
      '''
      def solve(data):
          tokens, previous, accepted = data["capacity"], 0, []
          for now in data["times"]:
              tokens = min(data["capacity"], tokens + (now - previous) * data["rate"])
              previous = now
              ok = tokens >= 1
              accepted.append(ok)
              if ok:
                  tokens -= 1
          return {"accepted": accepted, "state": {"tokens": tokens}}
      ''', ('min(data["capacity"], tokens + (now - previous) * data["rate"])', 'tokens + (now - previous) * data["rate"]'),
      [({"capacity": 2, "rate": 1, "times": [0, 0, 0]}, {"accepted": [True, True, False], "state": {"tokens": 0}}), ({"capacity": 2, "rate": 1, "times": [10, 10, 10]}, {"accepted": [True, True, False], "state": {"tokens": 0}}), ({"capacity": 1, "rate": 2, "times": []}, {"accepted": [], "state": {"tokens": 1}}), ({"capacity": 1, "rate": 1, "times": [0, 1, 1]}, {"accepted": [True, True, False], "state": {"tokens": 0}}), ({"capacity": 3, "rate": 1, "times": [0, 5]}, {"accepted": [True, True], "state": {"tokens": 2}})],
      ["What limits a burst after a long idle period?", "Refill creates tokens only up to the configured bucket capacity.", "Clamp the refill before checking and spending the next request's token."], ["rate-limiting", "token-bucket"]),
    p("tenant-window-isolation", "One tenant consumes every tenant's quota", "A fixed-window limiter keys its counters only by time window.",
      "Input.window is positive and limit is nonnegative. Requests contain {tenant: string, at: nonnegative integer} in time order. Allow at most limit requests per tenant per floor(at/window) window. Return acceptance booleans.",
      '''
      def solve(data):
          counts, result = {}, []
          for request in data["requests"]:
              key = (request["tenant"], request["at"] // data["window"])
              count = counts.get(key, 0)
              ok = count < data["limit"]
              result.append(ok)
              if ok:
                  counts[key] = count + 1
          return result
      ''', ('(request["tenant"], request["at"] // data["window"])', '("global", request["at"] // data["window"])'),
      [({"window": 10, "limit": 1, "requests": [{"tenant": "a", "at": 0}, {"tenant": "a", "at": 1}]}, [True, False]), ({"window": 10, "limit": 1, "requests": [{"tenant": "a", "at": 0}, {"tenant": "b", "at": 1}]}, [True, True]), ({"window": 10, "limit": 1, "requests": [{"tenant": "a", "at": 9}, {"tenant": "a", "at": 10}]}, [True, True]), ({"window": 1, "limit": 0, "requests": [{"tenant": "", "at": 0}]}, [False]), ({"window": 1, "limit": 1, "requests": []}, [])],
      ["What identities define one quota counter?", "The isolation boundary includes both tenant and time window.", "Key each counter by the tenant/window pair rather than by window alone."], ["multi-tenancy", "rate-limiting"]),
    p("cache-ttl-deadline", "An expired cache entry survives its deadline", "A TTL cache serves an entry at the exact instant it should expire.",
      "Input.ttl is positive. Events in nondecreasing nonnegative at order are put {key,value,at} or get {key,at}. Put expires at at+ttl and replaces the key. Return one value per get, or null for absent/expired keys. Entries are valid only while now < expires.",
      '''
      def solve(data):
          cache, result = {}, []
          for event in data["events"]:
              key = event["key"]
              if event["op"] == "put":
                  cache[key] = (event["value"], event["at"] + data["ttl"])
              else:
                  entry = cache.get(key)
                  result.append(entry[0] if entry is not None and event["at"] < entry[1] else None)
          return result
      ''', ('event["at"] < entry[1]', 'event["at"] <= entry[1]'),
      [({"ttl": 5, "events": [{"op": "put", "key": "a", "value": 3, "at": 0}, {"op": "get", "key": "a", "at": 4}]}, [3]), ({"ttl": 5, "events": [{"op": "put", "key": "a", "value": 3, "at": 0}, {"op": "get", "key": "a", "at": 5}]}, [None]), ({"ttl": 1, "events": [{"op": "get", "key": "x", "at": 0}]}, [None]), ({"ttl": 1, "events": []}, []), ({"ttl": 2, "events": [{"op": "put", "key": "a", "value": 0, "at": 0}, {"op": "put", "key": "a", "value": 4, "at": 1}, {"op": "get", "key": "a", "at": 2}]}, [4])],
      ["Is the expiry timestamp still inside the validity interval?", "TTL validity is a half-open interval and ends at the deadline.", "Serve an entry only when the current time is strictly before expiry."], ["caching", "expiration"]),
    p("lru-read-recency", "A popular cache entry gets evicted", "An LRU cache updates recency on writes but not on reads.",
      "Input.capacity is 0 through 20. Events are put {key,value} or get {key}. Return {reads: get values or null, state: {keys: least-to-most-recent keys}}. Successful reads and every put refresh recency; evict the least recent beyond capacity.",
      '''
      from collections import OrderedDict
      def solve(data):
          cache, reads = OrderedDict(), []
          for event in data["events"]:
              key = event["key"]
              if event["op"] == "put":
                  cache[key] = event["value"]
                  cache.move_to_end(key)
                  while len(cache) > data["capacity"]:
                      cache.popitem(last=False)
              else:
                  reads.append(cache.get(key))
                  if key in cache:
                      cache.move_to_end(key)
          return {"reads": reads, "state": {"keys": list(cache)}}
      ''', ('if key in cache:\n                cache.move_to_end(key)', 'if False:\n                cache.move_to_end(key)'),
      [({"capacity": 1, "events": [{"op": "put", "key": "a", "value": 1}, {"op": "get", "key": "a"}]}, {"reads": [1], "state": {"keys": ["a"]}}), ({"capacity": 2, "events": [{"op": "put", "key": "a", "value": 1}, {"op": "put", "key": "b", "value": 2}, {"op": "get", "key": "a"}, {"op": "put", "key": "c", "value": 3}]}, {"reads": [1], "state": {"keys": ["a", "c"]}}), ({"capacity": 0, "events": [{"op": "put", "key": "a", "value": 0}, {"op": "get", "key": "a"}]}, {"reads": [None], "state": {"keys": []}}), ({"capacity": 2, "events": []}, {"reads": [], "state": {"keys": []}}), ({"capacity": 2, "events": [{"op": "get", "key": "x"}]}, {"reads": [None], "state": {"keys": []}})],
      ["Does a read count as using an entry?", "Least-recently-used tracks successful reads as well as writes.", "Move a cache hit to the most-recent end before any later eviction."], ["caching", "eviction"]),
    p("majority-quorum-size", "Half the replicas are called a majority", "A replicated service allows writes with exactly half the configured replicas.",
      "Input.replicas is a positive integer and available is 0 through replicas. Return whether available is a strict majority of the configured replica count.",
      '''
      def solve(data):
          return data["available"] >= data["replicas"] // 2 + 1
      ''', ('data["replicas"] // 2 + 1', '(data["replicas"] + 1) // 2'),
      [({"replicas": 3, "available": 2}, True), ({"replicas": 4, "available": 2}, False), ({"replicas": 1, "available": 0}, False), ({"replicas": 1, "available": 1}, True), ({"replicas": 6, "available": 4}, True)],
      ["Can exactly half of an even replica set be a strict majority?", "Majority is floor(N/2)+1 for both odd and even N.", "Require at least replicas//2+1 available replicas."], ["replication", "quorums"], "easy"),
    p("read-write-quorum-overlap", "Read and write quorums never meet", "A configuration validator accepts quorum sizes whose sets may be disjoint.",
      "Input.n is positive, r and w are integer quorum sizes. Return true only if 1 <= r,w <= n and r+w > n, guaranteeing read/write set overlap for this fixed replica-set exercise. This check alone does not establish all consistency guarantees.",
      '''
      def solve(data):
          n, r, w = data["n"], data["r"], data["w"]
          return 1 <= r <= n and 1 <= w <= n and r + w > n
      ''', ('r + w > n', 'r + w >= n'),
      [({"n": 3, "r": 2, "w": 2}, True), ({"n": 4, "r": 2, "w": 2}, False), ({"n": 3, "r": 0, "w": 3}, False), ({"n": 3, "r": 4, "w": 1}, False), ({"n": 1, "r": 1, "w": 1}, True)],
      ["Can two sets whose sizes sum to N occupy opposite halves?", "Guaranteed overlap requires the sum to exceed the replica-set size.", "Keep individual bounds and require r+w > n rather than equality."], ["replication", "consistency"]),
    p("replica-distinct-hosts", "Two replicas land on the same host", "A placement routine counts virtual nodes as independent replicas even when they share a physical host.",
      "Input.ring contains host-ID strings already ordered clockwise from a key; repeated hosts represent virtual nodes. Input.count is nonnegative. Return the first count distinct hosts in traversal order, or all distinct hosts if fewer exist.",
      '''
      def solve(data):
          result = []
          for host in data["ring"]:
              if len(result) >= data["count"]:
                  break
              if host not in result:
                  result.append(host)
          return result
      ''', ('if host not in result:', 'if True:'),
      [({"ring": ["a", "b"], "count": 2}, ["a", "b"]), ({"ring": ["a", "a", "b"], "count": 2}, ["a", "b"]), ({"ring": ["a"], "count": 0}, []), ({"ring": [], "count": 3}, []), ({"ring": ["a", "b", "a"], "count": 5}, ["a", "b"])],
      ["Does a virtual node represent an independent failure domain?", "Repeated entries for one physical host cannot count as multiple durable host copies.", "Deduplicate host identities while retaining clockwise order before reaching the requested replica count."], ["placement", "failure-domains"]),
    p("rendezvous-score-choice", "The router chooses the lowest rendezvous score", "A rendezvous router reverses its ranking and assigns a key to the wrong healthy node.",
      "Input.nodes contains unique {id: ASCII string, score: integer, healthy: boolean}; scores are precomputed for one key. Choose the healthy node with highest score, breaking ties by smallest id. Return its id or null.",
      '''
      def solve(data):
          nodes = [n for n in data["nodes"] if n["healthy"]]
          nodes.sort(key=lambda n: (-n["score"], n["id"]))
          return nodes[0]["id"] if nodes else None
      ''', ('(-n["score"], n["id"])', '(n["score"], n["id"])'),
      [({"nodes": [{"id": "a", "score": 1, "healthy": True}]}, "a"), ({"nodes": [{"id": "a", "score": 1, "healthy": True}, {"id": "b", "score": 9, "healthy": True}]}, "b"), ({"nodes": []}, None), ({"nodes": [{"id": "a", "score": 9, "healthy": False}]}, None), ({"nodes": [{"id": "b", "score": 2, "healthy": True}, {"id": "a", "score": 2, "healthy": True}]}, "a")],
      ["Which end of the rendezvous ranking wins?", "The highest eligible score owns the key, with the documented deterministic tie-breaker.", "Sort on negative score followed by ascending id after filtering unhealthy nodes."], ["routing", "rendezvous-hashing"]),
    p("healthy-least-connections", "The load balancer sends work to a dead node", "A least-connections router chooses a node with zero connections because it is offline.",
      "Input.nodes contains unique {id: ASCII string, connections: nonnegative integer, healthy: boolean}. Return the healthy node with the fewest connections, breaking ties by smallest id, or null.",
      '''
      def solve(data):
          nodes = [n for n in data["nodes"] if n["healthy"]]
          best = min(nodes, key=lambda n: (n["connections"], n["id"]), default=None)
          return best["id"] if best is not None else None
      ''', ('if n["healthy"]', 'if True'),
      [({"nodes": [{"id": "a", "connections": 1, "healthy": True}]}, "a"), ({"nodes": [{"id": "a", "connections": 0, "healthy": False}, {"id": "b", "connections": 2, "healthy": True}]}, "b"), ({"nodes": []}, None), ({"nodes": [{"id": "a", "connections": 0, "healthy": False}]}, None), ({"nodes": [{"id": "b", "connections": 1, "healthy": True}, {"id": "a", "connections": 1, "healthy": True}]}, "a")],
      ["Can an offline node be an eligible routing candidate?", "Health is a feasibility gate before connection-count ranking.", "Filter unhealthy nodes before choosing the minimum (connections,id) pair."], ["load-balancing", "health-checks"]),
    p("queue-dead-letter-budget", "A poison job gets one extra attempt", "A worker retry policy confuses a total-attempt limit with a retry count.",
      "Input.max_attempts is positive and outcomes is a list of booleans for one job's successive attempts. Process until success or max_attempts failures; ignore later outcomes. Return {attempts, status: 'done'|'dead'|'pending'}. Pending means supplied outcomes ended before either terminal condition.",
      '''
      def solve(data):
          attempts, status = 0, "pending"
          for ok in data["outcomes"]:
              if status != "pending":
                  break
              attempts += 1
              if ok:
                  status = "done"
              elif attempts >= data["max_attempts"]:
                  status = "dead"
          return {"attempts": attempts, "status": status}
      ''', ('attempts >= data["max_attempts"]', 'attempts > data["max_attempts"]'),
      [({"max_attempts": 3, "outcomes": [True]}, {"attempts": 1, "status": "done"}), ({"max_attempts": 2, "outcomes": [False, False, True]}, {"attempts": 2, "status": "dead"}), ({"max_attempts": 1, "outcomes": []}, {"attempts": 0, "status": "pending"}), ({"max_attempts": 3, "outcomes": [False]}, {"attempts": 1, "status": "pending"}), ({"max_attempts": 2, "outcomes": [False, True]}, {"attempts": 2, "status": "done"})],
      ["Does max_attempts include the first execution?", "The job becomes terminal at the configured failed-attempt count.", "Dead-letter when attempts >= max_attempts and never process later supplied outcomes."], ["queues", "dead-letter"]),
    p("backoff-cap-before-growth", "Retry delays grow beyond their ceiling", "A backoff calculator forgets the configured maximum delay.",
      "Input.base and cap are positive integer milliseconds; count is 0 through 20. Return delay i = min(cap, base*2^i) for zero-based retry indexes i. These are deterministic nominal delays before any optional jitter.",
      '''
      def solve(data):
          return [min(data["cap"], data["base"] * 2 ** index) for index in range(data["count"])]
      ''', ('min(data["cap"], data["base"] * 2 ** index)', 'data["base"] * 2 ** index'),
      [({"base": 2, "cap": 10, "count": 2}, [2, 4]), ({"base": 2, "cap": 5, "count": 4}, [2, 4, 5, 5]), ({"base": 10, "cap": 3, "count": 1}, [3]), ({"base": 1, "cap": 1, "count": 3}, [1, 1, 1]), ({"base": 1, "cap": 2, "count": 0}, [])],
      ["What bounds the largest individual delay?", "Exponential growth must saturate at the configured cap.", "Take min(cap, base*2**index) independently for every retry."], ["retries", "backoff"], "easy"),
    p("bulkhead-slot-release", "A failed job permanently occupies a slot", "A concurrency limiter frees capacity after success but leaks slots after failure.",
      "Input.capacity is nonnegative. Events are start {id}, finish {id}, or fail {id}. Start accepts only a new active ID when capacity exists. Finish/fail accept only active IDs and both release their slot. Return {accepted, state: {active: sorted IDs}}. Completed IDs may be reused.",
      '''
      def solve(data):
          active, accepted = set(), []
          for event in data["events"]:
              key = event["id"]
              if event["op"] == "start":
                  ok = key not in active and len(active) < data["capacity"]
                  if ok:
                      active.add(key)
              else:
                  ok = key in active
                  if ok:
                      active.remove(key)
              accepted.append(ok)
          return {"accepted": accepted, "state": {"active": sorted(active)}}
      ''', ('if ok:\n                active.remove(key)', 'if ok and event["op"] == "finish":\n                active.remove(key)'),
      [({"capacity": 1, "events": [{"op": "start", "id": "a"}, {"op": "finish", "id": "a"}]}, {"accepted": [True, True], "state": {"active": []}}), ({"capacity": 1, "events": [{"op": "start", "id": "a"}, {"op": "fail", "id": "a"}, {"op": "start", "id": "b"}]}, {"accepted": [True, True, True], "state": {"active": ["b"]}}), ({"capacity": 0, "events": [{"op": "start", "id": "a"}]}, {"accepted": [False], "state": {"active": []}}), ({"capacity": 1, "events": [{"op": "finish", "id": "x"}]}, {"accepted": [False], "state": {"active": []}}), ({"capacity": 1, "events": []}, {"accepted": [], "state": {"active": []}})],
      ["Which terminal outcomes stop using the resource?", "Both success and failure release the same concurrency slot.", "Remove every active job on either terminal event, preserving rejection for unknown IDs."], ["bulkheads", "resource-lifecycle"]),
    p("tenant-round-robin", "The first tenant drains the entire queue", "A multi-tenant worker exhausts one tenant before serving the next.",
      "Input.queues is an ordered list of job-ID lists, one per tenant; limit is nonnegative. Repeatedly take at most one job from each nonempty tenant in input order per round until limit jobs are selected or all queues empty. Return selected IDs.",
      '''
      from collections import deque
      def solve(data):
          queues = [deque(items) for items in data["queues"]]
          output = []
          while len(output) < data["limit"] and any(queues):
              for queue in queues:
                  if queue and len(output) < data["limit"]:
                      output.append(queue.popleft())
          return output
      ''', ('if queue and len(output) < data["limit"]:', 'while queue and len(output) < data["limit"]:'),
      [({"queues": [["a"], ["b"]], "limit": 2}, ["a", "b"]), ({"queues": [["a1", "a2"], ["b1", "b2"]], "limit": 4}, ["a1", "b1", "a2", "b2"]), ({"queues": [[], ["b"]], "limit": 3}, ["b"]), ({"queues": [["a"]], "limit": 0}, []), ({"queues": [], "limit": 3}, [])],
      ["How much work may one tenant receive in a single round?", "Fairness requires returning to other eligible tenants after one job.", "Use one conditional dequeue per tenant, leaving the outer loop to begin the next round."], ["scheduling", "fairness"]),
    p("lease-owner-release", "A stale owner releases a new lock", "An expired lock holder can delete a lock that another owner has acquired.",
      "Input.ttl is positive. Events have nondecreasing at times and are acquire/release with owner strings. A lock is free at or after expiry. Acquire succeeds only if free, setting expiry=at+ttl. Release succeeds only for the current unexpired owner. Return acceptance booleans.",
      '''
      def solve(data):
          owner, expires, results = None, 0, []
          for event in data["events"]:
              now = event["at"]
              if now >= expires:
                  owner = None
              if event["op"] == "acquire":
                  ok = owner is None
                  if ok:
                      owner, expires = event["owner"], now + data["ttl"]
              else:
                  ok = owner is not None and owner == event["owner"]
                  if ok:
                      owner = None
              results.append(ok)
          return results
      ''', ('owner is not None and owner == event["owner"]', 'owner is not None'),
      [({"ttl": 5, "events": [{"op": "acquire", "owner": "a", "at": 0}, {"op": "release", "owner": "a", "at": 1}]}, [True, True]), ({"ttl": 5, "events": [{"op": "acquire", "owner": "a", "at": 0}, {"op": "acquire", "owner": "b", "at": 5}, {"op": "release", "owner": "a", "at": 6}]}, [True, True, False]), ({"ttl": 1, "events": [{"op": "release", "owner": "a", "at": 0}]}, [False]), ({"ttl": 1, "events": []}, []), ({"ttl": 2, "events": [{"op": "acquire", "owner": "", "at": 0}, {"op": "acquire", "owner": "b", "at": 1}]}, [True, False])],
      ["Does a release belong to the current lease owner?", "Expiry and reacquisition can change ownership while an old worker still runs.", "Compare the releasing owner with the current unexpired owner before clearing the lease."], ["leases", "ownership"], "hard"),
    p("monotonic-fencing-token", "An old worker overwrites newer state", "A storage service accepts writes from stale lease holders because it reverses its fencing comparison.",
      "Input.writes contains {token: positive integer, value: integer}. Start with last_token=0 and value=null. Accept only tokens strictly greater than last_token; accepted writes replace both. Return {accepted, state: {token,value}}. Equal tokens are rejected under this exercise's one-write-per-token contract.",
      '''
      def solve(data):
          token, value, accepted = 0, None, []
          for write in data["writes"]:
              ok = write["token"] > token
              accepted.append(ok)
              if ok:
                  token, value = write["token"], write["value"]
          return {"accepted": accepted, "state": {"token": token, "value": value}}
      ''', ('write["token"] > token', 'write["token"] != token'),
      [({"writes": [{"token": 1, "value": 3}]}, {"accepted": [True], "state": {"token": 1, "value": 3}}), ({"writes": [{"token": 2, "value": 9}, {"token": 1, "value": 4}]}, {"accepted": [True, False], "state": {"token": 2, "value": 9}}), ({"writes": []}, {"accepted": [], "state": {"token": 0, "value": None}}), ({"writes": [{"token": 1, "value": 2}, {"token": 1, "value": 3}]}, {"accepted": [True, False], "state": {"token": 1, "value": 2}}), ({"writes": [{"token": 1, "value": 0}, {"token": 3, "value": -1}]}, {"accepted": [True, True], "state": {"token": 3, "value": -1}})],
      ["Does a different token necessarily represent a newer owner?", "Fencing depends on monotonically increasing ownership generations.", "Accept only a strictly larger token and update the last token atomically with its value."], ["fencing", "stale-writes"], "hard"),
    p("vector-clock-partial-order", "Concurrent updates are forced into an order", "A conflict detector compares vector clocks by total count, hiding concurrent changes.",
      "Input.a and b are nonnegative integer lists of equal length. Return 'equal' if identical, 'before' if a<=b componentwise with some strict component, 'after' for the reverse, or 'concurrent' otherwise. Empty clocks are equal.",
      '''
      def solve(data):
          a, b = data["a"], data["b"]
          if a == b:
              return "equal"
          if all(x <= y for x, y in zip(a, b)):
              return "before"
          if all(x >= y for x, y in zip(a, b)):
              return "after"
          return "concurrent"
      ''', ('all(x <= y for x, y in zip(a, b))', 'sum(a) <= sum(b)'),
      [({"a": [1, 1], "b": [1, 2]}, "before"), ({"a": [2, 0], "b": [0, 3]}, "concurrent"), ({"a": [], "b": []}, "equal"), ({"a": [2, 2], "b": [1, 2]}, "after"), ({"a": [1, 0], "b": [0, 1]}, "concurrent")],
      ["Can one replica advance while another clock component remains behind?", "Vector-clock order is componentwise, not a ranking by sum.", "Require every component to be <= for before and >= for after; mixed directions are concurrent."], ["replication", "vector-clocks"], "hard"),
    p("compare-and-swap-version", "A stale revision overwrites the document", "An optimistic update checks a version only against the initial revision.",
      "Input.version is nonnegative and value is integer. Writes contain {expected: nonnegative version, value: integer}. Accept exactly when expected equals the current version; set value and increment version on success. Return {accepted, state: {version,value}}.",
      '''
      def solve(data):
          version, value, accepted = data["version"], data["value"], []
          for write in data["writes"]:
              ok = write["expected"] == version
              accepted.append(ok)
              if ok:
                  version += 1
                  value = write["value"]
          return {"accepted": accepted, "state": {"version": version, "value": value}}
      ''', ('write["expected"] == version', 'write["expected"] == data["version"]'),
      [({"version": 0, "value": 1, "writes": [{"expected": 0, "value": 2}]}, {"accepted": [True], "state": {"version": 1, "value": 2}}), ({"version": 0, "value": 1, "writes": [{"expected": 0, "value": 2}, {"expected": 0, "value": 3}]}, {"accepted": [True, False], "state": {"version": 1, "value": 2}}), ({"version": 2, "value": 0, "writes": []}, {"accepted": [], "state": {"version": 2, "value": 0}}), ({"version": 1, "value": 5, "writes": [{"expected": 2, "value": 9}]}, {"accepted": [False], "state": {"version": 1, "value": 5}}), ({"version": 0, "value": 0, "writes": [{"expected": 0, "value": 1}, {"expected": 1, "value": 2}]}, {"accepted": [True, True], "state": {"version": 2, "value": 2}})],
      ["Which revision does a later write need to match?", "Each accepted update changes the version that future callers must compare against.", "Compare expected with the current version, then advance the version together with the update."], ["optimistic-concurrency", "versioning"]),
    p("outbox-confirm-before-removal", "A failed publish disappears from the outbox", "An event dispatcher deletes durable work before the broker confirms delivery.",
      "Input.pending contains distinct event IDs in order. Outcomes contains booleans for repeated attempts at the current head. On true, remove and record that head as published; on false keep it for the next attempt. Ignore outcomes once empty. Return {published, state: {pending}}. This is a sequential publisher model, not an exactly-once delivery claim.",
      '''
      def solve(data):
          pending, published = list(data["pending"]), []
          for ok in data["outcomes"]:
              if not pending:
                  break
              event = pending[0]
              if ok:
                  published.append(event)
                  pending.pop(0)
          return {"published": published, "state": {"pending": pending}}
      ''', ('if ok:\n            published.append(event)\n            pending.pop(0)', 'pending.pop(0)\n        if ok:\n            published.append(event)'),
      [({"pending": ["a"], "outcomes": [True]}, {"published": ["a"], "state": {"pending": []}}), ({"pending": ["a", "b"], "outcomes": [False, True]}, {"published": ["a"], "state": {"pending": ["b"]}}), ({"pending": [], "outcomes": [False]}, {"published": [], "state": {"pending": []}}), ({"pending": ["a"], "outcomes": []}, {"published": [], "state": {"pending": ["a"]}}), ({"pending": ["a"], "outcomes": [False, False]}, {"published": [], "state": {"pending": ["a"]}})],
      ["What durable evidence allows deleting pending work?", "A failed attempt leaves the head event pending for retry.", "Remove the event only inside the confirmed-success branch, preserving order on failure."], ["outbox", "durability"], "hard"),
    p("replica-zone-diversity", "Every replica shares one outage zone", "A storage planner selects cheap hosts without maintaining zone diversity.",
      "Input.hosts contains unique {id: ASCII string, zone: string, cost: nonnegative integer}; count is nonnegative. Process hosts by (cost,id), selecting at most one host per zone until count is reached. Return selected IDs in that order, or null if count distinct zones are unavailable. Zero count returns [].",
      '''
      def solve(data):
          chosen, zones = [], set()
          for host in sorted(data["hosts"], key=lambda h: (h["cost"], h["id"])):
              if len(chosen) == data["count"]:
                  break
              if host["zone"] not in zones:
                  zones.add(host["zone"])
                  chosen.append(host["id"])
          return chosen if len(chosen) == data["count"] else None
      ''', ('host["zone"] not in zones', 'True'),
      [({"hosts": [{"id": "a", "zone": "x", "cost": 1}], "count": 1}, ["a"]), ({"hosts": [{"id": "a", "zone": "x", "cost": 1}, {"id": "b", "zone": "x", "cost": 2}, {"id": "c", "zone": "y", "cost": 3}], "count": 2}, ["a", "c"]), ({"hosts": [], "count": 0}, []), ({"hosts": [{"id": "a", "zone": "x", "cost": 1}], "count": 2}, None), ({"hosts": [{"id": "b", "zone": "y", "cost": 1}, {"id": "a", "zone": "x", "cost": 1}], "count": 2}, ["a", "b"])],
      ["Are two hosts in one zone independent against a zone outage?", "Diversity is a mandatory placement gate before accepting another host.", "Track selected zones and skip hosts in a zone already chosen; report infeasibility when too few zones exist."], ["placement", "availability"]),
    p("bounded-admission-queue", "The backlog grows past its admission limit", "A queue accepts work at its configured maximum pending depth.",
      "Input.capacity is nonnegative; events contains 'enqueue' and 'complete'. Start empty. Enqueue succeeds only below capacity and adds one pending job. Complete succeeds only when pending > 0 and removes one. Return {accepted, state: {pending}}.",
      '''
      def solve(data):
          pending, accepted = 0, []
          for event in data["events"]:
              if event == "enqueue":
                  ok = pending < data["capacity"]
                  if ok:
                      pending += 1
              else:
                  ok = pending > 0
                  if ok:
                      pending -= 1
              accepted.append(ok)
          return {"accepted": accepted, "state": {"pending": pending}}
      ''', ('pending < data["capacity"]', 'pending <= data["capacity"]'),
      [({"capacity": 2, "events": ["enqueue", "complete"]}, {"accepted": [True, True], "state": {"pending": 0}}), ({"capacity": 1, "events": ["enqueue", "enqueue"]}, {"accepted": [True, False], "state": {"pending": 1}}), ({"capacity": 0, "events": ["enqueue"]}, {"accepted": [False], "state": {"pending": 0}}), ({"capacity": 1, "events": ["complete", "enqueue", "complete", "enqueue"]}, {"accepted": [False, True, True, True], "state": {"pending": 1}}), ({"capacity": 2, "events": []}, {"accepted": [], "state": {"pending": 0}})],
      ["Would accepting at the limit exceed it after the increment?", "Admission must reserve space for the incoming job.", "Accept enqueue only when pending is strictly below capacity and leave rejected state unchanged."], ["queues", "backpressure"], "easy"),
]
