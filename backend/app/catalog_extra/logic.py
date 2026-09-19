"""Twenty algorithm and control-flow repairs."""
from functools import partial

from .common import make

p = partial(make, "logic")

PROBLEMS = [
    p("merge-unconsumed-tail", "The merge drops its remaining tail", "A merge service loses records after one sorted input runs out.",
      "Input.left and input.right are ascending integer lists. Return their sorted merge, preserving every occurrence.",
      '''
      def solve(data):
          a, b = data["left"], data["right"]
          i = j = 0
          result = []
          while i < len(a) and j < len(b):
              if a[i] <= b[j]:
                  result.append(a[i]); i += 1
              else:
                  result.append(b[j]); j += 1
          result.extend(a[i:])
          result.extend(b[j:])
          return result
      ''', ('result.extend(b[j:])', 'result.extend(b[j:j])'),
      [({"left": [1, 4], "right": [2, 3]}, [1, 2, 3, 4]), ({"left": [1], "right": [2, 3]}, [1, 2, 3]), ({"left": [], "right": [0]}, [0]), ({"left": [2, 2], "right": [2]}, [2, 2, 2]), ({"left": [], "right": []}, [])],
      ["What remains when the main loop ends?", "Only one input is exhausted; the other still owns unconsumed elements.", "Append both suffixes from their current indexes after the comparison loop."], ["merge", "arrays"], "easy"),
    p("insertion-sort-front", "The smallest value cannot reach the front", "An insertion sort leaves the first element in the wrong position.",
      "Input.values is an integer list. Return the list sorted ascending, retaining duplicates.",
      '''
      def solve(data):
          values = list(data["values"])
          for i in range(1, len(values)):
              item, j = values[i], i - 1
              while j >= 0 and values[j] > item:
                  values[j + 1] = values[j]
                  j -= 1
              values[j + 1] = item
          return values
      ''', ('j >= 0 and', 'j > 0 and'),
      [({"values": [1, 3, 2]}, [1, 2, 3]), ({"values": [2, 1]}, [1, 2]), ({"values": []}, []), ({"values": [3, 2, 1]}, [1, 2, 3]), ({"values": [0, -1, -1]}, [-1, -1, 0])],
      ["Can the shifting loop inspect index zero?", "The first element also belongs to the sorted prefix.", "Allow j == 0 while shifting and stop only after j becomes negative."], ["sorting", "loop-boundaries"], "easy"),
    p("gcd-final-remainder", "The common divisor becomes zero", "A fraction helper returns the remainder that ended Euclid's loop instead of the last divisor.",
      "Input.a and input.b are integers. Return their nonnegative greatest common divisor; gcd(0,0)=0.",
      '''
      def solve(data):
          a, b = abs(data["a"]), abs(data["b"])
          while b:
              a, b = b, a % b
          return a
      ''', ('return a', 'return b'),
      [({"a": 0, "b": 0}, 0), ({"a": 18, "b": 12}, 6), ({"a": -9, "b": 6}, 3), ({"a": 7, "b": 0}, 7), ({"a": 8, "b": 9}, 1)],
      ["Which variable is guaranteed to be zero at loop exit?", "The last nonzero divisor is retained in a.", "Return a after repeatedly replacing (a,b) with (b,a%b)."], ["number-theory", "state"], "easy"),
    p("prime-square-boundary", "A perfect square is labeled prime", "A primality check never tests the divisor exactly at the square root.",
      "Input.n is an integer from -100 to 1,000,000. Return whether it is prime; values below 2 are not prime.",
      '''
      def solve(data):
          n = data["n"]
          if n < 2:
              return False
          divisor = 2
          while divisor * divisor <= n:
              if n % divisor == 0:
                  return False
              divisor += 1
          return True
      ''', ('divisor * divisor <= n', 'divisor * divisor < n'),
      [({"n": 7}, True), ({"n": 49}, False), ({"n": 2}, True), ({"n": 1}, False), ({"n": 4}, False)],
      ["Which divisor proves a perfect square composite?", "The square-root boundary must be included.", "Continue while divisor squared is less than or equal to n."], ["number-theory", "boundaries"], "easy"),
    p("clockwise-matrix-rotation", "The preview rotates the wrong way", "A square image transformation mirrors the intended rotation.",
      "Input.matrix is a square integer matrix with side length 0 through 20. Return a new matrix rotated 90 degrees clockwise.",
      '''
      def solve(data):
          matrix = data["matrix"]
          n = len(matrix)
          return [[matrix[n - 1 - col][row] for col in range(n)] for row in range(n)]
      ''', ('matrix[n - 1 - col][row]', 'matrix[col][n - 1 - row]'),
      [({"matrix": [[1]]}, [[1]]), ({"matrix": [[1, 2], [3, 4]]}, [[3, 1], [4, 2]]), ({"matrix": []}, []), ({"matrix": [[1, 2, 3], [4, 5, 6], [7, 8, 9]]}, [[7, 4, 1], [8, 5, 2], [9, 6, 3]]), ({"matrix": [[0, -1], [2, 0]]}, [[2, 0], [0, -1]])],
      ["Where should the original top-left cell move?", "A clockwise turn sends original (r,c) to (c,n-1-r).", "Build output[row][col] from input[n-1-col][row]."], ["matrices", "indexing"]),
    p("bracket-type-matching", "Balanced counts hide crossed brackets", "A validator accepts mismatched bracket types as long as opening and closing counts balance.",
      "Input.text contains only ()[]{}. Return true exactly when brackets are correctly nested and paired. Empty text is valid.",
      '''
      def solve(data):
          stack = []
          pairs = {')': '(', ']': '[', '}': '{'}
          for char in data["text"]:
              if char in "([{":
                  stack.append(char)
              elif not stack or stack.pop() != pairs[char]:
                  return False
          return not stack
      ''', ('stack.pop() != pairs[char]', 'stack.pop() not in "([{"'),
      [({"text": "([])"}, True), ({"text": "([)]"}, False), ({"text": ""}, True), ({"text": "]"}, False), ({"text": "(("}, False)],
      ["Do equal opening and closing counts prove proper nesting?", "Each closing bracket must match the most recent opening type.", "Compare the popped opening character with the required opening for this closing character."], ["stacks", "parsing"]),
    p("postfix-operand-order", "Subtraction reverses its operands", "A postfix calculator passes addition examples but reverses subtraction.",
      "Input.tokens is a valid nonempty postfix expression containing integer strings and +, -, *. Every operator has two operands and the expression leaves one result. Return that integer result.",
      '''
      def solve(data):
          stack = []
          for token in data["tokens"]:
              if token in {"+", "-", "*"}:
                  right, left = stack.pop(), stack.pop()
                  stack.append(left + right if token == "+" else left - right if token == "-" else left * right)
              else:
                  stack.append(int(token))
          return stack[0]
      ''', ('right, left = stack.pop(), stack.pop()', 'left, right = stack.pop(), stack.pop()'),
      [({"tokens": ["2", "3", "+"]}, 5), ({"tokens": ["8", "3", "-"]}, 5), ({"tokens": ["-2"]}, -2), ({"tokens": ["2", "3", "4", "*", "+"]}, 14), ({"tokens": ["3", "8", "-"]}, -5)],
      ["Which operand is on top of the stack?", "The right operand is pushed later and must be popped first.", "Pop right, then left, and evaluate left operator right."], ["stacks", "expressions"]),
    p("common-prefix-shrinking", "The common prefix stops shrinking too soon", "A filename grouper removes only one mismatching suffix character.",
      "Input.words contains ASCII strings. Return their longest common prefix, or an empty string for no words.",
      '''
      def solve(data):
          if not data["words"]:
              return ""
          prefix = data["words"][0]
          for word in data["words"][1:]:
              while not word.startswith(prefix):
                  prefix = prefix[:-1]
          return prefix
      ''', ('while not word.startswith(prefix):', 'if not word.startswith(prefix):'),
      [({"words": ["cat", "car"]}, "ca"), ({"words": ["flower", "flight"]}, "fl"), ({"words": []}, ""), ({"words": ["abc", ""]}, ""), ({"words": ["same", "same"]}, "same")],
      ["Can a mismatch require removing more than one character?", "Every word must start with the full candidate prefix.", "Keep shortening in a loop until the current word accepts the prefix."], ["strings", "loops"], "easy"),
    p("flood-fill-diagonal", "Paint leaks through a diagonal corner", "A paint-bucket tool treats diagonal contact as connected pixels.",
      "Input.grid is a nonempty rectangular integer grid up to 20x20, input.row/col are valid indexes, and input.color is an integer. Replace cells connected to the start by four-direction steps that share its original color; return the grid.",
      '''
      def solve(data):
          grid = [row[:] for row in data["grid"]]
          start = (data["row"], data["col"])
          old, new = grid[start[0]][start[1]], data["color"]
          if old == new:
              return grid
          pending = [start]
          directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
          while pending:
              row, col = pending.pop()
              if not (0 <= row < len(grid) and 0 <= col < len(grid[0])) or grid[row][col] != old:
                  continue
              grid[row][col] = new
              pending.extend((row + dr, col + dc) for dr, dc in directions)
          return grid
      ''', ('[(1, 0), (-1, 0), (0, 1), (0, -1)]', '[(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)]'),
      [({"grid": [[1, 1]], "row": 0, "col": 0, "color": 2}, [[2, 2]]), ({"grid": [[1, 0], [0, 1]], "row": 0, "col": 0, "color": 2}, [[2, 0], [0, 1]]), ({"grid": [[1]], "row": 0, "col": 0, "color": 1}, [[1]]), ({"grid": [[0, 0], [0, 0]], "row": 1, "col": 1, "color": 3}, [[3, 3], [3, 3]]), ({"grid": [[1, 2, 1]], "row": 0, "col": 2, "color": 9}, [[1, 2, 9]])],
      ["What kind of adjacency does this tool promise?", "Diagonal contact does not create a four-connected path.", "Expand only up, down, left, and right, marking a cell by recoloring it."], ["graphs", "flood-fill"]),
    p("meeting-room-release", "A room stays occupied at the next start", "A room counter allocates an extra room for meetings that touch at their endpoints.",
      "Input.meetings contains [start,end] integers with start < end. Meetings occupy [start,end), so ending at another start does not overlap. Return the minimum number of rooms.",
      '''
      import heapq
      def solve(data):
          ends = []
          peak = 0
          for start, end in sorted(data["meetings"]):
              while ends and ends[0] <= start:
                  heapq.heappop(ends)
              heapq.heappush(ends, end)
              peak = max(peak, len(ends))
          return peak
      ''', ('ends[0] <= start', 'ends[0] < start'),
      [({"meetings": [[0, 3], [1, 2]]}, 2), ({"meetings": [[0, 1], [1, 2]]}, 1), ({"meetings": []}, 0), ({"meetings": [[2, 3], [0, 2], [1, 2]]}, 2), ({"meetings": [[0, 4], [0, 4], [0, 4]]}, 3)],
      ["Is a meeting still occupying a room at its end timestamp?", "Half-open intervals release resources exactly at their endpoint.", "Remove all end times <= the new start before allocating that meeting."], ["heaps", "intervals"]),
    p("window-expired-frequency", "A repeated character vanishes from the count", "A distinct-character window removes every copy of a character when only one occurrence leaves.",
      "Input.text is an ASCII string and input.k is 0 through 100. Return the longest substring length with at most k distinct characters.",
      '''
      def solve(data):
          counts = {}
          left = best = 0
          for right, char in enumerate(data["text"]):
              counts[char] = counts.get(char, 0) + 1
              while len(counts) > data["k"]:
                  old = data["text"][left]
                  counts[old] -= 1
                  if counts[old] == 0:
                      del counts[old]
                  left += 1
              best = max(best, right - left + 1)
          return best
      ''', ('counts[old] -= 1', 'counts[old] = 0'),
      [({"text": "abc", "k": 2}, 2), ({"text": "aabcc", "k": 2}, 3), ({"text": "", "k": 2}, 0), ({"text": "aaa", "k": 0}, 0), ({"text": "abaccc", "k": 2}, 4)],
      ["Does removing one occurrence remove every copy of that character?", "The frequency table must describe precisely the current window.", "Decrement one occurrence, deleting the key only when its count reaches zero."], ["sliding-window", "frequency"], "hard"),
    p("move-zeroes-stable", "Moving zeroes reverses the other values", "A compaction routine sends zeroes to the end but reverses the surviving values.",
      "Input.values contains integers. Move all zeroes to the end while preserving the relative order of nonzero values.",
      '''
      def solve(data):
          values = data["values"]
          nonzero = [value for value in values if value != 0]
          return nonzero + [0] * (len(values) - len(nonzero))
      ''', ('return nonzero +', 'return nonzero[::-1] +'),
      [({"values": [0, 1]}, [1, 0]), ({"values": [1, 0, 2, 0, 3]}, [1, 2, 3, 0, 0]), ({"values": []}, []), ({"values": [0, 0]}, [0, 0]), ({"values": [-2, 0, -1]}, [-2, -1, 0])],
      ["Does the contract permit reordering nonzero values?", "Compaction preserves the subsequence of surviving values.", "Append the nonzero values in their original order before the required zero suffix."], ["arrays", "stability"], "easy"),
    p("subsequence-forward-only", "A match reuses the same source character", "A subsequence checker counts one character more than once.",
      "Input.source and input.target are ASCII strings. Return true when target is a subsequence of source, using each source position at most once in order. Empty target is valid.",
      '''
      def solve(data):
          position = 0
          for char in data["target"]:
              found = data["source"].find(char, position)
              if found == -1:
                  return False
              position = found + 1
          return True
      ''', ('position = found + 1', 'position = found'),
      [({"source": "abc", "target": "ac"}, True), ({"source": "ab", "target": "aa"}, False), ({"source": "", "target": ""}, True), ({"source": "abc", "target": "ca"}, False), ({"source": "aab", "target": "aa"}, True)],
      ["Where should the next search start after consuming a match?", "A subsequence cannot reuse a source position.", "Advance the search position to found + 1 after every successful match."], ["strings", "two-pointers"], "easy"),
    p("staircase-empty-path", "The staircase recurrence forgets the empty path", "A step counter undercounts every staircase because it seeds the zero-step state incorrectly.",
      "Input.n is 0 through 50. Return the number of ordered ways to climb n steps using moves of size 1 or 2. There is one way to climb zero steps: take no moves.",
      '''
      def solve(data):
          previous, current = 1, 1
          for _ in range(data["n"]):
              previous, current = current, previous + current
          return previous
      ''', ('previous, current = 1, 1', 'previous, current = 0, 1'),
      [({"n": 1}, 1), ({"n": 3}, 3), ({"n": 0}, 1), ({"n": 2}, 2), ({"n": 5}, 8)],
      ["What does the zero-step state contribute to later states?", "The empty path is one valid construction, not zero constructions.", "Initialize ways(0) and ways(1) to one before advancing the recurrence."], ["dynamic-programming", "base-cases"]),
    p("coin-combination-order", "Coin permutations count as new combinations", "A change-making service counts different orders of the same coins as different combinations.",
      "Input.coins contains distinct positive integers and input.amount is 0 through 100. Return the number of unordered combinations using unlimited copies of these coins. Amount zero has one combination.",
      '''
      def solve(data):
          amount = data["amount"]
          ways = [0] * (amount + 1)
          ways[0] = 1
          for coin in data["coins"]:
              for total in range(coin, amount + 1):
                  ways[total] += ways[total - coin]
          return ways[amount]
      ''', ('for coin in data["coins"]:\n        for total in range(coin, amount + 1):', 'for total in range(1, amount + 1):\n        for coin in [c for c in data["coins"] if c <= total]:'),
      [({"coins": [2], "amount": 4}, 1), ({"coins": [1, 2], "amount": 3}, 2), ({"coins": [], "amount": 0}, 1), ({"coins": [2], "amount": 3}, 0), ({"coins": [1, 2, 5], "amount": 5}, 4)],
      ["Are 1+2 and 2+1 different combinations here?", "Processing one denomination at a time avoids recounting permutations.", "Put coins in the outer loop and increasing totals in the inner loop."], ["dynamic-programming", "combinatorics"], "hard"),
    p("histogram-width-boundary", "The histogram rectangle gains a column", "A rectangle analyzer measures one bar too many.",
      "Input.heights contains nonnegative integers, at most 100 bars of width one. Return the maximum area of a rectangle under consecutive bars; empty input returns 0.",
      '''
      def solve(data):
          heights = data["heights"]
          best = 0
          for left in range(len(heights)):
              height = heights[left]
              for right in range(left, len(heights)):
                  height = min(height, heights[right])
                  best = max(best, height * (right - left + 1))
          return best
      ''', ('right - left + 1', 'right - left + 2'),
      [({"heights": []}, 0), ({"heights": [5]}, 5), ({"heights": [2, 1, 2]}, 3), ({"heights": [2, 4]}, 4), ({"heights": [0, 0]}, 0)],
      ["How many bars are in an inclusive index interval?", "The interval from left to right contains right-left+1 bars.", "Multiply the running minimum height by the correct inclusive width."], ["arrays", "intervals"]),
    p("two-pointer-water", "The water container trusts its taller wall", "A container estimator overstates capacity by using the taller boundary.",
      "Input.heights contains nonnegative integers. Choose two distinct indexes; area equals their distance times the shorter height. Return the maximum area, or 0 for fewer than two heights.",
      '''
      def solve(data):
          heights = data["heights"]
          left, right, best = 0, len(heights) - 1, 0
          while left < right:
              best = max(best, (right - left) * min(heights[left], heights[right]))
              if heights[left] <= heights[right]:
                  left += 1
              else:
                  right -= 1
          return best
      ''', ('min(heights[left], heights[right])', 'max(heights[left], heights[right])'),
      [({"heights": [2, 2]}, 2), ({"heights": [1, 5]}, 1), ({"heights": []}, 0), ({"heights": [4]}, 0), ({"heights": [1, 8, 6, 2, 5, 4, 8, 3, 7]}, 49)],
      ["Which wall limits the retained water?", "Water spills over the shorter wall regardless of the other wall's height.", "Measure with the minimum of the two heights and move the shorter boundary inward."], ["two-pointers", "optimization"]),
    p("alternating-sign-run", "Zero bridges an alternating run", "A signal scanner treats zero as a negative value and joins runs that should be separated.",
      "Input.values contains integers. Return the longest contiguous run of nonzero values whose signs alternate. Zero breaks a run; empty input returns 0.",
      '''
      def solve(data):
          previous = run = best = 0
          for value in data["values"]:
              sign = 1 if value > 0 else -1 if value < 0 else 0
              if sign == 0:
                  run = 0
              else:
                  run = run + 1 if previous == -sign else 1
              previous = sign
              best = max(best, run)
          return best
      ''', ('1 if value > 0 else -1 if value < 0 else 0', '1 if value > 0 else -1'),
      [({"values": [1, -2, 3]}, 3), ({"values": [1, 0, 1]}, 1), ({"values": []}, 0), ({"values": [0, 0]}, 0), ({"values": [-1, -2, 3, -4]}, 3)],
      ["Does zero have a positive or negative sign under this contract?", "Zero must reset both the run and the previous sign.", "Represent zero with its own sign value and break the run when it occurs."], ["state-machines", "sequences"]),
    p("majority-candidate-verification", "A candidate is declared the majority", "A vote counter returns a candidate even when no value appears in more than half the positions.",
      "Input.values contains integers. Return the value occurring strictly more than n/2 times, or null when no such value exists.",
      '''
      def solve(data):
          candidate, balance = None, 0
          for value in data["values"]:
              if balance == 0:
                  candidate = value
              balance += 1 if value == candidate else -1
          if candidate is not None and data["values"].count(candidate) * 2 > len(data["values"]):
              return candidate
          return None
      ''', ('data["values"].count(candidate) * 2 > len(data["values"])', 'True'),
      [({"values": [2, 2, 1]}, 2), ({"values": [1, 2, 3]}, None), ({"values": []}, None), ({"values": [0]}, 0), ({"values": [1, 1, 2, 2]}, None)],
      ["Does candidate elimination prove a majority exists?", "The candidate phase assumes a possible majority; it does not count the final frequency.", "Verify the candidate occurs strictly more than half the time before returning it."], ["voting", "validation"]),
    p("next-greater-strict", "An equal value counts as greater", "A monotonic-stack scan accepts equal readings as the next greater reading.",
      "Input.values contains integers. For each position return the first strictly greater value to its right, or null when none exists.",
      '''
      def solve(data):
          values = data["values"]
          result = [None] * len(values)
          pending = []
          for index, value in enumerate(values):
              while pending and values[pending[-1]] < value:
                  result[pending.pop()] = value
              pending.append(index)
          return result
      ''', ('values[pending[-1]] < value', 'values[pending[-1]] <= value'),
      [({"values": [1, 3, 2]}, [3, None, None]), ({"values": [2, 2, 3]}, [3, 3, None]), ({"values": []}, []), ({"values": [3, 2, 1]}, [None, None, None]), ({"values": [-2, -1, 0]}, [-1, 0, None])],
      ["Does an equal reading satisfy strictly greater?", "Equal values must remain pending until a larger value arrives.", "Pop pending indexes only when their value is strictly less than the new value."], ["monotonic-stack", "comparisons"]),
]
