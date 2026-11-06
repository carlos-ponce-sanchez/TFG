const API_BASE = "/api";

// ── Correos de ejemplo ────────────────────────────────────────────────────────
const SAMPLE_EMAILS = {
  phishing_en: `Subject: URGENT: Your account has been suspended

Dear Customer,

We have detected suspicious activity on your account. Your access has been temporarily suspended for security reasons.

Please verify your identity immediately by clicking the link below:
http://secure-bank-verify.xyz/login?token=abc123

Failure to verify within 24 hours will result in permanent account closure. Your funds may be at risk.

Security Team
Customer Support`,

  legitimo_en: `Hi Sarah,

Just a quick follow-up on our meeting yesterday. I've attached the Q3 report you requested.

The numbers look good overall — revenue is up 12% compared to last quarter. Let me know if you have any questions before the board meeting on Friday.

Best regards,
Michael`,

  phishing_es: `Asunto: URGENTE: Su cuenta bancaria será bloqueada en 24 horas

Estimado cliente,

Hemos detectado un acceso no autorizado a su cuenta. Para proteger sus fondos debe verificar sus datos de forma inmediata.

Acceda ahora: http://banco-seguro-verificacion.es/confirmar

Si no verifica en las próximas 2 horas, su cuenta será bloqueada permanentemente. Introduzca su número de tarjeta y PIN para confirmar su identidad.

Departamento de Seguridad Bancaria`,

  legitimo_es: `Hola equipo,

Os recuerdo que mañana tenemos la reunión semanal a las 10:00 en la sala de conferencias B.

El orden del día incluye: revisión del sprint, planificación de la próxima iteración y feedback del cliente.

Por favor, traed vuestros portátiles. Si no podéis asistir en persona, el enlace de Teams está en el calendario.

Un saludo,
Carlos`,
};

// ── Exportación PDF ───────────────────────────────────────────────────────────
function downloadPDF(result, filename) {
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF({ unit: "mm", format: "a4" });

  const { label, score, features, top_tokens, headers } = result;
  const scorePercent = (score * 100).toFixed(1);
  const lang = (features.detected_lang || "en").toUpperCase();
  const now = new Date().toLocaleString("es-ES");
  const pageW = doc.internal.pageSize.getWidth();
  const pageH = doc.internal.pageSize.getHeight();
  const margin = 18;
  const contentW = pageW - margin * 2;
  let y = 20;

  // Función auxiliar: añade nueva página si queda poco espacio
  function checkPage(needed) {
    if (y + needed > pageH - 20) {
      doc.addPage();
      y = 20;
    }
  }

  // ── Cabecera ──
  doc.setFillColor(15, 23, 42);
  doc.rect(0, 0, pageW, 36, "F");
  doc.setTextColor(255, 255, 255);
  doc.setFontSize(16);
  doc.setFont("helvetica", "bold");
  doc.text("Informe de Análisis de Phishing", margin, y);
  y += 8;
  doc.setFontSize(9);
  doc.setFont("helvetica", "normal");
  doc.setTextColor(148, 163, 184);
  doc.text(`Generado: ${now}${filename ? "  ·  Archivo: " + filename : ""}`, margin, y);
  y = 48;

  // ── Resultado principal ──
  doc.setFontSize(13);
  doc.setFont("helvetica", "bold");
  if (label === "phishing") {
    doc.setTextColor(239, 68, 68);
    doc.text("PHISHING DETECTADO", margin, y);
  } else {
    doc.setTextColor(34, 197, 94);
    doc.text("CORREO LEGITIMO", margin, y);
  }
  y += 8;

  doc.setFontSize(10);
  doc.setFont("helvetica", "normal");
  doc.setTextColor(60, 60, 60);
  doc.text(`Probabilidad de phishing: ${scorePercent}%   ·   Idioma detectado: ${lang}`, margin, y);
  y += 5;
  doc.setFontSize(8);
  doc.setTextColor(120, 120, 120);
  const scoreExplain = "La probabilidad indica el grado de confianza del modelo en que el correo es phishing (0% = seguro, 100% = phishing claro).";
  const scoreLines = doc.splitTextToSize(scoreExplain, contentW);
  doc.text(scoreLines, margin, y);
  y += scoreLines.length * 4 + 4;

  // ── Barra de score ──
  doc.setFillColor(229, 231, 235);
  doc.rect(margin, y, contentW, 4, "F");
  const barColor = score > 0.7 ? [239, 68, 68] : score > 0.4 ? [234, 179, 8] : [34, 197, 94];
  doc.setFillColor(...barColor);
  doc.rect(margin, y, contentW * score, 4, "F");
  y += 12;

  // ── Features ──
  checkPage(50);
  doc.setFontSize(11);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(30, 30, 30);
  doc.text("Caracteristicas detectadas", margin, y);
  y += 5;
  doc.setFontSize(8);
  doc.setFont("helvetica", "normal");
  doc.setTextColor(120, 120, 120);
  doc.text("Indicadores extraidos automaticamente del texto del correo mediante analisis estatico.", margin, y);
  y += 6;

  doc.setFontSize(10);
  doc.setFont("helvetica", "normal");
  const domains = (features.domains || []).join(", ") || "Ninguno";
  const urgent = (features.urgent_words || []).join(", ") || "Ninguna";
  const blacklisted = (features.blacklisted_domains || []).join(", ");
  const rows = [
    ["N de enlaces", String(features.num_urls ?? 0)],
    ["Dominios detectados", domains],
    ["Palabras de urgencia", urgent],
    ["Longitud (caracteres)", String(features.num_chars ?? "—")],
  ];
  rows.forEach(([key, val]) => {
    checkPage(10);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(80, 80, 80);
    doc.text(key + ":", margin, y);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(30, 30, 30);
    const lines = doc.splitTextToSize(val, contentW - 60);
    doc.text(lines, margin + 58, y);
    y += 6 * lines.length + 1;
  });
  y += 4;

  // ── Dominios en lista negra ──
  if (blacklisted) {
    checkPage(20);
    doc.setFontSize(10);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(200, 30, 30);
    doc.text("Dominios en lista negra:", margin, y);
    y += 6;
    doc.setFont("helvetica", "normal");
    doc.setTextColor(180, 30, 30);
    const blLines = doc.splitTextToSize(blacklisted, contentW);
    doc.text(blLines, margin, y);
    y += blLines.length * 5 + 2;
    doc.setFontSize(8);
    doc.setTextColor(120, 120, 120);
    doc.text("Estos dominios aparecen en bases de datos publicas de phishing (PhishTank, APWG).", margin, y);
    y += 8;
  }

  // ── Cabeceras del correo (solo EML) ──
  if (headers) {
    checkPage(35);
    doc.setFontSize(11);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(30, 30, 30);
    doc.text("Analisis de cabeceras del correo", margin, y);
    y += 5;
    doc.setFontSize(8);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(120, 120, 120);
    doc.text("Las cabeceras revelan la ruta real del correo y posibles suplantaciones de identidad.", margin, y);
    y += 6;

    doc.setFontSize(10);
    const headerRows = [
      ["De (From)", headers.from || "—"],
      ["Responder a (Reply-To)", headers.reply_to || "—"],
      ["Return-Path", headers.return_path || "—"],
    ];
    headerRows.forEach(([key, val]) => {
      checkPage(10);
      doc.setFont("helvetica", "bold");
      doc.setTextColor(80, 80, 80);
      doc.text(key + ":", margin, y);
      doc.setFont("helvetica", "normal");
      doc.setTextColor(30, 30, 30);
      const lines = doc.splitTextToSize(val, contentW - 60);
      doc.text(lines, margin + 58, y);
      y += 6 * lines.length + 1;
    });

    if (headers.warnings && headers.warnings.length) {
      y += 2;
      doc.setFont("helvetica", "bold");
      doc.setTextColor(200, 30, 30);
      headers.warnings.forEach((w) => {
        checkPage(8);
        const wLines = doc.splitTextToSize("ALERTA: " + w, contentW);
        doc.text(wLines, margin, y);
        y += wLines.length * 5 + 2;
      });
    }
    y += 4;
  }

  // ── Tokens influyentes ──
  if (top_tokens && top_tokens.length) {
    checkPage(30);
    doc.setFontSize(11);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(30, 30, 30);
    doc.text("Tokens mas influyentes en la decision", margin, y);
    y += 5;
    doc.setFontSize(8);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(120, 120, 120);
    const tokenExplain = "El modelo analiza ~20.000 palabras (tokens) mediante TF-IDF. Aqui se muestran las que mas peso tuvieron. " +
      "Un valor positivo empuja hacia phishing; un valor negativo empuja hacia legitimo.";
    const tokenLines = doc.splitTextToSize(tokenExplain, contentW);
    doc.text(tokenLines, margin, y);
    y += tokenLines.length * 4 + 4;

    doc.setFontSize(10);
    top_tokens.forEach((t, i) => {
      checkPage(8);
      const contrib = (t.contribution || 0).toFixed(4);
      const direction = t.contribution > 0 ? "(+phishing)" : "(legitimo)";
      const tokenLabel = t.original
        ? `"${t.original}" (${t.token})`
        : `"${t.token}"`;
      doc.setFont("helvetica", "bold");
      doc.setTextColor(80, 80, 80);
      doc.text(`${i + 1}.`, margin, y);
      doc.setFont("helvetica", "normal");
      doc.setTextColor(30, 30, 30);
      doc.text(tokenLabel, margin + 8, y);
      doc.setTextColor(t.contribution > 0 ? 180 : 34, t.contribution > 0 ? 30 : 140, t.contribution > 0 ? 30 : 80);
      doc.text(`${contrib} ${direction}`, margin + 70, y);
      y += 6;
    });
    y += 6;
  }

  // ── Conclusión y recomendación ──
  checkPage(35);
  doc.setFontSize(11);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(30, 30, 30);
  doc.text("Conclusion y recomendacion", margin, y);
  y += 7;

  doc.setFontSize(10);
  doc.setFont("helvetica", "normal");
  doc.setTextColor(50, 50, 50);

  let conclusion;
  if (label === "phishing") {
    conclusion =
      `El sistema ha clasificado este correo como PHISHING con una confianza del ${scorePercent}%. ` +
      "Se recomienda no hacer clic en ningun enlace, no descargar archivos adjuntos y no responder al remitente. " +
      "Si el correo solicita datos personales o bancarios, es muy probable que se trate de un intento de fraude. " +
      "Reporte el correo como spam/phishing en su cliente de correo.";
  } else {
    conclusion =
      `El sistema ha clasificado este correo como LEGITIMO con una probabilidad de phishing del ${scorePercent}%. ` +
      "No se han detectado indicadores claros de suplantacion de identidad. " +
      "No obstante, mantenga siempre precaucion ante correos inesperados que soliciten informacion sensible.";
  }
  const concLines = doc.splitTextToSize(conclusion, contentW);
  doc.text(concLines, margin, y);
  y += concLines.length * 5 + 6;

  // Nota metodológica
  checkPage(20);
  doc.setFontSize(8);
  doc.setTextColor(120, 120, 120);
  const nota = "Nota: Este analisis es automatico y se basa en un modelo de Machine Learning entrenado con correos reales. " +
    "No sustituye el criterio humano. La precision del modelo varia segun el idioma y tipo de correo.";
  const notaLines = doc.splitTextToSize(nota, contentW);
  doc.text(notaLines, margin, y);

  // ── Pie de página ──
  doc.setFillColor(15, 23, 42);
  doc.rect(0, pageH - 12, pageW, 12, "F");
  doc.setFontSize(8);
  doc.setTextColor(148, 163, 184);
  doc.text("Detector de Phishing · TFG · Sistema de deteccion mediante IA y NLP", margin, pageH - 4);

  const safeName = (filename || "analisis").replace(/[^a-zA-Z0-9_.-]/g, "_");
  doc.save(`informe_${safeName}_${Date.now()}.pdf`);
}

// Sanitiza strings antes de insertarlos en innerHTML para prevenir XSS.
function sanitize(str) {
  const div = document.createElement("div");
  div.appendChild(document.createTextNode(String(str)));
  return div.innerHTML;
}

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
const clearBtn = document.getElementById("clear-btn");
const analysisCounterEl = document.getElementById("analysis-counter");

let selectedFiles = [];
let analysisCount = 0;

function updateCounter() {
  analysisCount++;
  analysisCounterEl.textContent = `${analysisCount} análisis realizados`;
}

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

// ── Ejemplos rápidos ──────────────────────────────────────────────────────────
document.querySelectorAll(".example-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const key = btn.dataset.example;
    if (SAMPLE_EMAILS[key]) {
      emailTextEl.value = SAMPLE_EMAILS[key];
      emailTextEl.focus();
      showToast("Ejemplo cargado. Pulsa Analizar.", "info");
    }
  });
});

// ── Limpiar resultados ────────────────────────────────────────────────────────
clearBtn.addEventListener("click", () => {
  clearResults();
  clearBtn.classList.add("hidden");
});

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

function renderSingleResult(result, filename) {
  const { label, score, features, top_tokens } = result;
  const scorePercent = (score * 100).toFixed(1);

  const container = document.createElement("div");
  container.className = "result-fade-in";

  const summary = document.createElement("div");
  summary.className = "result-summary";

  const labelPill = document.createElement("div");
  labelPill.className = `pill-label ${label}`;
  labelPill.textContent = label === "phishing" ? "PHISHING" : "LEGÍTIMO";

  const langBadge = document.createElement("span");
  const detectedLang = features.detected_lang || "en";
  langBadge.className = `lang-badge lang-${detectedLang}`;
  langBadge.textContent = detectedLang.toUpperCase();
  langBadge.title = detectedLang === "es" ? "Idioma detectado: Español" : "Detected language: English";

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
  summary.appendChild(langBadge);
  summary.appendChild(scoreBar);
  summary.appendChild(scoreText);

  const statsGrid = document.createElement("div");
  statsGrid.className = "stats-grid";

  const statNumUrls = document.createElement("div");
  statNumUrls.className = "stat-card";
  statNumUrls.innerHTML = `
    <div class="stat-label">Nº de enlaces</div>
    <div class="stat-value">${sanitize(features.num_urls ?? 0)}</div>
  `;

  const statDomains = document.createElement("div");
  statDomains.className = "stat-card";
  const blacklisted = features.blacklisted_domains || [];
  const domainsHtml = (features.domains || []).slice(0, 3).map(d => {
    const isBlacklisted = blacklisted.includes(d);
    return isBlacklisted
      ? `<span class="blacklisted-domain">${sanitize(d)} ⚠</span>`
      : sanitize(d);
  }).join(", ") || "—";
  statDomains.innerHTML = `
    <div class="stat-label">Dominios detectados</div>
    <div class="stat-value">${domainsHtml || "—"}</div>
    ${blacklisted.length ? `<div class="blacklist-warning">⚠ ${blacklisted.length === 1 ? "Dominio en lista negra" : blacklisted.length + " dominios en lista negra"}</div>` : ""}
  `;

  const statUrgent = document.createElement("div");
  statUrgent.className = "stat-card";
  const urgentText = (features.urgent_words || []).slice(0, 4).map(sanitize).join(", ") || "Ninguna palabra clave detectada";
  statUrgent.innerHTML = `
    <div class="stat-label">Palabras de urgencia</div>
    <div class="stat-value">${urgentText}</div>
  `;

  const statLength = document.createElement("div");
  statLength.className = "stat-card";
  statLength.innerHTML = `
    <div class="stat-label">Longitud (caracteres)</div>
    <div class="stat-value">${sanitize(features.num_chars ?? "—")}</div>
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
      // Mostrar "palabra_original → token" si hay palabra original diferente
      nameSpan.textContent = t.original
        ? `${t.original} → ${t.token}`
        : t.token;
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

  // ── Cabeceras EML (solo si el archivo era .eml) ──
  const headers = result.headers;
  let headersBlock = null;
  if (headers) {
    headersBlock = document.createElement("div");
    headersBlock.className = "headers-block";
    const title = document.createElement("div");
    title.className = "headers-title";
    title.textContent = "Análisis de cabeceras del correo";
    headersBlock.appendChild(title);

    const rows = [
      ["Remitente (From)", headers.from],
      ["Responder a (Reply-To)", headers.reply_to],
      ["Ruta de retorno", headers.return_path],
    ].filter(([, v]) => v);

    rows.forEach(([label, value]) => {
      const row = document.createElement("div");
      row.className = "header-row";
      row.innerHTML = `<span class="header-key">${sanitize(label)}:</span> <span class="header-val">${sanitize(value)}</span>`;
      headersBlock.appendChild(row);
    });

    if (headers.warnings && headers.warnings.length) {
      headers.warnings.forEach(w => {
        const warn = document.createElement("div");
        warn.className = "header-warning";
        warn.textContent = "⚠ " + w;
        headersBlock.appendChild(warn);
      });
    }
  }

  const pdfBtn = document.createElement("button");
  pdfBtn.className = "button pdf-btn";
  pdfBtn.textContent = "Descargar informe PDF";
  pdfBtn.addEventListener("click", () => downloadPDF(result, filename || null));

  // ── Bloque de feedback ────────────────────────────────────────────────────
  const feedbackBlock = document.createElement("div");
  feedbackBlock.className = "feedback-block";

  const feedbackLabel = document.createElement("span");
  feedbackLabel.className = "feedback-label";
  feedbackLabel.textContent = "¿Es correcta esta predicción?";
  feedbackBlock.appendChild(feedbackLabel);

  const btnYes = document.createElement("button");
  btnYes.className = "feedback-btn feedback-yes";
  btnYes.textContent = "Sí, es correcta";

  const btnNo = document.createElement("button");
  btnNo.className = "feedback-btn feedback-no";
  btnNo.textContent = "No, es incorrecta";

  const feedbackMsg = document.createElement("span");
  feedbackMsg.className = "feedback-msg hidden";

  async function sendFeedback(correct, trueLabel) {
    btnYes.disabled = true;
    btnNo.disabled = true;
    try {
      await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: result._text || "",
          predicted_label: result.label,
          correct,
          true_label: trueLabel || null,
        }),
      });
      feedbackMsg.textContent = correct
        ? "Gracias por confirmar la predicción."
        : "Gracias. Tu corrección ayudará a mejorar el modelo.";
    } catch {
      feedbackMsg.textContent = "No se pudo enviar el feedback.";
    }
    feedbackMsg.classList.remove("hidden");
    btnYes.classList.add("hidden");
    btnNo.classList.add("hidden");
    feedbackLabel.classList.add("hidden");
  }

  btnYes.addEventListener("click", () => sendFeedback(true, null));
  btnNo.addEventListener("click", () => {
    const opposite = result.label === "phishing" ? "legitimo" : "phishing";
    sendFeedback(false, opposite);
  });

  feedbackBlock.appendChild(btnYes);
  feedbackBlock.appendChild(btnNo);
  feedbackBlock.appendChild(feedbackMsg);

  container.appendChild(summary);
  container.appendChild(statsGrid);
  container.appendChild(tokensList);
  if (headersBlock) container.appendChild(headersBlock);
  container.appendChild(pdfBtn);
  container.appendChild(feedbackBlock);

  return container;
}

function showSkeleton() {
  resultsPlaceholderEl.style.display = "none";
  resultsContainerEl.classList.remove("hidden");
  resultsContainerEl.innerHTML = `
    <div class="skeleton-result">
      <div class="skeleton-header">
        <div class="skeleton skeleton-pill"></div>
        <div class="skeleton skeleton-badge"></div>
        <div class="skeleton-bar-wrap">
          <div class="skeleton skeleton-bar"></div>
          <div class="skeleton skeleton-text-sm"></div>
        </div>
      </div>
      <div class="skeleton-grid">
        <div class="skeleton skeleton-card"></div>
        <div class="skeleton skeleton-card"></div>
        <div class="skeleton skeleton-card"></div>
        <div class="skeleton skeleton-card"></div>
      </div>
      <div class="skeleton-tokens">
        <div class="skeleton skeleton-chip"></div>
        <div class="skeleton skeleton-chip"></div>
        <div class="skeleton skeleton-chip"></div>
        <div class="skeleton skeleton-chip"></div>
        <div class="skeleton skeleton-chip"></div>
      </div>
    </div>
  `;
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
  clearBtn.classList.remove("hidden");

  const block = renderSingleResult(result);
  resultsContainerEl.appendChild(block);
  updateCounter();
}

function showResultsForFiles(results) {
  resultsContainerEl.innerHTML = "";
  resultsPlaceholderEl.style.display = "none";
  resultsContainerEl.classList.remove("hidden");
  clearBtn.classList.remove("hidden");

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

    const details = renderSingleResult(entry, entry.filename);
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
  analyzeTextBtn.innerHTML = `<span class="btn-spinner"></span>Analizando...`;
  showSkeleton();

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
    data._text = text;  // guardamos el texto para el feedback
    showResultsForText(data);
    addToHistory(data, text, "text", null);
    showToast("Análisis completado.", "success");
  } catch (err) {
    console.error(err);
    showToast(err.message || "No se ha podido conectar con la API.", "error");
  } finally {
    analyzeTextBtn.disabled = false;
    analyzeTextBtn.innerHTML = "Analizar texto";
  }
});

analyzeFilesBtn.addEventListener("click", async () => {
  if (!selectedFiles.length) {
    showToast("Selecciona al menos un fichero para analizar.", "error");
    return;
  }

  analyzeFilesBtn.disabled = true;
  analyzeFilesBtn.innerHTML = `<span class="btn-spinner"></span>Analizando...`;
  showSkeleton();

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
      data.results.forEach((entry) => {
        updateCounter();
        addToHistory(entry, entry.filename, "file", entry.filename);
      });
      showToast("Análisis de ficheros completado.", "success");
    } else {
      showToast("La API no devolvió resultados.", "error");
    }
  } catch (err) {
    console.error(err);
    showToast(err.message || "No se ha podido conectar con la API.", "error");
  } finally {
    analyzeFilesBtn.disabled = false;
    analyzeFilesBtn.innerHTML = "Analizar ficheros";
  }
});

clearResults();
checkApiStatus();

// ── Historial (localStorage) ──────────────────────────────────────────────────

const HISTORY_KEY = "phishing_history";
const MAX_HISTORY = 10;

const historyListEl   = document.getElementById("history-list");
const historyEmptyEl  = document.getElementById("history-empty");
const historyClearBtn = document.getElementById("history-clear-btn");
const historyBadgeEl  = document.getElementById("history-count-badge");

function loadHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch (e) {
    console.error("[Historial] Error al leer localStorage:", e);
    return [];
  }
}

function saveHistory(items) {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(items));
    console.log("[Historial] Guardado:", items.length, "elemento(s).");
  } catch (e) {
    console.error("[Historial] Error al guardar en localStorage:", e);
  }
}

function addToHistory(result, preview, source, filename) {
  try {
    const previewStr = String(preview || "").slice(0, 80).replace(/\s+/g, " ").trim();
    const items = loadHistory();
    items.unshift({
      id: Date.now(),
      timestamp: new Date().toISOString(),
      preview: previewStr,
      source,
      filename: filename || null,
      result,
    });
    saveHistory(items.slice(0, MAX_HISTORY));
    renderHistoryPanel();
  } catch (e) {
    console.error("[Historial] Error en addToHistory:", e);
  }
}

function updateHistoryBadge(count) {
  if (!historyBadgeEl) return;
  if (count > 0) {
    historyBadgeEl.textContent = count;
    historyBadgeEl.classList.remove("hidden");
  } else {
    historyBadgeEl.classList.add("hidden");
  }
}

function renderHistoryPanel() {
  const items = loadHistory();
  console.log("[Historial] Renderizando:", items.length, "elemento(s).");
  updateHistoryBadge(items.length);

  if (!items.length) {
    if (historyEmptyEl)  historyEmptyEl.classList.remove("hidden");
    if (historyListEl)   historyListEl.classList.add("hidden");
    if (historyClearBtn) historyClearBtn.classList.add("hidden");
    return;
  }

  if (historyEmptyEl)  historyEmptyEl.classList.add("hidden");
  if (historyListEl)   historyListEl.classList.remove("hidden");
  if (historyClearBtn) historyClearBtn.classList.remove("hidden");
  if (!historyListEl)  return;

  historyListEl.innerHTML = "";

  items.forEach((item, idx) => {
    try {
      const result   = item.result || {};
      const label    = result.label || "legitimo";
      const score    = typeof result.score === "number" ? result.score : 0;
      const features = result.features || {};
      const lang     = features.detected_lang || "en";
      const scorePercent = (score * 100).toFixed(1);
      const date   = new Date(item.timestamp);
      const timeStr = date.toLocaleDateString("es-ES", { day: "2-digit", month: "2-digit" })
        + " " + date.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
      const preview = item.preview || "";

      const card = document.createElement("div");
      card.className = "history-item";
      card.innerHTML = `
        <div class="history-item-header">
          <span class="pill-label ${label} pill-sm">${label === "phishing" ? "PHISHING" : "LEGÍTIMO"}</span>
          <span class="lang-badge lang-${lang}">${lang.toUpperCase()}</span>
          <span class="history-score">${scorePercent}%</span>
          <span class="history-time">${timeStr}</span>
          ${item.filename ? `<span class="history-source">${sanitize(item.filename)}</span>` : ""}
        </div>
        <div class="history-preview">${sanitize(preview)}${preview.length >= 80 ? "…" : ""}</div>
      `;
      card.addEventListener("click", () => {
        switchTab("analyzer");
        showResultsForText(result);
        showToast("Resultado cargado desde historial.", "info");
      });
      historyListEl.appendChild(card);
    } catch (e) {
      console.error("[Historial] Error renderizando item", idx, ":", e);
    }
  });
}

if (historyClearBtn) {
  historyClearBtn.addEventListener("click", () => {
    localStorage.removeItem(HISTORY_KEY);
    renderHistoryPanel();
    showToast("Historial borrado.", "info");
  });
}

// ── Tab switching ─────────────────────────────────────────────────────────────

const tabAnalyzer = document.getElementById("tab-analyzer");
const tabHistory  = document.getElementById("tab-history");
const tabStats    = document.getElementById("tab-stats");
let statsLoaded = false;
let statsLoading = false;

function switchTab(target) {
  document.querySelectorAll(".tab-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === target);
  });
  tabAnalyzer.classList.toggle("hidden", target !== "analyzer");
  tabHistory.classList.toggle("hidden",  target !== "history");
  tabStats.classList.toggle("hidden",    target !== "stats");

  if (target === "history") renderHistoryPanel();
  if (target === "stats" && !statsLoaded && !statsLoading) loadStats();
}

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});

// ── Stats page ────────────────────────────────────────────────────────────────

const MODEL_LABELS = {
  Regresion_Logistica: "Regresión Logística",
  SVM_Lineal: "SVM Lineal",
  Random_Forest: "Random Forest",
  Red_Neuronal_MLP: "Red Neuronal MLP",
};

function pct(v) {
  return (v * 100).toFixed(2) + "%";
}

async function loadStats() {
  statsLoading = true;
  const loadingEl = document.getElementById("stats-loading");
  const contentEl = document.getElementById("stats-content");

  try {
    const res = await fetch("/api/metrics");
    if (!res.ok) {
      const detail = res.status === 404
        ? "Ejecuta primero: python -m backend.ml.compare_models"
        : `Error ${res.status}`;
      throw new Error(detail);
    }
    const data = await res.json();

    renderStats(data.models, data.active_model);
    loadingEl.classList.add("hidden");
    contentEl.classList.remove("hidden");
    statsLoaded = true;
  } catch (err) {
    loadingEl.textContent = "No se han podido cargar las métricas. " + err.message;
  } finally {
    statsLoading = false;
  }
}

function renderStats(models, activeModelKey) {
  const active = models.find((m) => m.modelo === activeModelKey) || models[0];

  // Active model metric cards
  document.getElementById("active-model-name").textContent =
    MODEL_LABELS[active.modelo] || active.modelo;

  const metricsGrid = document.getElementById("active-metrics-grid");
  const activeCards = [
    { label: "Accuracy", value: pct(active.accuracy) },
    { label: "Precisión (phishing)", value: pct(active.precision_phishing) },
    { label: "Recall (phishing)", value: pct(active.recall_phishing) },
    { label: "F1 (phishing)", value: pct(active.f1_phishing) },
    { label: "F1 macro", value: pct(active.f1_macro) },
    { label: "Tiempo entren.", value: active.tiempo_entrenamiento_s + " s" },
  ];
  metricsGrid.innerHTML = activeCards
    .map(
      (c) => `
    <div class="metric-card">
      <div class="metric-label">${c.label}</div>
      <div class="metric-value">${c.value}</div>
    </div>`
    )
    .join("");

  // Comparison table
  const tbody = document.getElementById("models-table-body");
  tbody.innerHTML = models
    .map((m) => {
      const isActive = m.modelo === activeModelKey;
      return `<tr class="${isActive ? "row-active" : ""}">
        <td>${MODEL_LABELS[m.modelo] || m.modelo}${isActive ? ' <span class="active-badge">activo</span>' : ""}</td>
        <td>${pct(m.accuracy)}</td>
        <td>${pct(m.precision_phishing)}</td>
        <td>${pct(m.recall_phishing)}</td>
        <td>${pct(m.f1_phishing)}</td>
        <td>${pct(m.f1_macro)}</td>
        <td>${m.tiempo_entrenamiento_s}</td>
      </tr>`;
    })
    .join("");

  // Confusion matrices
  const cmContainer = document.getElementById("confusion-matrices");
  cmContainer.innerHTML = models
    .map((m) => {
      const [[tn, fp], [fn, tp]] = m.confusion_matrix;
      const total = tn + fp + fn + tp;
      return `
      <div class="cm-card">
        <div class="cm-title">${MODEL_LABELS[m.modelo] || m.modelo}</div>
        <table class="cm-table">
          <thead>
            <tr><th></th><th>Pred. Legítimo</th><th>Pred. Phishing</th></tr>
          </thead>
          <tbody>
            <tr>
              <th>Real Legítimo</th>
              <td class="cm-tn">${tn}<br><span class="cm-pct">${((tn/total)*100).toFixed(1)}%</span></td>
              <td class="cm-fp">${fp}<br><span class="cm-pct">${((fp/total)*100).toFixed(1)}%</span></td>
            </tr>
            <tr>
              <th>Real Phishing</th>
              <td class="cm-fn">${fn}<br><span class="cm-pct">${((fn/total)*100).toFixed(1)}%</span></td>
              <td class="cm-tp">${tp}<br><span class="cm-pct">${((tp/total)*100).toFixed(1)}%</span></td>
            </tr>
          </tbody>
        </table>
      </div>`;
    })
    .join("");
}

// ── Inicialización del badge del historial ─────────────────────────────────────
// Se ejecuta al final, cuando todos los elementos del DOM ya están declarados.
updateHistoryBadge(loadHistory().length);
