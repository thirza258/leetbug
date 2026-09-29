"""Ten business-rule and workflow repairs with explicit state expectations."""
from functools import partial

from ..common import make

p = partial(make, "business")

PROBLEMS = [
    p("explicit-deny-precedence", "An explicit deny is overruled by a broad allow", "A permission check trusts the first matching policy rule, so a wildcard allow listed before a specific deny grants access the deny was meant to block.",
      "Input.rules contains {effect: 'allow'|'deny', action: string} objects; the action '*' matches every action. Input.requests contains concrete action strings, never '*'. Grant a request only when at least one allow rule matches it and no deny rule matches it; rule order does not matter. Return {granted: booleans, state: {denied: number of rejected requests}}.",
      '''
      def solve(data):
          granted = []
          for action in data["requests"]:
              effects = [rule["effect"] for rule in data["rules"] if rule["action"] in ("*", action)]
              granted.append("allow" in effects and "deny" not in effects)
          return {"granted": granted, "state": {"denied": granted.count(False)}}
      ''', ('"allow" in effects and "deny" not in effects', 'bool(effects) and effects[0] == "allow"'),
      [({"rules": [{"effect": "allow", "action": "read"}], "requests": ["read", "write"]}, {"granted": [True, False], "state": {"denied": 1}}), ({"rules": [{"effect": "allow", "action": "*"}, {"effect": "deny", "action": "delete"}], "requests": ["delete", "read"]}, {"granted": [False, True], "state": {"denied": 1}}), ({"rules": [], "requests": ["read"]}, {"granted": [False], "state": {"denied": 1}}), ({"rules": [{"effect": "deny", "action": "*"}, {"effect": "allow", "action": "read"}], "requests": ["read", "write"]}, {"granted": [False, False], "state": {"denied": 2}}), ({"rules": [{"effect": "allow", "action": "read"}, {"effect": "allow", "action": "*"}, {"effect": "deny", "action": "write"}, {"effect": "deny", "action": "write"}], "requests": ["write", "read", "list"]}, {"granted": [False, True, True], "state": {"denied": 1}}), ({"rules": [{"effect": "allow", "action": "*"}], "requests": []}, {"granted": [], "state": {"denied": 0}})],
      ["Should the order of policy rules decide whether a deny applies?", "Under deny-overrides semantics, any matching deny blocks the request even when an allow matched first.", "Collect every matching effect, then grant only when an allow matched and no deny matched."], ["authorization", "policies"]),
    p("overtime-excess-hours", "Overtime multiplies every hour", "A payroll calculator switches the whole week to the overtime rate once an employee passes 40 hours, instead of paying the premium only on the extra hours.",
      "Input.rate is a nonnegative hourly rate in cents, and input.hours contains nonnegative integer hours worked in each week. The first 40 hours of a week are paid at rate; hours beyond 40 are paid at one and a half times rate. Round each week's pay down to a whole cent. Return each week's pay in cents.",
      '''
      def solve(data):
          rate, pay = data["rate"], []
          for hours in data["hours"]:
              extra = max(hours - 40, 0)
              pay.append(hours * rate + extra * rate // 2)
          return pay
      ''', ('max(hours - 40, 0)', 'hours if hours > 40 else 0'),
      [({"rate": 2000, "hours": [40, 10]}, [80000, 20000]), ({"rate": 2000, "hours": [45]}, [95000]), ({"rate": 1000, "hours": [0, 41]}, [0, 41500]), ({"rate": 1555, "hours": [43]}, [69197]), ({"rate": 999, "hours": [40, 80]}, [39960, 99900]), ({"rate": 0, "hours": []}, [])],
      ["Which hours earn the overtime premium?", "Only hours beyond 40 in a week are overtime; the first 40 hours stay at the regular rate.", "Compute overtime hours as max(hours - 40, 0) and add half the rate for those hours on top of regular pay."], ["payroll", "thresholds"], "easy"),
    p("birthday-age-gate", "A seventeen-year-old passes the age check", "An age-restricted checkout computes age by subtracting birth years, so a customer whose birthday has not happened yet this year is counted a year older.",
      "Input.today is a canonical YYYY-MM-DD date, input.minimum is a nonnegative integer age, and input.birthdates contains canonical dates no later than today. Age is the number of completed years; someone born on February 29 completes a year on March 1 in non-leap years. Return whether each customer's age is at least minimum.",
      '''
      from datetime import date
      def solve(data):
          today = date.fromisoformat(data["today"])
          result = []
          for text in data["birthdates"]:
              born = date.fromisoformat(text)
              age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
              result.append(age >= data["minimum"])
          return result
      ''', (' - ((today.month, today.day) < (born.month, born.day))', ''),
      [({"today": "2026-09-28", "minimum": 18, "birthdates": ["2000-01-15", "2010-05-01"]}, [True, False]), ({"today": "2026-09-28", "minimum": 18, "birthdates": ["2008-12-01", "2008-09-28"]}, [False, True]), ({"today": "2026-02-28", "minimum": 18, "birthdates": ["2008-02-29"]}, [False]), ({"today": "2026-03-01", "minimum": 18, "birthdates": ["2008-02-29", "2008-03-02"]}, [True, False]), ({"today": "2024-02-29", "minimum": 21, "birthdates": ["2003-02-28", "2003-03-01"]}, [True, False]), ({"today": "2026-01-01", "minimum": 0, "birthdates": []}, [])],
      ["Has the customer's birthday already occurred this year?", "Subtracting years overstates age until the birthday is reached; compare (month, day) pairs to see whether this year's birthday has passed.", "Subtract one from the year difference when today's (month, day) is before the birth (month, day)."], ["dates", "eligibility"], "easy"),
    p("currency-minor-units", "Yen prices gain two decimal places", "A checkout converts prices to minor units with a table that only knows two-decimal currencies, although JPY has no minor unit and BHD has three decimal places.",
      "Input.items contains {amount: nonnegative decimal string, currency: 'USD'|'EUR'|'JPY'|'KRW'|'BHD'|'KWD'} objects. USD and EUR use 2 decimal places, JPY and KRW use 0, and BHD and KWD use 3; each amount has at most that many fractional digits. Return each amount as an integer count of its currency's minor units.",
      '''
      from decimal import Decimal
      MINOR_DIGITS = {"USD": 2, "EUR": 2, "JPY": 0, "KRW": 0, "BHD": 3, "KWD": 3}
      def solve(data):
          result = []
          for item in data["items"]:
              digits = MINOR_DIGITS.get(item["currency"], 2)
              result.append(int(Decimal(item["amount"]).scaleb(digits)))
          return result
      ''', ('{"USD": 2, "EUR": 2, "JPY": 0, "KRW": 0, "BHD": 3, "KWD": 3}', '{"USD": 2, "EUR": 2}'),
      [({"items": [{"amount": "19.99", "currency": "USD"}, {"amount": "5", "currency": "EUR"}]}, [1999, 500]), ({"items": [{"amount": "1500", "currency": "JPY"}, {"amount": "12.345", "currency": "BHD"}]}, [1500, 12345]), ({"items": []}, []), ({"items": [{"amount": "0.001", "currency": "KWD"}, {"amount": "0", "currency": "KRW"}, {"amount": "0.10", "currency": "EUR"}]}, [1, 0, 10]), ({"items": [{"amount": "999999", "currency": "KRW"}, {"amount": "7.5", "currency": "BHD"}]}, [999999, 7500])],
      ["Does every currency have cents?", "ISO 4217 assigns different minor-unit exponents: JPY and KRW have none, while BHD and KWD use three decimal places.", "Look up each currency's exponent and scale the exact decimal amount by that many places."], ["money", "currencies"]),
    p("sla-paused-clock", "The SLA clock runs while the ticket waits on the customer", "A support-desk report measures response time from open to resolve, including periods when the ticket was paused waiting for the customer.",
      "Input.sla is a positive number of minutes. Input.events lists one ticket's events in nondecreasing minute order: {type: 'open'|'pause'|'resume'|'resolve', at: integer}. The first event is open and the last is resolve; pause and resume alternate starting with pause, and a pause may still be active at resolve. Only minutes while the ticket is open and not paused count. Return {elapsed: counted minutes, breached: elapsed > sla}.",
      '''
      def solve(data):
          elapsed, running_since = 0, None
          for event in data["events"]:
              if event["type"] in ("open", "resume") and running_since is None:
                  running_since = event["at"]
              elif event["type"] in ("pause", "resolve") and running_since is not None:
                  elapsed += event["at"] - running_since
                  running_since = None
          return {"elapsed": elapsed, "breached": elapsed > data["sla"]}
      ''', ('("pause", "resolve")', '("resolve",)'),
      [({"sla": 30, "events": [{"type": "open", "at": 0}, {"type": "resolve", "at": 25}]}, {"elapsed": 25, "breached": False}), ({"sla": 30, "events": [{"type": "open", "at": 0}, {"type": "pause", "at": 10}, {"type": "resume", "at": 50}, {"type": "resolve", "at": 60}]}, {"elapsed": 20, "breached": False}), ({"sla": 5, "events": [{"type": "open", "at": 100}, {"type": "pause", "at": 103}, {"type": "resolve", "at": 200}]}, {"elapsed": 3, "breached": False}), ({"sla": 10, "events": [{"type": "open", "at": 0}, {"type": "pause", "at": 4}, {"type": "resume", "at": 4}, {"type": "pause", "at": 6}, {"type": "resume", "at": 20}, {"type": "resolve", "at": 29}]}, {"elapsed": 15, "breached": True}), ({"sla": 60, "events": [{"type": "open", "at": 0}, {"type": "resolve", "at": 60}]}, {"elapsed": 60, "breached": False}), ({"sla": 1, "events": [{"type": "open", "at": 7}, {"type": "pause", "at": 7}, {"type": "resume", "at": 9}, {"type": "resolve", "at": 9}]}, {"elapsed": 0, "breached": False})],
      ["Which intervals should the SLA timer count?", "A pause stops the clock until the next resume, so time spent waiting on the customer is excluded.", "Close the running segment at every pause as well as at resolve, and start a new segment only at open or resume."], ["sla", "timers", "state-machine"], "hard"),
    p("guest-cart-merge", "Logging in drops guest cart items", "When a guest signs in, the storefront merges carts by overwriting the account's quantities with the guest quantities instead of combining them.",
      "Input.account and input.guest map SKU strings to positive integer quantities, and input.stock maps every SKU in either cart to a nonnegative quantity. Merge by adding the quantities for each SKU, cap each merged quantity at that SKU's stock, and drop SKUs whose capped quantity is zero. Return {units: total merged units, state: {cart: merged map}}.",
      '''
      def solve(data):
          merged = dict(data["account"])
          for sku, quantity in data["guest"].items():
              merged[sku] = merged.get(sku, 0) + quantity
          cart = {sku: min(quantity, data["stock"][sku]) for sku, quantity in merged.items()}
          cart = {sku: quantity for sku, quantity in cart.items() if quantity > 0}
          return {"units": sum(cart.values()), "state": {"cart": cart}}
      ''', ('merged.get(sku, 0) + quantity', 'quantity'),
      [({"account": {"A": 1}, "guest": {"B": 2}, "stock": {"A": 5, "B": 5}}, {"units": 3, "state": {"cart": {"A": 1, "B": 2}}}), ({"account": {"A": 2}, "guest": {"A": 1}, "stock": {"A": 10}}, {"units": 3, "state": {"cart": {"A": 3}}}), ({"account": {}, "guest": {}, "stock": {}}, {"units": 0, "state": {"cart": {}}}), ({"account": {"A": 4, "B": 1}, "guest": {"A": 3, "C": 2}, "stock": {"A": 5, "B": 0, "C": 9}}, {"units": 7, "state": {"cart": {"A": 5, "C": 2}}}), ({"account": {"X": 1}, "guest": {"X": 1, "Y": 1}, "stock": {"X": 1, "Y": 0}}, {"units": 1, "state": {"cart": {"X": 1}}})],
      ["What should happen to a SKU that is in both carts?", "Merging must combine the quantities from both carts before applying the stock limit.", "Add the guest quantity to any existing account quantity, then cap each SKU at its stock and drop zero quantities."], ["e-commerce", "carts", "merging"]),
    p("early-renewal-extension", "Early renewal forfeits the remaining days", "A Go subscription service extends each renewal from its payment day, so members who renew before expiry lose the days they already paid for.",
      "Input.expires is the member's current expiry day, and input.renewals contains {on: integer day, days: positive integer} payments in nondecreasing on order. Each payment extends membership by days, starting from the later of the current expiry and the payment day. Return {expiries: expiry after each payment, state: {expires: final expiry}}.",
      '''
      package main

      func Solve(data map[string]interface{}) interface{} {
          expires := int(data["expires"].(float64))
          expiries := []int{}
          for _, raw := range data["renewals"].([]interface{}) {
              renewal := raw.(map[string]interface{})
              start := int(renewal["on"].(float64))
              if expires > start {
                  start = expires
              }
              expires = start + int(renewal["days"].(float64))
              expiries = append(expiries, expires)
          }
          return map[string]interface{}{"expiries": expiries, "state": map[string]interface{}{"expires": expires}}
      }
      ''', ('        if expires > start {\n            start = expires\n        }\n', ''),
      [({"expires": 10, "renewals": [{"on": 15, "days": 30}]}, {"expiries": [45], "state": {"expires": 45}}), ({"expires": 100, "renewals": [{"on": 90, "days": 30}]}, {"expiries": [130], "state": {"expires": 130}}), ({"expires": 5, "renewals": []}, {"expiries": [], "state": {"expires": 5}}), ({"expires": 0, "renewals": [{"on": 0, "days": 10}, {"on": 3, "days": 10}, {"on": 25, "days": 5}]}, {"expiries": [10, 20, 30], "state": {"expires": 30}}), ({"expires": 50, "renewals": [{"on": 50, "days": 1}]}, {"expiries": [51], "state": {"expires": 51}})],
      ["Where should an early renewal's new period begin?", "A member who renews before expiry still owns the remaining days, so the new period starts at the later of the expiry and the payment day.", "Take the maximum of the current expiry and the renewal day before adding the purchased days; Go 1.19 has no built-in max."], ["subscriptions", "renewals"], "easy", language="go"),
    p("draft-shallow-copy", "Editing a draft changes the live price list", "A pricing tool creates a draft with a shallow dictionary copy, so editing tier lists in the draft also rewrites the published price list.",
      "Input.published maps plan names to lists of integer tier prices. Input.edits contains {plan, tier, price} changes for existing plans and valid tier indexes, applied in order to a draft copy. Return {draft: the edited price list, state: {published: the published price list, which must stay unchanged}}.",
      '''
      def solve(data):
          published = data["published"]
          draft = {plan: list(prices) for plan, prices in published.items()}
          for edit in data["edits"]:
              draft[edit["plan"]][edit["tier"]] = edit["price"]
          return {"draft": draft, "state": {"published": published}}
      ''', ('{plan: list(prices) for plan, prices in published.items()}', 'dict(published)'),
      [({"published": {"basic": [10, 20]}, "edits": []}, {"draft": {"basic": [10, 20]}, "state": {"published": {"basic": [10, 20]}}}), ({"published": {"basic": [10, 20], "pro": [50]}, "edits": [{"plan": "pro", "tier": 0, "price": 45}]}, {"draft": {"basic": [10, 20], "pro": [45]}, "state": {"published": {"basic": [10, 20], "pro": [50]}}}), ({"published": {}, "edits": []}, {"draft": {}, "state": {"published": {}}}), ({"published": {"a": [1, 2, 3]}, "edits": [{"plan": "a", "tier": 2, "price": 30}, {"plan": "a", "tier": 0, "price": 10}, {"plan": "a", "tier": 2, "price": 33}]}, {"draft": {"a": [10, 2, 33]}, "state": {"published": {"a": [1, 2, 3]}}}), ({"published": {"x": [0], "y": [0]}, "edits": [{"plan": "x", "tier": 0, "price": 5}]}, {"draft": {"x": [5], "y": [0]}, "state": {"published": {"x": [0], "y": [0]}}})],
      ["Which objects does a shallow dictionary copy duplicate?", "A shallow copy creates a new outer dictionary but shares the inner tier lists with the original.", "Copy each plan's list as well, or use copy.deepcopy, before applying draft edits."], ["copying", "state", "pricing"]),
    p("journal-entry-balance", "An unbalanced journal entry posts", "A Java ledger checks that a journal entry has both debit and credit amounts, but never checks that the two sides balance.",
      "Input.balances maps account names to integer balances in cents. Input.entries contains journal entries in order; each entry is a list of {account, debit, credit} lines for existing accounts, with nonnegative integer amounts and exactly one positive amount per line. Post an entry only when it has at least one line and its total debits equal its total credits; posting adds debit minus credit to each line's account. Return {posted: booleans, state: {balances}}.",
      '''
      import com.google.gson.*;
      public class Solution {
        public static JsonElement solve(JsonObject data) {
          JsonObject balances = data.getAsJsonObject("balances").deepCopy();
          JsonArray posted = new JsonArray();
          for (JsonElement rawEntry : data.getAsJsonArray("entries")) {
            JsonArray lines = rawEntry.getAsJsonArray();
            long debits = 0, credits = 0;
            for (JsonElement rawLine : lines) {
              JsonObject line = rawLine.getAsJsonObject();
              debits += line.get("debit").getAsLong();
              credits += line.get("credit").getAsLong();
            }
            boolean ok = lines.size() > 0 && debits == credits;
            if (ok) {
              for (JsonElement rawLine : lines) {
                JsonObject line = rawLine.getAsJsonObject();
                String account = line.get("account").getAsString();
                long change = line.get("debit").getAsLong() - line.get("credit").getAsLong();
                balances.addProperty(account, balances.get(account).getAsLong() + change);
              }
            }
            posted.add(ok);
          }
          JsonObject state = new JsonObject();
          state.add("balances", balances);
          JsonObject result = new JsonObject();
          result.add("posted", posted);
          result.add("state", state);
          return result;
        }
      }
      ''', ('lines.size() > 0 && debits == credits', 'debits > 0 && credits > 0'),
      [({"balances": {"cash": 1000, "sales": 0}, "entries": [[{"account": "cash", "debit": 500, "credit": 0}, {"account": "sales", "debit": 0, "credit": 500}]]}, {"posted": [True], "state": {"balances": {"cash": 1500, "sales": -500}}}), ({"balances": {"cash": 1000, "sales": 0}, "entries": [[{"account": "cash", "debit": 500, "credit": 0}, {"account": "sales", "debit": 0, "credit": 400}]]}, {"posted": [False], "state": {"balances": {"cash": 1000, "sales": 0}}}), ({"balances": {"cash": 0}, "entries": [[]]}, {"posted": [False], "state": {"balances": {"cash": 0}}}), ({"balances": {"cash": 100, "rent": 0, "bank": 50}, "entries": [[{"account": "rent", "debit": 70, "credit": 0}, {"account": "cash", "debit": 0, "credit": 20}, {"account": "bank", "debit": 0, "credit": 50}], [{"account": "cash", "debit": 10, "credit": 0}]]}, {"posted": [True, False], "state": {"balances": {"cash": 80, "rent": 70, "bank": 0}}}), ({"balances": {"a": 0, "b": 0}, "entries": [[{"account": "a", "debit": 5, "credit": 0}, {"account": "b", "debit": 0, "credit": 3}], [{"account": "a", "debit": 3, "credit": 0}, {"account": "b", "debit": 0, "credit": 3}]]}, {"posted": [False, True], "state": {"balances": {"a": 3, "b": -3}}})],
      ["What makes a journal entry balanced?", "Having at least one debit and one credit does not mean the debit total equals the credit total.", "Sum the debit and credit amounts separately, and post the entry only when it has lines and the two totals are equal."], ["accounting", "double-entry", "validation"], language="java"),
    p("vat-inclusive-net", "VAT is removed at the wrong rate", "An invoicing export extracts the net price from a VAT-inclusive total by subtracting the VAT percentage of the gross amount, which removes too much tax.",
      "Input.lines contains {gross: nonnegative integer cents including VAT, rate_bps: VAT rate in basis points from 0 through 10,000} objects. For each line, net = gross * 10,000 / (10,000 + rate_bps), rounded half up to a whole cent, and vat = gross - net. Return [{net, vat}] in input order.",
      '''
      def solve(data):
          result = []
          for line in data["lines"]:
              gross, rate = line["gross"], line["rate_bps"]
              net = (2 * gross * 10000 + 10000 + rate) // (2 * (10000 + rate))
              result.append({"net": net, "vat": gross - net})
          return result
      ''', ('(2 * gross * 10000 + 10000 + rate) // (2 * (10000 + rate))', 'gross - (gross * rate + 5000) // 10000'),
      [({"lines": [{"gross": 1000, "rate_bps": 0}]}, [{"net": 1000, "vat": 0}]), ({"lines": [{"gross": 12000, "rate_bps": 2000}]}, [{"net": 10000, "vat": 2000}]), ({"lines": []}, []), ({"lines": [{"gross": 1999, "rate_bps": 1900}]}, [{"net": 1680, "vat": 319}]), ({"lines": [{"gross": 105, "rate_bps": 500}, {"gross": 1, "rate_bps": 10000}]}, [{"net": 100, "vat": 5}, {"net": 1, "vat": 0}])],
      ["Is the VAT inside a gross price a percentage of the gross or of the net?", "VAT is charged on the net amount, so gross = net * (1 + rate) and net = gross / (1 + rate), not gross * (1 - rate).", "Divide by (10,000 + rate_bps) with integer half-up rounding to obtain the net, then take the VAT as gross - net."], ["tax", "pricing", "rounding"]),
]
