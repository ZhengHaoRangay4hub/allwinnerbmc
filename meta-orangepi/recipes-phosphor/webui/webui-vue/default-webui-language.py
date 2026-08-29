#!/usr/bin/env python3
"""Enable zh-CN aliases and select Simplified Chinese for new browsers."""

from pathlib import Path
import sys


def replace_once(path, old, new):
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one occurrence in {path}, found {count}: {old!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main(arguments):
    if len(arguments) != 2:
        raise SystemExit("usage: default-webui-language.py WEBUI_SOURCE_DIR")
    source = Path(arguments[1])
    i18n = source / "src/i18n.js"
    store = source / "src/store/modules/GlobalStore.js"

    replace_once(
        i18n,
        "  addAlias('ka', 'ka-GE');\n",
        "  addAlias('ka', 'ka-GE');\n  addAlias('zh', 'zh-CN');\n",
    )
    replace_once(
        i18n,
        "    if (s === 'ka') return 'ka-GE';\n",
        "    if (s === 'ka') return 'ka-GE';\n"
        "    if (s === 'zh') return 'zh-CN';\n",
    )
    replace_once(
        i18n,
        "const stored = window.localStorage.getItem('storedLanguage');",
        "const stored = window.localStorage.getItem('storedLanguage') || 'zh-CN';",
    )
    replace_once(
        store,
        "languagePreference: localStorage.getItem('storedLanguage') || 'en-US'",
        "languagePreference: localStorage.getItem('storedLanguage') || 'zh-CN'",
    )


if __name__ == "__main__":
    main(sys.argv)
