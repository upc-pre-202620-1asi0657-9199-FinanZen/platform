const state = {
  userId: "demo-user",
  currency: "PEN",
  transactions: [],
};

const categories = {
  salary: { label: "Sueldo", icon: "◎", color: "#1c9b6c" },
  sales: { label: "Ventas", icon: "◇", color: "#49b98b" },
  food: { label: "Alimentación", icon: "◉", color: "#ef9c5d" },
  transport: { label: "Transporte", icon: "◆", color: "#6287c8" },
  services: { label: "Servicios", icon: "⌁", color: "#9a78c2" },
  education: { label: "Educación", icon: "□", color: "#45a9a5" },
  entertainment: { label: "Entretenimiento", icon: "☆", color: "#e66f87" },
  other: { label: "Otros", icon: "○", color: "#9ba7a1" },
};

const elements = {
  monthPicker: document.querySelector("#monthPicker"),
  balance: document.querySelector("#balanceValue"),
  income: document.querySelector("#incomeValue"),
  expenses: document.querySelector("#expenseValue"),
  count: document.querySelector("#movementCount"),
  rows: document.querySelector("#transactionRows"),
  empty: document.querySelector("#emptyState"),
  donut: document.querySelector("#expenseDonut"),
  donutTotal: document.querySelector("#donutTotal"),
  legend: document.querySelector("#expenseLegend"),
  status: document.querySelector("#connectionStatus"),
  modal: document.querySelector("#transactionModal"),
  form: document.querySelector("#transactionForm"),
  formMessage: document.querySelector("#formMessage"),
  submitButton: document.querySelector("#submitButton"),
  sidebar: document.querySelector(".sidebar"),
};

function currentMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function localDateTimeValue() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 16);
}

function money(value, decimals = 2) {
  return new Intl.NumberFormat("es-PE", {
    style: "currency",
    currency: state.currency,
    minimumFractionDigits: decimals,
  }).format(Number(value || 0));
}

function escapeHtml(value) {
  const node = document.createElement("span");
  node.textContent = value ?? "";
  return node.innerHTML;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "X-User-Id": state.userId,
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(body.detail)
      ? body.detail.map((item) => item.msg).join(". ")
      : body.detail;
    throw new Error(detail || "No se pudo completar la operación.");
  }
  return body;
}

function setConnectionStatus(kind, message) {
  elements.status.className = `connection-status ${kind}`;
  elements.status.innerHTML = `<span></span> ${escapeHtml(message)}`;
}

function renderTransactions() {
  const selectedMonth = elements.monthPicker.value;
  const visible = state.transactions.filter((transaction) =>
    transaction.occurred_at.startsWith(selectedMonth),
  );
  elements.empty.hidden = visible.length > 0;
  elements.rows.innerHTML = visible
    .map((transaction) => {
      const category = categories[transaction.category] || categories.other;
      const isIncome = transaction.type === "income";
      const date = new Intl.DateTimeFormat("es-PE", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      }).format(new Date(transaction.occurred_at));
      return `
        <tr>
          <td>
            <div class="transaction-name">
              <span class="transaction-badge">${category.icon}</span>
              <div>
                <strong>${escapeHtml(transaction.description || category.label)}</strong>
                <small>${isIncome ? "Ingreso" : "Gasto"}</small>
              </div>
            </div>
          </td>
          <td class="muted-cell">${category.label}</td>
          <td class="muted-cell">${date}</td>
          <td class="align-right ${isIncome ? "amount-income" : "amount-expense"}">
            ${isIncome ? "+" : "−"}${money(transaction.amount)}
          </td>
        </tr>`;
    })
    .join("");
  renderExpenseChart(visible);
}

function renderExpenseChart(transactions) {
  const expenses = transactions.filter((item) => item.type === "expense");
  const totals = expenses.reduce((result, item) => {
    result[item.category] = (result[item.category] || 0) + Number(item.amount);
    return result;
  }, {});
  const entries = Object.entries(totals).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((sum, [, value]) => sum + value, 0);
  elements.donutTotal.textContent = money(total, 0);

  if (!total) {
    elements.donut.style.background = "conic-gradient(#dfe9e4 0 100%)";
    elements.legend.innerHTML = '<p class="muted-cell">Sin gastos en este periodo.</p>';
    return;
  }

  let cursor = 0;
  const segments = entries.map(([key, value]) => {
    const start = cursor;
    cursor += (value / total) * 100;
    const color = (categories[key] || categories.other).color;
    return `${color} ${start}% ${cursor}%`;
  });
  elements.donut.style.background = `conic-gradient(${segments.join(",")})`;
  elements.legend.innerHTML = entries
    .slice(0, 5)
    .map(([key, value]) => {
      const category = categories[key] || categories.other;
      return `
        <div class="legend-row">
          <span class="legend-name"><i class="legend-dot" style="background:${category.color}"></i>${category.label}</span>
          <strong>${Math.round((value / total) * 100)}%</strong>
        </div>`;
    })
    .join("");
}

async function loadDashboard() {
  setConnectionStatus("", "Actualizando información…");
  try {
    const month = elements.monthPicker.value;
    const [summary, transactions] = await Promise.all([
      api(`/api/v1/summary?month=${month}&currency=${state.currency}`),
      api("/api/v1/transactions"),
    ]);
    state.transactions = transactions;
    elements.balance.textContent = money(summary.balance);
    elements.income.textContent = money(summary.income);
    elements.expenses.textContent = money(summary.expenses);
    elements.count.textContent = summary.transaction_count;
    renderTransactions();
    setConnectionStatus("online", "Servicio conectado y datos actualizados.");
  } catch (error) {
    setConnectionStatus("error", error.message);
  }
}

function openModal() {
  elements.form.reset();
  elements.form.elements.type.value = "income";
  elements.form.elements.occurred_at.value = localDateTimeValue();
  elements.formMessage.textContent = "";
  elements.modal.hidden = false;
  setTimeout(() => elements.form.elements.amount.focus(), 20);
}

function closeModal() {
  elements.modal.hidden = true;
}

async function submitTransaction(event) {
  event.preventDefault();
  elements.formMessage.textContent = "";
  elements.submitButton.disabled = true;
  elements.submitButton.textContent = "Guardando…";
  const data = new FormData(elements.form);
  const occurredAt = new Date(data.get("occurred_at"));
  const payload = {
    account_id: data.get("account_id"),
    type: data.get("type"),
    amount: Number(data.get("amount")),
    currency: state.currency,
    category: data.get("category"),
    occurred_at: occurredAt.toISOString(),
    description: data.get("description") || null,
  };

  try {
    await api("/api/v1/transactions", {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify(payload),
    });
    closeModal();
    elements.monthPicker.value = payload.occurred_at.slice(0, 7);
    await loadDashboard();
  } catch (error) {
    elements.formMessage.textContent = error.message;
  } finally {
    elements.submitButton.disabled = false;
    elements.submitButton.textContent = "Guardar movimiento";
  }
}

elements.monthPicker.value = currentMonth();
elements.form.elements.occurred_at.value = localDateTimeValue();
document.querySelector("#openTransactionButton").addEventListener("click", openModal);
document.querySelector("#heroTransactionButton").addEventListener("click", openModal);
document.querySelector("#closeModalButton").addEventListener("click", closeModal);
document.querySelector("#cancelButton").addEventListener("click", closeModal);
document.querySelector("#refreshButton").addEventListener("click", loadDashboard);
document.querySelector("#mobileMenu").addEventListener("click", () => elements.sidebar.classList.toggle("open"));
elements.monthPicker.addEventListener("change", loadDashboard);
elements.form.addEventListener("submit", submitTransaction);
elements.modal.addEventListener("click", (event) => {
  if (event.target === elements.modal) closeModal();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !elements.modal.hidden) closeModal();
});

loadDashboard();
