from collections.abc import Iterable


def calculate_pass_rate(total_count: int, passed_count: int) -> float:
    if total_count <= 0:
        return 0.0
    return round((passed_count / total_count) * 100, 2)


def normalize_step_lines(steps) -> list[str]:
    if isinstance(steps, list):
        return [_stringify_step(step) for step in steps if _stringify_step(step)]
    if isinstance(steps, dict):
        step_line = _stringify_step(steps)
        return [step_line] if step_line else []
    if isinstance(steps, str):
        return [line.strip() for line in steps.splitlines() if line.strip()]
    return []


def _stringify_step(step) -> str:
    if isinstance(step, str):
        return step.strip()
    if not isinstance(step, dict):
        return ""

    action = _clean_string(step.get("action") or step.get("step"))
    target = _clean_string(step.get("target"))
    expected = _clean_string(step.get("expected") or step.get("outcome"))

    segments: list[str] = []
    if action:
        segments.append(action)
    if target:
        segments.append(target)
    if expected:
        segments.append(f"expect {expected}")

    return " ".join(segment for segment in segments if segment).strip()


def _clean_string(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, dict)):
        return " ".join(str(item).strip() for item in value if str(item).strip()).strip()
    return str(value).strip()
