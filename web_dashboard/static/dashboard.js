document.addEventListener("DOMContentLoaded", () => {
    let config = {};
    let controlsEnabled = false;
    let notificationSettings = null;
    let currentSourceSettings = null;

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
    const controlsEnabledBadge = document.getElementById("controls-enabled-badge");
    const controlsDisabledReason = document.getElementById("controls-disabled-reason");
    const btnOpenNotificationSettings = document.getElementById("btn-open-notification-settings");
    const notificationSettingsPanel = document.getElementById("notification-settings-panel");
    const notificationSettingsErrors = document.getElementById("notification-settings-errors");
    const notificationSettingsResults = document.getElementById("notification-settings-results");
    const btnSaveNotificationSettings = document.getElementById("btn-save-notification-settings");
    const btnTestNotificationSettings = document.getElementById("btn-test-notification-settings");
    const aiSettingsErrors = document.getElementById("ai-settings-errors");
    const aiSettingsEffective = document.getElementById("ai-settings-effective");
    const aiAutoWarning = document.getElementById("ai-auto-warning");
    const aiStopWarning = document.getElementById("ai-stop-warning");
    const aiRunningBadge = document.getElementById("ai-running-badge");
    const aiControlsBadge = document.getElementById("ai-controls-badge");
    const aiAutoActionBadge = document.getElementById("ai-auto-action-badge");
    const aiModeBadge = document.getElementById("ai-mode-badge");
    const btnSaveAiSettings = document.getElementById("btn-save-ai-settings");
    const sourceSettingsErrors = document.getElementById("source-settings-errors");
    const sourceSettingsStatus = document.getElementById("source-settings-status");
    const btnSaveSourceSettings = document.getElementById("btn-save-source-settings");
    const configMonitoringSource = document.getElementById("config-monitoring-source");
    const feedSourceType = document.getElementById("feed-source-type");
    const feedActiveSource = document.getElementById("feed-active-source");
    const feedRoiBadge = document.getElementById("feed-roi-badge");
    const feedLastUpdate = document.getElementById("feed-last-update");
    const feedVisibleMode = document.getElementById("feed-visible-mode");
    const datasetNotes = document.getElementById("dataset-notes");
    const datasetCaptureError = document.getElementById("dataset-capture-error");
    const datasetCaptureResult = document.getElementById("dataset-capture-result");
    const datasetCaptureButtons = document.querySelectorAll(".dataset-capture-btn");
    const roiPresetButtons = document.querySelectorAll(".roi-preset-btn");

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
    const aiSettingsFields = {
        confidenceThresholdRange: document.getElementById("ai-confidence-threshold-range"),
        confidenceThreshold: document.getElementById("ai-confidence-threshold"),
        consecutiveFailFrames: document.getElementById("ai-consecutive-fail-frames"),
        alertCooldownSeconds: document.getElementById("ai-alert-cooldown-seconds"),
        autoActionEnabled: document.getElementById("ai-auto-action-enabled"),
        actionMode: document.getElementById("ai-action-mode"),
        roiEnabled: document.getElementById("ai-roi-enabled"),
        roiX: document.getElementById("ai-roi-x"),
        roiY: document.getElementById("ai-roi-y"),
        roiWidth: document.getElementById("ai-roi-width"),
        roiHeight: document.getElementById("ai-roi-height"),
    };
    const sourceFields = {
        sourceType: document.getElementById("source-type"),
        printerCameraUrlRow: document.getElementById("printer-camera-url-row"),
        printerCameraUrl: document.getElementById("printer-camera-url"),
        webcamIndexRow: document.getElementById("webcam-index-row"),
        webcamIndex: document.getElementById("webcam-index"),
        cameraTypeRow: document.getElementById("camera-type-row"),
        cameraType: document.getElementById("source-camera-type"),
        demoVideoPathRow: document.getElementById("demo-video-path-row"),
        demoVideoPath: document.getElementById("demo-video-path"),
        localVideoPathRow: document.getElementById("local-video-path-row"),
        localVideoPath: document.getElementById("local-video-path"),
    };

    // AI monitoring elements
    const btnCamRaw = document.getElementById("btn-cam-raw");
    const btnCamAi = document.getElementById("btn-cam-ai");
    const btnAiStart = document.getElementById("btn-ai-start");
    const btnAiStop = document.getElementById("btn-ai-stop");
    let showingAiStream = false;
    let rawCameraHtml = "";
    let aiStatusInterval = null;

    function setBadgeState(element, text, variant = "neutral") {
        if (!element) return;
        element.textContent = text;
        element.classList.remove("neutral", "connected", "disconnected", "success", "warning", "danger");
        element.classList.add(variant);
    }

    function formatBoolean(value) {
        return value ? "Enabled" : "Disabled";
    }

    function formatSourceType(value) {
        return (value || "--")
            .replaceAll("_", " ")
            .replace(/\b\w/g, (char) => char.toUpperCase());
    }

    function markLastUpdate(label = "Updated") {
        if (!feedLastUpdate) return;
        const timestamp = new Date().toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", second: "2-digit"});
        setBadgeState(feedLastUpdate, `${label} ${timestamp}`, "neutral");
    }

    function updateVisibleFeedMode() {
        if (feedVisibleMode) {
            feedVisibleMode.textContent = showingAiStream ? "AI Processed" : "Raw Feed";
        }
    }

    function updateControlsSummary() {
        setBadgeState(
            controlsEnabledBadge,
            `Controls ${formatBoolean(controlsEnabled)}`,
            controlsEnabled ? "success" : "neutral",
        );
        setBadgeState(
            aiControlsBadge,
            `Controls ${formatBoolean(controlsEnabled)}`,
            controlsEnabled ? "success" : "neutral",
        );
        if (controlsDisabledReason) {
            controlsDisabledReason.textContent = controlsEnabled
                ? "Real local control is enabled. Low-risk controls and live print actions are available."
                : "Controls are disabled because PRINTSENTINEL_CREALITY_CONTROL_ENABLED is not enabled.";
        }
    }

    function updateAiWarningState() {
        if (aiAutoWarning) {
            aiAutoWarning.style.display = aiSettingsFields.autoActionEnabled.checked ? "block" : "none";
        }
        if (aiAutoActionBadge) {
            setBadgeState(
                aiAutoActionBadge,
                `Auto action ${formatBoolean(aiSettingsFields.autoActionEnabled.checked)}`,
                aiSettingsFields.autoActionEnabled.checked ? "warning" : "neutral",
            );
        }
        if (aiModeBadge) {
            const mode = aiSettingsFields.actionMode.value || "detection_only";
            const modeLabel = mode === "detection_only"
                ? "Detection only"
                : mode.charAt(0).toUpperCase() + mode.slice(1);
            const variant = mode === "stop" ? "danger" : mode === "pause" ? "warning" : "neutral";
            setBadgeState(aiModeBadge, `Mode ${modeLabel}`, variant);
        }
    }

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

    function showAiSettingsErrors(errors) {
        aiSettingsErrors.textContent = Array.isArray(errors) ? errors.join("\n") : (errors || "");
    }

    function showAiSettingsEffective(lines) {
        aiSettingsEffective.textContent = Array.isArray(lines) ? lines.join("\n") : String(lines || "");
    }

    function showSourceSettingsErrors(errors) {
        sourceSettingsErrors.textContent = Array.isArray(errors) ? errors.join("\n") : (errors || "");
    }

    function showSourceSettingsStatus(lines) {
        sourceSettingsStatus.textContent = Array.isArray(lines) ? lines.join("\n") : String(lines || "");
    }

    function showDatasetCaptureError(message) {
        datasetCaptureError.textContent = message || "";
    }

    function showDatasetCaptureResult(lines) {
        datasetCaptureResult.textContent = Array.isArray(lines) ? lines.join("\n") : String(lines || "");
    }

    async function loadConfig() {
        try {
            const res = await fetch("/api/config");
            config = await res.json();
            const controlElements = [
                btnLightOn,
                btnLightOff,
                sliderModelFan,
                sliderAuxFan,
                sliderCaseFan,
                btnRefreshFiles,
                btnPausePrint,
                btnStopPrint,
            ].filter(Boolean);
            
            controlsEnabled = config.control_enabled;
            if (!controlsEnabled) {
                elWarning.style.display = "block";
                controlElements.forEach((element) => {
                    element.title = "Disabled because PRINTSENTINEL_CREALITY_CONTROL_ENABLED is not enabled.";
                });
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
                controlElements.forEach((element) => {
                    element.title = "";
                });
            }
            updateControlsSummary();

            configDevice.textContent = config.model_device;

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

    function updateSourceFieldVisibility() {
        const sourceType = sourceFields.sourceType.value;
        sourceFields.printerCameraUrlRow.style.display = sourceType === "printer_camera" ? "flex" : "none";
        sourceFields.webcamIndexRow.style.display = sourceType === "webcam" ? "flex" : "none";
        sourceFields.cameraTypeRow.style.display = sourceType === "printer_camera" ? "flex" : "none";
        sourceFields.demoVideoPathRow.style.display = sourceType === "demo_video" ? "flex" : "none";
        sourceFields.localVideoPathRow.style.display = sourceType === "local_video" ? "flex" : "none";
    }

    function updateRawCameraPreview() {
        if (currentSourceSettings && currentSourceSettings.source_type === "printer_camera" && currentSourceSettings.source_value) {
            rawCameraHtml = `<img src="${currentSourceSettings.source_value}" alt="Printer Camera Stream">`;
        } else {
            rawCameraHtml = `<div class="placeholder">Raw browser preview is only available for printer camera URLs. Start AI monitoring to test webcam or video-file sources.</div>`;
        }

        if (!showingAiStream) {
            cameraContainer.innerHTML = rawCameraHtml;
        }
        updateVisibleFeedMode();
    }

    function formatSourceStatus(data) {
        return [
            `Selected source: ${data.source_label || "--"}`,
            `Current active source: ${data.active_source || "--"}`,
            `Running: ${data.running ? "Yes" : "No"}`,
            `Needs restart: ${data.restart_required ? "Yes" : "No"}`,
            `Message: ${data.message || "--"}`,
        ];
    }

    function applySourceSettingsPayload(data) {
        const settings = data.settings || data;
        currentSourceSettings = settings;
        sourceFields.sourceType.value = settings.source_type;
        sourceFields.printerCameraUrl.value = settings.source_type === "printer_camera" ? (settings.source_value || "") : (sourceFields.printerCameraUrl.value || config.printer_camera_url || "");
        sourceFields.webcamIndex.value = settings.source_type === "webcam" ? (settings.source_value || "0") : (sourceFields.webcamIndex.value || "0");
        sourceFields.cameraType.value = settings.camera_type || "stream";
        sourceFields.demoVideoPath.value = settings.source_type === "demo_video" ? (settings.source_value || "") : sourceFields.demoVideoPath.value;
        sourceFields.localVideoPath.value = settings.source_type === "local_video" ? (settings.source_value || "") : sourceFields.localVideoPath.value;
        updateSourceFieldVisibility();
        updateRawCameraPreview();
        setBadgeState(feedSourceType, `Source: ${formatSourceType(settings.source_type)}`, "neutral");
        setBadgeState(feedActiveSource, `Active: ${data.active_source || data.source_label || "--"}`, data.running ? "connected" : "neutral");
        if (data.source_label || data.active_source || data.message) {
            showSourceSettingsStatus(formatSourceStatus(data));
        }
        markLastUpdate("Source");
    }

    async function loadSourceSettings() {
        try {
            const res = await fetch("/api/source");
            const data = await res.json();
            applySourceSettingsPayload(data);
            showSourceSettingsErrors("");
        } catch (e) {
            console.error("Failed to load source settings", e);
            showSourceSettingsStatus(`Failed to load source settings: ${e.message}`);
        }
    }

    function collectSourcePayload() {
        const sourceType = sourceFields.sourceType.value;
        let sourceValue = "";
        if (sourceType === "printer_camera") {
            sourceValue = sourceFields.printerCameraUrl.value.trim();
        } else if (sourceType === "webcam") {
            sourceValue = sourceFields.webcamIndex.value.trim();
        } else if (sourceType === "demo_video") {
            sourceValue = sourceFields.demoVideoPath.value.trim();
        } else {
            sourceValue = sourceFields.localVideoPath.value.trim();
        }

        return {
            source_type: sourceType,
            source_value: sourceValue,
            camera_type: sourceFields.cameraType.value,
        };
    }

    async function postSourceSettings() {
        const res = await fetch("/api/source", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(collectSourcePayload()),
        });
        const data = await res.json();
        if (!res.ok) {
            const errors = data.detail && data.detail.errors ? data.detail.errors : [data.detail || "Request failed"];
            throw new Error(errors.join("\n"));
        }
        return data;
    }

    function formatDatasetCaptureResult(capture) {
        return [
            `Category: ${capture.category}`,
            `Frame: ${capture.frame_path || "--"}`,
            `Annotated: ${capture.annotated_frame_path || "--"}`,
            `Crop: ${capture.crop_path || "not available"}`,
            `Label: ${capture.label || "--"}`,
            `Confidence: ${Number(capture.confidence || 0).toFixed(2)}`,
        ];
    }

    async function captureDatasetExample(category) {
        const res = await fetch("/api/dataset/capture", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                category,
                notes: datasetNotes.value.trim(),
            }),
        });
        const data = await res.json();
        if (!res.ok) {
            const detail = data.detail && data.detail.errors ? data.detail.errors.join("\n") : (data.detail || "Dataset capture failed");
            throw new Error(detail);
        }
        return data.capture;
    }

    function updateStopWarning() {
        if (!aiStopWarning) return;
        aiStopWarning.style.display = aiSettingsFields.actionMode.value === "stop" ? "block" : "none";
        updateAiWarningState();
    }

    function syncConfidenceInputs(source) {
        const value = source.value;
        aiSettingsFields.confidenceThreshold.value = value;
        aiSettingsFields.confidenceThresholdRange.value = value;
    }

    function applyAiSettingsPayload(payload) {
        const settings = payload.settings || payload;
        const effective = payload.effective || null;
        aiSettingsFields.confidenceThresholdRange.value = settings.confidence_threshold;
        aiSettingsFields.confidenceThreshold.value = settings.confidence_threshold;
        aiSettingsFields.consecutiveFailFrames.value = settings.consecutive_fail_frames;
        aiSettingsFields.alertCooldownSeconds.value = settings.alert_cooldown_seconds;
        aiSettingsFields.autoActionEnabled.checked = !!settings.auto_action_enabled;
        aiSettingsFields.actionMode.value = settings.action_mode;
        aiSettingsFields.roiEnabled.checked = !!settings.roi_enabled;
        aiSettingsFields.roiX.value = settings.roi_x;
        aiSettingsFields.roiY.value = settings.roi_y;
        aiSettingsFields.roiWidth.value = settings.roi_width;
        aiSettingsFields.roiHeight.value = settings.roi_height;
        document.getElementById("config-confidence").textContent = Number(settings.confidence_threshold).toFixed(2);
        setBadgeState(
            feedRoiBadge,
            `ROI ${settings.roi_enabled ? "Enabled" : "Disabled"}`,
            settings.roi_enabled ? "success" : "neutral",
        );
        updateStopWarning();
        if (effective) {
            showAiSettingsEffective(formatAiEffectiveSettings(effective));
        }
    }

    function formatAiEffectiveSettings(effective) {
        return [
            `Threshold: ${Number(effective.confidence_threshold).toFixed(2)}`,
            `Consecutive frames: ${effective.consecutive_fail_frames}`,
            `Cooldown: ${effective.alert_cooldown_seconds}s`,
            `ROI: ${effective.roi_enabled ? `enabled (${effective.roi_x}, ${effective.roi_y}, ${effective.roi_width}, ${effective.roi_height})` : "disabled"}`,
            `Auto action enabled: ${effective.auto_action_enabled ? "Yes" : "No"}`,
            `Action mode: ${effective.action_mode}`,
            `Backend: ${effective.printer_backend}${effective.real_printer_command ? " (real)" : " (simulated)"}`,
            `Will trigger action: ${effective.auto_action_active ? "Yes" : "No"}`,
            `Reason: ${effective.auto_action_reason}`,
            `Cooldown remaining: ${effective.cooldown_remaining_seconds}s`,
            `Monitoring running: ${effective.running ? "Yes" : "No"}`,
        ];
    }

    async function loadAiSettings() {
        try {
            const res = await fetch("/api/ai/settings");
            const data = await res.json();
            applyAiSettingsPayload(data);
            showAiSettingsErrors("");
        } catch (e) {
            console.error("Failed to load AI settings", e);
            showAiSettingsEffective(`Failed to load AI settings: ${e.message}`);
        }
    }

    function collectAiSettingsPayload() {
        return {
            confidence_threshold: aiSettingsFields.confidenceThreshold.value.trim(),
            consecutive_fail_frames: aiSettingsFields.consecutiveFailFrames.value.trim(),
            alert_cooldown_seconds: aiSettingsFields.alertCooldownSeconds.value.trim(),
            auto_action_enabled: aiSettingsFields.autoActionEnabled.checked,
            action_mode: aiSettingsFields.actionMode.value,
            roi_enabled: aiSettingsFields.roiEnabled.checked,
            roi_x: aiSettingsFields.roiX.value.trim(),
            roi_y: aiSettingsFields.roiY.value.trim(),
            roi_width: aiSettingsFields.roiWidth.value.trim(),
            roi_height: aiSettingsFields.roiHeight.value.trim(),
        };
    }

    async function postAiSettings() {
        const res = await fetch("/api/ai/settings", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(collectAiSettingsPayload()),
        });
        const data = await res.json();
        if (!res.ok) {
            const errors = data.detail && data.detail.errors ? data.detail.errors : [data.detail || "Request failed"];
            throw new Error(errors.join("\n"));
        }
        return data;
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
            elConnStatus.className = "status-badge neutral";
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
                    const statusLabel = n.status || "--";
                    const statusVariant = statusLabel.toLowerCase().includes("success") ? "success" : (statusLabel.toLowerCase().includes("fail") || statusLabel.toLowerCase().includes("error")) ? "danger" : "neutral";
                    tr.innerHTML = `
                        <td>${n.timestamp || "--"}</td>
                        <td>${n.target || "--"}</td>
                        <td><span class="status-pill ${statusVariant}">${statusLabel}</span></td>
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
                updateVisibleFeedMode();
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
                updateVisibleFeedMode();
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
            updateVisibleFeedMode();
            btnCamRaw.classList.add("active-tab");
            if (btnCamAi) btnCamAi.classList.remove("active-tab");
        });
    }
    if (btnCamAi) {
        btnCamAi.addEventListener("click", () => {
            showingAiStream = true;
            cameraContainer.innerHTML = `<img src="/api/ai/stream" alt="AI Stream">`;
            updateVisibleFeedMode();
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
            setBadgeState(aiRunningBadge, s.running ? "Running" : "Stopped", s.running ? "connected" : "danger");
            setBadgeState(feedRoiBadge, `ROI ${s.roi_enabled ? "Enabled" : "Disabled"}`, s.roi_enabled ? "success" : "neutral");
            if (s.confidence_threshold !== undefined) {
                document.getElementById("config-confidence").textContent = Number(s.confidence_threshold).toFixed(2);
            }
            if (configMonitoringSource) {
                configMonitoringSource.textContent = s.source_name || `${s.source_type || "--"}`;
            }
            setBadgeState(feedSourceType, `Source: ${formatSourceType(s.source_type)}`, "neutral");
            setBadgeState(feedActiveSource, `Active: ${s.source_name || s.source_type || "--"}`, s.running ? "connected" : "neutral");
            aiSettingsFields.autoActionEnabled.checked = !!s.auto_action_enabled;
            aiSettingsFields.actionMode.value = s.action_mode || aiSettingsFields.actionMode.value;
            updateAiWarningState();
            showAiSettingsEffective(formatAiEffectiveSettings({
                confidence_threshold: s.confidence_threshold,
                consecutive_fail_frames: s.consecutive_fail_frames,
                alert_cooldown_seconds: s.alert_cooldown_seconds,
                auto_action_enabled: s.auto_action_enabled,
                action_mode: s.action_mode,
                roi_enabled: s.roi_enabled,
                roi_x: s.roi_x,
                roi_y: s.roi_y,
                roi_width: s.roi_width,
                roi_height: s.roi_height,
                printer_backend: s.printer_backend,
                real_printer_command: s.real_printer_command,
                auto_action_active: s.auto_action_active,
                auto_action_reason: s.auto_action_reason,
                cooldown_remaining_seconds: s.cooldown_remaining_seconds,
                running: s.running,
            }));
            markLastUpdate(s.running ? "Frame" : "Status");

            // Sync button state with server truth
            if (btnAiStart) { btnAiStart.disabled = !!s.running; }
            if (btnAiStop) { btnAiStop.disabled = !s.running; }
        } catch (e) {
            console.error("AI status error", e);
        }
    }

    if (aiSettingsFields.confidenceThresholdRange && aiSettingsFields.confidenceThreshold) {
        aiSettingsFields.confidenceThresholdRange.addEventListener("input", (e) => syncConfidenceInputs(e.target));
        aiSettingsFields.confidenceThreshold.addEventListener("input", (e) => syncConfidenceInputs(e.target));
    }

    if (aiSettingsFields.actionMode) {
        aiSettingsFields.actionMode.addEventListener("change", updateStopWarning);
    }
    if (aiSettingsFields.autoActionEnabled) {
        aiSettingsFields.autoActionEnabled.addEventListener("change", updateAiWarningState);
    }

    if (sourceFields.sourceType) {
        sourceFields.sourceType.addEventListener("change", updateSourceFieldVisibility);
        updateSourceFieldVisibility();
    }

    updateVisibleFeedMode();
    updateAiWarningState();
    updateControlsSummary();

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

    if (btnSaveAiSettings) {
        btnSaveAiSettings.addEventListener("click", async () => {
            showAiSettingsErrors("");
            try {
                const data = await postAiSettings();
                applyAiSettingsPayload(data);
            } catch (e) {
                showAiSettingsErrors(e.message.split("\n"));
            }
        });
    }

    roiPresetButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const preset = button.dataset.roi;
            const values = {
                full: [0, 0, 1, 1],
                center: [0.2, 0.2, 0.6, 0.6],
                lower: [0.2, 0.35, 0.6, 0.55],
            }[preset] || [0, 0, 1, 1];
            aiSettingsFields.roiX.value = values[0];
            aiSettingsFields.roiY.value = values[1];
            aiSettingsFields.roiWidth.value = values[2];
            aiSettingsFields.roiHeight.value = values[3];
            aiSettingsFields.roiEnabled.checked = preset !== "full";
        });
    });

    if (btnSaveSourceSettings) {
        btnSaveSourceSettings.addEventListener("click", async () => {
            showSourceSettingsErrors("");
            try {
                const data = await postSourceSettings();
                applySourceSettingsPayload(data);
            } catch (e) {
                showSourceSettingsErrors(e.message.split("\n"));
            }
        });
    }

    datasetCaptureButtons.forEach((button) => {
        button.addEventListener("click", async () => {
            showDatasetCaptureError("");
            try {
                const capture = await captureDatasetExample(button.dataset.category);
                showDatasetCaptureResult(formatDatasetCaptureResult(capture));
            } catch (e) {
                showDatasetCaptureError(e.message);
            }
        });
    });

    // Init
    loadConfig().then(() => {
        updateStatus();
        loadEvents();
        loadNotifications();
        loadNotificationSettings();
        loadAiSettings();
        loadSourceSettings();
        loadAiStatus();
        setInterval(updateStatus, 3000);
    });
});
