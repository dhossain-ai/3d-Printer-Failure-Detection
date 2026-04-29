"""PrintSentinel entry point."""

from config import CAPTURES_DIR, EVENTS_CSV_PATH, LOGS_DIR
from detector import YoloFailureDetector
from runner import PrintSentinelRunner
from ui import choose_source, show_error


def ensure_project_paths() -> None:
    """Create runtime directories and placeholder log file if they are missing."""

    CAPTURES_DIR.mkdir(exist_ok=True)
    LOGS_DIR.mkdir(exist_ok=True)
    EVENTS_CSV_PATH.touch(exist_ok=True)


def main() -> None:
    """Launch the PrintSentinel source picker and monitoring loop."""

    ensure_project_paths()

    source = choose_source()
    if source is None:
        return

    try:
        detector = YoloFailureDetector()
        runner = PrintSentinelRunner(detector)
    except (FileNotFoundError, RuntimeError) as exc:
        show_error(str(exc))
        return

    error = runner.run(source)
    if error is not None:
        show_error(error)


if __name__ == "__main__":
    main()
