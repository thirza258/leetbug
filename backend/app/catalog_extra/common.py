"""Authoring helpers; expected results are supplied explicitly, never computed from solutions."""
from textwrap import dedent


def make(category, slug, title, summary, requirements, solution, mutation, examples, hints, tags,
         difficulty="medium"):
    source = dedent(solution).strip() + "\n"
    correct, broken = mutation
    if source.count(correct) != 1:
        raise ValueError(f"{slug}: mutation must identify exactly one source fragment")
    tests = []
    for index, (data, expected) in enumerate(examples):
        tests.append({"name": f"Example {index + 1}" if index < 2 else f"Boundary check {index - 1}",
                      "input": data, "expected": expected, "hidden": index >= 2,
                      "assertions": [{"path": "state", "equals": expected["state"]}]
                      if isinstance(expected, dict) and "state" in expected else []})
    return dict(slug=slug, title=title, summary=summary, description=summary, category=category,
                difficulty=difficulty, tags=tags,
                requirements=[requirements, "Unless this problem specifies different limits, lists have at most 100 entries, strings at most 200 characters, and input integers have magnitude at most 1,000,000. Inputs follow the described shape."],
                starters={"python": source.replace(correct, broken, 1)}, solutions={"python": source},
                tests=tests, explanation=" ".join(hints[1:]), hints=hints,
                estimated_minutes={"easy": 12, "medium": 20, "hard": 30}[difficulty])
