"""Incident: daily digests drift an hour after daylight-saving changes (time handling, level 1)."""
from app.catalog import case, code
from app.incidents.catalog_common import artifact, event, log, series, span, text_artifact

STARTER = code('''
    from datetime import datetime, timedelta

    FORMAT = "%Y-%m-%dT%H:%M:%SZ"


    def parse_utc(text):
        return datetime.strptime(text, FORMAT)


    def offset_at(zone, instant):
        """UTC offset in minutes in effect at a UTC instant, from the zone's transition table."""
        offset = zone["standard_offset"]
        for transition in sorted(zone["transitions"], key=lambda item: item["at"]):
            if instant >= parse_utc(transition["at"]):
                offset = transition["offset"]
        return offset


    def local_to_utc(zone, local):
        """Convert a local wall-clock time to UTC with the offset in effect at that moment.

        Schedules never use a local time inside a clock-change hour, so exactly one offset matches.
        """
        offsets = sorted({zone["standard_offset"], *(item["offset"] for item in zone["transitions"])})
        for offset in offsets:
            instant = local - timedelta(minutes=offset)
            if offset_at(zone, instant) == offset:
                return instant
        raise ValueError("local time falls inside a clock change")


    def plan_runs(subscription, zone, start_date, days):
        """UTC instants of the daily runs for `days` local dates starting at `start_date`."""
        hour, minute = map(int, subscription["local_time"].split(":"))
        first = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=hour, minute=minute)
        # Offset captured when the subscription was created; saves a zone lookup per run.
        offset = timedelta(minutes=subscription["utc_offset_minutes"])
        return [first + timedelta(days=day) - offset for day in range(days)]


    def solve(data):
        runs = {}
        for subscription in data["subscriptions"]:
            zone = data["zones"][subscription["zone"]]
            planned = plan_runs(subscription, zone, data["start_date"], data["days"])
            runs[subscription["id"]] = [run.strftime(FORMAT) for run in planned]
        return {"runs": runs}
''')

SOLUTION = STARTER.replace('''    # Offset captured when the subscription was created; saves a zone lookup per run.
    offset = timedelta(minutes=subscription["utc_offset_minutes"])
    return [first + timedelta(days=day) - offset for day in range(days)]
''', '''    # The offset depends on the date: convert each local run time with the zone rules in effect
    # then. utc_offset_minutes is only the offset on the day the subscription was created.
    return [local_to_utc(zone, first + timedelta(days=day)) for day in range(days)]
''')
assert SOLUTION != STARTER

ZONES = {
    "Europe/Berlin": {"standard_offset": 60, "transitions": [{"at": "2026-03-29T01:00:00Z", "offset": 120},
                                                              {"at": "2026-10-25T01:00:00Z", "offset": 60}]},
    "America/New_York": {"standard_offset": -300, "transitions": [{"at": "2026-03-08T07:00:00Z", "offset": -240},
                                                                   {"at": "2026-11-01T06:00:00Z", "offset": -300}]},
    "Asia/Tokyo": {"standard_offset": 540, "transitions": []},
}


def _subscription(identifier, zone, local_time, stored_offset):
    return {"id": identifier, "zone": zone, "local_time": local_time, "utc_offset_minutes": stored_offset}


def _plan(subscriptions, start_date, days):
    return {"zones": ZONES, "subscriptions": subscriptions, "start_date": start_date, "days": days}


DIGEST = _subscription("sub-ops-digest", "Europe/Berlin", "09:00", 60)

TESTS = [
    case("Winter week in Berlin", _plan([DIGEST], "2026-03-02", 3),
         {"runs": {"sub-ops-digest": ["2026-03-02T08:00:00Z", "2026-03-03T08:00:00Z", "2026-03-04T08:00:00Z"]}}),
    case("Spring forward in Berlin", _plan([DIGEST], "2026-03-27", 4),
         {"runs": {"sub-ops-digest": ["2026-03-27T08:00:00Z", "2026-03-28T08:00:00Z", "2026-03-29T07:00:00Z",
                                      "2026-03-30T07:00:00Z"]}},
         assertions=[{"path": "runs.sub-ops-digest.2", "equals": "2026-03-29T07:00:00Z"}]),
    case("Fall back for a summer subscriber",
         _plan([_subscription("sub-berlin-early", "Europe/Berlin", "07:30", 120)], "2026-10-23", 4),
         {"runs": {"sub-berlin-early": ["2026-10-23T05:30:00Z", "2026-10-24T05:30:00Z", "2026-10-25T06:30:00Z",
                                        "2026-10-26T06:30:00Z"]}}, True),
    case("New York spring forward",
         _plan([_subscription("sub-ny-standup", "America/New_York", "08:00", -300)], "2026-03-06", 4),
         {"runs": {"sub-ny-standup": ["2026-03-06T13:00:00Z", "2026-03-07T13:00:00Z", "2026-03-08T12:00:00Z",
                                      "2026-03-09T12:00:00Z"]}}, True),
    case("Zone without daylight saving",
         _plan([_subscription("sub-tokyo-kpi", "Asia/Tokyo", "08:00", 540)], "2026-03-27", 3),
         {"runs": {"sub-tokyo-kpi": ["2026-03-26T23:00:00Z", "2026-03-27T23:00:00Z", "2026-03-28T23:00:00Z"]}}, True),
    case("Several subscribers across zones",
         _plan([_subscription("sub-berlin", "Europe/Berlin", "09:00", 60),
                _subscription("sub-ny", "America/New_York", "08:00", -300),
                _subscription("sub-tokyo", "Asia/Tokyo", "08:00", 540)], "2026-03-28", 2),
         {"runs": {"sub-berlin": ["2026-03-28T08:00:00Z", "2026-03-29T07:00:00Z"],
                   "sub-ny": ["2026-03-28T12:00:00Z", "2026-03-29T12:00:00Z"],
                   "sub-tokyo": ["2026-03-27T23:00:00Z", "2026-03-28T23:00:00Z"]}}, True),
    case("Late-evening run crosses the UTC date",
         _plan([_subscription("sub-night-batch", "Europe/Berlin", "23:30", 60)], "2026-03-28", 2),
         {"runs": {"sub-night-batch": ["2026-03-28T22:30:00Z", "2026-03-29T21:30:00Z"]}}, True),
    case("No days requested", _plan([DIGEST], "2026-03-27", 0), {"runs": {"sub-ops-digest": []}}, True),
    case("Summer subscriber in winter",
         _plan([_subscription("sub-summer-signup", "Europe/Berlin", "09:00", 120)], "2026-01-12", 2),
         {"runs": {"sub-summer-signup": ["2026-01-12T08:00:00Z", "2026-01-13T08:00:00Z"]}}, True),
]

LOGS = sorted([
    log("2026-03-10T09:01:12.330Z", "INFO", "report-scheduler", "service started", None, version="2026.03.10-1"),
    log("2026-03-10T09:02:40.912Z", "INFO", "report-scheduler", "backfill complete", None, subscriptions=1840,
        source="offset in effect at created_at"),
    log("2026-03-09T12:00:00.204Z", "INFO", "report-scheduler", "run planned", "t-s001", subscription="sub-ny-standup",
        zone="America/New_York", local_time="08:00", run_at="2026-03-09T12:00:00Z"),
    log("2026-03-09T12:00:02.840Z", "INFO", "report-sender", "digest sent", "t-s001", subscription="sub-ny-standup",
        delivered_local="08:00 EDT"),
    log("2026-03-11T13:00:00.418Z", "INFO", "report-scheduler", "run planned", "t-s020", subscription="sub-ny-standup",
        zone="America/New_York", local_time="08:00", stored_offset=-300, run_at="2026-03-11T13:00:00Z"),
    log("2026-03-11T13:00:03.105Z", "INFO", "report-sender", "digest sent", "t-s020", subscription="sub-ny-standup",
        delivered_local="09:00 EDT"),
    log("2026-03-11T14:20:00.000Z", "INFO", "support", "ticket opened", None, topic="digest arrives at 9:00 instead "
        "of 8:00 (US Eastern)", resolution="attributed to email delays"),
    log("2026-03-28T08:00:00.211Z", "INFO", "report-scheduler", "run planned", "t-s090", subscription="sub-ops-digest",
        zone="Europe/Berlin", local_time="09:00", stored_offset=60, run_at="2026-03-28T08:00:00Z"),
    log("2026-03-28T08:00:02.507Z", "INFO", "report-sender", "digest sent", "t-s090", subscription="sub-ops-digest",
        delivered_local="09:00 CET"),
    log("2026-03-29T08:00:00.198Z", "INFO", "report-scheduler", "run planned", "t-s100", subscription="sub-ops-digest",
        zone="Europe/Berlin", local_time="09:00", stored_offset=60, run_at="2026-03-29T08:00:00Z"),
    log("2026-03-29T08:00:02.611Z", "INFO", "report-sender", "digest sent", "t-s100", subscription="sub-ops-digest",
        delivered_local="10:00 CEST"),
    log("2026-03-29T23:00:00.120Z", "INFO", "report-scheduler", "run planned", "t-s110", subscription="sub-tokyo-kpi",
        zone="Asia/Tokyo", local_time="08:00", stored_offset=540, run_at="2026-03-29T23:00:00Z"),
    log("2026-03-29T23:00:02.300Z", "INFO", "report-sender", "digest sent", "t-s110", subscription="sub-tokyo-kpi",
        delivered_local="08:00 JST"),
    log("2026-03-30T06:30:00.144Z", "INFO", "report-scheduler", "run planned", "t-s120",
        subscription="sub-berlin-finance", zone="Europe/Berlin", local_time="07:30", stored_offset=60,
        run_at="2026-03-30T06:30:00Z"),
    log("2026-03-30T06:30:02.090Z", "INFO", "report-sender", "digest sent", "t-s120",
        subscription="sub-berlin-finance", delivered_local="08:30 CEST"),
    log("2026-03-30T08:40:00.000Z", "WARN", "support", "ticket spike", None, tickets=42, topic="late daily digest"),
], key=lambda entry: entry["ts"])

DAILY = "2026-03-08T00:00:00Z"
ARTIFACTS = [
    artifact("scheduler-logs", "logs", "Scheduler and sender logs",
             "Planning and delivery logs for sample subscriptions, 9–30 March.", {"entries": LOGS}),
    artifact("scheduler-metrics", "metrics", "Digest delivery", "Daily counts from 8 to 31 March 2026.", {
        "series": [
            series("digests_delivered_late_us", "digests per day", DAILY, 1440,
                   [0, 0, 311, 312, 311, 310, 311, 311, 312, 311, 311, 310, 311, 312, 311, 311, 311, 312, 311, 310,
                    311, 311, 312, 311]),
            series("digests_delivered_late_eu", "digests per day", DAILY, 1440, [0] * 21 + [612, 613, 612]),
            series("support_tickets_late_digest", "tickets per day", DAILY, 1440,
                   [0, 0, 0, 3, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 9, 42, 15]),
        ],
        "annotations": [
            {"at": "2026-03-08T07:00:00Z", "label": "US daylight saving time starts"},
            {"at": "2026-03-10T09:00:00Z", "label": "Deploy report-scheduler 2026.03.10-1"},
            {"at": "2026-03-29T01:00:00Z", "label": "EU summer time starts"},
        ]}),
    artifact("scheduler-traces", "traces", "Run planning before and after the deploy",
             "t-s001 planned a New York run on 9 March; t-s100 planned a Berlin run on 29 March.", {"traces": [
                 {"trace_id": "t-s001", "spans": [
                     span("t-s001-1", None, "report-scheduler", "plan_runs", 0, 4.1, subscription="sub-ny-standup"),
                     span("t-s001-2", "t-s001-1", "subscriptions-db", "SELECT subscription", 0.3, 1.2),
                     span("t-s001-3", "t-s001-1", "report-scheduler", "zone_rules.local_to_utc", 1.8, 0.9,
                          zone="America/New_York", offset_minutes=-240, run_at="2026-03-09T12:00:00Z"),
                 ]},
                 {"trace_id": "t-s100", "spans": [
                     span("t-s100-1", None, "report-scheduler", "plan_runs", 0, 1.9, subscription="sub-ops-digest",
                          stored_offset_minutes=60, run_at="2026-03-29T08:00:00Z"),
                     span("t-s100-2", "t-s100-1", "subscriptions-db", "SELECT subscription", 0.3, 1.1),
                 ]},
             ]}),
    artifact("scheduler-db", "database", "Subscriptions and recent runs", "Snapshot taken on 30 March.", {"tables": [
        {"name": "subscriptions", "columns": ["id", "zone", "local_time", "utc_offset_minutes", "created_at"],
         "rows": [["sub-ops-digest", "Europe/Berlin", "09:00", 60, "2026-01-14T10:22:00Z"],
                  ["sub-berlin-finance", "Europe/Berlin", "07:30", 60, "2026-02-02T08:01:00Z"],
                  ["sub-ny-standup", "America/New_York", "08:00", -300, "2026-01-20T15:40:00Z"],
                  ["sub-tokyo-kpi", "Asia/Tokyo", "08:00", 540, "2026-02-11T00:12:00Z"]]},
        {"name": "runs", "columns": ["subscription_id", "planned_run_utc", "delivered_local"],
         "rows": [["sub-ny-standup", "2026-03-09T12:00:00Z", "08:00 EDT"],
                  ["sub-ny-standup", "2026-03-11T13:00:00Z", "09:00 EDT"],
                  ["sub-ops-digest", "2026-03-28T08:00:00Z", "09:00 CET"],
                  ["sub-ops-digest", "2026-03-29T08:00:00Z", "10:00 CEST"],
                  ["sub-tokyo-kpi", "2026-03-29T23:00:00Z", "08:00 JST"],
                  ["sub-berlin-finance", "2026-03-30T06:30:00Z", "08:30 CEST"]]},
    ]}),
    text_artifact("scheduler-config", "config", "report-scheduler configuration", "Deployed configuration.",
                  "deploy/report-scheduler.yaml", "yaml", '''
service: report-scheduler
version: 2026.03.10-1
planning_horizon_days: 7
zone_rules: zones-2026a.json     # standard offsets and transitions per zone
database:
  host: subscriptions-db.internal
sender:
  queue: digest-runs
'''),
    artifact("deploy-2026-03-10-1", "diff", "Deploy 2026.03.10-1: store the UTC offset per subscription",
             "Deployed 2026-03-10 09:00 UTC with a backfill migration.", {
                 "title": "Store each subscription's UTC offset to skip zone lookups", "author": "dev-reports-team",
                 "content": '''
--- a/scheduler/planning.py
+++ b/scheduler/planning.py
@@ -38,4 +38,6 @@ def plan_runs(subscription, zone, start_date, days):
     hour, minute = map(int, subscription["local_time"].split(":"))
     first = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=hour, minute=minute)
-    return [local_to_utc(zone, first + timedelta(days=day)) for day in range(days)]
+    # Offset captured when the subscription was created; saves a zone lookup per run.
+    offset = timedelta(minutes=subscription["utc_offset_minutes"])
+    return [first + timedelta(days=day) - offset for day in range(days)]
--- /dev/null
+++ b/migrations/0042_subscription_offset.sql
@@ -0,0 +1,3 @@
+ALTER TABLE subscriptions ADD COLUMN utc_offset_minutes integer;
+-- Backfill with the offset in effect when each subscription was created.
+UPDATE subscriptions SET utc_offset_minutes = zone_offset_at(zone, created_at);
'''.strip("\n") + "\n"}),
    artifact("scheduler-architecture", "architecture", "Digest pipeline", "How daily digests are planned and sent.", {
        "nodes": [
            {"id": "web", "label": "web-app (subscription settings)", "kind": "service"},
            {"id": "db", "label": "subscriptions-db", "kind": "database"},
            {"id": "scheduler", "label": "report-scheduler", "kind": "service"},
            {"id": "queue", "label": "digest-runs queue", "kind": "queue"},
            {"id": "sender", "label": "report-sender", "kind": "service"},
            {"id": "mail", "label": "mail relay", "kind": "external"},
        ],
        "edges": [
            {"from": "web", "to": "db", "label": "zone and local time"},
            {"from": "scheduler", "to": "db", "label": "read subscriptions"},
            {"from": "scheduler", "to": "queue", "label": "planned runs (UTC)"},
            {"from": "queue", "to": "sender", "label": "due runs"},
            {"from": "sender", "to": "mail", "label": "send digest"},
        ]}),
]

INCIDENT = {
    "slug": "scheduler-dst-shift",
    "title": "Daily digests arrive an hour late after the clock change",
    "summary": "After Europe moved to summer time, the 09:00 operations digest started arriving at 10:00. US "
               "subscribers had quietly been receiving theirs an hour late for three weeks.",
    "severity": "SEV-3",
    "level": 1,
    "category": "time_handling",
    "taxonomy": {"bug_categories": ["time_handling", "configuration"],
                 "skills": ["state_inspection", "log_investigation", "reproduction", "regression_testing"]},
    "affected_services": ["report-scheduler"],
    "impact": [
        "About 600 subscribers in Europe and 310 in the US received daily digests an hour late.",
        "Teams that start their day with the digest worked from stale numbers.",
        "Support received 42 tickets on the first workday after the clock change.",
    ],
    "expected_behavior": "Each digest runs at the subscriber's chosen local time every day of the year, before and "
                         "after daylight-saving changes.",
    "observed_symptoms": [
        "Berlin digests planned for 09:00 are delivered at 10:00 CEST from 29 March.",
        "New York digests planned for 08:00 are delivered at 09:00 EDT since 10 March.",
        "Tokyo subscribers are unaffected.",
    ],
    "objective": "Find why runs drift by an hour, fix plan_runs() so every run uses the correct offset for its "
                 "date, and describe how to correct the stored data.",
    "timeline": [
        event("2026-03-08T07:00:00Z", "note", "US daylight saving time starts", "Eastern time moves to UTC-4."),
        event("2026-03-10T09:00:00Z", "deploy", "report-scheduler 2026.03.10-1",
              "Stores each subscription's UTC offset (backfilled from its creation time) and plans runs without "
              "zone lookups."),
        event("2026-03-11T14:20:00Z", "symptom", "US subscribers report late digests",
              "Three tickets say the 08:00 digest arrives at 09:00 Eastern; attributed to email delays."),
        event("2026-03-29T01:00:00Z", "note", "EU summer time starts", "Central European time moves to UTC+2."),
        event("2026-03-29T08:00:00Z", "symptom", "Berlin digests sent at 10:00 local",
              "The 09:00 digest is planned for 08:00 UTC, which is now 10:00 in Berlin."),
        event("2026-03-30T08:40:00Z", "alert", "Support ticket spike", "42 tickets about late daily digests."),
    ],
    "artifacts": ARTIFACTS,
    "scenarios": [
        {"id": "winter-baseline", "name": "Winter week in Berlin",
         "description": "No clock change in range: runs are correct.", "tests": ["Winter week in Berlin"]},
        {"id": "spring-forward", "name": "Spring forward in Berlin",
         "description": "Plan across 29 March, when Berlin moves to UTC+2.", "tests": ["Spring forward in Berlin"]},
    ],
    "rubric": {
        "version": 1, "source": "authored",
        "defect_categories": ["time_handling"],
        "related_categories": ["configuration", "logic_error"],
        "root_cause": [
            ["offset", "utc offset", "utc_offset_minutes", "fixed offset", "stored offset"],
            ["stored", "cached", "captured", "saved", "at creation", "when the subscription was created", "backfill",
             "signup"],
            ["daylight saving", "dst", "summer time", "clock change", "transition"],
            ["target date", "each run", "run date", "every date", "per date", "changes during the year",
             "depends on the date"],
        ],
        "component": ["plan_runs", "utc_offset_minutes", "local_to_utc", "offset_at"],
        "invariant": [
            ["same local time", "local time", "wall clock", "09:00 local", "local wall time"],
            ["every day", "each day", "all year", "year-round", "across dst", "after the change", "every run"],
        ],
        "correction": [
            ["offset for the date", "offset in effect", "offset_at", "per run", "for each run", "each date",
             "local_to_utc"],
            ["zone rules", "transitions", "time zone", "timezone", "zone table"],
            ["do not store", "don't store", "stop using the stored", "ignore the stored", "instead of the stored",
             "not the stored"],
        ],
        "reproduction": [
            ["dst", "transition", "spring forward", "clock change", "march 29", "fall back", "29 march"],
            ["plan runs", "schedule", "next runs", "dates spanning", "across", "several days"],
            ["09:00", "local time", "hour early", "hour late", "an hour off", "07:00", "08:00"],
        ],
    },
    "evaluation": {
        "remediation_concepts": [
            ["reschedule", "recompute", "replan", "backfill"],
            ["notify", "customers", "resend", "status page"],
            ["hotfix", "rollback", "revert", "deploy the fix"],
            ["data migration", "update subscriptions", "drop the column", "clear the stored offset"],
        ],
        "prevention_concepts": [
            ["test", "dst test", "transition test", "clock change test", "regression test"],
            ["store the zone", "zone name", "do not store offsets", "never store offsets"],
            ["tz database", "zoneinfo", "library", "zone rules"],
            ["monitor", "alert", "delivery time", "drift"],
        ],
        "impact_concepts": [
            ["hour late", "hour early", "wrong time", "an hour off", "late"],
            ["subscribers", "customers", "digests", "reports"],
            ["europe", "us", "new york", "berlin", "dst zones"],
            ["tickets", "complaints", "stale numbers"],
        ],
    },
    "problem": {
        "title": "Incident: the digest that moved with the clocks",
        "summary": "Daily runs use an offset stored when each subscription was created, so they drift by an hour "
                   "after a daylight-saving change. Plan every run at the right local time.",
        "category": "edge",
        "difficulty": "easy",
        "tags": ["time-zones", "scheduling", "dates", "configuration"],
        "requirements": [
            "Input has zones (standard_offset in minutes and UTC transitions [{at, offset}]), subscriptions [{id, "
            "zone, local_time \"HH:MM\", utc_offset_minutes}], start_date and days.",
            "Plan one run for each of the days local dates starting at start_date, at the subscription's local_time "
            "in its zone.",
            "Use the UTC offset in effect at each run. utc_offset_minutes is only the offset on the day the "
            "subscription was created. Local times inside a clock-change hour are not used.",
            "Return {runs: {subscription id: [UTC instants formatted YYYY-MM-DDTHH:MM:SSZ]}}.",
        ],
        "starters": {"python": STARTER},
        "solutions": {"python": SOLUTION},
        "tests": TESTS,
        "explanation": "The deploy stored each subscription's UTC offset from its creation time, and plan_runs() "
                       "subtracted that fixed offset from every local run time. After a daylight-saving change the "
                       "zone's offset differs from the stored one, so runs drift an hour in local time: New York "
                       "from 10 March and Berlin from 29 March. Converting each run's local wall time with the zone "
                       "rules in effect on that date (local_to_utc) keeps runs at the same local time all year. "
                       "Time O(d * t) for d days and t transitions.",
        "hints": [
            "Digests were on time in winter and an hour late after the clock change. What changed on that date?",
            "Look at the subscriptions table and the planning traces. Which offset does the scheduler use, and when "
            "was it recorded?",
            "plan_runs() subtracts the offset stored at signup for every date. Convert each local run time with "
            "local_to_utc() so the offset in effect on that date is used.",
        ],
        "minutes": 20,
    },
}
