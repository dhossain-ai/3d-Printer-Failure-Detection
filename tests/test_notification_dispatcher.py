"""Tests for background notification dispatch."""

from notifications.dispatcher import NotificationDispatcher


def test_notification_dispatcher_starts_daemon_thread() -> None:
    """Dispatcher should schedule work on a daemon thread."""

    started_threads: list[object] = []

    class FakeThread:
        """Thread stand-in."""

        def __init__(self, target, args, name, daemon) -> None:
            """Record construction arguments."""

            self.target = target
            self.args = args
            self.name = name
            self.daemon = daemon
            started_threads.append(self)

        def start(self) -> None:
            """Record start without running the target."""

            self.started = True

    def task() -> None:
        raise AssertionError("task should not run inline")

    NotificationDispatcher(thread_factory=FakeThread).dispatch(task)

    assert started_threads[0].name == "printsentinel-notifications"
    assert started_threads[0].daemon is True
    assert started_threads[0].started is True
