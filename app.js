let marketData = {};
let currentMarketKey = "";
let currentCrop = "mosambi";
let currentHorizon = 7;
let priceChart = null;

document.addEventListener("DOMContentLoaded", () => {
    loadCrops();
    fetchData();
    setupEventListeners();
});

async function loadCrops() {
    try {
        const response = await fetch("/api/crops");
        const res = await response.json();
        if (res.success && res.crops && res.crops.length > 0) {
            const selectEl = document.getElementById("crop-select");
            if (selectEl) {
                selectEl.innerHTML = "";
                res.crops.forEach(crop => {
                    const opt = document.createElement("option");
                    opt.value = crop;
                    const emoji = crop.toLowerCase().includes("mosambi") ? "🍊" : 
                                 crop.toLowerCase().includes("rice") ? "🌾" : 
                                 crop.toLowerCase().includes("tomato") ? "🍅" : 
                                 crop.toLowerCase().includes("apple") ? "🍎" : 
                                 crop.toLowerCase().includes("onion") ? "🧅" : "🌱";
                    opt.textContent = `${emoji} ${crop.charAt(0).toUpperCase() + crop.slice(1)}`;
                    selectEl.appendChild(opt);
                });
                selectEl.value = currentCrop;
            }
        }
    } catch (err) {
        console.warn("Using default crop 'mosambi':", err);
    }
}

async function fetchData() {
    try {
        // Try crop-specific predictions file first, fallback to root predictions
        let url = `predictions/${currentCrop}/all_market_forecasts.json`;
        let response = await fetch(url);
        if (!response.ok) {
            url = "predictions/all_market_forecasts.json";
            response = await fetch(url);
        }

        marketData = await response.json();
        initDashboard();
    } catch (error) {
        console.error("Error loading forecast data:", error);
        document.getElementById("market-list").innerHTML = `
            <div style="padding: 1rem; color: #ef4444; font-size: 0.9rem;">
                Failed to load prediction JSON for crop '${currentCrop}'. Please run <code>python train_future_price_models.py --crop ${currentCrop}</code>.
            </div>
        `;
    }
}

function initDashboard() {
    const keys = Object.keys(marketData);
    if (keys.length === 0) return;

    const nagpurKey = keys.find(k => k.includes("Nagpur")) || keys[0];
    currentMarketKey = nagpurKey;

    renderOverviewMetrics();
    renderMarketList();
    renderSelectedMarket(currentMarketKey);
}

function renderOverviewMetrics() {
    const keys = Object.keys(marketData);
    const totalMarkets = keys.length;
    
    let totalAcc = 0;
    let maxPrice = 0;
    let maxPriceMarket = "";

    keys.forEach(k => {
        const m = marketData[k];
        const acc = m.metrics && m.metrics["T+7d"] ? m.metrics["T+7d"].Accuracy : 80;
        totalAcc += acc;

        if (m.latest_recorded_price > maxPrice) {
            maxPrice = m.latest_recorded_price;
            maxPriceMarket = k.split("_").slice(-1)[0];
        }
    });

    const avgAcc = (totalAcc / totalMarkets).toFixed(1);

    document.getElementById("total-markets-val").textContent = totalMarkets;
    document.getElementById("avg-accuracy-val").textContent = `${avgAcc}%`;
    document.getElementById("top-market-val").textContent = `Rs. ${maxPrice.toLocaleString()} / q`;
    document.getElementById("top-market-sub").textContent = `Peak price in ${maxPriceMarket}`;
}

function renderMarketList() {
    const listEl = document.getElementById("market-list");
    listEl.innerHTML = "";

    Object.keys(marketData).forEach(key => {
        const item = marketData[key];
        const parts = key.split("_");
        const marketShort = parts[parts.length - 1];
        const stateShort = parts[0];

        const f7 = item.forecasts && item.forecasts.horizon_7d ? item.forecasts.horizon_7d[7] : null;
        const change = f7 ? (f7.predicted_price - item.latest_recorded_price) : 0;
        const changePct = item.latest_recorded_price ? ((change / item.latest_recorded_price) * 100).toFixed(1) : "0.0";
        const isUp = change >= 0;

        const el = document.createElement("div");
        el.className = `market-item ${key === currentMarketKey ? "active" : ""}`;
        el.onclick = () => selectMarket(key);

        el.innerHTML = `
            <div>
                <div class="market-name">${marketShort}</div>
                <div class="market-state">${stateShort} • <span style="color:var(--text-muted);">${item.latest_recorded_date}</span></div>
            </div>
            <div class="market-price-tag">
                <div>Rs. ${item.latest_recorded_price ? item.latest_recorded_price.toLocaleString() : 'N/A'}</div>
                <div style="font-size: 0.75rem; color: ${isUp ? '#10b981' : '#ef4444'};">
                    ${isUp ? '▲' : '▼'} ${Math.abs(changePct)}% (7d)
                </div>
            </div>
        `;

        listEl.appendChild(el);
    });
}

function selectMarket(key) {
    currentMarketKey = key;
    renderMarketList();
    renderSelectedMarket(key);
}

function renderSelectedMarket(key) {
    const data = marketData[key];
    if (!data) return;

    document.getElementById("selected-market-title").textContent = key.replace(/_/g, " ");
    document.getElementById("selected-as-of").textContent = `Last Recorded: ${data.latest_recorded_date} | Present Date: ${data.present_date}`;
    document.getElementById("current-price-display").textContent = `Rs. ${data.latest_recorded_price ? data.latest_recorded_price.toLocaleString() : 'N/A'}`;

    const gap = data.black_box_gap || {};
    const gapBanner = document.getElementById("black-box-banner");
    if (gapBanner) {
        gapBanner.innerHTML = `
            <div class="black-box-alert">
                <div class="black-box-icon">⬛</div>
                <div class="black-box-text">
                    <strong>BLACK BOX: UNREPORTED DATA GAP (${gap.start_date || 'N/A'} to ${gap.end_date || 'N/A'})</strong>
                    <div>Mandi data is not present for ${gap.gap_days || 0} days. <em>No graph line is plotted during this missing period.</em> AI forecasting resumes from Present Date (${data.present_date}).</div>
                </div>
            </div>
        `;
    }

    const m7 = data.metrics ? data.metrics["T+7d"] || {} : {};
    const m14 = data.metrics ? data.metrics["T+14d"] || {} : {};
    const m30 = data.metrics ? data.metrics["T+30d"] || {} : {};

    document.getElementById("metric-mae-7").textContent = `Rs. ${m7.MAE || 'N/A'}`;
    document.getElementById("metric-acc-7").textContent = `${m7.Accuracy || 'N/A'}%`;
    document.getElementById("metric-r2-7").textContent = `${m7.R2 || 'N/A'}`;

    document.getElementById("metric-mae-14").textContent = `Rs. ${m14.MAE || 'N/A'}`;
    document.getElementById("metric-acc-14").textContent = `${m14.Accuracy || 'N/A'}%`;

    document.getElementById("metric-mae-30").textContent = `Rs. ${m30.MAE || 'N/A'}`;
    document.getElementById("metric-acc-30").textContent = `${m30.Accuracy || 'N/A'}%`;

    renderLiveIntelligence(data);
    renderPriceChart(data);
    renderTopFeatures(data.top_features);
    updateSimulator();
}

function renderLiveIntelligence(data) {
    if (!data) return;
    const df = data.detailed_factors || {};
    const climate = df.climate_weather || {};
    const supply = df.supply_chain || {};
    const nasa = df.real_nasa_agronomic || {};
    const isLive = data.is_live_data_saved || false;

    // Badges
    const wBadge = document.getElementById("weather-live-badge");
    const sBadge = document.getElementById("supply-live-badge");
    if (wBadge) {
        wBadge.textContent = isLive ? "🔴 LIVE NWP SYNCED" : "BASELINE FEED";
        wBadge.className = isLive ? "intel-status-pill live" : "intel-status-pill";
    }
    if (sBadge) {
        sBadge.textContent = isLive ? "🔴 LIVE INFLOW SYNCED" : "BASELINE FLOW";
        sBadge.className = isLive ? "intel-status-pill live" : "intel-status-pill";
    }

    const setTxt = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    };

    setTxt("w-temp-val", `${climate.temp_mean_c != null ? climate.temp_mean_c : '--'} °C`);
    setTxt("w-temp-range", `Min: ${climate.temp_min_c != null ? climate.temp_min_c : '--'}°C | Max: ${climate.temp_max_c != null ? climate.temp_max_c : '--'}°C`);
    setTxt("w-hum-val", `${climate.humidity_pct != null ? climate.humidity_pct : '--'}%`);
    setTxt("w-condition", climate.weather_condition || "Optimal Mild Conditions");
    const rainVal = climate.rain_mm != null ? climate.rain_mm : (climate.precipitation_mm != null ? climate.precipitation_mm : 0);
    setTxt("w-rain-val", `${rainVal} mm`);
    setTxt("w-wind-val", `Wind: ${climate.wind_speed_max_kmh != null ? climate.wind_speed_max_kmh : '--'} km/h`);
    setTxt("w-soil-val", `${nasa.surface_soil_moisture_index != null ? nasa.surface_soil_moisture_index : '--'}`);
    setTxt("w-soil-status", nasa.soil_moisture_status || "Optimal Field Capacity");
    setTxt("w-earth-temp", `${nasa.earth_surface_temp_c != null ? nasa.earth_surface_temp_c : '--'} °C`);
    setTxt("w-pressure", `${climate.surface_pressure_hpa != null ? climate.surface_pressure_hpa : '1012.0'} hPa`);
    setTxt("w-harvest-cond", climate.weather_condition || "Harvest-Favorable Weather");

    const arrTonnes = supply.arrivals_tonnes != null ? Number(supply.arrivals_tonnes).toLocaleString() : '--';
    setTxt("s-arr-val", `${arrTonnes} Tonnes`);
    setTxt("s-arr-status", supply.supply_level || "Active Mandi Arrivals");
    const vel = supply.inflow_velocity_pct != null ? `${supply.inflow_velocity_pct >= 0 ? '+' : ''}${supply.inflow_velocity_pct}%` : '+0.0%';
    setTxt("s-velocity-val", vel);
    setTxt("s-rolling-val", `7d Mean: ${supply.arrivals_rolling_mean_7d != null ? Number(supply.arrivals_rolling_mean_7d).toLocaleString() : arrTonnes} T`);
    setTxt("s-diesel-val", `Rs. ${supply.diesel_fuel_price_rs_l != null ? supply.diesel_fuel_price_rs_l : '92.5'} / L`);
    setTxt("s-freight-idx", `Freight Index: ${supply.logistics_freight_index != null ? supply.logistics_freight_index : '1.05'}x`);
    setTxt("s-procure-val", `${supply.fci_procurement_demand_idx != null ? supply.fci_procurement_demand_idx : '1.10'}x Index`);
    setTxt("s-trade-velocity", supply.mandi_trade_velocity || "Active Wholesale Flow");
    setTxt("s-lag-val", `${supply.arrivals_lag_7d != null ? Number(supply.arrivals_lag_7d).toLocaleString() : arrTonnes} Tonnes`);
    setTxt("s-export-idx", `${supply.export_parity_index != null ? supply.export_parity_index : '1.12'}x Parity`);
    setTxt("s-occupancy", `${supply.storage_occupancy_pct != null ? supply.storage_occupancy_pct : '78.5'}% (Buffer Stocked)`);
}

function renderPriceChart(data) {
    const ctx = document.getElementById("priceChart").getContext("2d");

    const hist = data.historical_recent || [];
    const f7 = data.forecasts ? data.forecasts.horizon_7d || [] : [];
    const gap = data.black_box_gap || {};

    const labels = [];
    const histPrices = [];
    const gapPrices = [];
    const predPrices = [];
    const upperBounds = [];
    const lowerBounds = [];

    hist.forEach(h => {
        labels.push(h.date);
        histPrices.push(h.price);
        gapPrices.push(null);
        predPrices.push(null);
        upperBounds.push(null);
        lowerBounds.push(null);
    });

    if (gap.start_date && gap.end_date) {
        labels.push(`[Black Box Start: ${gap.start_date}]`);
        histPrices.push(null);
        gapPrices.push(null);
        predPrices.push(null);
        upperBounds.push(null);
        lowerBounds.push(null);

        labels.push(`[Black Box End: ${gap.end_date}]`);
        histPrices.push(null);
        gapPrices.push(null);
        predPrices.push(null);
        upperBounds.push(null);
        lowerBounds.push(null);
    }

    const activeForecasts = f7.slice(0, currentHorizon + 1);
    activeForecasts.forEach(f => {
        labels.push(f.day === 0 ? `PRESENT (${f.date})` : f.date);
        histPrices.push(null);
        gapPrices.push(null);
        predPrices.push(f.predicted_price);
        upperBounds.push(f.upper_bound);
        lowerBounds.push(f.lower_bound);
    });

    if (priceChart) {
        priceChart.destroy();
    }

    priceChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Recorded Historical Price (Rs/q)",
                    data: histPrices,
                    borderColor: "#3b82f6",
                    backgroundColor: "rgba(59, 130, 246, 0.1)",
                    borderWidth: 2,
                    tension: 0.2,
                    pointRadius: 2,
                    spanGaps: false
                },
                {
                    label: "Black Box: Unreported Data Gap (No Graph Plotted)",
                    data: gapPrices,
                    borderColor: "transparent",
                    backgroundColor: "rgba(15, 23, 42, 0.9)",
                    borderWidth: 0,
                    pointRadius: 0,
                    spanGaps: false
                },
                {
                    label: "AI Present & Future Forecast (Rs/q)",
                    data: predPrices,
                    borderColor: "#10b981",
                    backgroundColor: "rgba(16, 185, 129, 0.2)",
                    borderWidth: 3,
                    borderDash: [5, 5],
                    tension: 0.2,
                    pointRadius: 4,
                    pointBackgroundColor: "#10b981",
                    spanGaps: false
                },
                {
                    label: "95% Upper Bound",
                    data: upperBounds,
                    borderColor: "rgba(245, 158, 11, 0.4)",
                    borderWidth: 1,
                    borderDash: [2, 2],
                    pointRadius: 0,
                    fill: false,
                    spanGaps: false
                },
                {
                    label: "95% Lower Bound",
                    data: lowerBounds,
                    borderColor: "rgba(245, 158, 11, 0.4)",
                    backgroundColor: "rgba(245, 158, 11, 0.08)",
                    borderWidth: 1,
                    borderDash: [2, 2],
                    pointRadius: 0,
                    fill: "-1",
                    spanGaps: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: "index",
                intersect: false
            },
            plugins: {
                legend: {
                    labels: { color: "#94a3b8" }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            if (context.raw !== null) {
                                return `${context.dataset.label}: Rs. ${context.raw.toLocaleString()}`;
                            } else if (context.dataset.label.includes("Black Box")) {
                                return "⬛ BLACK BOX: Data Not Reported (No Line Plotted)";
                            }
                            return "";
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: "#334155" },
                    ticks: { color: "#94a3b8", maxTicksLimit: 14 }
                },
                y: {
                    grid: { color: "#334155" },
                    ticks: { color: "#94a3b8" }
                }
            }
        }
    });
}

function renderTopFeatures(features) {
    const listEl = document.getElementById("features-list");
    listEl.innerHTML = "";

    if (!features || features.length === 0) {
        listEl.innerHTML = "<div style='color:#94a3b8;'>No feature importance data available.</div>";
        return;
    }

    const maxImp = Math.max(...features.map(f => f.importance));

    features.slice(0, 6).forEach(f => {
        const pct = Math.round((f.importance / maxImp) * 100);
        const name = f.feature.replace(/_/g, " ").replace("real ", "NASA ").replace("pct", "%").toUpperCase();

        const row = document.createElement("div");
        row.className = "factor-item";
        row.innerHTML = `
            <div class="factor-label" title="${f.feature}">${name}</div>
            <div class="factor-bar-bg">
                <div class="factor-bar-fill" style="width: ${pct}%;"></div>
            </div>
            <div class="factor-score">${pct}%</div>
        `;
        listEl.appendChild(row);
    });
}

function setupEventListeners() {
    const cropSelect = document.getElementById("crop-select");
    if (cropSelect) {
        cropSelect.addEventListener("change", (e) => {
            currentCrop = e.target.value;
            fetchData();
        });
    }

    const btns = document.querySelectorAll(".horizon-btn");
    btns.forEach(btn => {
        btn.addEventListener("click", (e) => {
            btns.forEach(b => b.classList.remove("active"));
            e.target.classList.add("active");
            currentHorizon = parseInt(e.target.getAttribute("data-horizon"));
            if (currentMarketKey && marketData[currentMarketKey]) {
                renderPriceChart(marketData[currentMarketKey]);
            }
        });
    });

    document.getElementById("sim-supply").addEventListener("input", updateSimulator);
    document.getElementById("sim-moisture").addEventListener("input", updateSimulator);
    document.getElementById("sim-demand").addEventListener("input", updateSimulator);

    const openBtn = document.getElementById("open-saved-modal-btn");
    const closeBtn = document.getElementById("close-saved-modal-btn");
    const modal = document.getElementById("saved-modal");

    if (openBtn) {
        openBtn.addEventListener("click", openSavedModal);
    }
    if (closeBtn) {
        closeBtn.addEventListener("click", () => {
            modal.style.display = "none";
        });
    }
    window.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && modal) {
            modal.style.display = "none";
        }
    });
}

function openSavedModal() {
    const modal = document.getElementById("saved-modal");
    if (!modal) return;
    modal.style.display = "flex";

    renderModalCityList();
    if (currentMarketKey && marketData[currentMarketKey]) {
        renderModalCityDetail(currentMarketKey);
    } else if (Object.keys(marketData).length > 0) {
        renderModalCityDetail(Object.keys(marketData)[0]);
    }
}

function renderModalCityList() {
    const listEl = document.getElementById("modal-city-list");
    if (!listEl) return;
    listEl.innerHTML = "";

    Object.keys(marketData).forEach(key => {
        const item = marketData[key];
        const parts = key.split("_");
        const marketShort = parts[parts.length - 1];
        const stateShort = parts[0];

        const el = document.createElement("div");
        el.className = `modal-city-item ${key === currentMarketKey ? "active" : ""}`;
        el.onclick = () => {
            document.querySelectorAll(".modal-city-item").forEach(i => i.classList.remove("active"));
            el.classList.add("active");
            renderModalCityDetail(key);
        };

        el.innerHTML = `
            <div>
                <div style="font-weight: 700; font-size: 0.9rem; color: #fff;">${marketShort}</div>
                <div style="font-size: 0.75rem; color: var(--text-muted);">${stateShort}</div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 0.85rem; font-weight: 700; color: var(--primary);">Rs. ${item.latest_recorded_price ? item.latest_recorded_price : 'N/A'}</div>
                <span style="font-size: 0.7rem; background: rgba(16, 185, 129, 0.2); color: var(--primary); padding: 0.15rem 0.4rem; border-radius: 4px;">Saved</span>
            </div>
        `;

        listEl.appendChild(el);
    });
}

function renderModalCityDetail(key) {
    const detailEl = document.getElementById("modal-city-detail");
    if (!detailEl || !marketData[key]) return;

    const mData = marketData[key];
    const df = mData.detailed_factors || {};

    const price = df.real_price || {};
    const climate = df.climate_weather || {};
    const supply = df.supply_chain || {};
    const nasa = df.real_nasa_agronomic || {};
    const season = df.seasonality || {};

    const isLiveToday = (df.date === mData.present_date) || mData.is_live_data_saved;

    detailEl.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem; flex-wrap: wrap; gap: 1rem; border-bottom: 1px solid var(--border-color); padding-bottom: 1rem;">
            <div>
                <h3 style="font-size: 1.4rem; font-weight: 800; color: #fff; display: flex; align-items: center; gap: 0.5rem;">
                    ${df.city_town || key} <span style="font-size: 0.9rem; font-weight: 500; color: var(--text-muted);">(${df.state || ''} • ${currentCrop.toUpperCase()})</span>
                    ${isLiveToday ? '<span class="live-badge">🔴 LIVE DATA SAVED (2026-10-07)</span>' : ''}
                </h3>
                <p style="font-size: 0.85rem; color: var(--text-muted);">Reported Date: <strong>${df.date || mData.latest_recorded_date}</strong> | Present Date: <strong>${mData.present_date}</strong></p>
            </div>
            <div style="display: flex; gap: 0.75rem; align-items: center;">
                <button class="live-fetch-btn" onclick="fetchLiveForMarket('${key}')" id="btn-fetch-${key}">
                    ⚡ Fetch & Save Today's Live Data
                </button>
                <div style="background: var(--bg-dark); padding: 0.5rem 0.9rem; border-radius: 10px; border: 1px solid var(--border-color); text-align: right;">
                    <div style="font-size: 0.7rem; color: var(--text-muted);">Modal Price</div>
                    <div style="font-size: 1.15rem; font-weight: 800; color: var(--primary);">Rs. ${price.modal_price || mData.latest_recorded_price || 'N/A'} / q</div>
                </div>
            </div>
        </div>

        <div class="factor-matrix-grid">
            <div class="matrix-card">
                <div class="matrix-card-title" style="color: var(--primary);">
                    <span>💰</span> Real Price Factors
                </div>
                <table class="matrix-table">
                    <tr><td class="label">Modal Price</td><td class="value" style="color:var(--primary);">Rs. ${price.modal_price || 'N/A'}</td></tr>
                    <tr><td class="label">Min Price</td><td class="value">Rs. ${price.min_price || 'N/A'}</td></tr>
                    <tr><td class="label">Max Price</td><td class="value">Rs. ${price.max_price || 'N/A'}</td></tr>
                    <tr><td class="label">Price Spread (Max-Min)</td><td class="value">Rs. ${price.price_spread || 'N/A'}</td></tr>
                    <tr><td class="label">7-Day Price Lag</td><td class="value">Rs. ${price.price_lag_7d || 'N/A'}</td></tr>
                    <tr><td class="label">7-Day Rolling Mean</td><td class="value">Rs. ${price.price_rolling_mean_7d || 'N/A'}</td></tr>
                    <tr><td class="label">7-Day Price Trend</td><td class="value" style="color: ${price.price_pct_change_7d >= 0 ? '#10b981' : '#ef4444'};">${price.price_pct_change_7d >= 0 ? '+' : ''}${price.price_pct_change_7d || 0}%</td></tr>
                </table>
            </div>

            <div class="matrix-card">
                <div class="matrix-card-title" style="color: #3b82f6;">
                    <span>🌤️</span> Climate & Weather (Open-Meteo)
                </div>
                <table class="matrix-table">
                    <tr><td class="label">Mean Temperature</td><td class="value" style="color:#38bdf8;">${climate.temp_mean_c != null ? climate.temp_mean_c : 0} °C</td></tr>
                    <tr><td class="label">Max Temperature</td><td class="value">${climate.temp_max_c != null ? climate.temp_max_c : 0} °C</td></tr>
                    <tr><td class="label">Min Temperature</td><td class="value">${climate.temp_min_c != null ? climate.temp_min_c : 0} °C</td></tr>
                    <tr><td class="label">Condition</td><td class="value" style="color:#10b981;">${climate.weather_condition || 'Optimal Mild'}</td></tr>
                    <tr><td class="label">Precipitation / Rain</td><td class="value">${climate.rain_mm != null ? climate.rain_mm : (climate.precipitation_mm || 0)} mm</td></tr>
                    <tr><td class="label">Relative Humidity</td><td class="value">${climate.humidity_pct != null ? climate.humidity_pct : 0}%</td></tr>
                    <tr><td class="label">Max Wind Speed</td><td class="value">${climate.wind_speed_max_kmh != null ? climate.wind_speed_max_kmh : 0} km/h</td></tr>
                    <tr><td class="label">Surface Pressure</td><td class="value">${climate.surface_pressure_hpa || 1012.0} hPa</td></tr>
                </table>
            </div>

            <div class="matrix-card">
                <div class="matrix-card-title" style="color: var(--accent);">
                    <span>🚚</span> Supply Chain & Logistics
                </div>
                <table class="matrix-table">
                    <tr><td class="label">Mandi Inflow Arrivals</td><td class="value" style="color:var(--accent);">${supply.arrivals_tonnes ? Number(supply.arrivals_tonnes).toLocaleString() : 0} Tonnes</td></tr>
                    <tr><td class="label">7-Day Lag Arrivals</td><td class="value">${supply.arrivals_lag_7d || 0} Tonnes</td></tr>
                    <tr><td class="label">7-Day Rolling Mean</td><td class="value">${supply.arrivals_rolling_mean_7d || 0} Tonnes</td></tr>
                    <tr><td class="label">Inflow Velocity</td><td class="value"><span style="color:${(supply.inflow_velocity_pct || 0) >= 0 ? '#10b981' : '#ef4444'};">${supply.inflow_velocity_pct ? (supply.inflow_velocity_pct >= 0 ? '+' : '') + supply.inflow_velocity_pct + '%' : 'Steady Flow'}</span></td></tr>
                    <tr><td class="label">Supply Status</td><td class="value">${supply.supply_level || 'Normal Supply Inflow'}</td></tr>
                    <tr><td class="label">Diesel Transport Fuel</td><td class="value" style="color:#ef4444;">Rs. ${supply.diesel_fuel_price_rs_l || 92.5} / L</td></tr>
                    <tr><td class="label">Freight Index</td><td class="value">${supply.logistics_freight_index || 1.05}x</td></tr>
                    <tr><td class="label">Procurement Demand</td><td class="value" style="color:#10b981;">${supply.fci_procurement_demand_idx || 1.10}x Index</td></tr>
                    <tr><td class="label">Export Parity Index</td><td class="value">${supply.export_parity_index || 1.12}x</td></tr>
                </table>
            </div>

            <div class="matrix-card">
                <div class="matrix-card-title" style="color: #a855f7;">
                    <span>🛰️</span> Real NASA Agronomic
                </div>
                <table class="matrix-table">
                    <tr><td class="label">Surface Soil Moisture</td><td class="value" style="color:#a855f7;">${nasa.surface_soil_moisture_index || 0}</td></tr>
                    <tr><td class="label">Rootzone Soil Moisture</td><td class="value">${nasa.rootzone_soil_moisture_index || 0}</td></tr>
                    <tr><td class="label">NASA Earth Surface Temp</td><td class="value">${nasa.earth_surface_temp_c || 0} °C</td></tr>
                    <tr><td class="label">NASA Air Temp (2m)</td><td class="value">${nasa.air_temp_2m_c || 0} °C</td></tr>
                    <tr><td class="label">NASA Humidity</td><td class="value">${nasa.relative_humidity_pct || 0}%</td></tr>
                    <tr><td class="label">Moisture Status</td><td class="value" style="color:#10b981;">${nasa.soil_moisture_status || 'Optimal Field Capacity'}</td></tr>
                </table>
            </div>

            <div class="matrix-card">
                <div class="matrix-card-title" style="color: #ec4899;">
                    <span>🍊</span> Seasonality & Crop Cycle
                </div>
                <table class="matrix-table">
                    <tr><td class="label">Harvest Season</td><td class="value" style="color:#ec4899;">${season.harvest_season || 'Main Harvest'}</td></tr>
                    <tr><td class="label">Supply Window Phase</td><td class="value">${season.supply_phase || 'Peak Supply'}</td></tr>
                    <tr><td class="label">Relative Demand Index</td><td class="value">${season.relative_demand_index || 1.0}x</td></tr>
                    <tr><td class="label">Seasonal Price Trend</td><td class="value">${season.seasonal_price_trend || 'Stable'}</td></tr>
                    <tr><td class="label">Reported Month</td><td class="value">${season.month_name || ''} (Day ${season.day_of_year || ''})</td></tr>
                </table>
            </div>
        </div>
    `;
}

async function fetchLiveForMarket(key) {
    if (!key) key = currentMarketKey;

    const btn = document.getElementById(`btn-fetch-${key}`);
    const mainBtn = document.getElementById("main-live-fetch-btn");

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = "⏳ Querying Live APIs...";
    }
    if (mainBtn) {
        mainBtn.disabled = true;
        mainBtn.innerHTML = "⏳ Querying Live APIs...";
    }

    try {
        const response = await fetch(`/api/fetch_live?crop=${encodeURIComponent(currentCrop)}&market=${encodeURIComponent(key)}`);
        const res = await response.json();

        if (res.success) {
            const sc = res.supply_chain || {};
            const wt = res.weather || {};
            const ns = res.nasa || {};
            alert(`✅ ${res.message}\n\n• Live Weather: ${wt.temp_mean_c}°C (${wt.weather_condition || 'Clear'}), ${wt.humidity_pct}% Humidity, Rain: ${wt.rain_mm || 0}mm\n• Live Supply Chain: ${sc.arrivals_tonnes} Tonnes Inflow, Diesel: Rs.${sc.diesel_fuel_price_rs_l}/L, Demand Index: ${sc.fci_procurement_demand_idx}x\n• Live NASA Soil Moisture: ${ns.surface_soil_moisture_index} (${ns.soil_moisture_status || 'Optimal'})\n• Saved across all 5 dataset CSVs for crop '${currentCrop}'!`);
            
            await fetchData();
            renderMarketList();
            renderSelectedMarket(key);
            renderModalCityList();
            renderModalCityDetail(key);
        } else {
            alert(`Error: ${res.message}`);
        }
    } catch (err) {
        console.error("Live fetch error:", err);
        alert("Failed to fetch live API data. Please ensure Python server.py is running.");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = "⚡ Fetch & Save Today's Live Data";
        }
        if (mainBtn) {
            mainBtn.disabled = false;
            mainBtn.innerHTML = "⚡ Fetch & Save Today's Live Data";
        }
    }
}

async function fetchLiveForAllMarkets() {
    const btn = document.getElementById("modal-fetch-all-live-btn");
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = "⏳ Querying Live APIs for ALL Mandis...";
    }

    try {
        const response = await fetch(`/api/fetch_live_all?crop=${encodeURIComponent(currentCrop)}`);
        const res = await response.json();

        if (res.success) {
            alert(`✅ ${res.message}\n\n• Updated Live Weather (Open-Meteo & NASA)\n• Updated Live Supply Chain (Arrivals, Diesel Logistics Index & FCI/Trade Demand)\n• Saved across all 5 dataset CSVs for ${res.total_markets_updated} mandis in crop '${currentCrop}'!`);
            await fetchData();
            renderMarketList();
            if (currentMarketKey) {
                renderSelectedMarket(currentMarketKey);
            }
            renderModalCityList();
            if (currentMarketKey) {
                renderModalCityDetail(currentMarketKey);
            }
        }
    } catch (err) {
        console.error("Live fetch all error:", err);
        alert("Failed to fetch live API data. Please ensure Python server.py is running.");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = "⚡ Fetch & Save Today's Live Data for ALL Mandis";
        }
    }
}

function updateSimulator() {
    if (!currentMarketKey || !marketData[currentMarketKey]) return;

    const data = marketData[currentMarketKey];
    const basePrice = data.latest_recorded_price || 1000;

    const supplyShift = parseFloat(document.getElementById("sim-supply").value);
    const moistureShift = parseFloat(document.getElementById("sim-moisture").value);
    const demandMultiplier = parseFloat(document.getElementById("sim-demand").value);

    document.getElementById("val-supply").textContent = `${supplyShift > 0 ? '+' : ''}${supplyShift}%`;
    document.getElementById("val-moisture").textContent = `${moistureShift > 0 ? '+' : ''}${moistureShift}%`;
    document.getElementById("val-demand").textContent = `${demandMultiplier}x`;

    let simPrice = basePrice * demandMultiplier * (1 - (supplyShift / 100) * 0.45) * (1 + (moistureShift / 100) * 0.18);
    simPrice = Math.max(500, Math.round(simPrice));

    const delta = simPrice - basePrice;
    const deltaPct = ((delta / basePrice) * 100).toFixed(1);

    document.getElementById("sim-result-price").textContent = `Rs. ${simPrice.toLocaleString()} / q`;
    
    const deltaEl = document.getElementById("sim-result-delta");
    deltaEl.textContent = `${delta >= 0 ? '▲ +' : '▼ '}${delta.toLocaleString()} (${deltaPct}%)`;
    deltaEl.style.color = delta >= 0 ? '#10b981' : '#ef4444';

    const recEl = document.getElementById("sim-recommendation");
    if (deltaPct > 8) {
        recEl.innerHTML = `<strong>Farmer Strategy:</strong> Hold stock for 10-14 days. Prices expected to surge due to favorable demand/supply deficit.`;
    } else if (deltaPct < -8) {
        recEl.innerHTML = `<strong>Farmer Strategy:</strong> Sell immediately to minimize loss. Heavy oversupply or reduced demand ahead.`;
    } else {
        recEl.innerHTML = `<strong>Farmer Strategy:</strong> Stable market environment. Sell in regular staggered tranches.`;
    }
}
