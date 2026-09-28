"""Ten pricing, inventory, and customer-policy repairs."""
from functools import partial

from ..common import make

p = partial(make, "business")

PROBLEMS = [
    p("three-for-two-grouping", "The promotion gives away the priciest items", "A 3-for-2 promotion groups items from cheapest to most expensive, so the free item in each group is the most expensive one instead of the cheapest.",
      "Input.prices contains nonnegative integer item prices in cents. Under the 3-for-2 promotion, sort prices from highest to lowest and split them into consecutive groups of three; the last, cheapest item of each complete group is free, and items in an incomplete final group are paid. Return {discount, total}.",
      '''
      def solve(data):
          ordered = sorted(data["prices"], reverse=True)
          discount = sum(ordered[2::3])
          return {"discount": discount, "total": sum(ordered) - discount}
      ''', ('sorted(data["prices"], reverse=True)', 'sorted(data["prices"])'),
      [({"prices": [500, 500, 500]}, {"discount": 500, "total": 1000}), ({"prices": [100, 300, 200]}, {"discount": 100, "total": 500}), ({"prices": [999, 1]}, {"discount": 0, "total": 1000}), ({"prices": [10, 60, 20, 50, 30, 40, 70]}, {"discount": 70, "total": 210}), ({"prices": []}, {"discount": 0, "total": 0}), ({"prices": [0, 0, 100, 100, 100, 100]}, {"discount": 100, "total": 300})],
      ["Which item should be free in each group of three?", "Grouping from the cheapest item upward puts the most expensive item of each group in the free position.", "Sort prices from highest to lowest before taking every third item as the discount."], ["promotions", "pricing"], "easy"),
    p("weighted-average-cost", "Average cost ignores how many units each lot holds", "An inventory valuation averages purchase-lot prices directly, so a small expensive lot counts as much as a large cheap one.",
      "Input.lots contains {units: positive integer, unit_cost: nonnegative integer cents} purchases, and input.sold is a nonnegative number of units no greater than the total units. Under weighted-average costing, the average unit cost is total lot cost divided by total units. Return {average: that cost rounded half up to a whole cent, cogs: sold times the exact average cost, rounded half up to a whole cent}. With no lots, return {average: 0, cogs: 0}.",
      '''
      from fractions import Fraction
      def solve(data):
          lots = data["lots"]
          if not lots:
              return {"average": 0, "cogs": 0}
          average = Fraction(sum(lot["units"] * lot["unit_cost"] for lot in lots), sum(lot["units"] for lot in lots))
          half = Fraction(1, 2)
          return {"average": int(average + half), "cogs": int(average * data["sold"] + half)}
      ''', ('Fraction(sum(lot["units"] * lot["unit_cost"] for lot in lots), sum(lot["units"] for lot in lots))', 'Fraction(sum(lot["unit_cost"] for lot in lots), len(lots))'),
      [({"lots": [{"units": 10, "unit_cost": 100}], "sold": 4}, {"average": 100, "cogs": 400}), ({"lots": [{"units": 90, "unit_cost": 100}, {"units": 10, "unit_cost": 200}], "sold": 50}, {"average": 110, "cogs": 5500}), ({"lots": [], "sold": 0}, {"average": 0, "cogs": 0}), ({"lots": [{"units": 3, "unit_cost": 100}, {"units": 1, "unit_cost": 101}], "sold": 3}, {"average": 100, "cogs": 301}), ({"lots": [{"units": 1, "unit_cost": 1}, {"units": 1, "unit_cost": 2}], "sold": 1}, {"average": 2, "cogs": 2}), ({"lots": [{"units": 2, "unit_cost": 0}, {"units": 8, "unit_cost": 5}], "sold": 10}, {"average": 4, "cogs": 40})],
      ["Should a lot of 10 units influence the average as much as a lot of 90 units?", "Weighted-average cost divides total purchase cost by total units, so each lot contributes in proportion to its quantity.", "Sum units * unit_cost across lots and divide by the total units before rounding the average and the cost of goods sold."], ["inventory", "accounting"]),
    p("rolling-loyalty-tier", "Gold status never expires", "A loyalty service assigns tiers from lifetime spend, although the program defines tiers by spend in the last 365 days.",
      "Input.today is an integer day number, input.purchases contains {day: integer no later than today, amount: nonnegative integer} records, and input.tiers lists [minimum spend, name] pairs in ascending minimum order, starting with minimum 0. Qualifying spend is the sum of purchases with today - day < 365. Return the name of the highest tier whose minimum is at most the qualifying spend.",
      '''
      def solve(data):
          spend = sum(p["amount"] for p in data["purchases"] if data["today"] - p["day"] < 365)
          tier = data["tiers"][0][1]
          for minimum, name in data["tiers"]:
              if spend >= minimum:
                  tier = name
          return tier
      ''', (' if data["today"] - p["day"] < 365', ''),
      [({"today": 400, "purchases": [{"day": 100, "amount": 1500}], "tiers": [[0, "basic"], [1000, "silver"], [5000, "gold"]]}, "silver"), ({"today": 800, "purchases": [{"day": 100, "amount": 6000}, {"day": 700, "amount": 200}], "tiers": [[0, "basic"], [1000, "silver"], [5000, "gold"]]}, "basic"), ({"today": 0, "purchases": [], "tiers": [[0, "basic"], [1000, "silver"], [5000, "gold"]]}, "basic"), ({"today": 365, "purchases": [{"day": 0, "amount": 5000}, {"day": 1, "amount": 999}], "tiers": [[0, "basic"], [1000, "silver"], [5000, "gold"]]}, "basic"), ({"today": 1000, "purchases": [{"day": 999, "amount": 9}, {"day": 100, "amount": 50}], "tiers": [[0, "member"], [10, "plus"]]}, "member")],
      ["Which purchases count toward the current tier?", "Tier qualification uses a rolling 365-day window, so older purchases stop counting.", "Sum only purchases with today - day < 365 before comparing the spend with the tier minimums."], ["loyalty", "time-windows"], "easy"),
    p("stacked-percent-coupons", "Two 10% coupons take 20% off", "A checkout adds the percentages of stackable coupons together, although the store applies each coupon to the price left after the previous one.",
      "Input.subtotal is a nonnegative integer in cents, and input.percents lists stackable coupon percentages from 0 through 100 in application order. Apply each coupon to the running total, rounding the discounted total down to a whole cent after each coupon. Return {total, discount: subtotal - total}.",
      '''
      def solve(data):
          total = data["subtotal"]
          for percent in data["percents"]:
              total = total * (100 - percent) // 100
          return {"total": total, "discount": data["subtotal"] - total}
      ''', ('total = data["subtotal"]\n    for percent in data["percents"]:\n        total = total * (100 - percent) // 100\n', 'total = data["subtotal"] * max(0, 100 - sum(data["percents"])) // 100\n'),
      [({"subtotal": 1000, "percents": [10]}, {"total": 900, "discount": 100}), ({"subtotal": 1000, "percents": [10, 10]}, {"total": 810, "discount": 190}), ({"subtotal": 0, "percents": [50]}, {"total": 0, "discount": 0}), ({"subtotal": 999, "percents": [50, 50, 100]}, {"total": 0, "discount": 999}), ({"subtotal": 1999, "percents": [15, 5]}, {"total": 1614, "discount": 385}), ({"subtotal": 500, "percents": []}, {"total": 500, "discount": 0})],
      ["Does the second coupon apply to the original subtotal or to the already discounted price?", "Stacked percentage coupons compound: two 10% coupons leave 0.9 * 0.9 = 81% of the price, not 80%.", "Apply the coupons one at a time to the running total, rounding down after each step."], ["promotions", "pricing", "rounding"], "easy"),
    p("dimensional-weight-billing", "Bulky parcels ship at feather rates", "A shipping quote bills parcels by scale weight alone, ignoring the carrier's dimensional-weight rule for large, light boxes.",
      "Input.divisor is a positive integer, input.rate is the price in cents per started kilogram, and input.parcels contains {grams, length, width, height} with nonnegative integer grams and centimetre dimensions. Dimensional weight in grams is ceil(length * width * height * 1000 / divisor). Billable grams are the larger of the actual and dimensional weights, and each parcel costs rate * ceil(billable grams / 1000). Return each parcel's cost.",
      '''
      def solve(data):
          costs = []
          for parcel in data["parcels"]:
              billable = max(parcel["grams"], -(-parcel["length"] * parcel["width"] * parcel["height"] * 1000 // data["divisor"]))
              costs.append(data["rate"] * -(-billable // 1000))
          return costs
      ''', ('max(parcel["grams"], -(-parcel["length"] * parcel["width"] * parcel["height"] * 1000 // data["divisor"]))', 'parcel["grams"]'),
      [({"divisor": 5000, "rate": 700, "parcels": [{"grams": 1500, "length": 10, "width": 10, "height": 10}]}, [1400]), ({"divisor": 5000, "rate": 700, "parcels": [{"grams": 800, "length": 50, "width": 40, "height": 30}]}, [8400]), ({"divisor": 5000, "rate": 700, "parcels": []}, []), ({"divisor": 5000, "rate": 700, "parcels": [{"grams": 0, "length": 0, "width": 0, "height": 0}]}, [0]), ({"divisor": 6000, "rate": 100, "parcels": [{"grams": 5000, "length": 20, "width": 30, "height": 50}, {"grams": 2001, "length": 1, "width": 1, "height": 1}]}, [500, 300]), ({"divisor": 5000, "rate": 250, "parcels": [{"grams": 100, "length": 100, "width": 100, "height": 1}]}, [500])],
      ["Which weight does the carrier bill for a large but light box?", "Carriers bill the greater of the actual weight and the dimensional weight derived from the box volume.", "Compute ceil(volume * 1000 / divisor), take the maximum with the actual grams, then round up to started kilograms."], ["shipping", "pricing"]),
    p("reorder-inbound-stock", "The reorder job orders stock that is already on the way", "A replenishment job compares only shelf stock with the reorder point, ignoring units already on inbound purchase orders.",
      "Input.items contains {sku, on_hand, on_order, reserved, reorder_point, target} objects with nonnegative integers and target >= reorder_point. The inventory position is on_hand + on_order - reserved. When the position is below reorder_point, order target - position units; otherwise order nothing. Return {orders: [[sku, units], ...]} in input order for the SKUs that need an order.",
      '''
      def solve(data):
          orders = []
          for item in data["items"]:
              position = item["on_hand"] + item["on_order"] - item["reserved"]
              if position < item["reorder_point"]:
                  orders.append([item["sku"], item["target"] - position])
          return {"orders": orders}
      ''', ('item["on_hand"] + item["on_order"] - item["reserved"]', 'item["on_hand"] - item["reserved"]'),
      [({"items": [{"sku": "A", "on_hand": 5, "on_order": 0, "reserved": 0, "reorder_point": 10, "target": 20}]}, {"orders": [["A", 15]]}), ({"items": [{"sku": "A", "on_hand": 2, "on_order": 30, "reserved": 0, "reorder_point": 10, "target": 40}]}, {"orders": []}), ({"items": []}, {"orders": []}), ({"items": [{"sku": "B", "on_hand": 10, "on_order": 5, "reserved": 8, "reorder_point": 10, "target": 25}, {"sku": "C", "on_hand": 0, "on_order": 0, "reserved": 0, "reorder_point": 0, "target": 0}]}, {"orders": [["B", 18]]}), ({"items": [{"sku": "D", "on_hand": 3, "on_order": 4, "reserved": 7, "reorder_point": 1, "target": 6}]}, {"orders": [["D", 6]]})],
      ["Which units will be available soon even though they are not on the shelf yet?", "Inbound purchase orders already cover part of the shortfall, so ignoring them duplicates orders.", "Use on_hand + on_order - reserved as the inventory position for both the reorder check and the order quantity."], ["inventory", "replenishment"], "easy"),
    p("effective-dated-price", "Next month's price is charged today", "A billing job picks the price with the latest effective day for each plan, even when that price does not take effect until after the order.",
      "Input.prices contains {plan, effective: integer day, amount} records in any order, and input.orders contains {plan, day} objects. For each order, use the price for its plan with the latest effective day at or before the order day; ties on effective day go to the later record in the list. Return each order's amount, or null when no price is effective yet.",
      '''
      def solve(data):
          result = []
          for order in data["orders"]:
              best = None
              for price in data["prices"]:
                  if price["plan"] == order["plan"] and price["effective"] <= order["day"]:
                      if best is None or price["effective"] >= best["effective"]:
                          best = price
              result.append(best["amount"] if best else None)
          return result
      ''', (' and price["effective"] <= order["day"]', ''),
      [({"prices": [{"plan": "pro", "effective": 0, "amount": 1000}], "orders": [{"plan": "pro", "day": 5}]}, [1000]), ({"prices": [{"plan": "pro", "effective": 0, "amount": 1000}, {"plan": "pro", "effective": 30, "amount": 1200}], "orders": [{"plan": "pro", "day": 10}, {"plan": "pro", "day": 30}]}, [1000, 1200]), ({"prices": [], "orders": [{"plan": "basic", "day": 1}]}, [None]), ({"prices": [{"plan": "pro", "effective": 20, "amount": 900}, {"plan": "pro", "effective": 5, "amount": 800}, {"plan": "basic", "effective": 0, "amount": 100}], "orders": [{"plan": "pro", "day": 4}, {"plan": "pro", "day": 19}, {"plan": "basic", "day": 100}]}, [None, 800, 100]), ({"prices": [{"plan": "pro", "effective": 10, "amount": 1}, {"plan": "pro", "effective": 10, "amount": 2}], "orders": [{"plan": "pro", "day": 10}]}, [2])],
      ["Can a price apply to an order placed before its effective day?", "Only prices whose effective day is on or before the order day are candidates; among them, the latest effective day wins.", "Filter by effective <= order day before choosing the latest effective price, and return null when nothing qualifies."], ["pricing", "effective-dating"]),
    p("quantity-break-aggregation", "Quantity discounts miss split cart lines", "A Java cart totals quantities per SKU for bulk pricing, but it stores each line's quantity instead of adding it, so a SKU split across lines misses the bulk threshold.",
      "Input.lines contains {sku, quantity, price} objects with positive integer quantities and nonnegative integer unit prices in cents. Input.threshold is a positive integer, and input.percent is 0 through 100. When a SKU's combined quantity across all lines is at least threshold, every line of that SKU is discounted by percent, rounding each line's discounted subtotal down to a whole cent. Return the cart total in cents.",
      '''
      import com.google.gson.*;
      import java.util.*;
      public class Solution {
        public static JsonElement solve(JsonObject data) {
          JsonArray lines = data.getAsJsonArray("lines");
          Map<String, Long> combined = new HashMap<>();
          for (JsonElement raw : lines) {
            JsonObject line = raw.getAsJsonObject();
            combined.merge(line.get("sku").getAsString(), line.get("quantity").getAsLong(), Long::sum);
          }
          int threshold = data.get("threshold").getAsInt(), percent = data.get("percent").getAsInt();
          long total = 0;
          for (JsonElement raw : lines) {
            JsonObject line = raw.getAsJsonObject();
            long subtotal = line.get("quantity").getAsLong() * line.get("price").getAsLong();
            boolean bulk = combined.get(line.get("sku").getAsString()) >= threshold;
            total += bulk ? subtotal * (100 - percent) / 100 : subtotal;
          }
          return new JsonPrimitive(total);
        }
      }
      ''', ('combined.merge(line.get("sku").getAsString(), line.get("quantity").getAsLong(), Long::sum)', 'combined.put(line.get("sku").getAsString(), line.get("quantity").getAsLong())'),
      [({"lines": [{"sku": "A", "quantity": 12, "price": 100}], "threshold": 10, "percent": 10}, 1080), ({"lines": [{"sku": "A", "quantity": 6, "price": 100}, {"sku": "B", "quantity": 1, "price": 50}, {"sku": "A", "quantity": 6, "price": 100}], "threshold": 10, "percent": 10}, 1130), ({"lines": [], "threshold": 10, "percent": 10}, 0), ({"lines": [{"sku": "X", "quantity": 1, "price": 99}, {"sku": "X", "quantity": 1, "price": 99}, {"sku": "X", "quantity": 1, "price": 99}], "threshold": 3, "percent": 50}, 147), ({"lines": [{"sku": "Y", "quantity": 5, "price": 7}], "threshold": 5, "percent": 0}, 35), ({"lines": [{"sku": "P", "quantity": 2, "price": 10}, {"sku": "Q", "quantity": 4, "price": 10}, {"sku": "P", "quantity": 1, "price": 10}], "threshold": 4, "percent": 25}, 60)],
      ["Does the bulk threshold apply to a single line or to the SKU's whole quantity in the cart?", "Map.put replaces the previous quantity for a SKU, so splitting a SKU across lines hides its combined total.", "Accumulate quantities with merge(sku, quantity, Long::sum) and check the combined total for every line of that SKU."], ["pricing", "aggregation", "e-commerce"], language="java"),
    p("refund-net-of-discount", "Refunds pay back the discount too", "A JavaScript returns service refunds a returned line at its list price, although an order-wide discount reduced what the customer actually paid for it.",
      "Input.discount_bps is the order-wide discount in basis points from 0 through 10,000, applied to every line. Input.lines contains {id, price, quantity} with unique IDs, nonnegative integer prices of at most 100,000 cents, and quantities of at most 100. Input.returns contains {id, quantity} requests for existing lines that never exceed the quantity still unreturned. Refund each request as floor(price * quantity * (10,000 - discount_bps) / 10,000). Return {refunds: the amount for each request, state: {refunded: the total refunded}}.",
      '''
      function solve(data) {
        const prices = new Map(data.lines.map(line => [line.id, line.price]));
        const refunds = data.returns.map(request => Math.floor(prices.get(request.id) * request.quantity * (10000 - data.discount_bps) / 10000));
        return { refunds, state: { refunded: refunds.reduce((sum, amount) => sum + amount, 0) } };
      }
      module.exports = { solve };
      ''', ('Math.floor(prices.get(request.id) * request.quantity * (10000 - data.discount_bps) / 10000)', 'prices.get(request.id) * request.quantity'),
      [({"discount_bps": 0, "lines": [{"id": "a", "price": 1000, "quantity": 2}], "returns": [{"id": "a", "quantity": 1}]}, {"refunds": [1000], "state": {"refunded": 1000}}), ({"discount_bps": 2000, "lines": [{"id": "a", "price": 1000, "quantity": 2}], "returns": [{"id": "a", "quantity": 1}]}, {"refunds": [800], "state": {"refunded": 800}}), ({"discount_bps": 500, "lines": [], "returns": []}, {"refunds": [], "state": {"refunded": 0}}), ({"discount_bps": 3333, "lines": [{"id": "a", "price": 999, "quantity": 3}, {"id": "b", "price": 1, "quantity": 1}], "returns": [{"id": "a", "quantity": 2}, {"id": "b", "quantity": 1}, {"id": "a", "quantity": 1}]}, {"refunds": [1332, 0, 666], "state": {"refunded": 1998}}), ({"discount_bps": 10000, "lines": [{"id": "z", "price": 500, "quantity": 1}], "returns": [{"id": "z", "quantity": 1}]}, {"refunds": [0], "state": {"refunded": 0}})],
      ["How much did the customer actually pay for the returned units?", "An order-wide discount lowered every line's net price, so refunding the list price pays the discount back to the customer.", "Refund price * quantity * (10,000 - discount_bps) / 10,000, rounded down, for each request."], ["refunds", "discounts", "e-commerce"], "easy", language="javascript"),
    p("fx-bid-ask-side", "The exchange desk buys at its selling price", "A C++ currency desk converts both directions with the ask rate, so customers selling currency receive the desk's higher selling price.",
      "Input.bid and input.ask are the EUR prices of one USD in millionths of a euro, with bid <= ask. Input.trades contains {side: 'sell_usd'|'buy_usd', amount: nonnegative integer USD cents}. When the customer sells USD, the desk pays floor(amount * bid / 1,000,000) euro cents. When the customer buys USD, the desk charges ceil(amount * ask / 1,000,000) euro cents. Return the euro-cent amount for each trade.",
      '''
      #include <nlohmann/json.hpp>
      #include <string>
      using nlohmann::json;
      json solve(const json& data) {
          long long bid = data.at("bid").get<long long>(), ask = data.at("ask").get<long long>();
          json result = json::array();
          for (const auto& trade : data.at("trades")) {
              long long amount = trade.at("amount").get<long long>();
              if (trade.at("side").get<std::string>() == "sell_usd") {
                  result.push_back(amount * bid / 1000000);
              } else {
                  result.push_back((amount * ask + 999999) / 1000000);
              }
          }
          return result;
      }
      ''', ('result.push_back(amount * bid / 1000000);', 'result.push_back(amount * ask / 1000000);'),
      [({"bid": 900000, "ask": 920000, "trades": [{"side": "buy_usd", "amount": 100}]}, [92]), ({"bid": 900000, "ask": 920000, "trades": [{"side": "sell_usd", "amount": 100}]}, [90]), ({"bid": 900000, "ask": 920000, "trades": []}, []), ({"bid": 900000, "ask": 920000, "trades": [{"side": "sell_usd", "amount": 1}, {"side": "buy_usd", "amount": 1}]}, [0, 1]), ({"bid": 1085000, "ask": 1095500, "trades": [{"side": "sell_usd", "amount": 12345}, {"side": "buy_usd", "amount": 12345}]}, [13394, 13524]), ({"bid": 900000, "ask": 920000, "trades": [{"side": "buy_usd", "amount": 0}]}, [0])],
      ["Which quoted price applies when the desk buys currency from a customer?", "A dealer buys at the lower bid and sells at the higher ask; using the ask on both sides overpays customers who sell.", "Use bid with rounding down for sell_usd trades and ask with rounding up for buy_usd trades."], ["currency-exchange", "pricing"], "easy", language="cpp"),
]
