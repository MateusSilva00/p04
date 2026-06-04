// ================================================================
// app.js — REST Client + SSE Consumer
// ================================================================

const API_BASE = "http://localhost:8000";

// ── Atalhos DOM ──────────────────────────────────────────────────

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const DOM = {
  // Tabs
  tabButtons: $$("[data-tab]"),

  // Loja
  formPromocao: $("#form-promocao"),
  formStatus: $("#form-status"),

  // Consumidor — Conexão
  inputClientId: $("#input-client-id"),
  btnConectar: $("#btn-conectar"),
  badgeSSE: $("#badge-sse"),

  // Consumidor — Painéis condicionais
  panelInteresses: $("#panel-interesses"),
  panelNotificacoes: $("#panel-notificacoes"),

  // Consumidor — Interesses
  inputInteresse: $("#input-interesse"),
  btnAddInteresse: $("#btn-add-interesse"),
  chipContainer: $("#chip-container"),

  // Consumidor — Promoções e Notificações
  btnRefresh: $("#btn-refresh"),
  promoList: $("#promo-list"),
  notificationPanel: $("#notification-panel"),
};

// ── Estado ────────────────────────────────────────────────────────

let sseConnection = null;
let clientId = null;
const interests = new Set();
let firstNotification = true;

// ================================================================
// TABS
// ================================================================

DOM.tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    DOM.tabButtons.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");

    $$(".tab-content").forEach((c) => c.classList.remove("active"));
    $(`#tab-${btn.dataset.tab}`).classList.add("active");
  });
});

// ================================================================
// API CLIENT
// ================================================================

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail);
  }

  return response.json();
}

const api = {
  criarPromocao: (data) =>
    apiRequest("/promocoes", { method: "POST", body: JSON.stringify(data) }),

  listarPromocoes: () =>
    apiRequest("/promocoes"),

  registrarVoto: (id, voto) =>
    apiRequest(`/promocoes/${id}/votos`, {
      method: "POST",
      body: JSON.stringify({ voto }),
    }),

  registrarInteresse: (clientId, category) =>
    apiRequest(`/clientes/${clientId}/interesses`, {
      method: "POST",
      body: JSON.stringify({ category }),
    }),

  removerInteresse: (clientId, category) =>
    apiRequest(`/clientes/${clientId}/interesses/${category}`, {
      method: "DELETE",
    }),
};

// ================================================================
// LOJA — Cadastro de Promoção
// ================================================================

DOM.formPromocao.addEventListener("submit", async (e) => {
  e.preventDefault();

  const data = {
    nome_produto: $("#input-produto").value.trim(),
    categoria: $("#input-categoria").value.trim().toLowerCase(),
    preco: parseFloat($("#input-preco").value),
    loja: $("#input-loja").value.trim(),
    loja_email: $("#input-email").value.trim(),
    signature: "placeholder", // TODO: assinar com Web Crypto API
  };

  setFormStatus("⏳ Enviando...", "var(--text-secondary)");

  try {
    const result = await api.criarPromocao(data);
    setFormStatus(
      `✅ Promoção enviada! ID: ${result.id_promocao}`,
      "var(--green-500)"
    );
    DOM.formPromocao.reset();
  } catch (err) {
    setFormStatus(`❌ Erro: ${err.message}`, "var(--red-400)");
  }
});

function setFormStatus(text, color) {
  DOM.formStatus.textContent = text;
  DOM.formStatus.style.color = color;
}

// ================================================================
// CONSUMIDOR — Conexão SSE
// ================================================================

DOM.btnConectar.addEventListener("click", connectSSE);

function connectSSE() {
  clientId = DOM.inputClientId.value.trim();
  if (!clientId) return alert("Digite um nome de usuário.");

  if (sseConnection) sseConnection.close();

  sseConnection = new EventSource(
    `${API_BASE}/clientes/${clientId}/sse`
  );

  sseConnection.onopen = () => {
    setBadge("Conectado", true);
    DOM.btnConectar.textContent = "Reconectar";
    showPostConnectPanels();
    pushNotification("Sistema", `Conectado como "${clientId}"`, "promo");
  };

  sseConnection.addEventListener("promocao_publicada", (e) => {
    const d = JSON.parse(e.data);
    pushNotification(
      "🏷️ Nova Promoção",
      `${d.nome_produto} — R$ ${d.preco.toFixed(2)} (${d.loja})`,
      "promo"
    );
    refreshPromocoes();
  });

  sseConnection.addEventListener("hot_deal", (e) => {
    const d = JSON.parse(e.data);
    pushNotification(
      "🔥 HOT DEAL",
      `${d.nome_produto || d.id_promocao} — Score: ${d.score}`,
      "hot-deal"
    );
  });

  sseConnection.onerror = () => setBadge("Desconectado", false);
}

function setBadge(text, connected) {
  DOM.badgeSSE.textContent = text;
  DOM.badgeSSE.className = connected
    ? "badge badge-connected"
    : "badge badge-disconnected";
}

function showPostConnectPanels() {
  DOM.panelInteresses.style.display = "block";
  DOM.panelNotificacoes.style.display = "block";
  DOM.panelInteresses.style.animation = "aero-fade-in 0.35s ease";
  DOM.panelNotificacoes.style.animation = "aero-fade-in 0.35s ease";
}

// ================================================================
// CONSUMIDOR — Interesses (Categorias)
// ================================================================

DOM.btnAddInteresse.addEventListener("click", addInterest);
DOM.inputInteresse.addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); addInterest(); }
});

async function addInterest() {
  const category = DOM.inputInteresse.value.trim().toLowerCase();
  if (!category) return;
  if (!clientId) return alert("Conecte-se ao SSE primeiro.");

  try {
    await api.registrarInteresse(clientId, category);
    interests.add(category);
    renderChips();
    DOM.inputInteresse.value = "";
  } catch (err) {
    alert(`Erro: ${err.message}`);
  }
}

async function removeInterest(category) {
  if (!clientId) return;

  try {
    await api.removerInteresse(clientId, category);
    interests.delete(category);
    renderChips();
  } catch (err) {
    alert(`Erro: ${err.message}`);
  }
}

function renderChips() {
  if (interests.size === 0) {
    DOM.chipContainer.innerHTML =
      '<span style="color: var(--text-secondary); font-style: italic;">Nenhuma categoria selecionada.</span>';
    return;
  }

  DOM.chipContainer.innerHTML = [...interests]
    .map((cat) => `
      <span class="chip">
        ${cat}
        <button class="chip-remove" data-category="${cat}" type="button">✕</button>
      </span>
    `)
    .join("");
}

// Event delegation para remover chips
DOM.chipContainer.addEventListener("click", (e) => {
  const btn = e.target.closest(".chip-remove");
  if (btn) removeInterest(btn.dataset.category);
});

// ================================================================
// CONSUMIDOR — Promoções Ativas
// ================================================================

DOM.btnRefresh.addEventListener("click", refreshPromocoes);

async function refreshPromocoes() {
  try {
    const promos = await api.listarPromocoes();

    if (promos.length === 0) {
      DOM.promoList.innerHTML =
        '<div class="empty-state">Nenhuma promoção disponível ainda.</div>';
      return;
    }

    DOM.promoList.innerHTML = promos
      .map((p) => `
        <div class="promo-card">
          <div class="promo-info">
            <h3>${p.nome_produto}</h3>
            <span class="promo-meta">${p.loja} · ${p.categoria}</span>
          </div>
          <span class="promo-price">R$ ${p.preco.toFixed(2)}</span>
          <div class="promo-actions">
            <button class="btn btn-success btn-sm" data-vote-id="${p.id_promocao}" data-vote="1">👍</button>
            <button class="btn btn-danger btn-sm" data-vote-id="${p.id_promocao}" data-vote="-1">👎</button>
          </div>
        </div>
      `)
      .join("");
  } catch (err) {
    DOM.promoList.innerHTML =
      `<div class="empty-state">❌ Erro: ${err.message}</div>`;
  }
}

// Event delegation para votos
DOM.promoList.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-vote-id]");
  if (!btn) return;

  const id = btn.dataset.voteId;
  const voto = parseInt(btn.dataset.vote, 10);

  try {
    await api.registrarVoto(id, voto);
    const emoji = voto > 0 ? "👍" : "👎";
    pushNotification("Voto", `${emoji} Voto registrado!`, "promo");
  } catch (err) {
    alert(`Erro ao votar: ${err.message}`);
  }
});

// ================================================================
// NOTIFICAÇÕES
// ================================================================

function pushNotification(title, message, type) {
  if (firstNotification) {
    DOM.notificationPanel.innerHTML = "";
    firstNotification = false;
  }

  const item = document.createElement("div");
  item.className = `notification-item ${type}`;
  item.innerHTML = `<strong>${title}</strong> — ${message}`;

  DOM.notificationPanel.prepend(item);

  // Limita a 50 itens
  while (DOM.notificationPanel.children.length > 50) {
    DOM.notificationPanel.lastChild.remove();
  }
}
