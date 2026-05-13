document.addEventListener("DOMContentLoaded", () => {
    let config = {};
    let controlsEnabled = false;
    let notificationSettings = null;

    // Elements
    const elConnStatus = document.getElementById("connection-status");
    const elWarning = document.getElementById("controls-warning");
    const elError = document.getElementById("control-error");
    
    // Status elements
    const els = {
        model: document.getElementById("printer-model"),
        hostname: document.getElementById("printer-hostname"),
        state: document.getElementById("printer-state"),
        deviceState: document.getElementById("printer-device-state"),
        nozzleTemp: document.getElementById("printer-nozzle-temp"),
        bedTemp: document.getElementById("printer-bed-temp"),
        boxTemp: document.getElementById("printer-box-temp"),
        lightStatus: document.getElementById("printer-light-status"),
    };

    // Controls
    const btnLightOn = document.getElementById("btn-light-on");
    const btnLightOff = document.getElementById("btn-light-off");
    const sliderModelFan = document.getElementById("slider-model-fan");
    const valModelFan = document.getElementById("val-model-fan");
    const sliderAuxFan = document.getElementById("slider-auxiliary-fan");
    const valAuxFan = document.getElementById("val-auxiliary-fan");
    const sliderCaseFan = document.getElementById("slider-case-fan");
    const valCaseFan = document.getElementById("val-case-fan");
    const btnPausePrint = document.getElementById("btn-pause-print");
    const btnStopPrint = document.getElementById("btn-stop-print");
    const btnRefreshFiles = document.getElementById("btn-refresh-files");
    const filesPreview = document.getElementById("files-preview");
    const cameraContainer = document.getElementById("camera-container");
    const configDevice = document.getElementById("config-device");
    const btnOpenNotificationSettings = document.getElementById("btn-open-notification-settings");
    const notificationSettingsPanel = document.getElementById("notification-settings-panel");
    const notificationSettingsErrors = document.getElementById("notification-settings-errors");
    const notificationSettingsResults = document.getElementById("notification-settings-results");
    const btnSaveNotificationSettings = document.getElementById("btn-save-notification-settings");
    const btnTestNotificationSettings = document.getElementById("btn-test-notification-settings");

    const notificationFields = {
        notificationsEnabled: document.getElementById("notifications-enabled"),
        windowsEnabled: document.getElementById("windows-enabled"),
        telegramEnabled: document.getElementById("telegram-enabled"),
        telegramBotToken: document.getElementById("telegram-bot-token"),
        telegramChatId: document.getElementById("telegram-chat-id"),
        telegramSendScreenshot: document.getElementById("telegram-send-screenshot"),
        emailEnabled: document.getElementById("email-enabled"),
        smtpHost: document.getElementById("smtp-host"),
        smtpPort: document.getElementById("smtp-port"),
        smtpSecurity: document.getElementById("smtp-security"),
        smtpUsername: document.getElementById("smtp-username"),
        smtpPassword: document.getElementById("smtp-password"),
        emailFrom: document.getElementById("email-from"),
        emailTo: document.getElementById("email-to"),
        emailSendScreenshot: document.getElementById("email-send-screenshot"),
    };

    // AI monitoring elements
    const btnCamRaw = document.getElementById("btn-cam-raw");
    const btnCamAi = document.getElementById("btn-cam-ai");
    const btnAiStart = document.getElementById("btn-ai-start");
    const btnAiStop = document.getElementById("btn-ai-stop");
    let showingAiStream = false;
    let rawCameraHtml = "";
    let aiStatusInterval = null;

    function showError(msg) {
        elError.textContent = msg;
        setTimeout(() => { elError.textContent = ""; }, 5000);
    }

    function showNotificationSettingsErrors(errors) {
        notificationSettingsErrors.textContent = Array.isArray(errors) ? errors.join("\n") : (errors || "");
    }

    function showNotificationSettingsResults(lines) {
        notificationSettingsResults.textContent = Array.isArray(lines) ? lines.join("\n") : String(lines || "");
    }

    async function loadConfig() {
        try {
            const res = await fetch("/api/config");
            config = await res.json();
            
            controlsEnabled = config.control_enabled;
            if (!controlsEnabled) {
                elWarning.style.display = "block";
            } else {
                elWarning.style.display = "none";
                btnLightOn.disabled = false;
                btnLightOff.disabled = false;
                sliderModelFan.disabled = false;
                sliderAuxFan.disabled = false;
                sliderCaseFan.disabled = false;
                btnRefreshFiles.disabled = false;
                if (btnPausePrint) btnPausePrint.disabled = false;
                if (btnStopPrint) btnStopPrint.disabled = false;
            }

            configDevice.textContent = config.model_device;

            if (config.camera_configured && config.printer_camera_url) {
                rawCameraHtml = `<img src="${config.printer_camera_url}" alt="Printer Camera Stream">`;
                if (!showingAiStream) {
                    cameraContainer.innerHTML = rawCameraHtml;
                }
            }

            // Update new config fields
            document.getElementById("config-controls").textContent = config.control_enabled ? "Yes" : "No";
            document.getElementById("config-camera").textContent = config.camera_configured ? "Yes" : "No";
            document.getElementById("config-ws").textContent = config.status_ws_configured ? "Yes" : "No";
            document.getElementById("config-notifications").textContent = config.notifications_enabled ? "Yes" : "No";
        } catch (e) {
            console.error("Failed to load config", e);
        }
    }

    function applyNotificationSettings(settings) {
        notificationSettings = settings;
        notificationFields.notificationsEnabled.checked = !!settings.notifications_enabled;
        notificationFields.windowsEnabled.checked = !!settings.windows_enabled;
        notificationFields.telegramEnabled.checked = !!settings.telegram_enabled;
        notificationFields.telegramBotToken.value = "";
        notificationFields.telegramBotToken.placeholder = settings.telegram_bot_token_masked || "Leave blank to keep existing token";
        notificationFields.telegramChatId.value = "";
        notificationFields.telegramChatId.placeholder = settings.telegram_chat_id_masked || "Leave blank to keep existing chat ID";
        notificationFields.telegramSendScreenshot.checked = !!settings.telegram_send_screenshot;
        notificationFields.emailEnabled.checked = !!settings.email_enabled;
        notificationFields.smtpHost.value = settings.smtp_host || "";
        notificationFields.smtpPort.value = settings.smtp_port || 465;
        notificationFields.smtpSecurity.value = settings.smtp_security || "ssl";
        notificationFields.smtpUsername.value = "";
        notificationFields.smtpUsername.placeholder = settings.smtp_username_masked || "Leave blank to keep existing username";
        notificationFields.smtpPassword.value = "";
        notificationFields.smtpPassword.placeholder = settings.smtp_password_masked || "Leave blank to keep existing password";
        notificationFields.emailFrom.value = settings.email_from || "";
        notificationFields.emailTo.value = settings.email_to || "";
        notificationFields.emailSendScreenshot.checked = !!settings.email_send_screenshot;
    }

    async function loadNotificationSettings() {
        try {
            const res = await fetch("/api/settings/notifications");
            const data = await res.json();
            applyNotificationSettings(data.settings);
            showNotificationSettingsErrors("");
            showNotificationSettingsResults(`Local settings file: ${data.settings_file}`);
        } catch (e) {
            console.error("Failed to load notification settings", e);
            showNotificationSettingsResults(`Failed to load notification settings: ${e.message}`);
        }
    }

    function collectNotificationPayload() {
        return {
            notifications_enabled: notificationFields.notificationsEnabled.checked,
            windows_enabled: notificationFields.windowsEnabled.checked,
            telegram_enabled: notificationFields.telegramEnabled.checked,
            telegram_bot_token: notificationFields.telegramBotToken.value.trim(),
            telegram_chat_id: notificationFields.telegramChatId.value.trim(),
            telegram_send_screenshot: notificationFields.telegramSendScreenshot.checked,
            email_enabled: notificationFields.emailEnabled.checked,
            smtp_host: notificationFields.smtpHost.value.trim(),
            smtp_port: notificationFields.smtpPort.value.trim(),
            smtp_security: notificationFields.smtpSecurity.value,
            smtp_username: notificationFields.smtpUsername.value.trim(),
            smtp_password: notificationFields.smtpPassword.value,
            email_from: notificationFields.emailFrom.value.trim(),
            email_to: notificationFields.emailTo.value.trim(),
            email_send_screenshot: notificationFields.emailSendScreenshot.checked,
        };
    }

    function formatNotificationResults(results) {
        if (!results || results.length === 0) {
            return ["No notification providers are enabled."];
        }
        return results.map((result) => (
            `${result.provider}/${result.destination_id}: ${result.success ? "success" : "failed"} - ${result.message}`
        ));
    }

    async function updateStatus() {
        if (!config.status_ws_configured) {
            elConnStatus.textContent = "Status not configured";
            elConnStatus.className = "status-badge disconnected";
            return;
        }

        try {
            const res = await fetch("/api/status");
            const data = await res.json();
            
            if (data.connected && data.status) {
                elConnStatus.textContent = "Connected";
                elConnStatus.className = "status-badge connected";
                
                const s = data.status;
                els.model.textContent = s.model || "--";
                els.hostname.textContent = s.hostname || "--";
                els.state.textContent = s.state || "--";
                els.deviceState.textContent = s.device_state || "--";
                els.nozzleTemp.textContent = `${s.nozzle_temp || 0} / ${s.nozzle_target_temp || 0} °C`;
                els.bedTemp.textContent = `${s.bed_temp || 0} / ${s.bed_target_temp || 0} °C`;
                els.boxTemp.textContent = `${s.box_temp || 0} °C`;
                els.lightStatus.textContent = s.light_on ? "On" : "Off";
            } else {
                elConnStatus.textContent = "Disconnected";
                elConnStatus.className = "status-badge disconnected";
            }
        } catch (e) {
            console.error("Failed to update status", e);
            elConnStatus.textContent = "Error";
            elConnStatus.className = "status-badge disconnected";
        }
    }

    async function sendControl(endpoint, body) {
        if (!controlsEnabled) return;
        try {
            const res = await fetch(`/api/control/${endpoint}`, {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify(body)
            });
            const data = await res.json();
            if (!res.ok) {
                showError(data.detail || "Command failed");
            }
        } catch (e) {
            showError(e.message);
        }
    }

    // Light controls
    btnLightOn.addEventListener("click", () => sendControl("light", {enabled: true}));
    btnLightOff.addEventListener("click", () => sendControl("light", {enabled: false}));

    // Fan controls
    function setupFanSlider(slider, valSpan, fanName) {
        slider.addEventListener("input", (e) => {
            valSpan.textContent = e.target.value;
        });
        slider.addEventListener("change", (e) => {
            sendControl("fan", {fan: fanName, percent: parseInt(e.target.value)});
        });
    }

    setupFanSlider(sliderModelFan, valModelFan, "model");
    setupFanSlider(sliderAuxFan, valAuxFan, "auxiliary");
    setupFanSlider(sliderCaseFan, valCaseFan, "case");

    // Print Actions
    if (btnPausePrint) {
        btnPausePrint.addEventListener("click", () => {
            if (confirm("Are you sure you want to pause the print?")) {
                sendControl("pause", {});
            }
        });
    }

    if (btnStopPrint) {
        btnStopPrint.addEventListener("click", () => {
            const val = prompt("Type STOP to confirm cancelling the print:");
            if (val === "STOP") {
                sendControl("stop", {confirm: "STOP"});
            } else if (val !== null) {
                alert("Confirmation failed. Print not stopped.");
            }
        });
    }

    // Files
    btnRefreshFiles.addEventListener("click", async () => {
        if (!controlsEnabled) return;
        
        const filesPreview = document.getElementById("files-preview");
        const filesTable = document.getElementById("files-table");
        const filesTbody = document.getElementById("files-tbody");
        
        try {
            filesTable.style.display = "none";
            filesPreview.style.display = "block";
            filesPreview.textContent = "Loading...";
            
            const res = await fetch("/api/files");
            const data = await res.json();
            
            if (res.ok) {
                if (data.files && data.files.length > 0) {
                    filesPreview.style.display = "none";
                    filesTable.style.display = "table";
                    filesTbody.innerHTML = "";
                    data.files.forEach(f => {
                        const tr = document.createElement("tr");
                        tr.innerHTML = `<td>${f.name || "Unknown"}</td>`;
                        filesTbody.appendChild(tr);
                    });
                } else {
                    filesPreview.textContent = data.response_preview || "Empty response";
                }
            } else {
                filesPreview.textContent = `Error: ${data.detail}`;
            }
        } catch (e) {
            filesPreview.textContent = `Error: ${e.message}`;
        }
    });

    // Recent Events
    async function loadEvents() {
        try {
            const res = await fetch("/api/events/recent");
            const data = await res.json();
            const tbody = document.getElementById("events-tbody");
            
            if (data.events && data.events.length > 0) {
                tbody.innerHTML = "";
                data.events.forEach(ev => {
                    const tr = document.createElement("tr");
                    tr.innerHTML = `
                        <td>${ev.timestamp || "--"}</td>
                        <td>${ev.source || "--"}</td>
                        <td>${ev.label || "--"}</td>
                        <td>${ev.confidence || "--"}</td>
                        <td>${ev.action || "--"}</td>
                        <td>${ev.screenshot_path ? "Yes" : "No"}</td>
                    `;
                    tbody.appendChild(tr);
                });
            } else {
                tbody.innerHTML = `<tr><td colspan="6" class="placeholder">No recent events found.</td></tr>`;
            }
        } catch (e) {
            console.error("Failed to load events", e);
        }
    }

    // Recent Notifications
    async function loadNotifications() {
        try {
            const res = await fetch("/api/notifications/recent");
            const data = await res.json();
            const tbody = document.getElementById("notifications-tbody");
            
            if (data.notifications && data.notifications.length > 0) {
                tbody.innerHTML = "";
                data.notifications.forEach(n => {
                    const tr = document.createElement("tr");
                    tr.innerHTML = `
                        <td>${n.timestamp || "--"}</td>
                        <td>${n.target || "--"}</td>
                        <td>${n.status || "--"}</td>
                        <td>${n.message || "--"}</td>
                    `;
                    tbody.appendChild(tr);
                });
            } else {
                tbody.innerHTML = `<tr><td colspan="4" class="placeholder">No recent notifications found.</td></tr>`;
            }
        } catch (e) {
            console.error("Failed to load notifications", e);
        }
    }

    async function postNotificationSettings(url) {
        const res = await fetch(url, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(collectNotificationPayload()),
        });
        const data = await res.json();
        if (!res.ok) {
            const errors = data.detail && data.detail.errors ? data.detail.errors : [data.detail || "Request failed"];
            throw new Error(errors.join("\n"));
        }
        return data;
    }

    // AI Start / Stop
    if (btnAiStart) {
        btnAiStart.addEventListener("click", async () => {
            try {
                const res = await fetch("/api/ai/start", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({})});
                const data = await res.json();
                if (!res.ok) {
                    showError(data.detail || "Failed to start AI monitoring");
                    return;
                }
                btnAiStart.disabled = true;
                btnAiStop.disabled = false;
                // Auto-switch to AI stream
                showingAiStream = true;
                cameraContainer.innerHTML = `<img src="/api/ai/stream" alt="AI Stream">`;
                btnCamAi && (btnCamAi.classList.add("active-tab"));
                btnCamRaw && (btnCamRaw.classList.remove("active-tab"));
                // Poll AI status
                if (!aiStatusInterval) aiStatusInterval = setInterval(loadAiStatus, 1500);
            } catch (e) {
                showError(e.message);
            }
        });
    }

    if (btnAiStop) {
        btnAiStop.addEventListener("click", async () => {
            try {
                await fetch("/api/ai/stop", {method: "POST"});
                btnAiStart.disabled = false;
                btnAiStop.disabled = true;
                showingAiStream = false;
                if (rawCameraHtml) cameraContainer.innerHTML = rawCameraHtml;
                btnCamRaw && (btnCamRaw.classList.add("active-tab"));
                btnCamAi && (btnCamAi.classList.remove("active-tab"));
                if (aiStatusInterval) { clearInterval(aiStatusInterval); aiStatusInterval = null; }
            } catch (e) {
                showError(e.message);
            }
        });
    }

    // Camera tab toggle
    if (btnCamRaw) {
        btnCamRaw.addEventListener("click", () => {
            showingAiStream = false;
            if (rawCameraHtml) cameraContainer.innerHTML = rawCameraHtml;
            btnCamRaw.classList.add("active-tab");
            if (btnCamAi) btnCamAi.classList.remove("active-tab");
        });
    }
    if (btnCamAi) {
        btnCamAi.addEventListener("click", () => {
            showingAiStream = true;
            cameraContainer.innerHTML = `<img src="/api/ai/stream" alt="AI Stream">`;
            btnCamAi.classList.add("active-tab");
            if (btnCamRaw) btnCamRaw.classList.remove("active-tab");
        });
    }

    async function loadAiStatus() {
        try {
            const res = await fetch("/api/ai/status");
            const s = await res.json();
            const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
            set("ai-running", s.running ? "Running ▶" : "Stopped ■");
            set("ai-frames", s.frames_processed);
            set("ai-label", s.last_detection_label || "--");
            set("ai-confidence", s.last_detection_confidence ? s.last_detection_confidence.toFixed(2) : "--");
            set("ai-fail-frames", `${s.fail_frame_count} / ${s.consecutive_fail_frames}`);
            set("ai-confirmed", s.confirmed_failure ? "YES ⚠" : "No");
            set("ai-action-result", s.last_action_result || "--");
            set("ai-last-error", s.last_error || "--");

            // Sync button state with server truth
            if (!s.running && btnAiStart) { btnAiStart.disabled = false; }
            if (!s.running && btnAiStop) { btnAiStop.disabled = true; }
        } catch (e) {
            console.error("AI status error", e);
        }
    }

    if (btnOpenNotificationSettings && notificationSettingsPanel) {
        btnOpenNotificationSettings.addEventListener("click", () => {
            notificationSettingsPanel.scrollIntoView({behavior: "smooth", block: "start"});
        });
    }

    if (btnSaveNotificationSettings) {
        btnSaveNotificationSettings.addEventListener("click", async () => {
            showNotificationSettingsErrors("");
            try {
                const data = await postNotificationSettings("/api/settings/notifications");
                applyNotificationSettings(data.settings);
                showNotificationSettingsResults("Notification settings saved.");
            } catch (e) {
                showNotificationSettingsErrors(e.message.split("\n"));
                showNotificationSettingsResults("Notification settings were not saved.");
            }
        });
    }

    if (btnTestNotificationSettings) {
        btnTestNotificationSettings.addEventListener("click", async () => {
            showNotificationSettingsErrors("");
            try {
                const data = await postNotificationSettings("/api/settings/notifications/test");
                showNotificationSettingsResults(formatNotificationResults(data.results));
            } catch (e) {
                showNotificationSettingsErrors(e.message.split("\n"));
                showNotificationSettingsResults("Test notification failed validation.");
            }
        });
    }

    // Init
    loadConfig().then(() => {
        updateStatus();
        loadEvents();
        loadNotifications();
        loadNotificationSettings();
        loadAiStatus();
        setInterval(updateStatus, 3000);
    });
});
