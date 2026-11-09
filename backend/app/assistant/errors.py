"""Interpretation of common runtime and compile errors per language (deterministic assistant)."""
import re

# (languages or None for all, pattern, label, meaning, what to check). ``{0}``/``{1}`` are match groups.
ERROR_PATTERNS = [
    (("python",), r"KeyError: (.+)", "KeyError",
     "a dictionary lookup used the key {0}, which is not present",
     "Find where that key is read. Decide whether a missing key is valid input (read it with a default) or should be rejected earlier."),
    (("python",), r"IndexError: (.+)", "IndexError",
     "an index was outside the sequence ({0})",
     "Check loop bounds and empty inputs; the last valid index is len(sequence) - 1."),
    (("python",), r"TypeError: '?NoneType'? object (is not subscriptable|is not iterable|has no attribute.*)", "TypeError on None",
     "a value the code expected to be a collection or object was None ({0})",
     "Find which variable or call returned None: a missing return statement, an optional field, or a lookup that found nothing."),
    (("python",), r"TypeError: (.+)", "TypeError",
     "an operation received a value of the wrong type ({0})",
     "Print or inspect the types involved at that line; JSON input gives dict, list, str, int, float, bool or None."),
    (("python",), r"ZeroDivisionError", "ZeroDivisionError",
     "a division or modulo used a zero divisor",
     "Handle the empty or zero case before dividing."),
    (("python",), r"AttributeError: (.+)", "AttributeError",
     "an attribute or method does not exist on that value ({0})",
     "Check the value's actual type; dictionaries use keys, not attributes."),
    (("python",), r"RuntimeError: dictionary changed size during iteration", "RuntimeError",
     "the code added or removed dictionary entries while iterating over the same dictionary",
     "Iterate over a copy such as list(d.items()), or collect changes and apply them after the loop."),
    (("python",), r"RecursionError", "RecursionError",
     "a recursive call never reached its base case",
     "Check the base case and that each call moves toward it; cycles in input data need a visited set."),
    (("python",), r"JSONDecodeError|Expecting value", "JSONDecodeError",
     "text that is not valid JSON was parsed",
     "Inspect the exact string being parsed and handle empty or malformed input."),
    (("python",), r"(?:NameError|UnboundLocalError): (.+)", "NameError",
     "a variable was used before it was defined in that scope ({0})",
     "Check spelling and whether the variable is assigned on every path before use."),
    (("python",), r"(?:SyntaxError|IndentationError): (.+)", "SyntaxError",
     "the file could not be parsed ({0})",
     "Fix the syntax at the reported line before testing behaviour."),
    (("python",), r"ValueError: (.+)", "ValueError",
     "a value had the right type but an invalid content ({0})",
     "Validate or normalize the input before converting it."),
    (("javascript",), r"TypeError: Cannot read propert(?:y|ies) of (undefined|null)(?: \(reading '([^']+)'\))?",
     "TypeError on {0}", "the code read a property of {0}",
     "Find which expression is {0}: a missing object key, an out-of-range array element, or a function that returned nothing."),
    (("javascript",), r"TypeError: Cannot mix BigInt and other types", "TypeError (BigInt)",
     "BigInt and Number values were combined in one arithmetic expression",
     "Convert explicitly with BigInt() or Number() so both operands have the same type."),
    (("javascript",), r"TypeError: (?:Converting circular structure to JSON|Do not know how to serialize a BigInt)",
     "TypeError in JSON.stringify", "the result could not be serialized to JSON",
     "Return plain objects, arrays, strings, numbers and booleans; convert BigInt to strings and break cycles."),
    (("javascript",), r"TypeError: Assignment to constant variable", "TypeError (const)",
     "a const binding was reassigned",
     "Use let for values that change, or build a new value instead of reassigning."),
    (("javascript",), r"TypeError: (\S+) is not a function", "TypeError",
     "{0} is not callable",
     "Check the value's type and whether a method exists on it."),
    (("javascript",), r"ReferenceError: (\S+) is not defined", "ReferenceError",
     "{0} is used but never declared in scope",
     "Declare the variable or fix its name."),
    (("javascript",), r"RangeError: Maximum call stack size exceeded", "RangeError",
     "recursion never reached its base case",
     "Check the base case and cycles in the input."),
    (("javascript",), r"SyntaxError: (.+)", "SyntaxError", "parsing failed ({0})",
     "Check the reported location; JSON.parse needs valid JSON text."),
    (("java",), r"NullPointerException(?:: (.+))?", "NullPointerException",
     "null was used where an object was required",
     "Find which reference or boxed number is null at that line, for example a missing map entry or an unboxed Integer."),
    (("java",), r"(ArrayIndexOutOfBounds|StringIndexOutOfBounds|IndexOutOfBounds)Exception(?:: (.+))?", "{0}Exception",
     "an index was outside the valid range ({1})",
     "Check loop bounds and empty inputs; valid indexes run from 0 to length - 1."),
    (("java",), r"ArithmeticException: / by zero", "ArithmeticException",
     "an integer division used a zero divisor",
     "Handle the zero or empty case before dividing."),
    (("java",), r"ArithmeticException: Non-terminating decimal expansion", "ArithmeticException",
     "BigDecimal.divide had no rounding rule for a repeating decimal",
     "Pass a scale and RoundingMode to divide."),
    (("java",), r"NumberFormatException(?:: (.+))?", "NumberFormatException",
     "a string could not be parsed as a number ({0})",
     "Validate or trim the text before parsing."),
    (("java",), r"ClassCastException(?:: (.+))?", "ClassCastException",
     "a value was cast to a type it does not have ({0})",
     "Check the runtime type of the JSON element before converting it."),
    (("java",), r"ConcurrentModificationException", "ConcurrentModificationException",
     "a collection was modified while it was being iterated",
     "Use Iterator.remove() or removeIf, or iterate over a copy."),
    (("java",), r"IllegalStateException: Duplicate key (.+)", "IllegalStateException",
     "Collectors.toMap received two values for the key {0}",
     "Provide a merge function that decides which value wins."),
    (("java",), r"StackOverflowError", "StackOverflowError",
     "recursion never reached its base case",
     "Check the base case and cycles in the input."),
    (("go",), r"assignment to entry in nil map", "panic: nil map",
     "the code wrote into a map that was never allocated",
     "Create the map with make (or a literal) before adding entries."),
    (("go",), r"invalid memory address or nil pointer dereference", "panic: nil pointer",
     "a nil pointer was dereferenced",
     "Find which pointer is nil at that line and check it before use."),
    (("go",), r"index out of range \[(-?\d+)\] with length (\d+)", "panic: index out of range",
     "index {0} was used on a slice of length {1}",
     "Check loop bounds and empty slices; valid indexes run from 0 to len - 1."),
    (("go",), r"slice bounds out of range(.*)", "panic: slice bounds",
     "a slice expression used bounds outside the slice{0}",
     "Check both slice bounds against len(s), including empty input."),
    (("go",), r"all goroutines are asleep - deadlock", "fatal: deadlock",
     "every goroutine was blocked waiting on a channel or lock",
     "Check that every send has a receiver (or buffer space), that channels are closed, and that locks are released."),
    (("go",), r"interface conversion: (.+)", "panic: interface conversion",
     "a type assertion used the wrong type ({0})",
     "JSON numbers decode as float64 and objects as map[string]interface{}; assert those types."),
    (("go",), r"integer divide by zero", "panic: divide by zero",
     "an integer division used a zero divisor",
     "Handle the zero or empty case before dividing."),
    (("cpp",), r"\[json\.exception\.type_error\.\d+\] (.+)", "nlohmann::json type_error",
     "a JSON value had a different type than requested ({0})",
     "Check the element's type before calling get<T>()."),
    (("cpp",), r"\[json\.exception\.out_of_range\.\d+\] (.+)", "nlohmann::json out_of_range",
     "a JSON key or index was missing ({0})",
     "Check that the key exists (contains) or the index is below size() before at()."),
    (("cpp",), r"std::out_of_range|what\(\):\s+(.+out of range.*)", "std::out_of_range",
     "a bounds-checked access used an invalid position",
     "Check indexes against size(), including empty containers."),
    (("cpp",), r"Segmentation fault|SIGSEGV", "segmentation fault",
     "memory outside a valid object was accessed",
     "Check indexes and iterator validity, especially on empty containers."),
    (None, r"Expected a single JSON result", "Extra output",
     "the program printed something besides its JSON result",
     "Remove debug prints from standard output; write diagnostics to standard error instead."),
]
COMPILED = [(languages, re.compile(pattern), label, meaning, check)
            for languages, pattern, label, meaning, check in ERROR_PATTERNS]

LOCATIONS = {
    "python": (re.compile(r'solution\.py", line (\d+)'), "last"),
    "javascript": (re.compile(r"solution\.js:(\d+)"), "first"),
    "java": (re.compile(r"Solution\.java:(\d+)"), "first"),
    "go": (re.compile(r"solution\.go:(\d+)"), "first"),
    "cpp": (re.compile(r"solution\.cpp:(\d+)"), "first"),
}


def _clean(text: str) -> str:
    # Optional groups that did not match leave "()" or doubled spaces behind.
    return re.sub(r"\s{2,}", " ", re.sub(r"\s*\(\)", "", text)).strip()


def interpret_error(message: str, language: str) -> dict | None:
    if not message:
        return None
    for languages, pattern, label, meaning, check in COMPILED:
        if languages is not None and language not in languages:
            continue
        match = pattern.search(message)
        if not match:
            continue
        groups = [group.strip() if group else "" for group in match.groups()] + ["", ""]
        return {"type": _clean(label.format(*groups)), "meaning": _clean(meaning.format(*groups)),
                "check": _clean(check.format(*groups)), "excerpt": match.group(0)[:200]}
    lines = [line.strip() for line in message.splitlines() if line.strip()]
    if not lines:
        return None
    return {"type": "error", "meaning": f"the program reported: {lines[-1][:200]}",
            "check": "Read the last lines of the error output and the line it points to.", "excerpt": lines[-1][:200]}


def locate_error(message: str, language: str, code: str) -> dict | None:
    """The user's code line an error points to, when the error output names it."""
    if not message or language not in LOCATIONS:
        return None
    pattern, which = LOCATIONS[language]
    matches = pattern.findall(message)
    if not matches:
        return None
    line = int(matches[-1] if which == "last" else matches[0])
    lines = code.splitlines()
    if not 1 <= line <= len(lines):
        return None
    return {"line": line, "text": lines[line - 1].strip()[:200]}
