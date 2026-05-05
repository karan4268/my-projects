# A.T.O.M/tools/code_review.py
"""
Code review tool for the A.T.O.M agent.
Can review raw code strings or files on disk.
Input format:  "file|/path/to/file.py"  OR  "code|python|<raw code>"
"""
from local_engine import get_response_from_atom
try:
    from tools.file_tool import read_file
except ImportError:
    from file_tool import read_file

REVIEW_STANDARDS = {
    "python": """
Python / PEP 8 standards:
- Naming: snake_case for functions/variables, PascalCase for classes, UPPER_CASE for constants.
- Max line length: 79 chars (docstrings/comments: 72).
- Two blank lines between top-level definitions; one blank line between methods.
- All public functions/classes must have docstrings.
- Imports: stdlib first, then third-party, then local. One import per line.
- No bare `except:` — always catch specific exceptions.
- Avoid mutable default arguments (def f(x=[])).
- Use `is` / `is not` for None comparisons.
- Prefer f-strings over % or .format().
""",
    "javascript": """
JavaScript / ESLint standards:
- Use const for values that don't change, let otherwise. Never var.
- Semicolons at end of statements.
- Arrow functions for callbacks. Regular functions for methods.
- === instead of ==.
- Async/await over raw Promises where possible.
- No console.log left in production code.
""",
    "cpp": """
C++ standards:
- Use smart pointers (unique_ptr, shared_ptr) over raw pointers.
- Prefer references over pointers where nullability is not needed.
- RAII for resource management.
- const-correctness: mark methods and parameters const where applicable.
- Avoid C-style casts; use static_cast / dynamic_cast.
- Include guards or #pragma once in headers.
""",
    "default": """
General code quality standards:
- Functions should do one thing (single responsibility).
- Avoid magic numbers — use named constants.
- Variable names should be descriptive.
- No deeply nested logic — extract to helper functions.
- Handle errors explicitly; don't silently swallow exceptions.
- Remove dead/commented-out code before review.
""",
}


def review_code(instruction: str) -> str:
    """
    Review code from a file or raw string.
    Instruction format:
      file|/path/to/file.py
      code|python|<raw code here>
    """
    parts = instruction.split("|", 2)
    mode = parts[0].strip().lower() if parts else ""

    if mode == "file":
        path = parts[1].strip() if len(parts) > 1 else ""
        if not path:
            return "❌ No file path provided. Use: file|/path/to/code.py"
        code = read_file(path)
        if code.startswith("❌"):
            return code
        # Infer language from extension
        ext = path.rsplit(".", 1)[-1].lower() if "." in path else "default"
        lang_map = {"py": "python", "js": "javascript", "ts": "javascript",
                    "cpp": "cpp", "cc": "cpp", "h": "cpp", "hpp": "cpp"}
        language = lang_map.get(ext, "default")

    elif mode == "code":
        language = parts[1].strip().lower() if len(parts) > 1 else "default"
        code = parts[2] if len(parts) > 2 else ""
        if not code.strip():
            return "❌ No code provided. Use: code|python|<your code>"
    else:
        return (
            "❌ Unknown mode. Use:\n"
            "  file|/path/to/file.py\n"
            "  code|python|<raw code>"
        )

    standards = REVIEW_STANDARDS.get(language, REVIEW_STANDARDS["default"])

    # Truncate very long code to stay within model context
    if len(code) > 3000:
        code = code[:3000] + "\n... [truncated]"

    prompt = f"""You are a senior code reviewer. Review the following {language} code.

Standards to check against:
{standards}

Code under review:
```{language}
{code}
```

Provide:
1. A brief summary (1-2 sentences).
2. Issues found — for each: location (line/function), severity (low/medium/high), description.
3. Top 3 most important improvements.
Keep the review concise and actionable."""

    return get_response_from_atom(prompt, max_tokens=900, temperature=0.2)
