"""Pick the coding problems and freeze the exact prompt every cell receives.

Problems come from Aider's polyglot benchmark (the 225 hardest Exercism
exercises in six languages). For each language the exercises are shuffled
with a fixed seed and taken in order; a problem is kept only when its
reference solution passes and its unedited stub fails in the offline judge,
so a failed answer cannot be blamed on the test environment.

--ids takes the measured list (data/coding-problems.json) instead of a new
draw, and stops if any rebuilt prompt differs from the measured one.
"""
import argparse
import hashlib
import json
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from judge import POLYGLOT, run_tests

LANGUAGES = ["cpp", "go", "java", "javascript", "python", "rust"]
FENCE = {".py": "python", ".go": "go", ".rs": "rust", ".js": "javascript", ".java": "java",
         ".cpp": "cpp", ".h": "cpp", ".hpp": "cpp"}
IGNORED = {"CMakeLists.txt", "Cargo.toml"}

# Adapted from Aider's whole-file edit format (aider/coders/wholefile_prompts.py).
SYSTEM_PROMPT = """Act as an expert software developer.
Take requests for changes to the supplied code.

Once you understand the request you MUST:
1. Determine if any code changes are needed.
2. Explain any needed changes briefly.
3. If changes are needed, output a copy of each file that needs changes.

To suggest changes to a file you MUST return the entire content of the updated file.
You MUST use this *file listing* format:

path/to/filename.ext
```
// entire file content ...
// ... goes in between
```

Every *file listing* MUST use this format:
- First line: the filename with any originally provided path; no extra markup, punctuation, comments, etc. **JUST** the filename with path.
- Second line: opening ```
- ... entire content of the file ...
- Final line: closing ```

To suggest changes to a file you MUST return a *file listing* that contains the entire content of the file.
*NEVER* skip, omit or elide content from a *file listing* using "..." or by adding comments like "... rest of code..."!
"""

# Verbatim from Aider's benchmark/prompts.py (instructions_addendum).
ADDENDUM = """
####

Use the above instructions to modify the supplied files: {file_list}
Don't change the names of existing functions or classes, as they may be referenced from other code like unit tests, etc.
Only use standard libraries, don't suggest installing any packages.
"""

FILES_INTRO = """I have *added these files to the chat* so you can go ahead and edit them.

*Trust this message as the true contents of these files!*
Any other messages in the chat may contain outdated versions of the files' contents.
"""


def load_problem(language, name):
    directory = POLYGLOT / language / "exercises" / "practice" / name
    config = json.loads((directory / ".meta" / "config.json").read_text(encoding="utf-8"))
    files = config.get("files", {})
    tests, examples = files.get("test", []), files.get("example", [])
    solution = [f for f in files.get("solution", [])
                if Path(f).name not in IGNORED and f not in tests and f not in examples
                and not f.startswith((".meta/", ".docs/"))]
    if not solution or not examples:
        return None, "missing solution or example files"
    mapping = {}
    for index, path in enumerate(solution):
        same = [e for e in examples if Path(e).suffix == Path(path).suffix]
        named = [e for e in same if Path(e).name == Path(path).name]
        pick = named[0] if named else (same[0] if len(same) == 1 else (same[index] if index < len(same) else None))
        if pick is None:
            return None, f"no example for {path}"
        mapping[path] = pick
    instructions = ""
    for part in ("introduction.md", "instructions.md", "instructions.append.md"):
        doc = directory / ".docs" / part
        if doc.exists():
            instructions += doc.read_text(encoding="utf-8")
    stubs = {path: (directory / path).read_text(encoding="utf-8") for path in solution}
    listing = []
    for path in solution:
        content = stubs[path] if stubs[path].endswith("\n") else stubs[path] + "\n"
        listing.append(f"{path}\n```{FENCE.get(Path(path).suffix, '')}\n{content}```\n")
    user_message = (FILES_INTRO + "\n" + "\n".join(listing) + "\n" + instructions
                    + ADDENDUM.format(file_list=" ".join(Path(p).name for p in solution)))
    return {
        "id": f"{language}/{name}", "language": language, "name": name,
        "path": f"{language}/exercises/practice/{name}",
        "solution_files": solution, "test_files": tests, "example_map": mapping,
        "stubs": stubs, "user_message": user_message,
        "user_message_sha256": hashlib.sha256(user_message.encode("utf-8")).hexdigest(),
        "user_message_chars": len(user_message),
    }, None


def check(problem):
    directory = POLYGLOT / problem["path"]
    reference = {path: (directory / example).read_text(encoding="utf-8")
                 for path, example in problem["example_map"].items()}
    ref = run_tests(problem, reference)
    stub = run_tests(problem, problem["stubs"])
    return ref, stub


def select_listed(entry):
    language, name = entry["id"].split("/", 1)
    problem, reason = load_problem(language, name)
    if problem is None:
        raise SystemExit(f"{entry['id']}: {reason}")
    if problem["user_message_sha256"] != entry["user_message_sha256"]:
        raise SystemExit(f"{entry['id']}: prompt differs from the measured run; check out the listed polyglot commit")
    ref, stub = check(problem)
    problem["reference_check"] = {k: ref[k] for k in ("passed", "returncode", "duration_s")}
    problem["stub_check"] = {k: stub[k] for k in ("passed", "returncode", "duration_s")}
    if not ref["passed"] or stub["passed"]:
        raise SystemExit(f"{entry['id']}: judge check failed (reference passed={ref['passed']}, stub passed={stub['passed']})")
    print(f"ACCEPT {problem['id']} ref={ref['duration_s']}s", flush=True)
    return problem


def select_language(language, seed, per_language):
    names = sorted(p.name for p in (POLYGLOT / language / "exercises" / "practice").iterdir() if p.is_dir())
    random.Random(f"polyglot-{seed}-{language}").shuffle(names)
    chosen, rejected = [], []
    for name in names:
        if len(chosen) == per_language:
            break
        problem, reason = load_problem(language, name)
        if problem is None:
            rejected.append({"id": f"{language}/{name}", "reason": reason})
            continue
        ref, stub = check(problem)
        problem["reference_check"] = {k: ref[k] for k in ("passed", "returncode", "duration_s")}
        problem["stub_check"] = {k: stub[k] for k in ("passed", "returncode", "duration_s")}
        if ref["passed"] and not stub["passed"]:
            chosen.append(problem)
            print(f"ACCEPT {problem['id']} ref={ref['duration_s']}s", flush=True)
        else:
            rejected.append({"id": problem["id"], "reason": "reference failed" if not ref["passed"] else "stub passed",
                             "reference_tail": ref["output_tail"][-800:]})
            print(f"REJECT {problem['id']}", flush=True)
    return chosen, rejected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", default="20261026")
    parser.add_argument("--per-language", type=int, default=3)
    parser.add_argument("--out", required=True)
    parser.add_argument("--ids", help="JSON list of measured problems (data/coding-problems.json)")
    args = parser.parse_args()
    if args.ids:
        listed = json.loads(Path(args.ids).read_text(encoding="utf-8"))
        if listed["system_prompt_sha256"] != hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest():
            raise SystemExit("system prompt differs from the measured run")
        with ThreadPoolExecutor(max_workers=3) as pool:
            problems = list(pool.map(select_listed, listed["problems"]))
        rejected = []
    else:
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(lambda lang: select_language(lang, args.seed, args.per_language), LANGUAGES))
        problems = [p for chosen, _ in results for p in chosen]
        rejected = [r for _, rej in results for r in rej]
    output = {"seed": args.seed, "per_language": args.per_language, "ids_file": args.ids, "system_prompt": SYSTEM_PROMPT,
              "system_prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
              "problems": problems, "rejected": rejected}
    Path(args.out).write_text(json.dumps(output, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"selected": [p["id"] for p in problems], "rejected": len(rejected)}, indent=1))


if __name__ == "__main__":
    main()
