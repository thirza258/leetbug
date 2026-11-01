"""Ten reporting, funnel, and event-data repairs."""
from functools import partial

from ..common import make

p = partial(make, "data_analytics")

PROBLEMS = [
    p("funnel-step-conversion", "Funnel steps divide by the wrong base",
      "A funnel report divides every step by the first step, so it shows overall conversion for each stage instead of the conversion from the previous stage.",
      "Input.steps is a non-increasing list of nonnegative step counts. For each step after the first, return the percentage of the previous step's count that reached it, rounded to two decimal places. Return 0.0 when the previous step is zero.",
      '''
      def solve(data):
          steps = data["steps"]
          rates = []
          for index in range(1, len(steps)):
              previous = steps[index - 1]
              rates.append(round(steps[index] / previous * 100, 2) if previous else 0.0)
          return rates
      ''', ('previous = steps[index - 1]', 'previous = steps[0]'),
      [({"steps": [1000, 400, 200]}, [40.0, 50.0]), ({"steps": [500, 250, 250, 100]}, [50.0, 100.0, 40.0]), ({"steps": [100]}, []), ({"steps": [10, 0, 0]}, [0.0, 0.0]), ({"steps": [7, 3, 3, 3, 1]}, [42.86, 100.0, 100.0, 33.33]), ({"steps": [0, 0]}, [0.0])],
      ["Is a step's conversion measured against the start of the funnel or the step before it?", "Step conversion describes each transition, so its denominator is the immediately previous step.", "Use steps[index - 1] as the base for the step at index."], ["funnel", "conversion", "product-analytics"], "easy"),
    p("daily-active-users-dedupe", "Daily actives count events, not people",
      "A daily-active report counts event rows instead of distinct users, so a single heavy user can look like a crowd.",
      "Input.events contains {user, day} records in any order. Return [[day, count], ...] sorted by day, where count is the number of distinct users with an event on that day.",
      '''
      def solve(data):
          users = {}
          for event in data["events"]:
              users.setdefault(event["day"], set()).add(event["user"])
          return [[day, len(users[day])] for day in sorted(users)]
      ''', ('users.setdefault(event["day"], set()).add(event["user"])', 'users.setdefault(event["day"], []).append(event["user"])'),
      [({"events": [{"user": "a", "day": 1}, {"user": "a", "day": 1}, {"user": "b", "day": 1}, {"user": "a", "day": 2}]}, [[1, 2], [2, 1]]), ({"events": [{"user": "a", "day": 1}, {"user": "b", "day": 1}, {"user": "c", "day": 1}]}, [[1, 3]]), ({"events": []}, []), ({"events": [{"user": "x", "day": 3}, {"user": "y", "day": 2}, {"user": "x", "day": 2}, {"user": "x", "day": 3}]}, [[2, 2], [3, 1]]), ({"events": [{"user": "a", "day": 1}, {"user": "a", "day": 1}, {"user": "a", "day": 1}]}, [[1, 1]])],
      ["What does a daily-active user metric count for each day?", "A user who opens the app five times still counts once that day, so duplicate events must collapse.", "Collect a set of user identifiers per day and report each set's size."], ["dau", "deduplication", "product-analytics"], "easy"),
    p("session-timeout-gap", "Sessions restart at midnight instead of on idle",
      "A session builder starts a new session only when the calendar day changes, so long silences inside one day remain a single session and midnight splits active users.",
      "Input.events contains {user, at} records sorted by increasing integer at, and input.timeout is a positive integer. An event continues the user's session when its gap from that user's previous event is at most timeout; otherwise it starts a new session. Return {\"sessions\": total session count}.",
      '''
      def solve(data):
          last = {}
          sessions = 0
          for event in data["events"]:
              user, at = event["user"], event["at"]
              if user not in last or at - last[user] > data["timeout"]:
                  sessions += 1
              last[user] = at
          return {"sessions": sessions}
      ''', ('at - last[user] > data["timeout"]', 'at // 86400 != last[user] // 86400'),
      [({"timeout": 150, "events": [{"user": "a", "at": 0}, {"user": "a", "at": 200}, {"user": "a", "at": 250}]}, {"sessions": 2}), ({"timeout": 20, "events": [{"user": "a", "at": 0}, {"user": "b", "at": 5}, {"user": "a", "at": 30}, {"user": "b", "at": 40}]}, {"sessions": 4}), ({"timeout": 10, "events": []}, {"sessions": 0}), ({"timeout": 10, "events": [{"user": "a", "at": 0}, {"user": "a", "at": 10}, {"user": "a", "at": 20}]}, {"sessions": 1}), ({"timeout": 10, "events": [{"user": "a", "at": 0}, {"user": "a", "at": 11}, {"user": "a", "at": 22}]}, {"sessions": 3}), ({"timeout": 100, "events": [{"user": "a", "at": 0}, {"user": "a", "at": 86400}]}, {"sessions": 2})],
      ["What actually separates two sessions?", "Sessions are defined by inactivity, so the gap between consecutive events matters more than the calendar date.", "Compare the current event with the same user's previous event and start a session when the gap exceeds timeout."], ["sessions", "time-windows", "event-data"], "medium"),
    p("day-one-retention-cohort", "Day-one retention counts every return visit",
      "A retention report counts any later activity as day-one retention, so a user who returns on day thirty looks just as engaged as one who returned tomorrow.",
      "Input.signups contains unique {id, day} rows and input.activity contains {id, day} rows. For each signed-up user, they are retained when they have an activity exactly one day after their signup day. Return {\"cohort\": number of signups, \"retained\": retained users, \"rate\": retained divided by cohort times 100 rounded to two decimal places, or 0.0 for an empty cohort}.",
      '''
      def solve(data):
          signup = {row["id"]: row["day"] for row in data["signups"]}
          active = {(row["id"], row["day"]) for row in data["activity"]}
          retained = sum((user, day + 1) in active for user, day in signup.items())
          size = len(signup)
          return {"cohort": size, "retained": retained, "rate": round(retained / size * 100, 2) if size else 0.0}
      ''', ('retained = sum((user, day + 1) in active for user, day in signup.items())', 'retained = sum(any(row["id"] == user and row["day"] > day for row in data["activity"]) for user, day in signup.items())'),
      [({"signups": [{"id": "u1", "day": 1}, {"id": "u2", "day": 1}], "activity": [{"id": "u1", "day": 2}, {"id": "u2", "day": 5}]}, {"cohort": 2, "retained": 1, "rate": 50.0}), ({"signups": [{"id": "u1", "day": 0}, {"id": "u2", "day": 0}, {"id": "u3", "day": 3}], "activity": [{"id": "u1", "day": 1}, {"id": "u2", "day": 2}, {"id": "u3", "day": 4}]}, {"cohort": 3, "retained": 2, "rate": 66.67}), ({"signups": [{"id": "a", "day": 5}], "activity": []}, {"cohort": 1, "retained": 0, "rate": 0.0}), ({"signups": [{"id": "a", "day": 0}, {"id": "b", "day": 0}], "activity": [{"id": "a", "day": 1}, {"id": "b", "day": 1}]}, {"cohort": 2, "retained": 2, "rate": 100.0}), ({"signups": [{"id": "a", "day": 2}, {"id": "b", "day": 2}], "activity": [{"id": "a", "day": 3}, {"id": "b", "day": 4}]}, {"cohort": 2, "retained": 1, "rate": 50.0}), ({"signups": [], "activity": []}, {"cohort": 0, "retained": 0, "rate": 0.0})],
      ["Should a user active on day thirty count toward day-one retention?", "A retention interval names one specific day after signup; activity on any other day answers a different question.", "Look for an activity row whose user matches and whose day is exactly signup day plus one."], ["retention", "cohorts", "product-analytics"], "medium"),
    p("weighted-conversion-rate", "Averaging channel rates ignores traffic",
      "A conversion summary averages each channel's percentage, so a tiny channel with one lucky visitor can outweigh a large channel with steady demand.",
      "Input.groups contains {visits, conversions} rows with nonnegative integers. Return the overall conversion rate: total conversions divided by total visits times 100, rounded to two decimal places, or 0.0 when there are no visits.",
      '''
      def solve(data):
          numerator = sum(row["conversions"] * 100 for row in data["groups"])
          denominator = sum(row["visits"] for row in data["groups"])
          return round(numerator / denominator, 2) if denominator else 0.0
      ''', ('numerator / denominator', 'sum(row["conversions"] / row["visits"] * 100 for row in data["groups"] if row["visits"]) / sum(1 for row in data["groups"] if row["visits"])'),
      [({"groups": [{"visits": 100, "conversions": 10}, {"visits": 300, "conversions": 90}]}, 25.0), ({"groups": [{"visits": 1000, "conversions": 1}, {"visits": 10, "conversions": 5}]}, 0.59), ({"groups": []}, 0.0), ({"groups": [{"visits": 10, "conversions": 10}]}, 100.0), ({"groups": [{"visits": 0, "conversions": 0}, {"visits": 50, "conversions": 25}]}, 50.0), ({"groups": [{"visits": 2, "conversions": 2}, {"visits": 1000, "conversions": 1}]}, 0.3)],
      ["Should two channels with different traffic counts contribute equally to one conversion rate?", "An aggregate rate weights each channel by its traffic; averaging percentages gives a one-visit channel the same influence as a thousand-visit channel.", "Sum conversions and visits across groups before dividing, rather than averaging per-group percentages."], ["conversion", "weighting", "aggregation"], "easy"),
    p("percentile-nearest-rank", "The percentile rounds down to a smaller value",
      "A percentile helper uses floor instead of ceiling on the rank, so any percentile that does not land exactly on a row returns the value below it.",
      "Input.values is a nonempty list of integers and input.p is an integer from 1 through 100. Use the nearest-rank definition: sort the values and take the value at rank ceil(p * n / 100), counting from 1. Return that value.",
      '''
      import math
      def solve(data):
          ordered = sorted(data["values"])
          rank = math.ceil(data["p"] * len(ordered) / 100)
          return ordered[max(0, rank - 1)]
      ''', ('rank = math.ceil(data["p"] * len(ordered) / 100)', 'rank = len(ordered) * data["p"] // 100'),
      [({"values": [10, 20, 30, 40], "p": 60}, 30), ({"values": [5, 1, 3], "p": 50}, 3), ({"values": [7], "p": 1}, 7), ({"values": [1, 2, 3, 4, 5], "p": 100}, 5), ({"values": [1, 2, 3, 4, 5, 6, 7], "p": 99}, 7), ({"values": [10, 20, 30, 40], "p": 25}, 10)],
      ["When the percentile rank falls between two rows, which row should nearest-rank select?", "Nearest-rank always moves upward to the next whole rank, which is the ceiling of p * n / 100.", "Ceil the rank before converting from one-based rank to zero-based index."], ["percentiles", "statistics", "aggregation"], "medium"),
    p("timezone-day-buckets", "Late-night events land on the wrong day",
      "A daily report buckets UTC timestamps directly, so events after the local evening boundary are attributed to the next or previous calendar day.",
      "Input.events contains {at} UTC epoch-second integers, and input.offset_hours is the local offset from UTC. Bucket each event by floor((at + offset_hours * 3600) / 86400). Return [[day, count], ...] sorted by day.",
      '''
      def solve(data):
          counts = {}
          for event in data["events"]:
              day = (event["at"] + data["offset_hours"] * 3600) // 86400
              counts[day] = counts.get(day, 0) + 1
          return [[day, counts[day]] for day in sorted(counts)]
      ''', ('(event["at"] + data["offset_hours"] * 3600)', 'event["at"]'),
      [({"offset_hours": 2, "events": [{"at": 82800}, {"at": 90000}, {"at": 3600}]}, [[0, 1], [1, 2]]), ({"offset_hours": -5, "events": [{"at": 3600}, {"at": 43200}]}, [[-1, 1], [0, 1]]), ({"offset_hours": 2, "events": []}, []), ({"offset_hours": 0, "events": [{"at": 0}, {"at": 86400}]}, [[0, 1], [1, 1]]), ({"offset_hours": 14, "events": [{"at": 0}, {"at": 82800}]}, [[0, 1], [1, 1]]), ({"offset_hours": -12, "events": [{"at": 0}, {"at": 43200}]}, [[-1, 1], [0, 1]])],
      ["Which timestamp belongs to the report's calendar day?", "A local day boundary is shifted by the offset; the UTC day number alone is the wrong bucket.", "Add the offset in seconds before performing floor division by 86400."], ["timezones", "bucketing", "event-data"], "medium"),
    p("weekly-growth-baseline", "Growth divides by this week's total",
      "A growth report subtracts last week's total but divides the change by this week's total, so a decline can look worse than it is and a recovery can look smaller.",
      "Input.daily is a list of daily totals with at least 14 entries. Compare the sum of the last seven entries with the sum of the seven before them. Return {\"previous\": previous total, \"current\": current total, \"growth\": percent change rounded to two decimal places, using 0.0 when the previous total is zero}.",
      '''
      def solve(data):
          daily = data["daily"]
          previous = sum(daily[-14:-7])
          current = sum(daily[-7:])
          growth = round((current - previous) / previous * 100, 2) if previous else 0.0
          return {"previous": previous, "current": current, "growth": growth}
      ''', ('(current - previous) / previous', '(current - previous) / current'),
      [({"daily": [1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2]}, {"previous": 7, "current": 14, "growth": 100.0}), ({"daily": [10, 10, 10, 10, 10, 10, 10, 5, 5, 5, 5, 5, 5, 5]}, {"previous": 70, "current": 35, "growth": -50.0}), ({"daily": [0, 0, 0, 0, 0, 0, 0, 3, 3, 3, 3, 3, 3, 3]}, {"previous": 0, "current": 21, "growth": 0.0}), ({"daily": [2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2]}, {"previous": 14, "current": 14, "growth": 0.0}), ({"daily": [3, 3, 3, 3, 3, 3, 3, 6, 6, 6, 6, 6, 6, 6]}, {"previous": 21, "current": 42, "growth": 100.0}), ({"daily": [5, 5, 5, 5, 5, 5, 5, 4, 4, 4, 4, 4, 4, 4]}, {"previous": 35, "current": 28, "growth": -20.0})],
      ["What is the baseline for a week-over-week percent change?", "Percent change expresses the difference as a fraction of the earlier value, so the previous week is the denominator.", "Divide the change by the previous total rather than the current total."], ["growth", "time-series", "reporting"], "easy"),
    p("first-touch-attribution", "Attribution credits the last touch",
      "A marketing report assigns a conversion to the user's latest touch, so a closing reminder receives credit that belongs to the campaign that first found the customer.",
      "Input.conversions contains {user, day} rows and input.touches contains {user, channel, day} rows. Attribute each conversion to the user's earliest touch on or before the conversion day; break same-day ties by the alphabetically smaller channel. Ignore conversions with no eligible touch. Return {\"channels\": [[channel, count], ...]} sorted by channel.",
      '''
      def solve(data):
          counts = {}
          for conversion in data["conversions"]:
              candidates = [t for t in data["touches"]
                            if t["user"] == conversion["user"] and t["day"] <= conversion["day"]]
              if candidates:
                  chosen = min(candidates, key=lambda t: (t["day"], t["channel"]))["channel"]
                  counts[chosen] = counts.get(chosen, 0) + 1
          return {"channels": [[channel, counts[channel]] for channel in sorted(counts)]}
      ''', ('min(candidates', 'max(candidates'),
      [({"conversions": [{"user": "a", "day": 5}], "touches": [{"user": "a", "channel": "search", "day": 1}, {"user": "a", "channel": "social", "day": 5}]}, {"channels": [["search", 1]]}), ({"conversions": [{"user": "a", "day": 3}, {"user": "b", "day": 2}], "touches": [{"user": "a", "channel": "search", "day": 1}, {"user": "a", "channel": "email", "day": 3}, {"user": "b", "channel": "social", "day": 1}, {"user": "b", "channel": "email", "day": 2}]}, {"channels": [["search", 1], ["social", 1]]}), ({"conversions": [{"user": "a", "day": 1}], "touches": [{"user": "a", "channel": "email", "day": 2}]}, {"channels": []}), ({"conversions": [{"user": "a", "day": 3}], "touches": [{"user": "a", "channel": "email", "day": 1}, {"user": "a", "channel": "email", "day": 3}, {"user": "a", "channel": "social", "day": 3}]}, {"channels": [["email", 1]]}), ({"conversions": [], "touches": [{"user": "a", "channel": "x", "day": 1}]}, {"channels": []}), ({"conversions": [{"user": "a", "day": 5}, {"user": "b", "day": 1}], "touches": [{"user": "a", "channel": "x", "day": 1}, {"user": "a", "channel": "y", "day": 2}, {"user": "b", "channel": "z", "day": 1}]}, {"channels": [["x", 1], ["z", 1]]})],
      ["Which touch should receive credit for a conversion?", "First-touch attribution credits the campaign that introduced the customer, not the most recent reminder.", "Choose the minimum eligible touch by day, using the channel name to settle same-day ties."], ["attribution", "marketing", "event-data"], "hard"),
    p("retry-duplicate-events", "Retried events inflate the totals",
      "An ingestion job deduplicates on event type instead of event id, so a retry is dropped only when the whole type has been seen and repeated ids of different types are still counted.",
      "Input.events contains {id, type} records with possible repeated ids. Keep only the first occurrence of each id, then count the kept events by type. Return {\"counts\": [[type, count], ...]} sorted by type.",
      '''
      def solve(data):
          seen = set()
          counts = {}
          for event in data["events"]:
              if event["id"] in seen:
                  continue
              seen.add(event["id"])
              counts[event["type"]] = counts.get(event["type"], 0) + 1
          return {"counts": [[kind, counts[kind]] for kind in sorted(counts)]}
      ''', ('seen.add(event["id"])', 'seen.add(event["type"])'),
      [({"events": [{"id": "e1", "type": "view"}, {"id": "e1", "type": "view"}, {"id": "e2", "type": "view"}, {"id": "e3", "type": "click"}]}, {"counts": [["click", 1], ["view", 2]]}), ({"events": [{"id": "a", "type": "view"}, {"id": "a", "type": "click"}]}, {"counts": [["view", 1]]}), ({"events": []}, {"counts": []}), ({"events": [{"id": "1", "type": "x"}, {"id": "1", "type": "y"}, {"id": "2", "type": "x"}, {"id": "1", "type": "z"}]}, {"counts": [["x", 2]]}), ({"events": [{"id": "a", "type": "p"}, {"id": "b", "type": "p"}, {"id": "b", "type": "p"}]}, {"counts": [["p", 2]]}), ({"events": [{"id": "a", "type": "m"}, {"id": "a", "type": "m"}, {"id": "a", "type": "n"}]}, {"counts": [["m", 1]]})],
      ["What makes two ingested events the same logical event?", "Retries repeat the same event id, so identity belongs to the id rather than the event type.", "Track seen ids and skip a record only when its own id has already appeared."], ["deduplication", "events", "reporting"], "easy"),
]
