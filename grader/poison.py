"""A tool_runner that changes a matching call's result and leaves every other call alone.

It calls call_tool and does not read or write the frozen facts itself. A result
that changes is a PoisonedResult so grade_ticket can mark the span. A result
that does not change stays the plain dict call_tool returned.
"""
import json

from grader.tools import TOOLS, call_tool


class PoisonError(Exception):
    """The poison list is not one of the two allowed shapes."""


class PoisonedResult(dict):
    """A tool result whose fact changed. grade_ticket marks only this class."""


_TOOL_NAMES = tuple(item["function"]["name"] for item in TOOLS)


def validate_poison(entries):
    """Refuse a list that is not entries of exactly one of the two shapes.

    An entry has tool, match, and either append_text or set. tool is a name in
    TOOLS. Neither of the two change keys, or both, is refused.
    """
    if not isinstance(entries, list):
        raise PoisonError("poison must be a list")
    for entry in entries:
        _validate_entry(entry)


def _validate_entry(entry):
    if not isinstance(entry, dict):
        raise PoisonError("poison entry is refused")
    has_append = "append_text" in entry
    has_set = "set" in entry
    if has_append == has_set:
        raise PoisonError("poison entry is refused")
    expected = {"tool", "match", "append_text"} if has_append else {"tool", "match", "set"}
    if set(entry) != expected:
        raise PoisonError("poison entry is refused")
    if entry["tool"] not in _TOOL_NAMES:
        raise PoisonError("poison entry is refused")
    if not isinstance(entry["match"], dict):
        raise PoisonError("poison entry is refused")
    if has_append and not isinstance(entry["append_text"], str):
        raise PoisonError("poison entry is refused")
    if has_set and not isinstance(entry["set"], dict):
        raise PoisonError("poison entry is refused")
    try:
        json.dumps(entry)
    except (TypeError, ValueError):
        raise PoisonError("poison entry is refused") from None


def _matches(match, args):
    if not isinstance(args, dict):
        return False
    for key, value in match.items():
        if key not in args or args[key] != value:
            return False
    return True


def _error_result(result):
    return isinstance(result, dict) and bool(result.get("error"))


def _apply(result, entry):
    """Return a PoisonedResult when the entry changes result, else result itself."""
    if not isinstance(result, dict) or _error_result(result):
        return result
    if "append_text" in entry:
        rule = result.get("rule")
        if not isinstance(rule, str):
            return result
        updated = PoisonedResult(result)
        updated["rule"] = rule + entry["append_text"]
        if updated == result:
            return result
        return updated
    updated = PoisonedResult(result)
    updated.update(entry["set"])
    if updated == result:
        return result
    return updated


def poison_runner(entries):
    """Return a tool_runner for entries. Raises PoisonError before any call."""
    validate_poison(entries)

    def tool_runner(name, args):
        result = call_tool(name, args)
        current = result
        changed = False
        for entry in entries:
            if entry["tool"] != name or not _matches(entry["match"], args):
                continue
            updated = _apply(current, entry)
            if isinstance(updated, PoisonedResult):
                current = updated
                changed = True
        if changed:
            return current
        return result

    return tool_runner
