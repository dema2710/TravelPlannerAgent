"use strict";

const els = {
  form: document.getElementById("planner-form"),
  destination: document.getElementById("destination"),
  departure: document.getElementById("departure_city"),
  startDate: document.getElementById("start_date"),
  endDate: document.getElementById("end_date"),
  budget: document.getElementById("budget"),
  currency: document.getElementById("currency"),
  pace: document.getElementById("pace"),
  interests: document.getElementById("interests"),
  dietary: document.getElementById("dietary"),
  modeNote: document.getElementById("mode-note"),
  generateButton: document.getElementById("generate-button"),
  buttonLabel: document.querySelector("#generate-button .button-label"),
  formStatus: document.getElementById("form-status"),
  errorPanel: document.getElementById("error-panel"),
  errorMessage: document.getElementById("error-message"),
  errorDetails: document.getElementById("error-details"),
  sideIdle: document.getElementById("side-idle"),
  sideLoading: document.getElementById("side-loading"),
  loadingCopy: document.getElementById("loading-copy"),
  results: document.getElementById("results"),
  resultTitle: document.getElementById("result-title"),
  resultSubtitle: document.getElementById("result-subtitle"),
  resultBadges: document.getElementById("result-badges"),
  totalCost: document.getElementById("total-cost"),
  budgetStatus: document.getElementById("budget-status"),
  budgetTotal: document.getElementById("budget-total"),
  budgetRemaining: document.getElementById("budget-remaining"),
  budgetFill: document.getElementById("budget-fill"),
  budgetPercent: document.getElementById("budget-percent"),
  budgetBreakdown: document.getElementById("budget-breakdown"),
  flightCard: document.getElementById("flight-card"),
  stayCard: document.getElementById("stay-card"),
  weather: document.getElementById("weather"),
  itinerary: document.getElementById("itinerary"),
  itineraryCount: document.getElementById("itinerary-count"),
  recommendations: document.getElementById("recommendations"),
  notes: document.getElementById("practical-notes"),
  traceLine: document.getElementById("trace-line"),
  disclaimer: document.getElementById("result-disclaimer"),
};

let config = null;
let isGenerating = false;
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

class APIError extends Error {
  constructor(message, details = [], traceFile = null) {
    super(message);
    this.name = "APIError";
    this.details = details;
    this.traceFile = traceFile;
  }
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[character]));
}

function formatMoney(value, currency) {
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(Number(value));
  } catch {
    return `${Number(value).toFixed(2)} ${currency}`;
  }
}

function formatDate(isoDate, options = {}) {
  const date = new Date(`${isoDate}T12:00:00`);
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    ...options,
  }).format(date);
}

function formatDay(isoDate) {
  return new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  }).format(new Date(`${isoDate}T12:00:00`));
}

function displayLabel(value) {
  if (value === "gluten_free") return "Gluten-free";
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function toISODate(date) {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
}

function setOptions(select, values, selected) {
  select.innerHTML = values
    .map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(displayLabel(value))}</option>`)
    .join("");
  if (selected && values.includes(selected)) {
    select.value = selected;
  }
}

function setChips(container, values, name, selectedValues = []) {
  const selected = new Set(selectedValues);
  container.innerHTML = values
    .map((value) => `
      <label class="chip">
        <input type="checkbox" name="${name}" value="${escapeHtml(value)}"${selected.has(value) ? " checked" : ""}>
        <span>${escapeHtml(displayLabel(value))}</span>
      </label>
    `)
    .join("");
}

function setDefaultDates() {
  const today = new Date();
  const start = new Date(today);
  start.setDate(today.getDate() + 30);
  const end = new Date(start);
  end.setDate(start.getDate() + 2);
  els.startDate.min = toISODate(today);
  els.startDate.value = toISODate(start);
  els.endDate.min = toISODate(start);
  els.endDate.value = toISODate(end);
}

function getMode() {
  return els.form.querySelector('input[name="mode"]:checked')?.value || "offline";
}

function updateModeNote() {
  if (!config) return;
  if (config.live_api_available) {
    els.modeNote.textContent = getMode() === "live"
      ? "Live mode sends this request to DeepSeek and may use API credits."
      : "Offline mode uses the deterministic scripted model. No API credits are used.";
  } else {
    els.modeNote.textContent = "Live mode is unavailable until a DeepSeek API key is configured. Offline mode is ready.";
  }
}

async function requestJSON(url, options = {}) {
  let response;
  try {
    response = await fetch(url, {
      ...options,
      headers: {
        Accept: "application/json",
        ...(options.headers || {}),
      },
    });
  } catch {
    throw new APIError("Could not reach the local web server. Is it still running?");
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    // The status code still gives the user a useful fallback message.
  }

  if (!response.ok) {
    const error = payload?.error;
    throw new APIError(
      error?.message || `The request failed with HTTP ${response.status}.`,
      error?.details || [],
      error?.trace_file || null,
    );
  }

  return payload;
}

async function loadConfig() {
  try {
    config = await requestJSON("/api/config");
    setOptions(els.destination, config.destinations, "Paris");
    setOptions(els.departure, config.departure_cities, config.default_departure_city);
    setOptions(els.currency, config.currencies, "EUR");
    setOptions(els.pace, config.paces, "moderate");
    setChips(els.interests, config.interests, "interests", ["architecture", "museums", "history"]);
    setChips(els.dietary, config.dietary_preferences, "dietary");
    setDefaultDates();

    const liveInput = els.form.querySelector('input[name="mode"][value="live"]');
    liveInput.disabled = !config.live_api_available;
    if (!config.live_api_available) {
      els.form.querySelector('input[name="mode"][value="offline"]').checked = true;
    }
    updateModeNote();
    els.generateButton.disabled = false;
    els.formStatus.textContent = "Ready when you are.";
  } catch (error) {
    els.generateButton.disabled = true;
    els.buttonLabel.textContent = "Planner unavailable";
    els.formStatus.textContent = "Planner options could not be loaded.";
    showError(error);
  }
}

function collectRequest() {
  const interests = [...els.form.querySelectorAll('input[name="interests"]:checked')]
    .map((input) => input.value);
  const dietary = [...els.form.querySelectorAll('input[name="dietary"]:checked')]
    .map((input) => input.value);
  const budget = Number(els.budget.value);
  const mode = getMode();

  if (!els.destination.value || !els.departure.value) {
    throw new APIError("Choose a destination and a departure city.");
  }
  if (els.destination.value === els.departure.value) {
    throw new APIError("Departure city must differ from the destination.");
  }
  if (!els.startDate.value || !els.endDate.value || els.endDate.value <= els.startDate.value) {
    throw new APIError("Return date must be after the departure date.");
  }
  if (!Number.isFinite(budget) || budget <= 0) {
    throw new APIError("Enter a total budget greater than zero.");
  }
  if (!interests.length) {
    throw new APIError("Choose at least one interest.");
  }
  if (mode === "live" && !config?.live_api_available) {
    throw new APIError("Live mode is not configured on this server.");
  }

  return {
    mode,
    request: {
      destination: els.destination.value,
      departure_city: els.departure.value,
      start_date: els.startDate.value,
      end_date: els.endDate.value,
      budget,
      currency: els.currency.value,
      pace: els.pace.value,
      interests,
      dietary_restrictions: dietary,
    },
  };
}

function setGenerationEnabled(enabled) {
  isGenerating = !enabled;
  els.generateButton.disabled = !enabled;
  els.generateButton.classList.toggle("is-loading", !enabled);
  els.generateButton.setAttribute("aria-busy", String(!enabled));
  els.buttonLabel.textContent = enabled ? "Generate itinerary" : "Planning your trip...";
  if (!enabled) {
    els.sideIdle.hidden = true;
    els.sideLoading.hidden = false;
    els.loadingCopy.textContent = getMode() === "live"
      ? "DeepSeek is selecting tools, checking the budget and shaping the days."
      : "Checking flights, stays, weather and local highlights.";
    els.formStatus.textContent = "The agent is working on your request.";
  } else {
    els.sideLoading.hidden = true;
    els.sideIdle.hidden = false;
    els.formStatus.textContent = "";
  }
}

function hideError() {
  els.errorPanel.hidden = true;
  els.errorMessage.textContent = "";
  els.errorDetails.innerHTML = "";
}

function showError(error) {
  const details = [...(error.details || [])];
  if (error.traceFile) {
    details.push(`Trace: ${error.traceFile}`);
  }
  els.errorMessage.textContent = error.message || "Something went wrong.";
  els.errorDetails.innerHTML = details
    .map((detail) => `<li>${escapeHtml(detail)}</li>`)
    .join("");
  els.errorPanel.hidden = false;
  els.errorPanel.setAttribute("tabindex", "-1");
  els.errorPanel.focus({ preventScroll: true });
  els.formStatus.textContent = "";
}

function weatherIcon(condition) {
  const normalized = condition.toLowerCase();
  if (normalized.includes("rain") || normalized.includes("shower")) return "🌧️";
  if (normalized.includes("cloud")) return "☁️";
  if (normalized.includes("sun") || normalized.includes("clear")) return "☀️";
  return "🌤️";
}

function renderBudget(plan) {
  const budget = plan.budget_breakdown;
  const currency = budget.currency;
  const percent = Math.min(100, Math.max(0, (budget.total_estimated_cost / budget.budget) * 100));
  const overBudget = !budget.budget_respected;

  els.totalCost.textContent = formatMoney(budget.total_estimated_cost, currency);
  els.totalCost.classList.toggle("is-over", overBudget);
  els.budgetTotal.textContent = formatMoney(budget.budget, currency);
  els.budgetRemaining.textContent = formatMoney(budget.remaining_budget, currency);
  els.budgetRemaining.classList.toggle("is-over", overBudget);
  els.budgetStatus.textContent = overBudget
    ? `This plan is over budget by ${formatMoney(Math.abs(budget.remaining_budget), currency)}.`
    : `The plan stays within budget with ${formatMoney(budget.remaining_budget, currency)} to spare.`;
  els.budgetFill.style.width = `${percent}%`;
  els.budgetFill.classList.toggle("is-over", overBudget);
  els.budgetPercent.textContent = `${Math.round(percent)}% of budget`;

  const categories = [
    ["Flights", budget.flights],
    ["Accommodation", budget.accommodation],
    ["Food", budget.food],
    ["Activities", budget.activities],
    ["Local transport", budget.local_transportation],
  ];
  els.budgetBreakdown.innerHTML = categories
    .map(([label, value]) => `
      <div class="breakdown-item">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(formatMoney(value, currency))}</strong>
      </div>
    `)
    .join("");
}

function renderFlight(flight, currency) {
  els.flightCard.innerHTML = `
    <div class="card-topline"><span>Flight · simulated</span><span class="card-price">${escapeHtml(formatMoney(flight.price, currency))}</span></div>
    <h3>${escapeHtml(flight.airline)}</h3>
    <p class="card-subtitle">Round trip for one traveller · ${flight.stops === 0 ? "Direct" : `${flight.stops} stop${flight.stops === 1 ? "" : "s"}`}</p>
    <div class="route">
      <span>${escapeHtml(flight.origin_city)}</span>
      <span class="route-dash" aria-hidden="true"></span>
      <span>${escapeHtml(flight.destination_city)}</span>
    </div>
    <div class="time-grid">
      <div><small>Outbound</small><strong>${escapeHtml(flight.departure_date)} · ${escapeHtml(flight.outbound_departure_time)}–${escapeHtml(flight.outbound_arrival_time)}</strong></div>
      <div><small>Return</small><strong>${escapeHtml(flight.return_date)} · ${escapeHtml(flight.return_departure_time)}–${escapeHtml(flight.return_arrival_time)}</strong></div>
    </div>
  `;
}

function renderStay(hotel, currency) {
  els.stayCard.innerHTML = `
    <div class="card-topline"><span>Stay · simulated</span><span class="card-price">${escapeHtml(formatMoney(hotel.total_price, currency))}</span></div>
    <h3>${escapeHtml(hotel.name)}</h3>
    <p class="card-subtitle">${escapeHtml(hotel.location)} · ${escapeHtml(hotel.category)}</p>
    <div class="hotel-detail">
      <div><small>Rating</small><strong>${Number(hotel.rating).toFixed(1)} / 5</strong></div>
      <div><small>Nightly</small><strong>${escapeHtml(formatMoney(hotel.price_per_night, currency))}</strong></div>
      <div><small>Nights</small><strong>${escapeHtml(hotel.nights)}</strong></div>
    </div>
  `;
}

function renderWeather(weather) {
  els.weather.innerHTML = weather
    .map((day) => `
      <article class="weather-card">
        <div class="weather-icon" aria-hidden="true">${weatherIcon(day.condition)}</div>
        <strong>${escapeHtml(day.max_temp_c)}° / ${escapeHtml(day.min_temp_c)}°</strong>
        <p class="weather-condition">${escapeHtml(day.condition)}</p>
        <span class="weather-meta">${escapeHtml(formatDay(day.date))} · ${escapeHtml(day.precipitation_probability)}% rain</span>
      </article>
    `)
    .join("");
}

function renderActivity(activity, currency) {
  return `
    <li class="activity">
      <span class="activity-time">${escapeHtml(activity.start_time)}–${escapeHtml(activity.end_time)}</span>
      <div class="activity-body">
        <strong>${escapeHtml(activity.name)}</strong>
        <p>${escapeHtml(activity.description)}</p>
        ${activity.location ? `<span class="activity-location">${escapeHtml(activity.location)}</span>` : ""}
      </div>
      <span class="activity-cost">${escapeHtml(formatMoney(activity.estimated_cost, currency))}</span>
    </li>
  `;
}

function renderItinerary(days, currency) {
  els.itineraryCount.textContent = `${days.length} day${days.length === 1 ? "" : "s"}`;
  els.itinerary.innerHTML = days
    .map((day) => `
      <article class="day-card">
        <div class="day-marker">
          <span>Day ${escapeHtml(day.day_number)}</span>
          <strong>${escapeHtml(formatDay(day.date))}</strong>
          <small>${escapeHtml(day.theme)}</small>
        </div>
        <div>
          ${day.activities.length
            ? `<ul class="activity-list">${day.activities.map((activity) => renderActivity(activity, currency)).join("")}</ul>`
            : `<p class="empty-day">No paid activities scheduled. Keep this day open for wandering.</p>`}
          <div class="day-foot">
            <span>Food <strong>${escapeHtml(formatMoney(day.daily_food_estimate, currency))}</strong></span>
            <span>Local transport <strong>${escapeHtml(formatMoney(day.local_transport_estimate, currency))}</strong></span>
            <span>Day total <strong>${escapeHtml(formatMoney(day.daily_total, currency))}</strong></span>
          </div>
        </div>
      </article>
    `)
    .join("");
}

function renderList(element, items) {
  element.innerHTML = items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
}

function renderPlan(response) {
  const { plan } = response;
  const request = plan.request;
  const currency = request.currency;
  const budget = plan.budget_breakdown;
  const modeLabel = response.mode === "live" ? "DeepSeek live" : "Offline demo";

  els.resultTitle.textContent = `${request.destination}, in your own rhythm`;
  els.resultSubtitle.textContent = `${formatDate(request.start_date)} – ${formatDate(request.end_date)} · ${plan.daily_itinerary.length} days from ${request.departure_city} · ${displayLabel(request.pace)} pace · one traveller`;
  els.resultBadges.innerHTML = [
    modeLabel,
    budget.budget_respected ? "Within budget" : "Over budget",
    request.currency,
  ].map((label) => `<span>${escapeHtml(label)}</span>`).join("");

  renderBudget(plan);
  renderFlight(plan.selected_flight, currency);
  renderStay(plan.selected_accommodation, currency);
  renderWeather(plan.weather);
  renderItinerary(plan.daily_itinerary, currency);
  renderList(els.recommendations, plan.recommendations);
  renderList(els.notes, plan.practical_notes);
  els.traceLine.innerHTML = `Execution trace: <code>${escapeHtml(response.trace_file)}</code> · run ${escapeHtml(response.run_id.slice(0, 8))} · ${escapeHtml(response.provider)} / ${escapeHtml(response.model)}`;
  els.disclaimer.textContent = plan.data_disclaimer;

  els.results.hidden = false;
  window.setTimeout(() => {
    els.results.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
  }, 80);
}

async function handleSubmit(event) {
  event.preventDefault();
  if (isGenerating) return;
  hideError();

  let payload;
  try {
    payload = collectRequest();
  } catch (error) {
    showError(error);
    return;
  }

  els.results.hidden = true;
  setGenerationEnabled(false);
  let completed = false;
  try {
    const response = await requestJSON("/api/itineraries", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    renderPlan(response);
    completed = true;
  } catch (error) {
    showError(error instanceof APIError ? error : new APIError("The request could not be completed."));
  } finally {
    setGenerationEnabled(true);
    if (completed) {
      els.formStatus.textContent = "Itinerary ready.";
    }
  }
}

els.form.addEventListener("submit", handleSubmit);
els.form.querySelectorAll('input[name="mode"]').forEach((input) => {
  input.addEventListener("change", updateModeNote);
});
els.startDate.addEventListener("change", () => {
  els.endDate.min = els.startDate.value;
  if (els.endDate.value && els.endDate.value <= els.startDate.value) {
    const nextDay = new Date(`${els.startDate.value}T12:00:00`);
    nextDay.setDate(nextDay.getDate() + 1);
    els.endDate.value = toISODate(nextDay);
  }
});

loadConfig();
