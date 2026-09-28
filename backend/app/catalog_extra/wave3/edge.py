"""Ten precision, path, calendar, and integer-width repairs."""
from functools import partial

from ..common import make

p = partial(make, "edge")

PROBLEMS = [
    p("float-sum-exact-cents", "Ten dimes do not make a dollar", "A payment matcher adds floating-point amounts and compares the sum with the bill using ==, so binary rounding error rejects exact payments.",
      "Input.bills contains {total, payments} objects where total and every payment are JSON numbers with at most two decimal places and magnitude below 100,000; there are at most 100 payments per bill. Return, for each bill, whether its payments add up to exactly its total in cents.",
      '''
      def solve(data):
          result = []
          for bill in data["bills"]:
              paid = 0.0
              for payment in bill["payments"]:
                  paid += payment
              result.append(round(paid * 100) == round(bill["total"] * 100))
          return result
      ''', ('round(paid * 100) == round(bill["total"] * 100)', 'paid == bill["total"]'),
      [({"bills": [{"total": 3, "payments": [1, 2]}]}, [True]), ({"bills": [{"total": 1, "payments": [0.1] * 10}]}, [True]), ({"bills": []}, []), ({"bills": [{"total": 0.3, "payments": [0.1, 0.2]}, {"total": 0.3, "payments": [0.1, 0.1]}]}, [True, False]), ({"bills": [{"total": 99999.99, "payments": [0.01, 99999.98]}, {"total": 0, "payments": []}]}, [True, True])],
      ["Can 0.1 be represented exactly as a binary floating-point number?", "Adding binary approximations accumulates tiny errors, so an exact == comparison of float sums fails for amounts that are equal in cents.", "Convert to integer cents, for example round(value * 100), before comparing, or do the arithmetic with Decimal."], ["floating-point", "money"], "easy"),
    p("end-of-day-fraction", "Events at 23:59:59.5 fall outside the day", "A daily report selects events up to 23:59:59 inclusive, which silently drops events in the last fraction of a second before midnight.",
      "Input.day is a canonical YYYY-MM-DD date, and input.events contains UTC timestamps formatted YYYY-MM-DDTHH:MM:SS with an optional fractional part of one to six digits. Return the number of events on day, meaning at or after its midnight and before the next day's midnight.",
      '''
      from datetime import datetime, timedelta
      def solve(data):
          start = datetime.fromisoformat(data["day"] + "T00:00:00")
          return sum(start <= datetime.fromisoformat(text) < start + timedelta(days=1) for text in data["events"])
      ''', ('< start + timedelta(days=1)', '<= start + timedelta(hours=23, minutes=59, seconds=59)'),
      [({"day": "2026-09-28", "events": ["2026-09-28T12:00:00"]}, 1), ({"day": "2026-09-28", "events": ["2026-09-28T23:59:59.5", "2026-09-29T00:00:00"]}, 1), ({"day": "2026-09-28", "events": []}, 0), ({"day": "2026-09-28", "events": ["2026-09-28T00:00:00", "2026-09-27T23:59:59.999999", "2026-09-28T23:59:59"]}, 2), ({"day": "2026-09-28", "events": ["2026-09-28T23:59:59.999999", "2026-09-28T23:59:59.100"]}, 2)],
      ["Is 23:59:59 really the last moment of a day?", "Timestamps with fractional seconds can fall after 23:59:59 but before midnight, and an inclusive end at a whole second misses them.", "Use a half-open interval: at or after midnight and strictly before the next midnight."], ["time", "intervals", "precision"], "easy"),
    p("path-segment-slash", "A slash inside a filename splits the URL path", "A download-link builder percent-encodes filenames with urllib.parse.quote, whose default leaves '/' unescaped, so a filename containing a slash becomes two path segments.",
      "Input.names contains Unicode filenames. Return each name percent-encoded as one URL path segment: every UTF-8 byte except ASCII letters, digits, and '-._~' must be escaped, including '/'.",
      '''
      from urllib.parse import quote
      def solve(data):
          return [quote(name, safe="") for name in data["names"]]
      ''', ('quote(name, safe="")', 'quote(name)'),
      [({"names": ["report.pdf"]}, ["report.pdf"]), ({"names": ["q3/q4 plan.txt"]}, ["q3%2Fq4%20plan.txt"]), ({"names": []}, []), ({"names": ["a~b_c-d.e", "100%"]}, ["a~b_c-d.e", "100%25"]), ({"names": ["café/ü", "?#"]}, ["caf%C3%A9%2F%C3%BC", "%3F%23"])],
      ["Which characters does quote leave unescaped by default?", "quote treats '/' as safe by default because it is meant for whole paths, so a slash inside one segment survives and creates an extra segment.", "Pass safe='' when encoding a single path segment."], ["urls", "encoding"], "easy"),
    p("weekday-convention-saturday", "Saturday counts as a business day", "A delivery estimator uses date.weekday() as if it returned ISO weekday numbers, so Saturdays are counted as business days.",
      "Input.ranges contains {start, end} canonical YYYY-MM-DD dates with start <= end, each spanning at most 366 days. Return, for each range, the number of Monday-through-Friday dates from start to end inclusive.",
      '''
      from datetime import date, timedelta
      def solve(data):
          counts = []
          for item in data["ranges"]:
              day, end, total = date.fromisoformat(item["start"]), date.fromisoformat(item["end"]), 0
              while day <= end:
                  total += day.isoweekday() < 6
                  day += timedelta(days=1)
              counts.append(total)
          return counts
      ''', ('day.isoweekday() < 6', 'day.weekday() < 6'),
      [({"ranges": [{"start": "2026-09-28", "end": "2026-10-02"}]}, [5]), ({"ranges": [{"start": "2026-10-03", "end": "2026-10-04"}]}, [0]), ({"ranges": []}, []), ({"ranges": [{"start": "2026-10-02", "end": "2026-10-05"}]}, [2]), ({"ranges": [{"start": "2026-09-01", "end": "2026-09-30"}, {"start": "2026-10-03", "end": "2026-10-03"}]}, [22, 0])],
      ["Which number does date.weekday() return for Saturday?", "weekday() numbers Monday as 0 and Sunday as 6, while isoweekday() numbers Monday as 1 and Sunday as 7.", "Use isoweekday() < 6, or weekday() < 5, so only Monday through Friday count."], ["dates", "calendar"], "easy"),
    p("absolute-upload-path", "An absolute filename escapes the upload folder", "An upload handler builds storage paths with posixpath.join, which discards the base directory whenever the user-supplied name is absolute.",
      "Input.base is an absolute POSIX directory path without a trailing slash, and input.names contains user-supplied filenames. A name is valid when it is nonempty, is not absolute, and none of its '/'-separated segments is empty, '.', or '..'. Return base + '/' + name for each valid name and null for each invalid name.",
      '''
      import posixpath
      def solve(data):
          result = []
          for name in data["names"]:
              valid = bool(name) and not posixpath.isabs(name) and all(part not in ("", ".", "..") for part in name.split("/"))
              result.append(posixpath.join(data["base"], name) if valid else None)
          return result
      ''', ('not posixpath.isabs(name) and all(part not in ("", ".", "..")', 'all(part not in (".", "..")'),
      [({"base": "/srv/uploads", "names": ["report.pdf"]}, ["/srv/uploads/report.pdf"]), ({"base": "/srv/uploads", "names": ["/etc/passwd", "img/cat.png"]}, [None, "/srv/uploads/img/cat.png"]), ({"base": "/srv/uploads", "names": []}, []), ({"base": "/srv/uploads", "names": ["../secret", "a/./b", ""]}, [None, None, None]), ({"base": "/srv/uploads", "names": ["a//b", "dir/", ".hidden"]}, [None, None, "/srv/uploads/.hidden"]), ({"base": "/data", "names": ["//double"]}, [None])],
      ["What does posixpath.join return when a later argument starts with '/'?", "join discards every earlier component when a later one is absolute, so a name like /etc/passwd replaces the upload directory entirely.", "Reject absolute names and empty segments along with '.' and '..' before joining."], ["paths", "validation", "security"], "hard"),
    p("find-npos-domain", "An address without an at sign becomes its own domain", "A C++ mailer extracts the domain with substr(find('@') + 1), and when '@' is missing, npos + 1 wraps around to 0, so the whole text is treated as the domain.",
      "Input.addresses contains ASCII strings. Return the text after the first '@' in each string, or an empty string when the string contains no '@'.",
      '''
      #include <nlohmann/json.hpp>
      #include <string>
      using nlohmann::json;
      json solve(const json& data) {
          json result = json::array();
          for (const auto& raw : data.at("addresses")) {
              std::string address = raw.get<std::string>();
              std::size_t at = address.find('@');
              result.push_back(at == std::string::npos ? std::string() : address.substr(at + 1));
          }
          return result;
      }
      ''', ('at == std::string::npos ? std::string() : address.substr(at + 1)', 'address.substr(at + 1)'),
      [({"addresses": ["ada@example.com"]}, ["example.com"]), ({"addresses": ["localhost", "bo@mail.dev"]}, ["", "mail.dev"]), ({"addresses": []}, []), ({"addresses": ["a@b@c", "@x", "y@"]}, ["b@c", "x", ""]), ({"addresses": ["", "no-at-sign", "@"]}, ["", "", ""])],
      ["What does find return when '@' is absent, and what is that value plus one?", "std::string::npos is the largest size_t, so npos + 1 wraps to 0 and substr(0) returns the entire string.", "Compare the position with npos before calling substr, and return an empty domain when there is no '@'."], ["cpp", "strings", "unsigned-integers"], "easy", language="cpp"),
    p("half-add-rounding-negative", "Negative readings round toward zero", "A C++ sensor report rounds values with static_cast<long long>(x + 0.5), an idiom that works only for nonnegative numbers.",
      "Input.readings contains numbers with magnitude below 1,000,000 and at most two decimal places. Round each reading to the nearest integer, rounding halves away from zero. Return the rounded integers.",
      '''
      #include <nlohmann/json.hpp>
      #include <cmath>
      using nlohmann::json;
      json solve(const json& data) {
          json result = json::array();
          for (const auto& raw : data.at("readings")) {
              result.push_back(std::llround(raw.get<double>()));
          }
          return result;
      }
      ''', ('std::llround(raw.get<double>())', 'static_cast<long long>(raw.get<double>() + 0.5)'),
      [({"readings": [1.4, 2.5, 0]}, [1, 3, 0]), ({"readings": [-2.7, -1.2]}, [-3, -1]), ({"readings": []}, []), ({"readings": [-2.5, 2.5, -0.5, 0.5]}, [-3, 3, -1, 1]), ({"readings": [-0.4, 999999.5, -999999.49]}, [0, 1000000, -999999])],
      ["Which way does a cast to an integer type truncate a negative number?", "Adding 0.5 and truncating rounds toward zero for negative values, so -2.7 becomes -2 instead of -3.", "Use std::llround, or std::round, which rounds halves away from zero for both signs."], ["cpp", "rounding", "negative-values"], language="cpp"),
    p("float-plain-format", "A tiny rate prints in scientific notation", "A Go exporter formats rates with strconv's 'g' verb, which switches to exponent notation for very small or large values that the CSV importer cannot read.",
      "Input.values contains JSON numbers with magnitude below 10^22. Return each as a plain decimal string without an exponent, using the shortest digits that round-trip the float64: no trailing zeros after the decimal point and no decimal point for integral values.",
      '''
      package main

      import "strconv"

      func Solve(data map[string]interface{}) interface{} {
          result := []string{}
          for _, raw := range data["values"].([]interface{}) {
              result = append(result, strconv.FormatFloat(raw.(float64), 'f', -1, 64))
          }
          return result
      }
      ''', ("'f', -1, 64", "'g', -1, 64"),
      [({"values": [0.5, 42, 123456]}, ["0.5", "42", "123456"]), ({"values": [0.00001, 2500000]}, ["0.00001", "2500000"]), ({"values": []}, []), ({"values": [-0.0001, 1e21]}, ["-0.0001", "1000000000000000000000"]), ({"values": [0.1, 1.5e-7, 999999.25]}, ["0.1", "0.00000015", "999999.25"])],
      ["When does Go's 'g' format switch to exponent notation?", "With the shortest precision, 'g' uses an exponent when the decimal exponent is below -4 or at least 6, producing 1e-05 and 2.5e+06.", "Format with strconv.FormatFloat(value, 'f', -1, 64) to get the shortest plain decimal digits."], ["go", "formatting", "floating-point"], language="go"),
    p("parseint-number-truncation", "A tiny amount parses as five", "A JavaScript meter truncates numeric readings with parseInt, which first converts a number to a string, so 5e-7 becomes '5e-7' and parses as 5.",
      "Input.values contains nonnegative JSON numbers below 10^21. Return the integer part, the floor, of each value.",
      '''
      function solve(data) {
        return data.values.map(value => Math.floor(value));
      }
      module.exports = { solve };
      ''', ('Math.floor(value)', 'parseInt(value)'),
      [({"values": [12.7, 3, 0]}, [12, 3, 0]), ({"values": [0.0000005, 0.000001]}, [0, 0]), ({"values": []}, []), ({"values": [123456789.99, 0.9999999]}, [123456789, 0]), ({"values": [2.5e-10, 1e20]}, [0, 100000000000000000000])],
      ["What does parseInt do with an argument that is already a number?", "parseInt converts its argument to a string first, and very small numbers stringify in exponent form such as '5e-7', so parsing stops at the first non-digit.", "Use Math.floor, or Math.trunc, for numbers instead of parseInt."], ["javascript", "parsing", "coercion"], language="javascript"),
    p("abs-min-value-bucket", "The most negative hash lands in a negative bucket", "A Java shard router computes Math.abs(hash) % shards, but Math.abs(Integer.MIN_VALUE) is still negative, so one hash maps outside the valid range.",
      "Input.hashes contains signed 32-bit integers, from -2,147,483,648 through 2,147,483,647, overriding the default integer limit, and input.shards is a positive integer up to 1,000. Each hash's shard is |hash| mod shards, where |-2,147,483,648| is 2,147,483,648. Return the shard for each hash.",
      '''
      import com.google.gson.*;
      public class Solution {
        public static JsonElement solve(JsonObject data) {
          int shards = data.get("shards").getAsInt();
          JsonArray result = new JsonArray();
          for (JsonElement raw : data.getAsJsonArray("hashes")) {
            int hash = raw.getAsInt();
            result.add(Math.abs((long) hash) % shards);
          }
          return result;
        }
      }
      ''', ('Math.abs((long) hash) % shards', 'Math.abs(hash) % shards'),
      [({"hashes": [15, -15, 0], "shards": 10}, [5, 5, 0]), ({"hashes": [-2147483648], "shards": 10}, [8]), ({"hashes": [], "shards": 3}, []), ({"hashes": [2147483647, -2147483647], "shards": 1000}, [647, 647]), ({"hashes": [-2147483648, 7], "shards": 7}, [2, 0]), ({"hashes": [-2147483648], "shards": 8}, [0])],
      ["Is there an int whose absolute value does not fit in an int?", "Math.abs(Integer.MIN_VALUE) overflows and returns Integer.MIN_VALUE, which is negative, so the remainder is negative too.", "Widen the hash to long before taking the absolute value so every result lies from 0 through shards - 1."], ["java", "overflow", "hashing"], language="java"),
]
