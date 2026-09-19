"""Twenty independent crash-diagnosis exercises."""
from functools import partial

from .common import make

p = partial(make, "runtime")

PROBLEMS = [
    p("log-domain-guard", "A zero reading crashes the logarithm", "A sensor dashboard computes natural logarithms, but nonpositive readings stop the entire report.",
      "Input.values contains integers. Return one value per reading: its natural logarithm rounded to six decimal places, or null when the reading is nonpositive.",
      '''
      import math
      def solve(data):
          return [round(math.log(x), 6) if x > 0 else None for x in data["values"]]
      ''', ('if x > 0', 'if x >= 0'),
      [({"values": [1, 2]}, [0.0, 0.693147]), ({"values": [0, 1]}, [None, 0.0]), ({"values": [-3]}, [None]), ({"values": []}, []), ({"values": [10, 0, -1]}, [2.302585, None, None])],
      ["Which values are outside the logarithm domain?", "Zero is outside the real logarithm domain, just like negative inputs.", "Require x > 0 before calling log and preserve one output slot per reading."], ["math", "validation"], "easy"),
    p("square-root-domain", "A negative area stops the geometry report", "A geometry import should flag invalid areas while still calculating valid side lengths.",
      "Input.areas contains integers. Return square roots rounded to six places for nonnegative areas and null for negative areas.",
      '''
      import math
      def solve(data):
          return [round(math.sqrt(x), 6) if x >= 0 else None for x in data["areas"]]
      ''', ('if x >= 0', 'if True'),
      [({"areas": [0, 4]}, [0.0, 2.0]), ({"areas": [-1, 9]}, [None, 3.0]), ({"areas": []}, []), ({"areas": [2]}, [1.414214]), ({"areas": [-9, -4]}, [None, None])],
      ["Can every imported area have a real square root?", "An invalid area should affect only its own output slot.", "Check x >= 0 before sqrt; retain zero as a valid area."], ["math", "batch-processing"], "easy"),
    p("safe-key-removal", "Removing an absent preference throws", "Preference cleanup crashes when a client removes a key that is already absent.",
      "Input.settings is an object and input.remove is a list of string keys. Remove each key if present, ignore missing/repeated keys, and return the remaining object.",
      '''
      def solve(data):
          result = dict(data["settings"])
          for key in data["remove"]:
              result.pop(key, None)
          return result
      ''', ('result.pop(key, None)', 'result.pop(key)'),
      [({"settings": {"a": 1, "b": 2}, "remove": ["a"]}, {"b": 2}), ({"settings": {}, "remove": ["x"]}, {}), ({"settings": {"a": 0}, "remove": ["a", "a"]}, {}), ({"settings": {"a": None}, "remove": []}, {"a": None}), ({"settings": {"a": False}, "remove": ["b"]}, {"a": False})],
      ["What happens when pop cannot find its key?", "Deletion is idempotent under this cleanup contract.", "Use the dictionary pop default or an explicit membership guard so absent keys do not raise."], ["dictionaries", "cleanup"], "easy"),
    p("empty-high-score", "An empty tournament has no winner", "The high-score endpoint crashes before the first result arrives.",
      "Input.scores is a list of integers. Return the maximum score, or null for an empty list. Negative scores are valid.",
      '''
      def solve(data):
          return max(data["scores"], default=None)
      ''', ('max(data["scores"], default=None)', 'max(data["scores"])'),
      [({"scores": [3, 9, 2]}, 9), ({"scores": []}, None), ({"scores": [-8, -2]}, -2), ({"scores": [0]}, 0), ({"scores": [4, 4]}, 4)],
      ["Does max define a result for no candidates?", "Empty input has no score; zero would be a fabricated result.", "Supply an explicit empty default while keeping normal maximum selection."], ["aggregation", "empty-input"], "easy"),
    p("optional-rank-sort", "Unranked entries break the sorter", "A leaderboard mixes ranked and unranked entries, causing comparisons between integers and null.",
      "Input.entries contains {id: string, rank: integer or null}. Return IDs sorted by ascending rank, with null ranks last. Preserve input order for ties.",
      '''
      def solve(data):
          return [e["id"] for e in sorted(data["entries"], key=lambda e: (e["rank"] is None, e["rank"] or 0))]
      ''', ('(e["rank"] is None, e["rank"] or 0)', 'e["rank"]'),
      [({"entries": [{"id": "a", "rank": 2}, {"id": "b", "rank": 1}]}, ["b", "a"]), ({"entries": [{"id": "a", "rank": None}, {"id": "b", "rank": 0}]}, ["b", "a"]), ({"entries": []}, []), ({"entries": [{"id": "a", "rank": None}, {"id": "b", "rank": None}]}, ["a", "b"]), ({"entries": [{"id": "x", "rank": -1}, {"id": "y", "rank": 0}]}, ["x", "y"])],
      ["Which sort keys cannot be compared directly?", "Absence needs its own sort group; zero is a valid rank.", "Sort by a missing flag followed by the numeric rank, relying on stable sorting for ties."], ["sorting", "optional-values"]),
    p("division-batch-isolation", "One zero denominator cancels every ratio", "A metrics batch aborts on a single zero denominator instead of marking that ratio unavailable.",
      "Input.pairs contains [numerator, denominator] integer pairs. Return each quotient rounded to six places, or null for a zero denominator. Keep order and length.",
      '''
      def solve(data):
          return [round(a / b, 6) if b != 0 else None for a, b in data["pairs"]]
      ''', ('if b != 0', 'if a != 0'),
      [({"pairs": [[6, 2]]}, [3.0]), ({"pairs": [[5, 0], [0, 2]]}, [None, 0.0]), ({"pairs": []}, []), ({"pairs": [[-1, 2], [1, -2]]}, [-0.5, -0.5]), ({"pairs": [[0, 0], [1, 3]]}, [None, 0.333333])],
      ["Which operand controls whether division is defined?", "A zero numerator is valid; a zero denominator is not.", "Guard the denominator independently for every pair, preserving the other results."], ["division", "batch-processing"], "easy"),
    p("strict-base64-batch", "A corrupt attachment stops the decoder", "An attachment import needs to report malformed base64 records without discarding valid neighbors.",
      "Input.tokens contains ASCII strings. Decode each using Python base64.b64decode with validate=True. Return decoded bytes as integer lists, or null on a decoding error. Empty text decodes to [].",
      '''
      import base64
      import binascii
      def solve(data):
          result = []
          for token in data["tokens"]:
              try:
                  result.append(list(base64.b64decode(token, validate=True)))
              except binascii.Error:
                  result.append(None)
          return result
      ''', ('except binascii.Error:', 'except KeyError:'),
      [({"tokens": ["YQ=="]}, [[97]]), ({"tokens": ["!", "Yg=="]}, [None, [98]]), ({"tokens": [""]}, [[]]), ({"tokens": []}, []), ({"tokens": ["YQ", "AA=="]}, [None, [0]])],
      ["Which exception does the decoder raise?", "Handle the decoder's documented error inside the per-record loop.", "Catch binascii.Error so a malformed token yields null while later records still decode."], ["encoding", "exceptions"]),
    p("short-import-row", "A short import row crashes validation", "An import expects three columns, but its validator indexes short rows before checking their shape.",
      "Input.rows contains lists of strings. For rows of exactly three columns return the third string unchanged; for every other row length return null.",
      '''
      def solve(data):
          return [row[2] if len(row) == 3 else None for row in data["rows"]]
      ''', ('len(row) == 3', 'len(row) <= 3'),
      [({"rows": [["a", "b", "c"]]}, ["c"]), ({"rows": [["a"], ["x", "y", "z"]]}, [None, "z"]), ({"rows": [[]]}, [None]), ({"rows": [["1", "2", "3", "4"]]}, [None]), ({"rows": [["a", "b", ""]]}, [""])],
      ["What row shape makes index 2 safe and acceptable?", "The contract requires exactly three columns, not at most three.", "Check len(row) == 3 before accessing the third field."], ["validation", "tabular-data"], "easy"),
    p("missing-template-variable", "A missing template value stops rendering", "A simple message template should leave unknown placeholders visible, but missing values raise KeyError.",
      "Input.template contains plain text and {name} placeholders with lowercase ASCII names; no nested braces or format specifiers. Input.values maps names to strings. Replace known names and preserve unknown placeholders literally.",
      r'''
      import re
      def solve(data):
          values = data["values"]
          return re.sub(r"\{([a-z]+)\}", lambda m: values.get(m[1], m[0]), data["template"])
      ''', ('values.get(m[1], m[0])', 'values[m[1]]'),
      [({"template": "Hi {name}", "values": {"name": "Ada"}}, "Hi Ada"), ({"template": "Hi {name}", "values": {}}, "Hi {name}"), ({"template": "{x}{x}", "values": {"x": ""}}, ""), ({"template": "plain", "values": {}}, "plain"), ({"template": "{a}-{b}", "values": {"a": "A"}}, "A-{b}")],
      ["What should an unknown placeholder become?", "Missing keys are permitted template content rather than exceptional application state.", "Use a lookup fallback containing the original matched placeholder and preserve known empty strings."], ["templates", "dictionaries"]),
    p("requested-index-validation", "An invalid selection escapes its list", "A selection endpoint trusts caller-supplied indexes, including negative indexes and indexes past the end.",
      "Input.values is a list of integers and input.indices a list of integers. Return the selected value for each index in [0, len(values)); otherwise return null. Python-style negative indexing is not allowed.",
      '''
      def solve(data):
          values = data["values"]
          return [values[i] if 0 <= i < len(values) else None for i in data["indices"]]
      ''', ('0 <= i < len(values)', '0 <= i <= len(values)'),
      [({"values": [8, 9], "indices": [0, 1]}, [8, 9]), ({"values": [8], "indices": [1]}, [None]), ({"values": [], "indices": [0]}, [None]), ({"values": [3], "indices": [-1, 0]}, [None, 3]), ({"values": [1], "indices": [8]}, [None])],
      ["What is the largest valid index?", "The upper bound is exclusive, even for a list with one element.", "Require 0 <= index < length before indexing."], ["indices", "bounds"], "easy"),
    p("heap-equal-priorities", "Tied priorities compare whole job objects", "A priority queue works until two jobs tie, when Python tries to compare their dictionary payloads.",
      "Input.jobs contains {id: string, priority: integer}. Return IDs by ascending priority, preserving arrival order for ties.",
      '''
      import heapq
      def solve(data):
          heap = []
          for index, job in enumerate(data["jobs"]):
              heapq.heappush(heap, (job["priority"], index, job))
          return [heapq.heappop(heap)[2]["id"] for _ in range(len(heap))]
      ''', ('(job["priority"], index, job)', '(job["priority"], 0, job)'),
      [({"jobs": [{"id": "a", "priority": 2}, {"id": "b", "priority": 1}]}, ["b", "a"]), ({"jobs": [{"id": "b", "priority": 1}, {"id": "a", "priority": 1}]}, ["b", "a"]), ({"jobs": []}, []), ({"jobs": [{"id": "a", "priority": -1}]}, ["a"]), ({"jobs": [{"id": "c", "priority": 0}, {"id": "b", "priority": 0}, {"id": "a", "priority": 0}]}, ["c", "b", "a"])],
      ["Which tuple fields are compared when priorities tie?", "Use a unique ordered tie-breaker before the non-orderable payload.", "Insert the arrival index as the second heap tuple field so ties preserve arrival order."], ["heaps", "tie-breaking"]),
    p("invalid-regex-record", "One invalid expression stops every search", "A saved-search batch includes malformed regular expressions, and one bad pattern aborts the batch.",
      "Input.text is an ASCII string of at most 30 characters. Input.patterns has at most 10 patterns of length at most 20 using literals, dots, anchors, simple character classes, and ?; no groups, backreferences, or * or + quantifiers. Return re.search success per pattern, or null if it is invalid.",
      '''
      import re
      def solve(data):
          result = []
          for pattern in data["patterns"]:
              try:
                  result.append(re.search(pattern, data["text"]) is not None)
              except re.error:
                  result.append(None)
          return result
      ''', ('except re.error:', 'except IndexError:'),
      [({"text": "cat", "patterns": ["ca", "dog"]}, [True, False]), ({"text": "cat", "patterns": ["[", "cat"]}, [None, True]), ({"text": "", "patterns": ["^$"]}, [True]), ({"text": "abc", "patterns": []}, []), ({"text": "a", "patterns": ["[ab]", "?"]}, [True, None])],
      ["Which failure is raised while compiling a pattern?", "Invalid syntax must be isolated to its own result slot.", "Catch re.error around each search and return null without suppressing valid searches."], ["regex", "exceptions"]),
    p("mismatched-column-zip", "Unequal columns break the row builder", "A row builder uses strict zip before validating that both columns have matching lengths.",
      "Input.names is a list of strings and input.scores a list of integers. Return [[name, score], ...] when lengths match, otherwise null. Empty matching lists return [].",
      '''
      def solve(data):
          if len(data["names"]) != len(data["scores"]):
              return None
          return [list(pair) for pair in zip(data["names"], data["scores"], strict=True)]
      ''', ('len(data["names"]) != len(data["scores"])', 'len(data["names"]) < len(data["scores"])'),
      [({"names": ["a"], "scores": [2]}, [["a", 2]]), ({"names": ["a", "b"], "scores": [2]}, None), ({"names": [], "scores": []}, []), ({"names": [], "scores": [1]}, None), ({"names": [""], "scores": [0]}, [["", 0]])],
      ["Does the shape check reject both kinds of mismatch?", "Either column can be longer; strict zip raises for both.", "Reject unequal lengths with != before constructing rows."], ["iteration", "schema"], "easy"),
    p("single-codepoint-ordinal", "A multi-character field breaks ord", "An importer expects optional single-character codes but applies ord to every string.",
      "Input.codes contains valid Unicode strings without lone surrogates. Return ord(code) when it contains exactly one Python Unicode code point; otherwise null.",
      '''
      def solve(data):
          return [ord(value) if len(value) == 1 else None for value in data["codes"]]
      ''', ('len(value) == 1', 'len(value) >= 1'),
      [({"codes": ["A"]}, [65]), ({"codes": ["AB", "C"]}, [None, 67]), ({"codes": [""]}, [None]), ({"codes": ["😀"]}, [128512]), ({"codes": []}, [])],
      ["What exact string length does ord require?", "Nonempty is weaker than exactly one code point.", "Guard with len(value) == 1 and retain null for every other length."], ["unicode", "validation"], "easy"),
    p("hex-byte-decoder", "A malformed hex record aborts the import", "A binary import needs to isolate malformed hexadecimal strings while retaining valid decoded bytes.",
      "Input.records contains strings. Apply Python bytes.fromhex semantics, including ASCII whitespace. Return integer byte lists, or null for each ValueError.",
      '''
      def solve(data):
          output = []
          for value in data["records"]:
              try:
                  output.append(list(bytes.fromhex(value)))
              except ValueError:
                  output.append(None)
          return output
      ''', ('except ValueError:', 'except TypeError:'),
      [({"records": ["00ff"]}, [[0, 255]]), ({"records": ["g0", "41"]}, [None, [65]]), ({"records": ["a"]}, [None]), ({"records": ["", "AA bb"]}, [[], [170, 187]]), ({"records": []}, [])],
      ["Which exception represents invalid hexadecimal syntax?", "Bad digits and an incomplete byte both raise ValueError.", "Catch ValueError per record while allowing the next record to decode."], ["encoding", "batch-processing"]),
    p("fraction-zero-denominator", "An invalid fraction stops normalization", "A fraction service should flag undefined fractions but crashes when it builds them before checking the denominator.",
      "Input.fractions contains integer [numerator, denominator] pairs. Return each reduced pair with a positive denominator, or null when the denominator is zero.",
      '''
      from fractions import Fraction
      def solve(data):
          result = []
          for numerator, denominator in data["fractions"]:
              if denominator == 0:
                  result.append(None)
                  continue
              value = Fraction(numerator, denominator)
              result.append([value.numerator, value.denominator])
          return result
      ''', ('if denominator == 0:', 'if numerator == 0 and denominator == 0:'),
      [({"fractions": [[2, 4]]}, [[1, 2]]), ({"fractions": [[1, 0]]}, [None]), ({"fractions": [[0, 5]]}, [[0, 1]]), ({"fractions": [[2, -4]]}, [[-1, 2]]), ({"fractions": [[0, 0], [-6, -9]]}, [None, [2, 3]])],
      ["Is an undefined denominator specific to a zero numerator?", "Every fraction with denominator zero is undefined.", "Check the denominator alone before constructing Fraction; let Fraction normalize signs and common factors."], ["fractions", "validation"]),
    p("calendar-record-validation", "An impossible date stops the batch", "A calendar import encounters February 30 and stops processing valid dates that follow it.",
      "Input.dates contains strings. Accept only canonical YYYY-MM-DD dates in years 0001 through 9999. Return the weekday number Monday=0 through Sunday=6, or null for invalid syntax/date.",
      '''
      from datetime import date
      def solve(data):
          result = []
          for text in data["dates"]:
              try:
                  value = date.fromisoformat(text)
                  result.append(value.weekday() if value.isoformat() == text else None)
              except ValueError:
                  result.append(None)
          return result
      ''', ('except ValueError:', 'except KeyError:'),
      [({"dates": ["2024-02-29"]}, [3]), ({"dates": ["2024-02-30", "2024-03-01"]}, [None, 4]), ({"dates": ["20240229"]}, [None]), ({"dates": ["", "1900-02-29"]}, [None, None]), ({"dates": []}, [])],
      ["What does the date parser do with an impossible calendar date?", "Both syntax and calendar errors are normal invalid-record outcomes here.", "Catch ValueError per date and retain the canonical round-trip check."], ["dates", "parsing"]),
    p("sample-variance-minimum", "A single sample breaks the statistics job", "A sample-variance report crashes for a newly created stream with fewer than two readings.",
      "Input.samples contains integers. Return the sample variance rounded to six places, or null when fewer than two samples exist.",
      '''
      import statistics
      def solve(data):
          samples = data["samples"]
          return round(statistics.variance(samples), 6) if len(samples) >= 2 else None
      ''', ('len(samples) >= 2', 'len(samples) >= 1'),
      [({"samples": [1, 3]}, 2.0), ({"samples": [9]}, None), ({"samples": []}, None), ({"samples": [4, 4, 4]}, 0.0), ({"samples": [-1, 0, 1]}, 1.0)],
      ["How many samples does sample variance require?", "Sample variance divides by n - 1, which is zero for one sample.", "Require at least two samples before calling statistics.variance."], ["statistics", "empty-input"]),
    p("nested-path-through-scalar", "A lookup keeps walking through a number", "A nested configuration lookup assumes every intermediate value is an object.",
      "Input.document is any JSON value and input.path is a list of string object keys. Follow object keys only; return null if any step is missing or its current value is not an object. An empty path returns the document unchanged.",
      '''
      def solve(data):
          current = data["document"]
          for key in data["path"]:
              if not isinstance(current, dict) or key not in current:
                  return None
              current = current[key]
          return current
      ''', ('not isinstance(current, dict) or key not in current', 'key not in current'),
      [({"document": {"a": {"b": 2}}, "path": ["a", "b"]}, 2), ({"document": {"a": 3}, "path": ["a", "b"]}, None), ({"document": None, "path": []}, None), ({"document": [1], "path": []}, [1]), ({"document": {}, "path": ["x"]}, None)],
      ["What type must support the next object-key lookup?", "A previously valid key can lead to a scalar or null.", "Check isinstance(current, dict) before membership or indexing at every step."], ["nested-data", "type-checking"]),
    p("first-separator-unpack", "A second colon breaks header parsing", "A simple header parser unpacks every colon-separated part into exactly two variables.",
      "Input.lines contains strings. Split each line at its first colon into [name, value], preserving all whitespace and additional colons. Return null for a line without a colon.",
      '''
      def solve(data):
          result = []
          for line in data["lines"]:
              if ":" not in line:
                  result.append(None)
                  continue
              name, value = line.split(":", 1)
              result.append([name, value])
          return result
      ''', ('line.split(":", 1)', 'line.split(":")'),
      [({"lines": ["a:b"]}, [["a", "b"]]), ({"lines": ["time:12:30"]}, [["time", "12:30"]]), ({"lines": ["plain"]}, [None]), ({"lines": [":", "x:"]}, [["", ""], ["x", ""]]), ({"lines": []}, [])],
      ["How many values can an unrestricted split produce?", "Only the first delimiter separates the name from the value.", "Limit split to one separation so the value retains subsequent colons."], ["parsing", "unpacking"], "easy"),
]
