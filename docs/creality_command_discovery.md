# Creality Command Discovery

This workflow is for manually observing the Creality K1C web UI protocol before any real printer-control implementation is added to PrintSentinel.

PrintSentinel must not guess WebSocket command payloads. Capture the exact browser-to-printer messages first, then review them before any future code change.

## Browser WebSocket Capture

1. Open `http://<printer-ip>/` in Chrome or Edge.
2. Press `F12`.
3. Go to the `Network` tab.
4. Filter by `WS`.
5. Reload the page.
6. Click the `ws://<printer-ip>:9999` connection.
7. Open the `Messages` tab.
8. Manually toggle only low-risk light on/off first.
9. Copy outgoing browser-to-printer messages.
10. Optionally inspect pause/resume/stop only on a safe dummy print.
11. Never test stop/cancel on an important print.
12. Paste captured outgoing messages into a local notes file that is not committed if it contains sensitive details.

Do not send hand-written or guessed commands from DevTools, scripts, or PrintSentinel. Use the web UI controls only while observing what the browser sends.

## Capture Table

| Action | UI operation | Outgoing message | Incoming status change | Risk level | Tested on dummy print yes/no |
| --- | --- | --- | --- | --- | --- |
| Light on |  |  |  | Low |  |
| Light off |  |  |  | Low |  |
| Pause |  |  |  | Medium |  |
| Resume |  |  |  | Medium |  |
| Stop/cancel |  |  |  | High |  |
| Fan control |  |  |  | Medium |  |
| Nozzle temperature |  |  |  | High |  |
| Bed temperature |  |  |  | High |  |
| AI detection toggle |  |  |  | Medium |  |
| Timelapse/video |  |  |  | Low/Medium |  |
| File list/start print |  |  |  | Medium/High |  |

## Review Checklist

- Confirm whether the message is outgoing from browser to printer, not an incoming status update.
- Confirm whether the message is WebSocket traffic or an HTTP API request.
- Confirm whether any payload includes file names, hostnames, local IPs, tokens, or personal data before sharing.
- Capture the related incoming status change so future code can verify success without assuming it.
- Keep raw captures out of commits unless they are sanitized examples.
