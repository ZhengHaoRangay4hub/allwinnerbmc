#!/usr/bin/env python3
"""Merge and validate the Simplified Chinese WebUI locale."""

import json
from pathlib import Path
import re
import sys


def deep_merge(base, overlay):
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def leaves(value, prefix=""):
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else key
            result.update(leaves(child, child_prefix))
        return result
    return {prefix: value}


def placeholders(value):
    if not isinstance(value, str):
        return set()
    return set(re.findall(r"\{[^{}]+\}", value))


def normalize_legacy_placeholders(value):
    if isinstance(value, dict):
        for key, child in value.items():
            value[key] = normalize_legacy_placeholders(child)
    elif isinstance(value, list):
        value = [normalize_legacy_placeholders(child) for child in value]
    elif isinstance(value, str):
        value = value.replace("%{", "{")
    return value


def main(arguments):
    if len(arguments) != 5:
        raise SystemExit(
            "usage: merge-webui-locales.py ENGLISH UPSTREAM ADDITIONS OUTPUT"
        )
    english_path, upstream_path, additions_path, output_path = map(
        Path, arguments[1:]
    )
    english = json.loads(english_path.read_text(encoding="utf-8"))
    chinese = json.loads(upstream_path.read_text(encoding="utf-8"))
    additions = json.loads(additions_path.read_text(encoding="utf-8"))
    normalize_legacy_placeholders(chinese)
    deep_merge(chinese, additions)

    english_leaves = leaves(english)
    chinese_leaves = leaves(chinese)
    missing = sorted(set(english_leaves) - set(chinese_leaves))
    if missing:
        raise SystemExit("Simplified Chinese locale is missing: " + ", ".join(missing))

    mismatches = []
    for key, english_value in english_leaves.items():
        chinese_value = chinese_leaves[key]
        if placeholders(english_value) != placeholders(chinese_value):
            mismatches.append(key)
    if mismatches:
        raise SystemExit(
            "Simplified Chinese placeholder mismatch: " + ", ".join(mismatches)
        )

    output_path.write_text(
        json.dumps(chinese, ensure_ascii=False, indent=4) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main(sys.argv)
