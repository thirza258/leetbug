"""Twenty boundary, representation, and empty-input exercises."""
from functools import partial

from .common import make

p = partial(make, "edge")

PROBLEMS = [
    p("ascii-digit-tokens", "Unicode digits slip into an ASCII identifier", "An ID validator accepts digit characters outside its documented ASCII alphabet.",
      "Input.tokens contains Unicode strings. Return true for each nonempty string made only of ASCII digits 0 through 9; otherwise false.",
      '''
      def solve(data):
          return [bool(text) and all("0" <= char <= "9" for char in text) for text in data["tokens"]]
      ''', ('all("0" <= char <= "9" for char in text)', 'text.isdigit()'),
      [({"tokens": ["123", "x"]}, [True, False]), ({"tokens": ["１２", "²"]}, [False, False]), ({"tokens": [""]}, [False]), ({"tokens": ["0", "001"]}, [True, True]), ({"tokens": [" 1", "+1"]}, [False, False])],
      ["Does isdigit mean ASCII digit only?", "Unicode digit classification includes characters outside 0 through 9.", "Validate every character against the explicit ASCII range and reject empty strings."], ["unicode", "validation"], "easy"),
    p("integer-division-toward-zero", "Negative division rounds the wrong way", "A ported integer-division routine uses floor division where the interface requires truncation toward zero.",
      "Input.a and b are integers with b nonzero. Return the integer quotient truncated toward zero, using exact integer arithmetic.",
      '''
      def solve(data):
          a, b = data["a"], data["b"]
          magnitude = abs(a) // abs(b)
          return -magnitude if (a < 0) != (b < 0) else magnitude
      ''', ('return -magnitude if (a < 0) != (b < 0) else magnitude', 'return a // b'),
      [({"a": 7, "b": 3}, 2), ({"a": -7, "b": 3}, -2), ({"a": 7, "b": -3}, -2), ({"a": -7, "b": -3}, 2), ({"a": 0, "b": -2}, 0)],
      ["How do floor and truncation differ below zero?", "Truncation keeps the magnitude quotient and applies the sign afterward.", "Divide absolute integers, then negate only when the operand signs differ."], ["division", "negative-values"]),
    p("month-shift-clamping", "A month-end renewal skips February", "A monthly renewal adds a fixed number of days instead of moving to the next calendar month.",
      "Input.date is a canonical date in years 2000 through 2098. Return the same day next month, clamped to the last valid day of that month, as YYYY-MM-DD.",
      '''
      import calendar
      from datetime import date, timedelta
      def solve(data):
          current = date.fromisoformat(data["date"])
          year = current.year + (current.month == 12)
          month = current.month % 12 + 1
          day = min(current.day, calendar.monthrange(year, month)[1])
          return date(year, month, day).isoformat()
      ''', ('return date(year, month, day).isoformat()', 'return (current + timedelta(days=30)).isoformat()'),
      [({"date": "2026-04-01"}, "2026-05-01"), ({"date": "2026-01-31"}, "2026-02-28"), ({"date": "2024-01-31"}, "2024-02-29"), ({"date": "2026-12-31"}, "2027-01-31"), ({"date": "2026-02-28"}, "2026-03-28")],
      ["Do all calendar months last thirty days?", "Move the year/month first, then validate the original day in that destination month.", "Clamp the day to monthrange's last day and construct the destination date."], ["calendar", "boundaries"]),
    p("slice-zero-stop", "A zero endpoint returns the whole list", "An optional slice endpoint uses a truthiness fallback that treats zero as omitted.",
      "Input.values is an integer list; stop is null or an integer from 0 through len(values). Return values before stop, or the entire list only when stop is null.",
      '''
      def solve(data):
          stop = len(data["values"]) if data["stop"] is None else data["stop"]
          return data["values"][:stop]
      ''', ('len(data["values"]) if data["stop"] is None else data["stop"]', 'data["stop"] or len(data["values"])'),
      [({"values": [1, 2], "stop": 1}, [1]), ({"values": [1, 2], "stop": 0}, []), ({"values": [1, 2], "stop": None}, [1, 2]), ({"values": [], "stop": 0}, []), ({"values": [3], "stop": 1}, [3])],
      ["Is zero an absent endpoint or an explicit boundary?", "Only null means the endpoint was omitted.", "Test stop is None explicitly instead of using a truthiness fallback."], ["slicing", "sentinels"], "easy"),
    p("signed-decimal-string-order", "Negative identifiers sort by magnitude", "An exact integer-string sorter puts large negative magnitudes after small ones.",
      "Input.values contains canonical decimal integer strings up to 100 digits, optionally prefixed with minus; zero is '0'. Return them in numeric ascending order with duplicates retained. Do not use floating-point conversion.",
      '''
      def solve(data):
          return sorted(data["values"], key=int)
      ''', ('key=int', 'key=lambda text: (text[0] != "-", len(text.lstrip("-")), text.lstrip("-"))'),
      [({"values": ["2", "10"]}, ["2", "10"]), ({"values": ["-2", "-10", "0"]}, ["-10", "-2", "0"]), ({"values": []}, []), ({"values": ["9007199254740993", "9007199254740992"]}, ["9007199254740992", "9007199254740993"]), ({"values": ["0", "-1", "-1"]}, ["-1", "-1", "0"])],
      ["How should negative magnitudes compare?", "A larger absolute value is a smaller number when both operands are negative.", "Parse into Python's exact integers for the sort key, retaining the original strings in output."], ["exact-integers", "sorting"]),
    p("multiset-subtraction", "Removing one duplicate removes them all", "An inventory list subtracts a set of requested values instead of the requested occurrence counts.",
      "Input.values and remove are integer lists. For each occurrence in remove, delete one matching occurrence from values if available. Preserve the order of remaining values, consuming removals against the earliest occurrences.",
      '''
      from collections import Counter
      def solve(data):
          remaining = Counter(data["remove"])
          output = []
          for value in data["values"]:
              if remaining[value] > 0:
                  remaining[value] -= 1
              else:
                  output.append(value)
          return output
      ''', ('remaining[value] -= 1', 'remaining[value] = remaining[value]'),
      [({"values": [1, 2], "remove": [1]}, [2]), ({"values": [1, 2, 1], "remove": [1]}, [2, 1]), ({"values": [], "remove": [1]}, []), ({"values": [2, 2], "remove": [2, 2, 2]}, []), ({"values": [0, -1], "remove": []}, [0, -1])],
      ["Does a removal request name a value or an occurrence?", "A finite removal count must decrease whenever a matching occurrence is consumed.", "Decrement the counter after each removal and retain later occurrences once it reaches zero."], ["multisets", "duplicates"]),
    p("unicode-canonical-dedup", "Equivalent spellings become different labels", "A label importer stores composed and decomposed spellings as separate labels.",
      "Input.labels contains Unicode strings. Normalize each to NFC, remove duplicates after normalization, and return normalized labels in first-occurrence order. Case is significant.",
      '''
      import unicodedata
      def solve(data):
          result, seen = [], set()
          for label in data["labels"]:
              value = unicodedata.normalize("NFC", label)
              if value not in seen:
                  seen.add(value)
                  result.append(value)
          return result
      ''', ('value = unicodedata.normalize("NFC", label)', 'value = label'),
      [({"labels": ["a", "a", "b"]}, ["a", "b"]), ({"labels": ["e\u0301", "é"]}, ["é"]), ({"labels": []}, []), ({"labels": ["A", "a"]}, ["A", "a"]), ({"labels": ["", "", "Å", "A\u030a"]}, ["", "Å"])],
      ["Can two different code-point sequences have the same canonical form?", "Normalize before membership checks as well as before output.", "Apply NFC to each label, then deduplicate the normalized values in order."], ["unicode", "normalization"]),
    p("form-plus-decoding", "A form search keeps plus signs as spaces", "A form decoder confuses a literal encoded plus with a plus that represents a space.",
      "Input.values contains valid application/x-www-form-urlencoded value strings with valid UTF-8 percent encodings. Return decoded strings: raw + means space, percent-encoded %2B means literal +.",
      '''
      from urllib.parse import unquote_plus, unquote
      def solve(data):
          return [unquote_plus(value) for value in data["values"]]
      ''', ('unquote_plus(value)', 'unquote(value).replace("+", " ")'),
      [({"values": ["hello+world"]}, ["hello world"]), ({"values": ["a%2Bb"]}, ["a+b"]), ({"values": [""]}, [""]), ({"values": ["%2B+%20"]}, ["+  "]), ({"values": ["caf%C3%A9"]}, ["café"])],
      ["At what stage can a raw plus be distinguished from an encoded plus?", "Replacing plus after percent decoding destroys literal %2B characters.", "Use unquote_plus, which interprets form plus semantics before percent decoding."], ["urls", "encoding"]),
    p("mixed-newline-normalization", "Windows line endings become double breaks", "A text normalizer replaces carriage returns before accounting for CRLF pairs.",
      "Input.text is a string. Normalize CRLF and lone CR to LF, preserving all other characters and the exact number of logical line breaks. Return the normalized string.",
      r'''
      def solve(data):
          return data["text"].replace("\r\n", "\n").replace("\r", "\n")
      ''', ('.replace("\\r\\n", "\\n").replace("\\r", "\\n")', '.replace("\\r", "\\n").replace("\\r\\n", "\\n")'),
      [({"text": "a\nb"}, "a\nb"), ({"text": "a\r\nb"}, "a\nb"), ({"text": "a\rb"}, "a\nb"), ({"text": "\r\n\r"}, "\n\n"), ({"text": ""}, "")],
      ["Is CRLF one break or two?", "Replacing CR first prevents recognizing the original two-character delimiter.", "Replace CRLF pairs before normalizing the remaining lone carriage returns."], ["text", "normalization"]),
    p("dotfile-extension", "A hidden file becomes its own extension", "A filename helper mistakes a leading dot for an extension separator.",
      "Input.names contains filenames without directory separators. Return the substring after the last dot only when that dot is neither first nor last; otherwise return an empty string. Case is preserved.",
      '''
      def solve(data):
          result = []
          for name in data["names"]:
              dot = name.rfind(".")
              result.append(name[dot + 1:] if 0 < dot < len(name) - 1 else "")
          return result
      ''', ('0 < dot < len(name) - 1', '0 <= dot < len(name) - 1'),
      [({"names": ["report.txt"]}, ["txt"]), ({"names": [".env"]}, [""]), ({"names": ["name.", "plain", ""]}, ["", "", ""]), ({"names": [".config.json"]}, ["json"]), ({"names": ["a.tar.gz", "x.TXT"]}, ["gz", "TXT"])],
      ["Does a leading dot delimit a basename and extension?", "The separator needs characters both before and after it under this contract.", "Require the last dot index to be strictly greater than zero and less than length minus one."], ["filenames", "strings"], "easy"),
    p("utf8-byte-budget", "A character limit exceeds the byte budget", "A payload validator measures Unicode characters instead of the storage limit in UTF-8 bytes.",
      "Input.text is valid Unicode without lone surrogates; limit is a nonnegative byte count. Return whether UTF-8 encoding uses at most limit bytes.",
      '''
      def solve(data):
          return len(data["text"].encode("utf-8")) <= data["limit"]
      ''', ('len(data["text"].encode("utf-8"))', 'len(data["text"])'),
      [({"text": "abc", "limit": 3}, True), ({"text": "é", "limit": 1}, False), ({"text": "😀", "limit": 4}, True), ({"text": "😀", "limit": 3}, False), ({"text": "", "limit": 0}, True)],
      ["Which unit does the storage limit use?", "UTF-8 can use multiple bytes for one Unicode code point.", "Encode to UTF-8 and compare the encoded byte length with the inclusive limit."], ["unicode", "storage-limits"], "easy"),
    p("empty-cartesian-product", "No option groups produce no combinations", "A product builder loses the identity case when there are no option groups.",
      "Input.groups contains at most five lists of at most five integers. Return their Cartesian product as lists in nested input order. No groups yields [[]]; any empty group yields [].",
      '''
      def solve(data):
          result = [[]]
          for group in data["groups"]:
              result = [prefix + [item] for prefix in result for item in group]
          return result
      ''', ('result = [[]]', 'result = []'),
      [({"groups": [[]]}, []), ({"groups": [[1], [2, 3]]}, [[1, 2], [1, 3]]), ({"groups": []}, [[]]), ({"groups": [[0]]}, [[0]]), ({"groups": [[1, 2], []]}, [])],
      ["What partial combination exists before choosing from any group?", "There is exactly one empty choice, which later groups extend.", "Seed the product with one empty list; an empty actual group will correctly erase the product."], ["combinatorics", "identity"]),
    p("zero-exponent-identity", "Raising a number to zero returns zero", "An exponentiation routine starts with the additive identity instead of the multiplicative identity.",
      "Input.base is -10 through 10 and exponent is 0 through 30. Return base raised to exponent, defining 0^0 as 1 for this exercise.",
      '''
      def solve(data):
          result = 1
          for _ in range(data["exponent"]):
              result *= data["base"]
          return result
      ''', ('result = 1', 'result = data["base"] if data["exponent"] == 0 else 1'),
      [({"base": 2, "exponent": 3}, 8), ({"base": 7, "exponent": 0}, 1), ({"base": 0, "exponent": 0}, 1), ({"base": -2, "exponent": 3}, -8), ({"base": 0, "exponent": 4}, 0)],
      ["What is the result of taking no multiplication steps?", "The empty product is one, including the exercise's explicit 0^0 rule.", "Initialize result to one for every exponent and multiply exactly exponent times."], ["arithmetic", "identity"], "easy"),
    p("ceiling-division-negative", "Ceiling division truncates a negative result", "A capacity utility uses a truncating division shortcut that fails below zero.",
      "Input.a is integer and b is a positive integer. Return the mathematical ceiling of a/b using integer arithmetic.",
      '''
      def solve(data):
          return -((-data["a"]) // data["b"])
      ''', ('-((-data["a"]) // data["b"])', 'int(data["a"] / data["b"]) + (data["a"] % data["b"] != 0)'),
      [({"a": 7, "b": 3}, 3), ({"a": -7, "b": 3}, -2), ({"a": -6, "b": 3}, -2), ({"a": 0, "b": 4}, 0), ({"a": 1, "b": 5}, 1)],
      ["Which direction is ceiling on the negative side?", "Ceiling is the negation of floor applied to the negated numerator.", "Use -((-a)//b) so the rule works for both signs without a float conversion."], ["division", "rounding"]),
    p("nearest-rank-percentile", "The percentile selects the next reading", "A nearest-rank percentile passes its one-based rank directly to a zero-based array.",
      "Input.values is a nonempty integer list; percentile is 1 through 100. Sort values, calculate rank=ceil(percentile*n/100), and return the value at one-based rank.",
      '''
      def solve(data):
          values = sorted(data["values"])
          rank = (data["percentile"] * len(values) + 99) // 100
          return values[rank - 1]
      ''', ('values[rank - 1]', 'values[min(rank, len(values) - 1)]'),
      [({"values": [2], "percentile": 50}, 2), ({"values": [10, 20, 30, 40], "percentile": 50}, 20), ({"values": [1, 2], "percentile": 100}, 2), ({"values": [3, 1, 2], "percentile": 1}, 1), ({"values": [-4, -2], "percentile": 50}, -4)],
      ["Is the rank an array index?", "Nearest-rank definitions use one-based ranks while Python lists use zero-based indexes.", "Subtract one after computing the ceiling rank, including at the 100th percentile."], ["statistics", "indexing"]),
    p("padding-minimum-width", "Padding truncates an already long identifier", "A display formatter treats minimum width as a maximum length.",
      "Input.text is an ASCII string and width is 0 through 100. Left-pad with '0' until length is at least width; preserve strings already at least that long.",
      '''
      def solve(data):
          text = data["text"]
          return "0" * max(0, data["width"] - len(text)) + text
      ''', ('+ text', '+ text[:data["width"]]'),
      [({"text": "12", "width": 4}, "0012"), ({"text": "12345", "width": 3}, "12345"), ({"text": "a", "width": 0}, "a"), ({"text": "", "width": 2}, "00"), ({"text": "00", "width": 2}, "00")],
      ["Does minimum width authorize discarding characters?", "Padding adds missing positions but must not truncate existing content.", "Compute a nonnegative pad count and append the complete original string."], ["formatting", "boundaries"], "easy"),
    p("boolean-integer-validation", "True is accepted as a numeric count", "A schema validator uses Python's integer inheritance rules and accepts booleans as counts.",
      "Input.values contains JSON scalar values. Return true only for integer numbers, excluding booleans and all floats, and only in the inclusive range 0 through 100.",
      '''
      def solve(data):
          return [type(value) is int and 0 <= value <= 100 for value in data["values"]]
      ''', ('type(value) is int', 'isinstance(value, int)'),
      [({"values": [0, 100, 101]}, [True, True, False]), ({"values": [True, False, 1]}, [False, False, True]), ({"values": [1.0, "1", None]}, [False, False, False]), ({"values": [-1]}, [False]), ({"values": []}, [])],
      ["Does isinstance(True, int) match the API's number policy?", "Python booleans subclass integers, but this schema explicitly excludes them.", "Require the exact int type before applying the inclusive numeric range."], ["types", "json"], "easy"),
    p("hamming-length-contract", "Unequal strings hide unmatched positions", "A Hamming-distance helper silently truncates the longer input through zip.",
      "Input.left and right are ASCII strings. Return the number of differing positions if lengths are equal; otherwise null. Two empty strings have distance zero.",
      '''
      def solve(data):
          if len(data["left"]) != len(data["right"]):
              return None
          return sum(a != b for a, b in zip(data["left"], data["right"]))
      ''', ('len(data["left"]) != len(data["right"])', 'False'),
      [({"left": "cat", "right": "car"}, 1), ({"left": "a", "right": "ab"}, None), ({"left": "", "right": ""}, 0), ({"left": "", "right": "a"}, None), ({"left": "abc", "right": "xyz"}, 3)],
      ["What data does zip leave unexamined?", "Hamming distance under this contract requires equal-length inputs.", "Reject unequal lengths before comparing paired positions."], ["strings", "length-validation"], "easy"),
    p("fixed-width-bit-complement", "A complement includes infinitely many high bits", "A bitmask viewer uses Python's unbounded signed complement for a fixed-width field.",
      "Input.width is 1 through 20 and value is from 0 through 2^width-1. Return the integer complement restricted to exactly width bits.",
      '''
      def solve(data):
          return (~data["value"]) & ((1 << data["width"]) - 1)
      ''', ('(~data["value"]) & ((1 << data["width"]) - 1)', '~data["value"]'),
      [({"value": 0, "width": 1}, 1), ({"value": 5, "width": 3}, 2), ({"value": 7, "width": 3}, 0), ({"value": 0, "width": 4}, 15), ({"value": 1, "width": 1}, 0)],
      ["How many bits does the field have, and how many does Python's signed integer complement retain?", "The output must be masked to the field width.", "AND the complement with (1 << width) - 1 to discard all higher bits."], ["bitmasks", "integer-width"]),
    p("overnight-clock-window", "An overnight window is always closed", "An access schedule assumes its start time is earlier than its end time.",
      "Input.start, end, and now are minute-of-day integers 0 through 1439. Return whether now is in [start,end), wrapping midnight when start > end. Equal start/end defines an empty window.",
      '''
      def solve(data):
          start, end, now = data["start"], data["end"], data["now"]
          if start < end:
              return start <= now < end
          if start > end:
              return now >= start or now < end
          return False
      ''', ('return now >= start or now < end', 'return now >= start and now < end'),
      [({"start": 60, "end": 120, "now": 90}, True), ({"start": 1380, "end": 60, "now": 30}, True), ({"start": 1380, "end": 60, "now": 60}, False), ({"start": 0, "end": 0, "now": 0}, False), ({"start": 1380, "end": 60, "now": 1380}, True)],
      ["Is an overnight interval one ordinary ordered range?", "It is the union of the late-day and early-day ranges.", "Use OR between now >= start and now < end when the window wraps midnight."], ["time", "circular-ranges"]),
]
