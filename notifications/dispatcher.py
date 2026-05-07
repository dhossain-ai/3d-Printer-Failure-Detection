"""Background notification dispatch helpers."""

import sys
import threading
from collections.abc import Callable
from typing import Any


class NotificationDispatcher:
    """Dispatch notification work on a daemon background thread."""

    def __init__(self, thread_factory: Callable[..., Any] = threading.Thread) -> None:
        """Create a dispatcher with an injectable thread factory."""

        self._thread_factory = thread_factory

    def dispatch(
        self,
        task: Callable[[], None],
        name: str = "printsentinel-notifications",
    ) -> None:
        """Schedule notification work without blocking the caller."""

        thread = self._thread_factory(
            target=self._run_safely,
            args=(task,),
            name=name,
            daemon=True,
        )
        thread.start()

    @staticmethod
    def _run_safely(task: Callable[[], None]) -> None:
        """Run a notification task and report sanitized failures."""

        try:
            task()
        except Exception as exc:  # noqa: BLE001 - background dispatch must be isolated.
            print(
                (
                    "PRINTSENTINEL WARNING: background notification failed: "
                    f"{exc.__class__.__name__}"
                ),
                file=sys.stderr,
            )
