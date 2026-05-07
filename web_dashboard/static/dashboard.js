document.addEventListener("DOMContentLoaded", () => {
    let config = {};
    let controlsEnabled = false;

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

    function showError(msg) {
        elError.textContent = msg;
        setTimeout(() => { elError.textContent = ""; }, 5000);
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
                cameraContainer.innerHTML = `<img src="${config.printer_camera_url}" alt="Printer Camera Stream">`;
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

    // Init
    loadConfig().then(() => {
        updateStatus();
        loadEvents();
        loadNotifications();
        setInterval(updateStatus, 3000);
    });
});
