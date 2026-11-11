#!/usr/bin/env python3
"""Audits the Arabic String Catalog against the Swift sources.

Three things are checked:

1. `iPadn/Resources/Localizable.xcstrings` is valid, complete JSON and every
   translated value keeps the same number of format placeholders as its key.
2. Every `String(localized: "…")` key in the scanned sources exists in the
   catalog (these calls are explicit, so a missing key means a silent fallback
   to Chinese).
3. Every Chinese literal in a position SwiftUI localizes by itself
   (`Text("…")`, `Label("…")`, `.navigationTitle("…")`, alerts, …) exists in
   the catalog too.

Usage:
    python3 scripts/check_localization.py                 # audit every app source
    python3 scripts/check_localization.py --strict FILE…  # fail on misses in FILEs
    python3 scripts/check_localization.py --missing       # print missing keys only

The scan is lexical, not a Swift parser. It never replaces swiftc, Xcode or a
real RTL pass on a device.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "iPadn/Resources/Localizable.xcstrings"
CJK = re.compile(r"[\u4e00-\u9fff]")
LITERAL = re.compile(r'"((?:[^"\\]|\\.)*)"')
EXPLICIT = re.compile(r'String\(localized:\s*"((?:[^"\\]|\\.)*)"')
PLACEHOLDER = re.compile(r"%(?:\d+\$)?(?:lld|ld|d|u|@|\.\d+f|f|lf)")

# Calls whose first string literal SwiftUI treats as a LocalizedStringKey.
LOCALIZED_CALLS = re.compile(
    r"(?:Text|Label|Button|Toggle|Picker|Section|TextField|SecureField|Link|Stepper"
    r"|alert|confirmationDialog|navigationTitle|accessibilityLabel|accessibilityHint"
    r"|accessibilityValue)\(\s*$"
)


def placeholder_count(text: str) -> int:
    return len(PLACEHOLDER.findall(text))


def unescape(literal: str) -> str:
    return (literal.replace("\\\\", "\\").replace('\\"', '"')
            .replace("\\n", "\n").replace("\\t", "\t"))


def source_key(literal: str) -> str:
    r"""Turns `正在搜索 \(count) 个` into `正在搜索 %lld 个`-shaped text."""
    return re.sub(r"\\\([^)]*\)", "%lld", unescape(literal))


def load_catalog():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    if catalog.get("sourceLanguage") != "zh-Hans":
        raise SystemExit("catalog sourceLanguage must stay zh-Hans")
    errors = []
    strings = catalog.get("strings", {})
    for key, entry in strings.items():
        for language, payload in entry.get("localizations", {}).items():
            if "stringUnit" in payload:
                units = [("", payload["stringUnit"])]
            else:
                units = [(category, unit["stringUnit"])
                         for category, unit in payload.get("variations", {}).get("plural", {}).items()]
            for category, unit in units:
                if unit.get("state") != "translated":
                    errors.append(f"{language}: {key!r} is not marked translated")
                wanted = placeholder_count(key)
                found = placeholder_count(unit.get("value", ""))
                # Arabic zero/one/two forms read naturally without the number.
                if category in {"zero", "one", "two"} and found == 0:
                    continue
                if found != wanted:
                    errors.append(f"{language}: placeholder mismatch in {key!r} -> {unit.get('value')!r}")
    return strings, errors


def relative(file: Path) -> str:
    try:
        return file.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return file.as_posix()


def scan(files):
    explicit, implicit = {}, {}
    for file in files:
        text = file.read_text(encoding="utf-8")
        for match in EXPLICIT.finditer(text):
            explicit.setdefault(source_key(match.group(1)), set()).add(relative(file))
        for match in LITERAL.finditer(text):
            literal = match.group(1)
            if not CJK.search(literal):
                continue
            before = text[max(0, match.start() - 40):match.start()]
            if LOCALIZED_CALLS.search(before):
                implicit.setdefault(source_key(literal), set()).add(relative(file))
    return explicit, implicit


def normalized(keys):
    return {re.sub(r"%[^\s，。、）」]*", "%@", key) for key in keys}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--missing", action="store_true")
    args = parser.parse_args()

    strings, errors = load_catalog()
    files = [path if path.is_absolute() else Path.cwd() / path for path in args.files] or sorted((ROOT / "iPadn").rglob("*.swift"))
    explicit, implicit = scan(files)

    known = normalized(strings)
    missing_explicit = {k: v for k, v in explicit.items() if re.sub(r"%[^\s，。、）」]*", "%@", k) not in known}
    missing_implicit = {k: v for k, v in implicit.items() if re.sub(r"%[^\s，。、）」]*", "%@", k) not in known}

    for key, where in sorted(missing_explicit.items()):
        errors.append(f"String(localized:) key missing from catalog: {key!r} ({', '.join(sorted(where))})")
    for key in sorted(missing_implicit):
        message = f"localized literal missing from catalog: {key!r} ({', '.join(sorted(missing_implicit[key]))})"
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
