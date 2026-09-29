"""Ten representation and boundary repairs across five languages."""
from functools import partial

from ..common import make

p = partial(make, "edge")

PROBLEMS = [
    p("boxed-integer-identity", "Amounts above 127 never reconcile", "A Java reconciliation job compares boxed Integer amounts with ==, which happens to work for small cached values and fails for larger ones.",
      "Input.ledger and input.bank are equal-length lists of integer amounts in cents. Return the number of positions where the two amounts are equal.",
      '''
      import com.google.gson.*;
      import java.util.*;
      public class Solution {
        public static JsonElement solve(JsonObject data) {
          List<Integer> ledger = new ArrayList<>(), bank = new ArrayList<>();
          for (JsonElement value : data.getAsJsonArray("ledger")) ledger.add(value.getAsInt());
          for (JsonElement value : data.getAsJsonArray("bank")) bank.add(value.getAsInt());
          int matched = 0;
          for (int i = 0; i < ledger.size(); i++) {
            if (ledger.get(i).equals(bank.get(i))) matched++;
          }
          return new JsonPrimitive(matched);
        }
      }
      ''', ('ledger.get(i).equals(bank.get(i))', 'ledger.get(i) == bank.get(i)'),
      [({"ledger": [5, 100, 127], "bank": [5, 99, 127]}, 2), ({"ledger": [128, 2500], "bank": [128, 2500]}, 2), ({"ledger": [], "bank": []}, 0), ({"ledger": [-128, -129, 0], "bank": [-128, -129, 1]}, 2), ({"ledger": [1000000, 7], "bank": [999999, 7]}, 1)],
      ["What does == compare when both operands are Integer objects?", "On boxed Integers, == compares object identity, and Integer.valueOf caches only -128 through 127, so larger equal amounts are different objects.", "Compare values with equals, or unbox to int, instead of comparing references."], ["java", "autoboxing", "equality"], language="java"),
    p("subtraction-comparator-wrap", "Distant values sort backwards", "A Java comparator orders values by returning a - b, and differences outside the int range wrap around and flip the comparison.",
      "Input.values contains at most 20 signed 32-bit integers, from -2,147,483,648 through 2,147,483,647; this overrides the default integer limit. Return them sorted in ascending order, retaining duplicates.",
      '''
      import com.google.gson.*;
      import java.util.*;
      public class Solution {
        public static JsonElement solve(JsonObject data) {
          List<Integer> values = new ArrayList<>();
          for (JsonElement value : data.getAsJsonArray("values")) values.add(value.getAsInt());
          values.sort((a, b) -> Integer.compare(a, b));
          return new Gson().toJsonTree(values);
        }
      }
      ''', ('Integer.compare(a, b)', 'a - b'),
      [({"values": [3, -1, 2]}, [-1, 2, 3]), ({"values": [2000000000, -2000000000]}, [-2000000000, 2000000000]), ({"values": []}, []), ({"values": [2147483647, -2147483648, 0]}, [-2147483648, 0, 2147483647]), ({"values": [-1500000000, 1500000000, 0, -1]}, [-1500000000, -1, 0, 1500000000])],
      ["Can the difference between two ints fall outside the int range?", "a - b overflows for distant values, so a large positive minus a large negative can come out negative.", "Use Integer.compare(a, b), or Comparator.naturalOrder(), instead of subtraction."], ["java", "comparators", "overflow"], language="java"),
    p("split-empty-header", "An empty header produces one blank tag", "A Go tag parser trusts strings.Split, which returns one empty field for an empty input instead of no fields.",
      "Input.headers contains strings of comma-separated tags. Return one list per header containing its fields exactly as separated by commas, including empty fields between consecutive commas and without trimming. An empty header has no tags and returns [].",
      '''
      package main

      import "strings"

      func Solve(data map[string]interface{}) interface{} {
          result := [][]string{}
          for _, raw := range data["headers"].([]interface{}) {
              header := raw.(string)
              tags := []string{}
              if header != "" {
                  tags = strings.Split(header, ",")
              }
              result = append(result, tags)
          }
          return result
      }
      ''', ('tags := []string{}\n        if header != "" {\n            tags = strings.Split(header, ",")\n        }', 'tags := strings.Split(header, ",")'),
      [({"headers": ["a,b"]}, [["a", "b"]]), ({"headers": ["", "x"]}, [[], ["x"]]), ({"headers": []}, []), ({"headers": ["a,,b", ","]}, [["a", "", "b"], ["", ""]]), ({"headers": [" a , b "]}, [[" a ", " b "]])],
      ["How many fields does strings.Split return for an empty string?", "Split returns a slice containing one empty string when the input has no separator, including the empty input.", "Special-case the empty header to return an empty, non-nil slice, and keep Split for every other header."], ["go", "strings", "empty-input"], "easy", language="go"),
    p("blank-number-coercion", "A blank quantity becomes zero", "A JavaScript form handler validates quantities with Number(), which turns blank text, padded text, hexadecimal, and exponent notation into numbers.",
      "Input.values contains strings. A valid quantity is one or more ASCII digits with no sign, whitespace, decimal point, or exponent; leading zeros are allowed, and valid quantities have at most 15 digits. Return each valid quantity's integer value, or null for invalid text.",
      '''
      function solve(data) {
        return data.values.map(text => (/^[0-9]+$/.test(text) ? Number(text) : null));
      }
      module.exports = { solve };
      ''', ('/^[0-9]+$/.test(text)', 'Number.isInteger(Number(text)) && Number(text) >= 0'),
      [({"values": ["3", "12"]}, [3, 12]), ({"values": ["", "5"]}, [None, 5]), ({"values": [" 7", "007", "   "]}, [None, 7, None]), ({"values": ["0x1A", "1e3", "12.0"]}, [None, None, None]), ({"values": ["-1", "+2", "0"]}, [None, None, 0])],
      ["What number does Number('') produce?", "Number() trims whitespace and accepts empty strings, hexadecimal prefixes, and exponents, so it is not a digit-only validator.", "Validate the text against /^[0-9]+$/ before converting it, and return null for everything else."], ["javascript", "coercion", "validation"], "easy", language="javascript"),
    p("stoi-trailing-characters", "A trailing unit slips past the parser", "A C++ importer converts text with std::stoi and accepts whatever number it finds at the start, so values such as '12kg' and '3.5' are silently truncated.",
      "Input.tokens contains strings of at most nine characters drawn from ASCII digits, lowercase letters, '.', and '-'. A valid token is an optional '-' followed by one or more digits and nothing else. Return each valid token's integer value, or null for an invalid token.",
      '''
      #include <nlohmann/json.hpp>
      #include <stdexcept>
      #include <string>
      using nlohmann::json;
      json solve(const json& data) {
          json result = json::array();
          for (const auto& raw : data.at("tokens")) {
              std::string text = raw.get<std::string>();
              try {
                  std::size_t used = 0;
                  int value = std::stoi(text, &used);
                  result.push_back(used == text.size() ? json(value) : json(nullptr));
              } catch (const std::logic_error&) {
                  result.push_back(nullptr);
              }
          }
          return result;
      }
      ''', ('used == text.size() ? json(value) : json(nullptr)', 'json(value)'),
      [({"tokens": ["42", "-7"]}, [42, -7]), ({"tokens": ["12kg", "5"]}, [None, 5]), ({"tokens": ["3.5", "abc", ""]}, [None, None, None]), ({"tokens": ["007", "-0", "-"]}, [7, 0, None]), ({"tokens": ["1-2", "999999999", "-12a"]}, [None, 999999999, None])],
      ["Does std::stoi require the entire string to be a number?", "stoi parses the longest numeric prefix and reports how many characters it consumed through its optional position argument.", "Pass a size_t position to stoi and accept the value only when it equals the token length; keep catching invalid_argument for tokens without digits."], ["cpp", "parsing", "validation"], language="cpp"),
    p("string-false-flag", "The string false turns the flag on", "A feature-flag loader converts configuration text with bool(), so every nonempty string, including 'false' and '0', becomes True.",
      "Input.flags contains configuration strings. After removing surrounding whitespace and lowercasing, 'true', '1', 'yes', and 'on' mean enabled. Return a boolean for each flag: true only for those enabled spellings, otherwise false.",
      '''
      def solve(data):
          return [flag.strip().lower() in {"true", "1", "yes", "on"} for flag in data["flags"]]
      ''', ('flag.strip().lower() in {"true", "1", "yes", "on"}', 'bool(flag.strip())'),
      [({"flags": ["true", ""]}, [True, False]), ({"flags": ["false", "0"]}, [False, False]), ({"flags": [" YES ", "On", "1"]}, [True, True, True]), ({"flags": ["no", "off", "  "]}, [False, False, False]), ({"flags": ["enabled", "truee", "t"]}, [False, False, False])],
      ["Which strings does bool() treat as false?", "Only the empty string is falsy; 'false', '0', and 'no' are nonempty and therefore true.", "Normalize the text and compare it with the explicit set of enabled spellings."], ["truthiness", "configuration"], "easy"),
    p("iso-week-year", "New Year's Day lands in the wrong week-year", "A reporting job labels ISO weeks with the calendar year, so dates near January 1 are filed under a week that belongs to the neighboring year.",
      "Input.dates contains canonical YYYY-MM-DD dates in years 2000 through 2099. Return each date's ISO 8601 week label 'YYYY-Www', using the ISO week-numbering year and a two-digit week number.",
      '''
      from datetime import date
      def solve(data):
          labels = []
          for text in data["dates"]:
              iso = date.fromisoformat(text).isocalendar()
              labels.append(f"{iso.year}-W{iso.week:02d}")
          return labels
      ''', ('f"{iso.year}-W{iso.week:02d}"', 'f"{text[:4]}-W{iso.week:02d}"'),
      [({"dates": ["2026-06-15"]}, ["2026-W25"]), ({"dates": ["2027-01-01", "2024-12-30"]}, ["2026-W53", "2025-W01"]), ({"dates": []}, []), ({"dates": ["2021-01-03", "2021-01-04"]}, ["2020-W53", "2021-W01"]), ({"dates": ["2000-01-01", "2026-12-31"]}, ["1999-W52", "2026-W53"])],
      ["Which year does an ISO week belong to when it spans December and January?", "ISO weeks start on Monday and belong to the year that contains their Thursday, so the ISO year can differ from the calendar year.", "Use the year returned by isocalendar() together with its week number."], ["dates", "iso-8601"]),
    p("casefold-username-match", "Straße and STRASSE are treated as different users", "A username deduplicator compares lowercase spellings, which misses case-insensitive matches such as the German sharp s and typographic ligatures.",
      "Input.names contains Unicode strings. Two names are duplicates when they are equal under full Unicode case folding, as performed by str.casefold. Return the names that do not duplicate an earlier name, keeping their original spelling and order.",
      '''
      def solve(data):
          seen, result = set(), []
          for name in data["names"]:
              key = name.casefold()
              if key not in seen:
                  seen.add(key)
                  result.append(name)
          return result
      ''', ('name.casefold()', 'name.lower()'),
      [({"names": ["Ada", "ADA", "Bo"]}, ["Ada", "Bo"]), ({"names": ["Straße", "STRASSE"]}, ["Straße"]), ({"names": []}, []), ({"names": ["ﬁle", "FILE", "file"]}, ["ﬁle"]), ({"names": ["strasse", "Straße", "STRASSE"]}, ["strasse"])],
      ["Is lower() the strongest case-insensitive comparison Unicode defines?", "Some characters fold to several letters, such as ß to 'ss' and the ﬁ ligature to 'fi', and lower() does not perform that folding.", "Use casefold() for the comparison key while returning each name in its original spelling."], ["unicode", "case-folding"], "easy"),
    p("negative-zero-format", "A rounding crumb prints as negative zero", "A ledger formatter prints tiny negative adjustments with two decimals and produces '-0.00', which the accounting export rejects.",
      "Input.amounts contains JSON numbers with magnitude below 1,000,000 and at most three decimal places, none ending in exactly five thousandths. Format each with exactly two decimal places using ordinary rounding. A value that rounds to zero must be formatted as '0.00', never '-0.00'.",
      '''
      def solve(data):
          return [format(float(amount), "z.2f") for amount in data["amounts"]]
      ''', ('"z.2f"', '".2f"'),
      [({"amounts": [12.5, 3]}, ["12.50", "3.00"]), ({"amounts": [-0.004, 0.001]}, ["0.00", "0.00"]), ({"amounts": [-0.006, -12.346]}, ["-0.01", "-12.35"]), ({"amounts": [-0.001, 0]}, ["0.00", "0.00"]), ({"amounts": [-0.002, -0.996, 999999.999]}, ["0.00", "-1.00", "1000000.00"])],
      ["What sign does a negative value keep after it rounds to zero?", "Rounding -0.004 to two places produces negative zero, and standard float formatting prints it as '-0.00'.", "Use the 'z' format option, format(value, 'z.2f'), or normalize negative zero before formatting."], ["formatting", "floating-point", "negative-zero"], "easy"),
    p("half-even-star-average", "Half-point averages round toward even", "A ratings widget rounds averages with Python's round(), which sends exact halves to the nearest even integer instead of rounding them up.",
      "Input.ratings contains nonempty lists of integer star ratings from 1 through 5. Return each list's average rounded to the nearest integer, with an exact half rounded up. Use exact arithmetic.",
      '''
      def solve(data):
          return [(2 * sum(stars) + len(stars)) // (2 * len(stars)) for stars in data["ratings"]]
      ''', ('(2 * sum(stars) + len(stars)) // (2 * len(stars))', 'round(sum(stars) / len(stars))'),
      [({"ratings": [[5, 4, 3], [1, 2]]}, [4, 2]), ({"ratings": [[4, 5]]}, [5]), ({"ratings": []}, []), ({"ratings": [[2, 3], [3, 4], [1, 1, 2, 2]]}, [3, 4, 2]), ({"ratings": [[1], [5, 5, 4], [2, 2, 3, 3]]}, [1, 5, 3])],
      ["How does Python's round() break an exact tie such as 4.5?", "round() uses round-half-to-even, so 2.5 and 4.5 round down while 1.5 and 3.5 round up.", "Compute floor((2 * sum + n) / (2 * n)) with integer arithmetic so every exact half rounds up."], ["rounding", "integer-arithmetic"]),
]
