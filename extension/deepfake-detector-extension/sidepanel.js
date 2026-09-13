// sidepanel.js
// Multimodal Deepfake Detector — side panel logic
//
// Two ways media gets into this panel:
//   A) Right-click on the page -> background.js stores { srcUrl, mediaType, pageUrl }
//      in chrome.storage.local under "pendingMedia" and opens this panel.
//   B) User drags/drops or picks a local file directly in the panel.
//
// Both paths converge on a single `selectedFile` (a File/Blob) that gets
// POSTed as multipart/form-data to `${apiBase}/detect`.

const STORAGE_MEDIA_KEY = "pendingMedia";
const STORAGE_API_KEY = "apiBaseUrl";
const DEFAULT_API_BASE = "https://upside-shower-handling.ngrok-free.dev";

// ---------- Element refs ----------
const settingsToggle = document.getElementById("settingsToggle");
const settingsPanel = document.getElementById("settingsPanel");
const apiUrlInput = document.getElementById("apiUrlInput");
const saveHint = document.getElementById("saveHint");

const mediaPreview = document.getElementById("mediaPreview");
const mediaPreviewBody = document.getElementById("mediaPreviewBody");
const mediaSourceUrl = document.getElementById("mediaSourceUrl");
const clearMediaBtn = document.getElementById("clearMediaBtn");

const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("fileInput");
const dropText = document.getElementById("dropText");

const analyzeBtn = document.getElementById("analyzeBtn");
const loaderWrap = document.getElementById("loaderWrap");
const loaderText = document.getElementById("loaderText");
const errorBanner = document.getElementById("errorBanner");
const resultsDiv = document.getElementById("results");

// ---------- State ----------
let selectedFile = null;       // File or Blob ready to upload
let remoteMediaInfo = null;    // { srcUrl, mediaType, pageUrl } when sourced from context menu
let saveTimer = null;

// =====================================================================
// Settings (collapsible API endpoint)
// =====================================================================

settingsToggle.addEventListener("click", () => {
    settingsPanel.classList.toggle("open");
});

chrome.storage.local.get([STORAGE_API_KEY], (data) => {
    apiUrlInput.value = data[STORAGE_API_KEY] || DEFAULT_API_BASE;
});

apiUrlInput.addEventListener("input", () => {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
        const value = apiUrlInput.value.trim() || DEFAULT_API_BASE;
        chrome.storage.local.set({ [STORAGE_API_KEY]: value }, () => {
            saveHint.classList.add("show");
            setTimeout(() => saveHint.classList.remove("show"), 1200);
        });
    }, 400);
});

function getApiBase() {
    return (apiUrlInput.value.trim() || DEFAULT_API_BASE).replace(/\/$/, "");
}

// =====================================================================
// Context-menu media intake
// =====================================================================

// Check storage on load in case the panel was just opened by the context menu.
chrome.storage.local.get([STORAGE_MEDIA_KEY], (data) => {
    if (data[STORAGE_MEDIA_KEY]) {
        loadRemoteMedia(data[STORAGE_MEDIA_KEY]);
    }
});

// Also listen live, in case the panel is already open when the user right-clicks again.
chrome.runtime.onMessage.addListener((message) => {
    if (message && message.type === "NEW_MEDIA" && message.payload) {
        loadRemoteMedia(message.payload);
    }
});

function loadRemoteMedia(info) {
    remoteMediaInfo = info;
    selectedFile = null;
    resultsDiv.classList.remove("show");
    hideError();

    mediaPreviewBody.innerHTML = "";
    const tag = document.createElement(
        info.mediaType === "video" ? "video" : info.mediaType === "audio" ? "audio" : "img"
    );
    tag.src = info.srcUrl;
    if (info.mediaType === "video" || info.mediaType === "audio") {
        tag.controls = true;
    }
    if (info.mediaType === "image") {
        tag.alt = "Media to verify";
    }
    mediaPreviewBody.appendChild(tag);
    mediaSourceUrl.textContent = info.srcUrl;
    mediaPreview.classList.add("show");

    dropZone.style.display = "none";
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = "Fetch & Analyze Media";
    
    // Automatically trigger analysis
    setTimeout(() => {
        if (!analyzeBtn.disabled) {
            analyzeBtn.click();
        }
    }, 100);
}

clearMediaBtn.addEventListener("click", () => {
    remoteMediaInfo = null;
    selectedFile = null;
    mediaPreview.classList.remove("show");
    mediaPreviewBody.innerHTML = "";
    dropZone.style.display = "block";
    analyzeBtn.disabled = true;
    analyzeBtn.textContent = "Analyze Media";
    resultsDiv.classList.remove("show");
    hideError();
    chrome.storage.local.remove(STORAGE_MEDIA_KEY);
});

// =====================================================================
// Local drag-and-drop fallback
// =====================================================================

dropZone.addEventListener("click", () => fileInput.click());

dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
});

dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
});

dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files.length) {
        handleLocalFile(e.dataTransfer.files[0]);
    }
});

fileInput.addEventListener("change", () => {
    if (fileInput.files.length) {
        handleLocalFile(fileInput.files[0]);
    }
});

function handleLocalFile(file) {
    // A local pick always overrides any pending remote media.
    remoteMediaInfo = null;
    selectedFile = file;
    mediaPreview.classList.remove("show");
    mediaPreviewBody.innerHTML = "";
    chrome.storage.local.remove(STORAGE_MEDIA_KEY);

    dropText.innerHTML = `<strong>Selected:</strong> ${escapeHtml(file.name)}`;
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = "Analyze Media";
    resultsDiv.classList.remove("show");
    hideError();
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

// =====================================================================
// Analysis
// =====================================================================

analyzeBtn.addEventListener("click", async () => {
    hideError();
    analyzeBtn.disabled = true;
    setLoading(true, remoteMediaInfo ? "Fetching media…" : "Uploading media…");
    resultsDiv.classList.remove("show");

    try {
        let fileToSend = selectedFile;

        // If the media came from a right-click, we still need to fetch the
        // actual bytes before we can attach them to FormData.
        if (!fileToSend && remoteMediaInfo) {
            fileToSend = await fetchRemoteMediaAsFile(remoteMediaInfo);
        }

        if (!fileToSend) {
            throw new Error("No media selected.");
        }

        setLoading(true, "Analyzing media…");

        const formData = new FormData();
        formData.append("file", fileToSend);

        const apiUrl = `${getApiBase()}/detect`;

        const response = await fetch(apiUrl, {
            method: "POST", headers: {"ngrok-skip-browser-warning": "true"},
            body: formData
        });

        if (!response.ok) {
            throw new Error(`Server responded with ${response.status}`);
        }

        const data = await response.json();
        displayResults(data);
    } catch (err) {
        console.error("Deepfake Detector: analysis failed", err);
        showError(
            err && err.message
                ? `Couldn't complete analysis: ${err.message}`
                : "Error connecting to the Deepfake API. Is the server running?"
        );
    } finally {
        setLoading(false);
        analyzeBtn.disabled = false;
    }
});

async function fetchRemoteMediaAsFile(info) {
    const res = await fetch(info.srcUrl);
    if (!res.ok) {
        throw new Error(`Could not download media (${res.status})`);
    }
    const blob = await res.blob();
    const name = guessFilename(info.srcUrl, blob.type);
    return new File([blob], name, { type: blob.type });
}

function guessFilename(url, mimeType) {
    try {
        const clean = url.split("?")[0];
        const last = clean.substring(clean.lastIndexOf("/") + 1);
        if (last) return last;
    } catch (_) {
        // fall through
    }
    const ext = (mimeType && mimeType.split("/")[1]) || "bin";
    return `media.${ext}`;
}

function setLoading(isLoading, text) {
    loaderWrap.classList.toggle("show", isLoading);
    if (text) loaderText.textContent = text;
}

function showError(msg) {
    errorBanner.textContent = msg;
    errorBanner.classList.add("show");
}

function hideError() {
    errorBanner.classList.remove("show");
    errorBanner.textContent = "";
}

function displayResults(data) {
    resultsDiv.classList.add("show");

    if (data.vision_fake_probability !== null && data.vision_fake_probability !== undefined) {
        const vp = (data.vision_fake_probability * 100).toFixed(1);
        document.getElementById("visionScoreTxt").innerText = `${vp}%`;
        document.getElementById("visionScoreBar").style.width = `${vp}%`;
    } else {
        document.getElementById("visionScoreTxt").innerText = "N/A";
        document.getElementById("visionScoreBar").style.width = "0%";
    }

    if (data.audio_fake_probability !== null && data.audio_fake_probability !== undefined) {
        const ap = (data.audio_fake_probability * 100).toFixed(1);
        document.getElementById("audioScoreTxt").innerText = `${ap}%`;
        document.getElementById("audioScoreBar").style.width = `${ap}%`;
    } else {
        document.getElementById("audioScoreTxt").innerText = "N/A";
        document.getElementById("audioScoreBar").style.width = "0%";
    }

    const fp = (Number(data.fusion_score) * 100).toFixed(1);
    document.getElementById("fusionScoreTxt").innerText = `${fp}%`;
    const fBar = document.getElementById("fusionScoreBar");
    fBar.style.width = `${fp}%`;
    fBar.className = fp < 50 ? "score-fill fill-green" : "score-fill fill-red";

    const verdictEl = document.getElementById("verdict");
    const decision = (data.final_decision || "").toString();
    verdictEl.innerText = decision;
    verdictEl.className = `verdict ${decision.toLowerCase()}`;
}
