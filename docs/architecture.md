# PrintSentinel Architecture Notes

PrintSentinel is organized around a small set of focused modules:

- `ui.py` chooses the input source.
- `sources.py` opens the selected sample video, webcam, or mobile camera URL.
- `detector.py` wraps YOLO inference and failure-label filtering.
- `runner.py` coordinates capture, detection, confirmation, cooldown, overlays, and summaries.
- `annotator.py` draws runtime status overlays.
- `actions.py` handles confirmed-failure side effects: screenshot, CSV, alert, notification dispatch, and printer response.
- `notifications/` contains notification models, provider orchestration, and optional provider integrations for Windows toast, Telegram, and SMTP email alerts.
- `notifications/settings.py` handles local notification settings JSON, validation, and test notification dispatch.
- `printer_controller.py` contains safe simulated and generic HTTP printer backends.
- `session_summary.py` tracks run-level metrics and writes `logs/session_*.json`.

## Demo Asset Checklist

Suggested GitHub showcase assets:

- `docs/images/source-selection.png`
- `docs/images/monitoring.png`
- `docs/images/fail-detected.png`
- `docs/images/session-summary.png`

These files are placeholders for future captured screenshots. They are not required to run the app.

## Safety Model

The default printer backend is simulated. HTTP control is opt-in through environment variables or config values. If HTTP setup is incomplete or a request fails, PrintSentinel prints a warning and continues monitoring instead of crashing.

Notifications are also opt-in. `NotificationManager` sends confirmed-failure alerts to configured providers and converts provider exceptions into failed results. `actions.py` reports those failures as warnings and continues to the printer response, so a desktop, Telegram, or email notification problem cannot block a stop or pause action.

Provider integrations stay independent: Telegram uses the Bot API through `requests`, while email uses the Python standard library SMTP stack. Provider-specific secrets are read from environment-driven config and should never be committed.

Local notification settings are optional and live in `config/local_notification_settings.json`, which is ignored by Git. Environment variables take precedence over local settings, and local settings take precedence over defaults. The local file is plaintext for the MVP; production deployments should move secrets to environment variables, encrypted storage, or a secret manager.
