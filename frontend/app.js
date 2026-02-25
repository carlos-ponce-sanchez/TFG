const API_BASE = "/api";

const emailTextEl = document.getElementById("email-text");
const analyzeTextBtn = document.getElementById("analyze-text-btn");
const analyzeFilesBtn = document.getElementById("analyze-files-btn");
const dropzoneEl = document.getElementById("dropzone");
const fileInputEl = document.getElementById("file-input");
const fileListEl = document.getElementById("file-list");
const resultsPlaceholderEl = document.getElementById("results-placeholder");
const resultsContainerEl = document.getElementById("results-container");
const toastEl = document.getElementById("toast");
const apiStatusEl = document.getElementById("api-status");

let selectedFiles = [];

function showToast(message, type = "info", timeout = 3500) {
  toastEl.textContent = message;
  toastEl.className = "toast show " + (type === "error" ? "error" : type === "success" ? "success" : "");
  setTimeout(() => {
    toastEl.classList.remove("show");
  }, timeout);
}

async function checkApiStatus() {
  try {
    const res = await fetch(`${API_BASE}/predict-text`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: "ping" }),
    });
    if (res.ok) {
      apiStatusEl.textContent = "API: online";
      apiStatusEl.classList.add("ok");
    } else {
      apiStatusEl.textContent = "API: error";
      apiStatusEl.classList.add("error");
    }
  } catch (e) {
    apiStatusEl.textContent = "API: no conectada";
    apiStatusEl.classList.add("error");
  }
}

function renderFileList() {
  if (!selectedFiles.length) {
    fileListEl.textContent = "";
    return;
  }
  fileListEl.innerHTML = "";
  selectedFiles.forEach((file) => {
    const pill = document.createElement("div");
    pill.className = "file-pill";
    const span = document.createElement("span");
    span.textContent = file.name;
    pill.appendChild(span);
    fileListEl.appendChild(pill);
  });
}

dropzoneEl.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzoneEl.classList.add("dragover");
});

dropzoneEl.addEventListener("dragleave", (e) => {
  e.preventDefault();
  dropzoneEl.classList.remove("dragover");
});

dropzoneEl.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzoneEl.classList.remove("dragover");
  if (e.dataTransfer.files && e.dataTransfer.files.length) {
    selectedFiles = Array.from(e.dataTransfer.files);
    renderFileList();
  }
});

fileInputEl.addEventListener("change", (e) => {
  if (e.target.files && e.target.files.length) {
    selectedFiles = Array.from(e.target.files);
    renderFileList();
  }
});

function renderSingleResult(result) {
  const { label, score, features, top_tokens } = result;
  const scorePercent = (score * 100).toFixed(1);

  const container = document.createElement("div");

  const summary = document.createElement("div");
  summary.className = "result-summary";

  const labelPill = document.createElement("div");
  labelPill.className = `pill-label ${label}`;
  labelPill.textContent = label === "phishing" ? "PHISHING" : "LEGÍTIMO";

  const scoreBar = document.createElement("div");
  scoreBar.className = "score-bar";
  const scoreBarFill = document.createElement("div");
  scoreBarFill.className = "score-bar-fill";
  scoreBarFill.style.width = `${scorePercent}%`;
  scoreBar.appendChild(scoreBarFill);

  const scoreText = document.createElement("div");
  scoreText.className = "score-text";
  scoreText.textContent = `Probabilidad phishing: ${scorePercent}%`;

  summary.appendChild(labelPill);
  summary.appendChild(scoreBar);
  summary.appendChild(scoreText);

  const statsGrid = document.createElement("div");
  statsGrid.className = "stats-grid";

  const statNumUrls = document.createElement("div");
  statNumUrls.className = "stat-card";
  statNumUrls.innerHTML = `
    <div class="stat-label">Nº de enlaces</div>
    <div class="stat-value">${features.num_urls ?? 0}</div>
  `;

  const statDomains = document.createElement("div");
  statDomains.className = "stat-card";
  const domainsText = (features.domains || []).slice(0, 3).join(", ") || "—";
  statDomains.innerHTML = `
    <div class="stat-label">Dominios detectados</div>
    <div class="stat-value">${domainsText}</div>
  `;

  const statUrgent = document.createElement("div");
  statUrgent.className = "stat-card";
  const urgentText = (features.urgent_words || []).slice(0, 4).join(", ") || "Ninguna palabra clave detectada";
  statUrgent.innerHTML = `
    <div class="stat-label">Palabras de urgencia</div>
    <div class="stat-value">${urgentText}</div>
  `;

  const statLength = document.createElement("div");
  statLength.className = "stat-card";
  statLength.innerHTML = `
    <div class="stat-label">Longitud (caracteres)</div>
    <div class="stat-value">${features.num_chars ?? "—"}</div>
  `;

  statsGrid.appendChild(statNumUrls);
  statsGrid.appendChild(statDomains);
  statsGrid.appendChild(statUrgent);
  statsGrid.appendChild(statLength);

  const tokensList = document.createElement("div");
  tokensList.className = "tokens-list";
  if (top_tokens && top_tokens.length) {
    const labelEl = document.createElement("div");
    labelEl.textContent = "Tokens que más han influido en la decisión:";
    tokensList.appendChild(labelEl);

    top_tokens.forEach((t) => {
      const chip = document.createElement("span");
      chip.className = "token-chip";
      const nameSpan = document.createElement("span");
      nameSpan.textContent = t.token;
      const scoreSpan = document.createElement("span");
      scoreSpan.className = "token-score";
      scoreSpan.textContent = (t.contribution || 0).toFixed(3);
      chip.appendChild(nameSpan);
      chip.appendChild(scoreSpan);
      tokensList.appendChild(chip);
    });
  } else {
    const labelEl = document.createElement("div");
    labelEl.textContent = "No se han podido extraer tokens explicativos.";
    tokensList.appendChild(labelEl);
  }

  container.appendChild(summary);
  container.appendChild(statsGrid);
  container.appendChild(tokensList);

  return container;
}

function clearResults() {
  resultsContainerEl.innerHTML = "";
  resultsContainerEl.classList.add("hidden");
  resultsPlaceholderEl.style.display = "block";
}

function showResultsForText(result) {
  resultsContainerEl.innerHTML = "";
  resultsPlaceholderEl.style.display = "none";
  resultsContainerEl.classList.remove("hidden");

  const block = renderSingleResult(result);
  resultsContainerEl.appendChild(block);
}

function showResultsForFiles(results) {
  resultsContainerEl.innerHTML = "";
  resultsPlaceholderEl.style.display = "none";
  resultsContainerEl.classList.remove("hidden");

  results.forEach((entry) => {
    const wrapper = document.createElement("div");
    wrapper.className = "file-result";

    const header = document.createElement("div");
    header.className = "file-result-header";

    const nameSpan = document.createElement("span");
    nameSpan.className = "file-name";
    nameSpan.textContent = entry.filename;
    header.appendChild(nameSpan);

    const labelPill = document.createElement("div");
    labelPill.className = `pill-label ${entry.label}`;
    labelPill.textContent = entry.label === "phishing" ? "PHISHING" : "LEGÍTIMO";
    header.appendChild(labelPill);

    wrapper.appendChild(header);

    const details = renderSingleResult(entry);
    wrapper.appendChild(details);

    resultsContainerEl.appendChild(wrapper);
  });
}

analyzeTextBtn.addEventListener("click", async () => {
  const text = emailTextEl.value.trim();
  if (!text) {
    showToast("Introduce el texto del correo a analizar.", "error");
    return;
  }

  analyzeTextBtn.disabled = true;
  analyzeTextBtn.textContent = "Analizando...";

  try {
    const res = await fetch(`${API_BASE}/predict-text`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) {
      let msg = "Error al analizar el texto.";
      try {
        const data = await res.json();
        if (data.detail) msg = data.detail;
      } catch (_) {}
      throw new Error(msg);
    }
    const data = await res.json();
    showResultsForText(data);
    showToast("Análisis completado.", "success");
  } catch (err) {
    console.error(err);
    showToast(err.message || "No se ha podido conectar con la API.", "error");
  } finally {
    analyzeTextBtn.disabled = false;
    analyzeTextBtn.textContent = "Analizar texto";
  }
});

analyzeFilesBtn.addEventListener("click", async () => {
  if (!selectedFiles.length) {
    showToast("Selecciona al menos un fichero para analizar.", "error");
    return;
  }

  analyzeFilesBtn.disabled = true;
  analyzeFilesBtn.textContent = "Analizando...";

  const form = new FormData();
  selectedFiles.forEach((file) => form.append("files", file));

  try {
    const res = await fetch(`${API_BASE}/predict-file`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) {
      let msg = "Error al analizar los ficheros.";
      try {
        const data = await res.json();
        if (data.detail) msg = data.detail;
      } catch (_) {}
      throw new Error(msg);
    }
    const data = await res.json();
    if (data.results && data.results.length) {
      showResultsForFiles(data.results);
      showToast("Análisis de ficheros completado.", "success");
    } else {
      showToast("La API no devolvió resultados.", "error");
    }
  } catch (err) {
    console.error(err);
    showToast(err.message || "No se ha podido conectar con la API.", "error");
  } finally {
    analyzeFilesBtn.disabled = false;
    analyzeFilesBtn.textContent = "Analizar ficheros";
  }
});

clearResults();
checkApiStatus();

