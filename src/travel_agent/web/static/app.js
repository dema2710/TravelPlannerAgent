"use strict";

const els = {
  form: document.getElementById("planner-form"),
  destination: document.getElementById("destination"),
  departure: document.getElementById("departure_city"),
  startDate: document.getElementById("start_date"),
  endDate: document.getElementById("end_date"),
  budget: document.getElementById("budget"),
  budgetPrefix: document.getElementById("budget-prefix"),
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
  navResults: document.getElementById("nav-results"),
  headerStatus: document.getElementById("header-status"),
  headerStatusText: document.getElementById("header-status-text"),
  sideIdle: document.getElementById("side-idle"),
  sideLoading: document.getElementById("side-loading"),
  loadingCopy: document.getElementById("loading-copy"),
  summaryMode: document.getElementById("summary-mode"),
  sumRoute: document.getElementById("sum-route"),
  sumDates: document.getElementById("sum-dates"),
  sumDuration: document.getElementById("sum-duration"),
  sumBudget: document.getElementById("sum-budget"),
  sumPace: document.getElementById("sum-pace"),
  sumInterests: document.getElementById("sum-interests"),
  sumDietary: document.getElementById("sum-dietary"),
  summaryNote: document.getElementById("summary-note"),
  results: document.getElementById("results"),
  resultEyebrow: document.getElementById("result-eyebrow"),
  resultTitle: document.getElementById("result-title"),
  resultSubtitle: document.getElementById("result-subtitle"),
  resultBadges: document.getElementById("result-badges"),
  sourceBanner: document.getElementById("source-banner"),
  sourceMark: document.getElementById("source-mark"),
  sourceTitle: document.getElementById("source-title"),
  sourceCopy: document.getElementById("source-copy"),
  resultSummary: document.getElementById("result-summary"),
  overviewIncludes: document.getElementById("overview-includes"),
  overviewFacts: document.getElementById("overview-facts"),
  overviewMode: document.getElementById("overview-mode"),
  totalCost: document.getElementById("total-cost"),
  budgetFlag: document.getElementById("budget-flag"),
  budgetStatus: document.getElementById("budget-status"),
  budgetTotal: document.getElementById("budget-total"),
  budgetRemaining: document.getElementById("budget-remaining"),
  budgetFill: document.getElementById("budget-fill"),
  budgetTrack: document.getElementById("budget-track"),
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

const CURRENCY_SYMBOLS = {
  EUR: "€",
  USD: "$",
  GBP: "£",
  CZK: "Kč",
  CHF: "CHF",
};

const ICONS = {
  plane: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21.5 3.5 2.8 10.9l6.4 2.1 2.2 6.4 9.9-15.9Z"/><path d="M9.2 13 21.5 3.5"/></svg>`,
  bed: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 19V8"/><path d="M3 16h18v3"/><path d="M21 16v-3a3 3 0 0 0-3-3h-7v6"/><circle cx="7" cy="11" r="2"/></svg>`,
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

function formatShortDate(isoDate) {
  const date = new Date(`${isoDate}T12:00:00`);
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
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
  if (!value) return "";
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

function tripLength(startValue, endValue) {
  if (!startValue || !endValue) return null;
  const start = new Date(`${startValue}T12:00:00`);
  const end = new Date(`${endValue}T12:00:00`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end <= start) {
    return null;
  }
  return Math.round((end - start) / 86400000);
}

function selectedValues(name) {
  return [...els.form.querySelectorAll(`input[name="${name}"]:checked`)]
    .map((input) => input.value);
}

function setOptions(select, values, selected) {
  select.innerHTML = values
    .map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(displayLabel(value))}</option>`)
    .join("");
  if (selected && values.includes(selected)) {
    select.value = selected;
  }
}

function setChips(container, values, name, selectedValuesList = []) {
  const selected = new Set(selectedValuesList);
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

function updateCurrencyPrefix() {
  const currency = els.currency.value || "EUR";
  els.budgetPrefix.textContent = CURRENCY_SYMBOLS[currency] || currency;
}

function updateModeNote() {
  if (!config) return;
  const live = getMode() === "live";

  if (config.live_api_available) {
    els.modeNote.textContent = live
      ? "Live mode sends this request to DeepSeek and may use API credits."
      : "Offline mode uses the deterministic scripted model. No API credits are used.";
  } else {
    els.modeNote.textContent = "Live mode is unavailable until a DeepSeek API key is configured. Offline mode is ready.";
  }

  els.summaryMode.textContent = live ? "Live" : "Offline";
  els.summaryMode.classList.toggle("is-live", live);
  els.summaryNote.textContent = live
    ? "DeepSeek composes the plan; travel data stays simulated."
    : "Deterministic scripted plan using simulated travel data.";
}

function updateTripSummary() {
  if (!config) return;

  const destination = els.destination.value || "Destination";
  const departure = els.departure.value || "Departure";
  const nights = tripLength(els.startDate.value, els.endDate.value);

  els.sumRoute.textContent = `${departure} → ${destination}`;

  if (nights === null) {
    els.sumDates.textContent = "Choose valid dates";
    els.sumDuration.textContent = "—";
  } else {
    els.sumDates.textContent = `${formatShortDate(els.startDate.value)} – ${formatDate(els.endDate.value)}`;
    els.sumDuration.textContent = `${nights + 1} days · ${nights} night${nights === 1 ? "" : "s"}`;
  }

  const currency = els.currency.value || "EUR";
  els.sumBudget.textContent = formatMoney(Number(els.budget.value) || 0, currency);
  els.sumPace.textContent = displayLabel(els.pace.value) || "—";

  const interests = selectedValues("interests");
  els.sumInterests.textContent = interests.length
    ? interests.map(displayLabel).join(", ")
    : "Choose at least one";

  const dietary = selectedValues("dietary");
  els.sumDietary.textContent = dietary.length
    ? dietary.map(displayLabel).join(", ")
    : "No restrictions";

  updateCurrencyPrefix();
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

    els.headerStatusText.textContent = config.live_api_available
      ? "Live mode available"
      : "Offline demo ready";
    els.headerStatus.classList.toggle("is-live", config.live_api_available);
    els.headerStatus.classList.remove("is-error");

    updateModeNote();
    updateTripSummary();
    els.generateButton.disabled = false;
    els.formStatus.textContent = "Ready when you are.";
  } catch (error) {
    els.generateButton.disabled = true;
    els.buttonLabel.textContent = "Planner unavailable";
    els.formStatus.textContent = "Planner options could not be loaded.";
    els.headerStatusText.textContent = "Server unavailable";
    els.headerStatus.classList.add("is-error");
    showError(error);
  }
}

function collectRequest() {
  const interests = selectedValues("interests");
  const dietary = selectedValues("dietary");
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
    els.navResults.hidden = true;
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

function renderSource(mode) {
  const live = mode === "live";
  els.sourceBanner.classList.toggle("is-live", live);
  els.sourceBanner.classList.toggle("is-offline", !live);
  els.sourceMark.textContent = live ? "AI" : "S";
  els.sourceTitle.textContent = live
    ? "DeepSeek live · AI-composed itinerary"
    : "Offline demo · scripted itinerary";
  els.sourceCopy.textContent = live
    ? "DeepSeek selected and sequenced the agent tools, then composed this plan. Flights, stays, weather, prices and opening hours remain simulated demo data."
    : "A deterministic scripted model assembled this plan from simulated demo data. No API calls were made and nothing here is bookable.";
}

function renderOverview(plan, mode) {
  const request = plan.request;
  const nights = plan.daily_itinerary.length - 1;
  const facts = [
    ["Route", `${request.departure_city} → ${request.destination}`],
    ["Dates", `${formatShortDate(request.start_date)} – ${formatDate(request.end_date)}`],
    ["Duration", `${plan.daily_itinerary.length} days · ${nights} night${nights === 1 ? "" : "s"}`],
    ["Pace", displayLabel(request.pace)],
    ["Interests", request.interests.map(displayLabel).join(", ")],
    ["Dietary", request.dietary_restrictions.length
      ? request.dietary_restrictions.map(displayLabel).join(", ")
      : "No restrictions"],
  ];

  const activityCount = plan.daily_itinerary.reduce(
    (sum, day) => sum + day.activities.length,
    0,
  );
  const includes = [
    `Round-trip flight with ${plan.selected_flight.airline}`,
    `${nights} night${nights === 1 ? "" : "s"} at ${plan.selected_accommodation.name}`,
    `${activityCount} scheduled activit${activityCount === 1 ? "y" : "ies"} across ${plan.daily_itinerary.length} days`,
  ];

  els.resultSummary.textContent = plan.summary;
  els.overviewIncludes.innerHTML = includes
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
  els.overviewMode.textContent = mode === "live" ? "AI-composed" : "Scripted";
  els.overviewFacts.innerHTML = facts
    .map(([label, value]) => `
      <div>
        <dt>${escapeHtml(label)}</dt>
        <dd>${escapeHtml(value)}</dd>
      </div>
    `)
    .join("");
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
  els.budgetFlag.textContent = overBudget ? "Over budget" : "Within budget";
  els.budgetFlag.classList.toggle("is-over", overBudget);
  els.budgetFill.style.width = `${percent}%`;
  els.budgetFill.classList.toggle("is-over", overBudget);
  els.budgetTrack.setAttribute("aria-valuenow", String(Math.round(percent)));
  els.budgetPercent.textContent = `${Math.round(percent)}% of budget`;

  const categories = [
    ["Flights", budget.flights],
    ["Accommodation", budget.accommodation],
    ["Food", budget.food],
    ["Activities", budget.activities],
    ["Local transport", budget.local_transportation],
  ];
  const total = budget.total_estimated_cost;

  els.budgetBreakdown.innerHTML = categories
    .map(([label, value]) => {
      const share = total > 0 ? Math.min(100, (value / total) * 100) : 0;
      return `
        <div class="breakdown-row">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(formatMoney(value, currency))}</strong>
          <span class="breakdown-bar"><i style="width:${share.toFixed(1)}%"></i></span>
        </div>
      `;
    })
    .join("");
}

function renderFlight(flight, currency) {
  const stopsLabel = flight.stops === 0
    ? "Direct"
    : `${flight.stops} stop${flight.stops === 1 ? "" : "s"}`;

  els.flightCard.innerHTML = `
    <div class="info-head">
      <span class="info-tag">${ICONS.plane} Flight · simulated</span>
      <span class="info-price">${escapeHtml(formatMoney(flight.price, currency))}</span>
    </div>
    <h3>${escapeHtml(flight.airline)}</h3>
    <p class="info-sub">Round trip for one traveller · ${escapeHtml(stopsLabel)}</p>
    <div class="flight-route">
      <div class="flight-end">
        <small>${escapeHtml(flight.outbound_departure_time)}</small>
        <strong>${escapeHtml(flight.origin_airport)}</strong>
        <span>${escapeHtml(flight.origin_city)}</span>
      </div>
      <div class="flight-line"><span>${escapeHtml(stopsLabel)}</span></div>
      <div class="flight-end is-end">
        <small>${escapeHtml(flight.outbound_arrival_time)}</small>
        <strong>${escapeHtml(flight.destination_airport)}</strong>
        <span>${escapeHtml(flight.destination_city)}</span>
      </div>
    </div>
    <div class="info-meta">
      <div>
        <span>Outbound</span>
        <strong>${escapeHtml(formatShortDate(flight.departure_date))} · ${escapeHtml(flight.outbound_departure_time)}–${escapeHtml(flight.outbound_arrival_time)}</strong>
      </div>
      <div>
        <span>Return</span>
        <strong>${escapeHtml(formatShortDate(flight.return_date))} · ${escapeHtml(flight.return_departure_time)}–${escapeHtml(flight.return_arrival_time)}</strong>
      </div>
    </div>
  `;
}

function renderStay(hotel, currency) {
  els.stayCard.innerHTML = `
    <div class="info-head">
      <span class="info-tag">${ICONS.bed} Stay · simulated</span>
      <span class="info-price">${escapeHtml(formatMoney(hotel.total_price, currency))}</span>
    </div>
    <h3>${escapeHtml(hotel.name)}</h3>
    <p class="info-sub">${escapeHtml(hotel.location)} · ${escapeHtml(hotel.category)}</p>
    <div class="stay-rating">
      <span aria-hidden="true">★</span>
      <strong>${Number(hotel.rating).toFixed(1)}</strong>
      <small>/ 5</small>
    </div>
    <div class="info-meta">
      <div><span>Check-in</span><strong>${escapeHtml(formatShortDate(hotel.check_in))}</strong></div>
      <div><span>Check-out</span><strong>${escapeHtml(formatShortDate(hotel.check_out))}</strong></div>
      <div><span>Nightly</span><strong>${escapeHtml(formatMoney(hotel.price_per_night, currency))}</strong></div>
      <div><span>Nights</span><strong>${escapeHtml(hotel.nights)}</strong></div>
    </div>
  `;
}

function renderWeather(weather) {
  els.weather.innerHTML = weather
    .map((day) => `
      <article class="weather-card">
        <div class="weather-top">
          <span class="weather-icon" aria-hidden="true">${weatherIcon(day.condition)}</span>
          <span class="weather-date">${escapeHtml(formatDay(day.date))}</span>
        </div>
        <strong>${escapeHtml(day.max_temp_c)}° <span>/ ${escapeHtml(day.min_temp_c)}°</span></strong>
        <p class="weather-condition">${escapeHtml(day.condition)}</p>
        <span class="weather-meta">${escapeHtml(day.precipitation_probability)}% chance of rain</span>
      </article>
    `)
    .join("");
}

function renderActivity(activity, currency) {
  return `
    <li class="activity">
      <span class="activity-time">
        <strong>${escapeHtml(activity.start_time)}</strong>
        <span>${escapeHtml(activity.end_time)}</span>
      </span>
      <div class="activity-body">
        <span class="activity-name">${escapeHtml(activity.name)}</span>
        <p>${escapeHtml(activity.description)}</p>
        ${activity.location ? `<span class="activity-location">${escapeHtml(activity.location)}</span>` : ""}
      </div>
      <span class="activity-cost">${escapeHtml(formatMoney(activity.estimated_cost, currency))}</span>
    </li>
  `;
}

function renderItinerary(days, currency) {
  const nights = days.length - 1;
  els.itineraryCount.textContent = `${days.length} days · ${nights} night${nights === 1 ? "" : "s"}`;

  els.itinerary.innerHTML = days
    .map((day, index) => {
      const accent = (index % 3) + 1;
      const activityTotal = day.activities.reduce(
        (sum, activity) => sum + Number(activity.estimated_cost || 0),
        0,
      );

      return `
        <article class="day-card accent-${accent}">
          <header class="day-head">
            <span class="day-badge"><small>Day</small>${String(day.day_number).padStart(2, "0")}</span>
            <div class="day-heading">
              <h4>${escapeHtml(day.theme)}</h4>
              <span>${escapeHtml(formatDay(day.date))}</span>
            </div>
            <div class="day-total">
              <span>Day total</span>
              <strong>${escapeHtml(formatMoney(day.daily_total, currency))}</strong>
            </div>
          </header>
          <div class="day-body">
            ${day.activities.length
              ? `<ul class="activity-list">${day.activities.map((activity) => renderActivity(activity, currency)).join("")}</ul>`
              : `<p class="empty-day">No paid activities scheduled. Keep this day open for wandering.</p>`}
            <div class="day-foot">
              <span>Activities <strong>${escapeHtml(formatMoney(activityTotal, currency))}</strong></span>
              <span>Food <strong>${escapeHtml(formatMoney(day.daily_food_estimate, currency))}</strong></span>
              <span>Local transport <strong>${escapeHtml(formatMoney(day.local_transport_estimate, currency))}</strong></span>
            </div>
          </div>
        </article>
      `;
    })
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

  els.resultEyebrow.textContent = response.mode === "live"
    ? "Live AI itinerary"
    : "Simulated itinerary";
  els.resultTitle.textContent = `${request.destination}, in your own rhythm`;
  els.resultSubtitle.textContent = `${formatDate(request.start_date)} – ${formatDate(request.end_date)} · ${plan.daily_itinerary.length} days from ${request.departure_city} · ${displayLabel(request.pace)} pace · one traveller`;
  els.resultBadges.innerHTML = [
    `<span class="result-badge badge-mode ${response.mode === "live" ? "is-live" : "is-offline"}">${escapeHtml(modeLabel)}</span>`,
    `<span class="result-badge ${budget.budget_respected ? "is-good" : "is-over"}">${escapeHtml(budget.budget_respected ? "Within budget" : "Over budget")}</span>`,
    `<span class="result-badge">${escapeHtml(request.currency)}</span>`,
    `<span class="result-badge">${escapeHtml(displayLabel(request.pace))} pace</span>`,
  ].join("");

  renderSource(response.mode);
  renderOverview(plan, response.mode);
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
  els.navResults.hidden = false;
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
els.form.addEventListener("input", updateTripSummary);
els.form.addEventListener("change", updateTripSummary);
els.startDate.addEventListener("change", () => {
  els.endDate.min = els.startDate.value;
  if (els.endDate.value && els.endDate.value <= els.startDate.value) {
    const nextDay = new Date(`${els.startDate.value}T12:00:00`);
    nextDay.setDate(nextDay.getDate() + 1);
    els.endDate.value = toISODate(nextDay);
  }
});

loadConfig();
