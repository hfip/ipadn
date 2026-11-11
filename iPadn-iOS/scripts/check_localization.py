#!/usr/bin/env python3
"""Audits the Arabic String Catalogs against the Swift sources.

1. `Localizable.xcstrings` and `InfoPlist.xcstrings` must be valid catalogs with
   every value marked `translated` and the same number of format placeholders
   as their key (Arabic plural zero/one/two forms may drop the number).
2. Every `String(localized: "…")` literal must have a catalog entry, because a
   missing key silently falls back to Chinese.
3. Every Chinese literal in a position SwiftUI localizes by itself
   (`Text("…")`, `Label("…")`, `.navigationTitle("…")`, `LocalizedStringResource`
   for App Intents, …) must have an entry too.

The scan is lexical, not a Swift parser: comments are skipped, string literals
are read with their `\\( … )` interpolations (nested string literals included),
and placeholders are compared by count rather than by type, so `%lld` and `%@`
are interchangeable here. It never replaces swiftc, Xcode or a real RTL pass.

Usage:
    python3 scripts/check_localization.py                # report every app source
    python3 scripts/check_localization.py --missing      # list keys only
    python3 scripts/check_localization.py --strict FILE… # fail on misses in FILEs
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOGS = [ROOT / "iPadn/Resources/Localizable.xcstrings", ROOT / "iPadn/Resources/InfoPlist.xcstrings"]
CJK = re.compile(r"[\u4e00-\u9fff]")
PLACEHOLDER = re.compile(r"%(?:\d+\$)?(?:lld|ld|d|u|@|\.\d+f|f|lf)")
AUTO = re.compile(
    r"(?:Text|Label|Button|Toggle|Picker|Section|TextField|SecureField|Link|Stepper"
    r"|alert|confirmationDialog|navigationTitle|accessibilityLabel|accessibilityHint"
    r"|accessibilityValue|IntentDescription|Summary|LocalizedStringResource\s*=)\(\s*$|LocalizedStringResource\s*=\s*$"
)
MARK = "%PH"


def skip_string(src, i):
    """i points at the opening quote; returns the index after the closing quote."""
    triple = src.startswith('"""', i)
    i += 3 if triple else 1
    while i < len(src):
        if src.startswith("\\(", i):
            i += 2
            depth = 1
            while i < len(src) and depth:
                if src[i] == "(":
                    depth += 1
                elif src[i] == ")":
                    depth -= 1
                elif src[i] == '"':
                    i = skip_string(src, i)
                    continue
                i += 1
            continue
        if not triple and src[i] == "\\":
            i += 2
            continue
        if triple and src.startswith('"""', i):
            return i + 3
        if not triple and src[i] == '"':
            return i + 1
        i += 1
    return i


def code_literals(src):
    """Yields (start, end, body) for string literals outside comments."""
    i = 0
    while i < len(src):
        if src.startswith("//", i):
            j = src.find("\n", i)
            i = len(src) if j < 0 else j
            continue
        if src.startswith("/*", i):
            depth = 1
            i += 2
            while i < len(src) and depth:
                if src.startswith("/*", i):
                    depth += 1
                    i += 2
                elif src.startswith("*/", i):
                    depth -= 1
                    i += 2
                else:
                    i += 1
            continue
        if src[i] == '"':
            end = skip_string(src, i)
            triple = src.startswith('"""', i)
            body = src[i + (3 if triple else 1):end - (3 if triple else 1)]
            yield i, end, body
            i = end
            continue
        i += 1


def key_from_body(body):
    """`正在搜索 \\(count) 个` becomes `正在搜索 %PH 个`, with escapes resolved."""
    out = []
    i = 0
    while i < len(body):
        if body.startswith("\\(", i):
            depth = 1
            i += 2
            while i < len(body) and depth:
                if body[i] == "(":
                    depth += 1
                elif body[i] == ")":
                    depth -= 1
                elif body[i] == '"':
                    i = skip_string(body, i)
                    continue
                i += 1
            out.append(MARK)
            continue
        if body[i] == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            out.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(nxt, "\\" + nxt))
            i += 2
            continue
        out.append(body[i])
        i += 1
    return "".join(out)


def normalize(key):
    return PLACEHOLDER.sub(MARK, key)


def placeholders(text):
    return len(PLACEHOLDER.findall(text))


def load_catalogs():
    strings, errors = {}, []
    for path in CATALOGS:
        catalog = json.loads(path.read_text(encoding="utf-8"))
        if catalog.get("sourceLanguage") != "zh-Hans":
            errors.append(f"{path.name}: sourceLanguage must stay zh-Hans")
        for key, entry in catalog.get("strings", {}).items():
            strings.setdefault(key, set()).add(path.name)
            for language, payload in entry.get("localizations", {}).items():
                if "stringUnit" in payload:
                    units = [("", payload["stringUnit"])]
                else:
                    units = [(category, unit["stringUnit"])
                             for category, unit in payload.get("variations", {}).get("plural", {}).items()]
                for category, unit in units:
                    if unit.get("state") != "translated":
                        errors.append(f"{path.name}: {key!r} is not marked translated")
                    found = placeholders(unit.get("value", ""))
                    if category in {"zero", "one", "two"} and found == 0:
                        continue
                    if found != placeholders(key):
                        errors.append(f"{path.name}: placeholder mismatch in {key!r} -> {unit.get('value')!r}")
    return strings, errors


def scan(files):
    explicit, implicit = {}, {}
    for file in files:
        src = file.read_text(encoding="utf-8")
        try:
            name = file.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            name = file.as_posix()
        for start, end, body in code_literals(src):
            pre = src[max(0, start - 45):start]
            wrapped = pre.rstrip().endswith("String(localized:")
            if not (wrapped or AUTO.search(pre)):
                continue
            key = key_from_body(body)
            if not CJK.search(key):
                continue
            bucket = explicit if wrapped else implicit
            bucket.setdefault(key, set()).add(name)
    return explicit, implicit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--missing", action="store_true")
    args = parser.parse_args()

    strings, errors = load_catalogs()
    known = {normalize(key) for key in strings}
    files = [path if path.is_absolute() else Path.cwd() / path for path in args.files] or sorted((ROOT / "iPadn").rglob("*.swift"))
    explicit, implicit = scan(files)

    missing_explicit = {k: v for k, v in explicit.items() if normalize(k) not in known}
    missing_implicit = {k: v for k, v in implicit.items() if normalize(k) not in known}

    for key, where in sorted(missing_explicit.items()):
        errors.append(f"String(localized:) key missing from catalog: {key!r} ({', '.join(sorted(where))})")
    for key, where in sorted(missing_implicit.items()):
        message = f"localized literal missing from catalog: {key!r} ({', '.join(sorted(where))})"
        if args.strict:
            errors.append(message)
        elif args.missing:
            print(message)
        else:
            print("info: " + message, file=sys.stderr)

    print(json.dumps({
        "catalog_keys": len(strings),
        "explicit_keys": len(explicit),
        "implicit_keys": len(implicit),
        "missing_explicit": len(missing_explicit),
        "missing_implicit": len(missing_implicit),
        "errors": len(errors),
    }, ensure_ascii=False))
    for error in errors:
        print("error: " + error)
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
