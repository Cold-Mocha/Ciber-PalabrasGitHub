// Lógica de front que conecta por REST/WS y renderiza el tablero en tiempo real.
const SNAPSHOT_INTERVAL_MS = 15000;
const DEFAULT_REPO_LIMIT = 10;
const DEFAULT_ACTIVITY_LIMIT = 50;
const SUPPORTED_LANGUAGES = ["python", "java"];

const topNInput = document.getElementById("top-n");
const topCombinedInput = document.getElementById("top-combined");
const statusPanel = document.getElementById("status-panel");
const statusText = document.getElementById("connection-status");
const kpiGrid = document.getElementById("language-kpis");
const combinedTableBody = document.getElementById("top-words-combined");
const repoTableBody = document.getElementById("repo-table-body");
const activityFeed = document.getElementById("activity-feed");
const topWordTargets = {
    python: document.getElementById("top-words-python"),
    java: document.getElementById("top-words-java"),
};
const currentRepoCard = document.getElementById("current-repo-card");

const state = {
    language: SUPPORTED_LANGUAGES[0],
    topN: Number(topNInput?.value) || 15,
    topCombined: Number(topCombinedInput?.value) || 15,
    repoLimit: DEFAULT_REPO_LIMIT,
    activityLimit: DEFAULT_ACTIVITY_LIMIT,
};

let dashboardSocket;
const topWordsSockets = new Map();
const topWordsReconnectTimers = new Map();
let dashboardReconnectTimer;
let snapshotTimer;
let lastCompletedRepo;

function buildQuery(params) {
    return new URLSearchParams(params).toString();
}

function websocketUrl(path, params) {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const host = window.location.host;
    return `${protocol}://${host}${path}?${buildQuery(params)}`;
}

function setStatus(text, status = "") {
    statusText.textContent = text;
    statusPanel.classList.remove("connected", "error");
    if (status === "connected") statusPanel.classList.add("connected");
    if (status === "error") statusPanel.classList.add("error");
}

function describeNumber(num) {
    if (num === undefined || num === null) return "0";
    return Number(num).toLocaleString();
}

function renderKpis(languageMetrics = {}, globalMetrics = null) {
    const repos = describeNumber(globalMetrics?.repositories || 0);
    const filesTotal = describeNumber(globalMetrics?.total_files || 0);
    const wordsTotal = describeNumber(globalMetrics?.total_words || 0);
    const runtimeSecs = globalMetrics?.runtime_seconds || 0;
    const runtimeText = runtimeSecs > 0
        ? `${Math.floor(runtimeSecs / 3600)}h ${Math.floor((runtimeSecs % 3600) / 60)}m ${runtimeSecs % 60}s`
        : "0s";

    const javaWords = describeNumber(languageMetrics?.java?.total_words || 0);
    const pythonWords = describeNumber(languageMetrics?.python?.total_words || 0);
    const javaFiles = describeNumber(languageMetrics?.java?.files_processed || 0);
    const pythonFiles = describeNumber(languageMetrics?.python?.files_processed || 0);

    kpiGrid.innerHTML = `
        <table class="kpi-table">
            <tbody>
                <tr>
                    <th>Tiempo activo</th>
                    <th>Repos monitoreados</th>
                    <th>Archivos totales</th>
                    <th>Palabras totales</th>
                </tr>
                <tr>
                    <td class="kpi-number">${runtimeText}</td>
                    <td class="kpi-number">${repos}</td>
                    <td class="kpi-number">${filesTotal}</td>
                    <td class="kpi-number">${wordsTotal}</td>
                </tr>
                <tr>
                    <th>Palabras Java</th>
                    <th>Palabras Python</th>
                    <th>Archivos Java</th>
                    <th>Archivos Python</th>
                </tr>
                <tr>
                    <td class="kpi-number">${javaWords}</td>
                    <td class="kpi-number">${pythonWords}</td>
                    <td class="kpi-number">${javaFiles}</td>
                    <td class="kpi-number">${pythonFiles}</td>
                </tr>
            </tbody>
        </table>
    `;
}

function renderTopWordsTable(language, words = []) {
    const target = topWordTargets[language];
    if (!target) return;
    if (!words.length) {
        target.innerHTML = '<tr><td colspan="3">Recolectando datos…</td></tr>';
        return;
    }
    target.innerHTML = words
        .map((item, index) => `
            <tr>
                <td>${index + 1}</td>
                <td>${item.word}</td>
                <td>${item.count}</td>
            </tr>
        `)
        .join("");
}

function renderCombinedTopWords(words = []) {
    if (!combinedTableBody) return;
    if (!words.length) {
        combinedTableBody.innerHTML = '<tr><td colspan="3">Recolectando datos…</td></tr>';
        return;
    }
    combinedTableBody.innerHTML = words
        .map((item, index) => `
            <tr>
                <td>${index + 1}</td>
                <td>${item.word}</td>
                <td>${describeNumber(item.count)}</td>
            </tr>
        `)
        .join("");
}

function renderTopWordsByLanguage(map = {}) {
    SUPPORTED_LANGUAGES.forEach((lang) => {
        renderTopWordsTable(lang, map[lang] || []);
    });
}

function formatRepoLanguageTags(words = []) {
    if (!words?.length) return "—";
    return words
        .map(({ word, count }) => `<span class="tag">${word} (${describeNumber(count)})</span>`)
        .join(" ");
}

function renderRepoTable(repos = []) {
    if (!repoTableBody) return;
    if (!repos.length) {
        repoTableBody.innerHTML = '<tr><td colspan="7">Aún no llegan repositorios…</td></tr>';
        return;
    }
    repoTableBody.innerHTML = repos
        .map((entry) => {
            const pythonWords = describeNumber(entry.languages?.python || 0);
            const javaWords = describeNumber(entry.languages?.java || 0);
            const pythonFiles = describeNumber(entry.files_processed?.python || 0);
            const javaFiles = describeNumber(entry.files_processed?.java || 0);
            const pythonTopWords = formatRepoLanguageTags(entry.language_top_words?.python);
            const javaTopWords = formatRepoLanguageTags(entry.language_top_words?.java);
            return `
                <tr>
                    <td class="repo-name">${entry.repo}</td>
                    <td>${pythonWords}</td>
                    <td>${javaWords}</td>
                    <td>${pythonFiles}</td>
                    <td>${javaFiles}</td>
                    <td>${pythonTopWords}</td>
                    <td>${javaTopWords}</td>
                </tr>
            `;
        })
        .join("");
}

function renderActivityFeed(events = []) {
    if (!activityFeed) return;
    if (!events.length) {
        activityFeed.innerHTML = '<li class="activity-item"><span>Esperando eventos iniciales…</span></li>';
        return;
    }
    activityFeed.innerHTML = events
        .map((event) => {
            const time = new Date(event.timestamp * 1000).toLocaleTimeString();
            const functionLabel = event.function_name ? `${event.function_name}()` : "Identificador desconocido";
            const fileLabel = event.file_path || "Archivo no disponible";
            return `
                <li class="activity-item">
                    <div>
                        <div class="repo-name">${event.repo}</div>
                        <div class="activity-meta">${time} · ${event.language.toUpperCase()} · ${fileLabel}</div>
                    </div>
                    <div class="activity-meta">
                        ${functionLabel} → <span class="word-chip">${event.word}</span> (#${event.repo_word_total})
                    </div>
                </li>
            `;
        })
        .join("");
}

function renderCurrentRepoProgress(progress = null) {
    if (!currentRepoCard) return;
    if (!progress) {
        currentRepoCard.innerHTML = '<p>Esperando progreso del repositorio…</p>';
        return;
    }
    const overall = progress.percent_overall || 0;
    const py = progress.percent_python || 0;
    const jv = progress.percent_java || 0;
    const totalPy = progress.total_python_files || 0;
    const totalJv = progress.total_java_files || 0;
    const donePy = progress.processed_python_files || 0;
    const doneJv = progress.processed_java_files || 0;
    const status = progress.status === "complete" ? "Completado" : "Procesando";

    currentRepoCard.innerHTML = `
        <div class="repo-progress-header">
            <div>
                <p class="eyebrow">${status}</p>
                <h3>${progress.repo}</h3>
            </div>
            <div class="repo-progress-meta">
                <span>Archivos PY: ${donePy}/${totalPy}</span>
                <span>Archivos JAVA: ${doneJv}/${totalJv}</span>
            </div>
        </div>
        <div class="progress-row">
            <label>Avance global</label>
            <div class="progress-bar"><span style="width:${overall}%"></span></div>
            <small>${overall}%</small>
        </div>
        <div class="progress-row">
            <label>Python</label>
            <div class="progress-bar"><span style="width:${py}%"></span></div>
            <small>${py}%</small>
        </div>
        <div class="progress-row">
            <label>Java</label>
            <div class="progress-bar"><span style="width:${jv}%"></span></div>
            <small>${jv}%</small>
        </div>
    `;

    if (progress.status === "complete" && lastCompletedRepo !== progress.repo) {
        playCompletionSound();
        lastCompletedRepo = progress.repo;
    }
}

function playCompletionSound() {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "sine";
        osc.frequency.value = 880;
        gain.gain.value = 0.08;
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.2);
    } catch (e) {
        console.warn("No se pudo reproducir sonido", e);
    }
}

function renderDashboard(payload = {}) {
    renderKpis(payload.language_metrics || {}, payload.global_metrics || null);
    renderCombinedTopWords(payload.combined_top_words || []);
    renderTopWordsByLanguage(payload.top_words_by_language || {});
    renderRepoTable(payload.top_repos || []);
    renderActivityFeed(payload.recent_activity || []);
    renderCurrentRepoProgress(payload.current_repo_progress || null);
}

async function fetchSnapshot() {
    const params = buildQuery({
        language: state.language,
        limit: state.topN,
        combined_limit: state.topCombined,
        repo_limit: state.repoLimit,
        activity_limit: state.activityLimit,
    });
    try {
        const response = await fetch(`/dashboard?${params}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        renderDashboard(data);
    } catch (error) {
        console.error("No se pudo obtener el estado del panel", error);
    }
}

function resetDashboardSocket() {
    if (dashboardReconnectTimer) {
        clearTimeout(dashboardReconnectTimer);
        dashboardReconnectTimer = undefined;
    }
    if (dashboardSocket) {
        const socketToClose = dashboardSocket;
        dashboardSocket = undefined;
        socketToClose.close();
    }
}

function tearDownTopWordsFallback() {
    topWordsReconnectTimers.forEach((timer) => clearTimeout(timer));
    topWordsReconnectTimers.clear();
    topWordsSockets.forEach((socket) => socket.close());
    topWordsSockets.clear();
}

function openTopWordsFallback(language) {
    const url = websocketUrl("/ws/top-words", {
        language,
        limit: state.topN,
    });
    const ws = new WebSocket(url);
    topWordsSockets.set(language, ws);

    ws.addEventListener("open", () => {
        if (!dashboardSocket) {
            setStatus("Fallback stream active", "error");
        }
    });

    ws.addEventListener("message", (event) => {
        try {
            const payload = JSON.parse(event.data);
            renderTopWordsTable(payload.language, payload.top_words || []);
        } catch (error) {
            console.error("Respuesta de respaldo inválida", error);
        }
    });

    ws.addEventListener("close", () => {
        if (topWordsSockets.get(language) !== ws) {
            return;
        }
        topWordsSockets.delete(language);
        if (!dashboardSocket) {
            const timer = setTimeout(() => {
                topWordsReconnectTimers.delete(language);
                openTopWordsFallback(language);
            }, 2000);
            topWordsReconnectTimers.set(language, timer);
        }
    });

    ws.addEventListener("error", () => {
        if (!dashboardSocket) {
            setStatus("Error en el respaldo", "error");
        }
    });
}

function ensureTopWordsFallback() {
    SUPPORTED_LANGUAGES.forEach((language) => {
        if (topWordsSockets.has(language) || topWordsReconnectTimers.has(language)) {
            return;
        }
        openTopWordsFallback(language);
    });
}

function openDashboardSocket() {
    const url = websocketUrl("/ws/dashboard", {
        language: state.language,
        limit: state.topN,
        combined_limit: state.topCombined,
        repo_limit: state.repoLimit,
        activity_limit: state.activityLimit,
    });
    const ws = new WebSocket(url);
    dashboardSocket = ws;

    ws.addEventListener("open", () => {
        setStatus("Datos llegando activamente", "connected");
        tearDownTopWordsFallback();
    });

    ws.addEventListener("message", (event) => {
        try {
            const payload = JSON.parse(event.data);
            renderDashboard(payload);
        } catch (error) {
            console.error("Respuesta del panel inválida", error);
        }
    });

    ws.addEventListener("close", () => {
        if (dashboardSocket !== ws) {
            return;
        }
        dashboardSocket = undefined;
        setStatus("Programa en espera. Activando respaldo…", "error");
        ensureTopWordsFallback();
        dashboardReconnectTimer = setTimeout(() => {
            dashboardReconnectTimer = undefined;
            openDashboardSocket();
        }, 2000);
    });

    ws.addEventListener("error", () => {
        setStatus("Interrupción temporal del stream", "error");
    });
}

function startSnapshotPolling() {
    if (snapshotTimer) {
        clearInterval(snapshotTimer);
    }
    snapshotTimer = setInterval(fetchSnapshot, SNAPSHOT_INTERVAL_MS);
}

function applySettings() {
    state.language = SUPPORTED_LANGUAGES[0];
    if (topNInput) {
        const parsedTopN = Number(topNInput.value);
        if (!Number.isFinite(parsedTopN) || parsedTopN < 1) {
            topNInput.value = state.topN;
        } else {
            state.topN = Math.min(100, parsedTopN);
            topNInput.value = state.topN;
        }
    }
    if (topCombinedInput) {
        const parsedCombined = Number(topCombinedInput.value);
        if (!Number.isFinite(parsedCombined) || parsedCombined < 1) {
            topCombinedInput.value = state.topCombined;
        } else {
            state.topCombined = Math.min(100, parsedCombined);
            topCombinedInput.value = state.topCombined;
        }
    }
    state.repoLimit = DEFAULT_REPO_LIMIT;
    state.activityLimit = DEFAULT_ACTIVITY_LIMIT;
    fetchSnapshot();
    startSnapshotPolling();
    resetDashboardSocket();
    tearDownTopWordsFallback();
    openDashboardSocket();
}

if (topNInput) {
    topNInput.addEventListener("change", applySettings);
}

if (topCombinedInput) {
    topCombinedInput.addEventListener("change", applySettings);
}

window.addEventListener("load", () => {
    applySettings();
});
