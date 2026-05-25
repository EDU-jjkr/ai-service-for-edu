import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.services.prompt_policy import VAGUE_CONTROL_TERMS


ROOT = Path(__file__).resolve().parents[1]
TARGET_FILES = [
    ROOT / "routers" / "activity.py",
    ROOT / "routers" / "deck.py",
]
ALLOWED_PATTERNS = (
    "UI difficulty label:",
)


def audit_file(path: Path):
    findings = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if any(pattern in line for pattern in ALLOWED_PATTERNS):
            continue
        lowered = line.lower()
        for term in VAGUE_CONTROL_TERMS:
            if term in lowered:
                findings.append((path, line_number, term, line.strip()))
    return findings


def main():
    findings = []
    for path in TARGET_FILES:
        findings.extend(audit_file(path))

    if not findings:
        print("Prompt audit passed: no vague control terms found in AI-facing Python files.")
        raise SystemExit(0)

    print("Prompt audit found vague control terms:")
    for path, line_number, term, line in findings:
        print(f"{path}:{line_number} [{term}] {line}")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
