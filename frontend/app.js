/**
 * app.js — Lógica do frontend da aplicação de Análise de Dados com IA.
 *
 * Responsabilidades:
 *  - Gerenciar o upload de arquivos (drag & drop ou seleção)
 *  - Exibir os resultados: gráficos Plotly, tabela estatística e insights da IA
 *  - Controlar o chat interativo para perguntas sobre os dados carregados
 *  - Controlar os estados visuais da página (upload / carregando / erro / resultados)
 */

// API_URL vazio porque o frontend é servido pelo mesmo servidor FastAPI (mesma origem).
// Se servir o frontend separadamente, defina aqui: "http://localhost:8000"
const API_URL = "";

// Guarda o resumo do arquivo atual para enviar ao chat a cada mensagem
let currentSummary = null;

// Histórico da conversa no formato esperado pela OpenAI: [{role, content}, ...]
let chatHistory = [];

// Referências aos elementos de seção para controle de visibilidade
const dropZone   = document.getElementById("drop-zone");
const fileInput  = document.getElementById("file-input");
const uploadSec  = document.getElementById("upload-section");
const loadingSec = document.getElementById("loading-section");
const errorSec   = document.getElementById("error-section");
const resultsSec = document.getElementById("results-section");


// =============================================================================
// Drag & Drop
// =============================================================================

dropZone.addEventListener("dragover", (e) => {
  e.preventDefault(); // necessário para permitir o evento "drop"
  dropZone.classList.add("drag-over");
});

dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));

dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("drag-over");
  const file = e.dataTransfer.files[0];
  if (file) uploadFile(file);
});

// Dispara upload também ao selecionar via botão "Selecionar arquivo"
fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) uploadFile(fileInput.files[0]);
});


// =============================================================================
// Upload
// =============================================================================

/**
 * Envia o arquivo para o backend e processa a resposta.
 * Ao receber os dados, salva o summary no estado global e renderiza os resultados.
 */
async function uploadFile(file) {
  showSection("loading");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch(`${API_URL}/upload`, { method: "POST", body: formData });
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || `Erro ${res.status}`);
    }

    // Salva o summary e limpa o chat ao carregar um novo arquivo
    currentSummary = data.summary;
    chatHistory = [];
    document.getElementById("chat-messages").innerHTML = "";

    renderResults(data);
    showSection("results");
  } catch (err) {
    showError(err.message || "Falha na comunicação com o servidor.");
  }
}


// =============================================================================
// Renderização dos resultados
// =============================================================================

/**
 * Preenche a seção de resultados com o nome do arquivo, metadata,
 * insights da IA, tabela de estatísticas e gráficos interativos.
 */
function renderResults(data) {
  document.getElementById("file-name").textContent = data.filename;

  const isText = data.summary.kind === "text";
  const fileType = data.summary.file_type || "";

  if (isText) {
    // Modo texto (PDF/HTML/TXT sem tabelas)
    document.getElementById("file-meta").textContent =
      `${fileType} · ${data.summary.word_count.toLocaleString("pt-BR")} palavras · ${data.summary.line_count.toLocaleString("pt-BR")} linhas`;
    renderTextKPIs(data.summary);
  } else {
    // Modo tabela (CSV/Excel/PDF com tabelas/etc)
    const typeLabel = fileType ? `${fileType} · ` : "";
    document.getElementById("file-meta").textContent =
      `${typeLabel}${data.summary.rows.toLocaleString("pt-BR")} linhas · ${data.summary.columns} colunas`;
    renderTableKPIs(data.summary);
  }

  // Exibe o texto de insights gerado pela IA
  const insightsEl = document.getElementById("insights-text");
  insightsEl.textContent = data.insights || "Nenhum insight disponível.";

  // Tabela de estatísticas e seção de gráficos só fazem sentido no modo tabela
  const summaryDetails = document.querySelector(".summary-details");
  const chartsGrid     = document.getElementById("charts-grid");
  if (isText) {
    summaryDetails.classList.add("hidden");
    chartsGrid.classList.add("hidden");
    chartsGrid.innerHTML = "";
    return;
  }
  summaryDetails.classList.remove("hidden");
  chartsGrid.classList.remove("hidden");

  renderSummaryTable(data.summary);

  // Renderiza cada gráfico Plotly em seu próprio card
  const grid = document.getElementById("charts-grid");
  grid.innerHTML = "";
  data.charts.forEach((chart, i) => {
    const card = document.createElement("div");
    card.className = "chart-card";

    const title = document.createElement("h4");
    title.textContent = chart.title;

    const plotDiv = document.createElement("div");
    plotDiv.id = `chart-${i}`;

    card.appendChild(title);
    card.appendChild(plotDiv);
    grid.appendChild(card);

    // Mescla o layout vindo do backend, garantindo altura fixa, autosize e
    // removendo qualquer título interno (o card já tem um <h4> próprio —
    // mantê-lo aqui causaria sobreposição visual com o cabeçalho).
    Plotly.newPlot(
      plotDiv,
      chart.data.data,
      {
        ...chart.data.layout,
        title: undefined,
        autosize: true,
        height: 340,
      },
      { responsive: true, displayModeBar: false }
    );
  });
}

/**
 * Atualiza os 4 KPI cards com os números-chave de um dataset tabular.
 * Também ajusta os rótulos para o contexto de tabela.
 */
function renderTableKPIs(summary) {
  setKPI("kpi-rows",    summary.rows.toLocaleString("pt-BR"),    "Linhas");
  setKPI("kpi-cols",    summary.columns,                         "Colunas");
  setKPI("kpi-numeric", summary.numeric_columns.length,          "Numéricas");
  setKPI("kpi-nulls",   Object.keys(summary.null_counts || {}).length, "Com nulos");
}

/**
 * Atualiza os 4 KPI cards para um arquivo de texto (PDF/HTML/TXT).
 * Mostra contagens de palavras, linhas, caracteres e tipo do arquivo.
 */
function renderTextKPIs(summary) {
  setKPI("kpi-rows",    summary.word_count.toLocaleString("pt-BR"), "Palavras");
  setKPI("kpi-cols",    summary.line_count.toLocaleString("pt-BR"), "Linhas");
  setKPI("kpi-numeric", summary.char_count.toLocaleString("pt-BR"), "Caracteres");
  setKPI("kpi-nulls",   summary.file_type || "—",                   "Tipo");
}

/** Atualiza o valor e o rótulo de um KPI card pelo id. */
function setKPI(valueId, value, label) {
  const valEl = document.getElementById(valueId);
  valEl.textContent = value;
  // O <label> é o irmão imediato do <span class="kpi-value">
  const labelEl = valEl.nextElementSibling;
  if (labelEl) labelEl.textContent = label;
}

// Tradução dos rótulos estatísticos do pandas describe() para pt-BR
const STAT_LABELS = {
  "count": "Contagem",
  "mean":  "Média",
  "std":   "Desvio padrão",
  "min":   "Mínimo",
  "25%":   "1º quartil (25%)",
  "50%":   "Mediana (50%)",
  "75%":   "3º quartil (75%)",
  "max":   "Máximo",
};

/**
 * Constrói a tabela HTML de estatísticas descritivas (Contagem, Média, Desvio padrão, ...).
 * Usa o objeto describe do summary, onde cada chave é uma coluna numérica.
 */
function renderSummaryTable(summary) {
  const container = document.getElementById("summary-table");
  if (!summary.describe || Object.keys(summary.describe).length === 0) {
    container.innerHTML = "<p style='color:var(--muted);font-size:0.85rem'>Sem colunas numéricas para resumo.</p>";
    return;
  }

  const stats = Object.keys(Object.values(summary.describe)[0]); // ex: ["count","mean","std",...]
  const cols  = Object.keys(summary.describe);                    // nomes das colunas numéricas

  let html = "<table><thead><tr><th>Estatística</th>";
  cols.forEach(c => html += `<th>${c}</th>`);
  html += "</tr></thead><tbody>";

  stats.forEach(stat => {
    const label = STAT_LABELS[stat] || stat;
    html += `<tr><td><strong>${label}</strong></td>`;
    cols.forEach(col => {
      const val = summary.describe[col][stat];
      // "Contagem" deve aparecer como inteiro; demais com até 4 casas decimais.
      // null/undefined vira "—"
      if (val === null || val === undefined) {
        html += `<td>—</td>`;
      } else if (stat === "count") {
        html += `<td>${Number(val).toLocaleString("pt-BR", { maximumFractionDigits: 0 })}</td>`;
      } else {
        html += `<td>${Number(val).toLocaleString("pt-BR", { maximumFractionDigits: 4 })}</td>`;
      }
    });
    html += "</tr>";
  });

  html += "</tbody></table>";
  container.innerHTML = html;
}


// =============================================================================
// Controle de estado da UI
// =============================================================================

/**
 * Exibe apenas a seção indicada e esconde as demais.
 * Seções: "upload" | "loading" | "error" | "results"
 */
function showSection(name) {
  uploadSec.classList.add("hidden");
  loadingSec.classList.add("hidden");
  errorSec.classList.add("hidden");
  resultsSec.classList.add("hidden");

  if (name === "upload")   uploadSec.classList.remove("hidden");
  if (name === "loading")  loadingSec.classList.remove("hidden");
  if (name === "error")    errorSec.classList.remove("hidden");
  if (name === "results")  resultsSec.classList.remove("hidden");
}

function showError(msg) {
  document.getElementById("error-message").textContent = msg;
  showSection("error");
}

/** Reseta o estado global e volta para a tela de upload. */
function resetUI() {
  fileInput.value = "";
  document.getElementById("charts-grid").innerHTML = "";
  currentSummary = null;
  chatHistory = [];
  showSection("upload");
}


// =============================================================================
// Chat com IA sobre os dados
// =============================================================================

// Permite enviar a mensagem pressionando Enter (Shift+Enter não envia)
document.getElementById("chat-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendChatMessage();
  }
});

/**
 * Envia a pergunta do usuário ao backend junto com o summary do arquivo
 * e o histórico da conversa para manter o contexto entre mensagens.
 *
 * O backend é stateless: o summary e o histórico são enviados a cada requisição
 * porque o servidor não armazena estado de sessão.
 */
async function sendChatMessage() {
  const input = document.getElementById("chat-input");
  const question = input.value.trim();
  if (!question || !currentSummary) return;

  const sendBtn = document.getElementById("chat-send-btn");
  input.value = "";
  sendBtn.disabled = true;

  appendBubble("user", question);
  const thinkingEl = appendBubble("thinking", "Pensando…"); // indicador visual temporário

  try {
    const res = await fetch(`${API_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, summary: currentSummary, history: chatHistory }),
    });
    const data = await res.json();

    thinkingEl.remove(); // remove o "Pensando…" antes de exibir a resposta

    if (!res.ok) {
      appendBubble("assistant", `Erro: ${data.detail || res.status}`);
      return;
    }

    appendBubble("assistant", data.answer);

    // Atualiza o histórico local para manter o contexto nas próximas mensagens
    chatHistory.push({ role: "user",      content: question     });
    chatHistory.push({ role: "assistant", content: data.answer  });

    // Limita a 20 mensagens (10 trocas) para evitar prompts muito longos e caros
    if (chatHistory.length > 20) chatHistory = chatHistory.slice(-20);

  } catch (err) {
    thinkingEl.remove();
    appendBubble("assistant", `Erro de conexão: ${err.message}`);
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

/**
 * Cria e adiciona uma bolha de mensagem ao chat.
 * role: "user" (direita, roxo) | "assistant" (esquerda, cinza) | "thinking" (itálico)
 * Retorna o elemento criado para que o chamador possa removê-lo (ex: "Pensando…").
 */
function appendBubble(role, text) {
  const messages = document.getElementById("chat-messages");
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${role}`;
  bubble.textContent = text;
  messages.appendChild(bubble);
  messages.scrollTop = messages.scrollHeight; // rola para a última mensagem automaticamente
  return bubble;
}
