"use strict";
const $ = (id) => document.getElementById(id);
const BUILD = document.querySelector('meta[name="build"]').content;
const uploadEntry = /^\/upload\/?$/.test(location.pathname) ||
  new URLSearchParams(location.search).get("action") === "upload";
let pendingUploadEntry = uploadEntry;
const storage = {
  get(key) {
    try {
      return localStorage.getItem(key) || sessionStorage.getItem(key) || "";
    } catch (_) {
      return "";
    }
  },
  clear(key) {
    try {
      localStorage.removeItem(key);
      sessionStorage.removeItem(key);
    } catch (_) {}
  },
};
let token = storage.get("leapToken"),
  data = { daily: [], weekly: [], energy: [] };
let range = "month",
  view = "daily",
  pageName = "overview",
  busy = false,
  refreshing = false;
let custom = { start: "", end: "" },
  selectedMileage = "",
  mileagePage = 0,
  selectedWeek = "",
  calendarSelection = "";
let reviewId,
  reviewDraft,
  jsonDirty = false,
  recordsLimit = 60,
  daySelected = "",
  lastSynced = "";
const today = () =>
  new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
const day = (s) => new Date(s + "T00:00:00Z");
const iso = (d) => d.toISOString().slice(0, 10);
const add = (s, n) => {
  const d = day(s);
  d.setUTCDate(d.getUTCDate() + n);
  return iso(d);
};
const monday = (s) => add(s, -((day(s).getUTCDay() + 6) % 7));
const num = (n) => Number(Number(n).toFixed(1)).toLocaleString("zh-CN");
const fullDate = (s) =>
  new Intl.DateTimeFormat("zh-CN", {
    timeZone: "UTC",
    month: "long",
    day: "numeric",
    weekday: "long",
  }).format(day(s));
const monthName = (s) => s.slice(0, 4) + " 年 " + Number(s.slice(5, 7)) + " 月";
let calendar = today().slice(0, 7);
const node = (tag, cls, text) => {
  const el = document.createElement(tag);
  if (cls) el.className = cls;
  if (text !== undefined) el.textContent = text;
  return el;
};
const svgNode = (tag, attrs = {}, text) => {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, String(v)));
  if (text !== undefined) el.textContent = text;
  return el;
};
function notify(message) {
  $("toast").textContent = message;
  $("toast").hidden = false;
  clearTimeout(notify.timer);
  notify.timer = setTimeout(() => ($("toast").hidden = true), 5500);
}
function showDialog(id) {
  if (!$(id).open) $(id).showModal();
}
function empty(target, title, description) {
  const el = node("div", "empty");
  el.append(node("strong", "", title), node("p", "", description));
  target.replaceChildren(el);
}
async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    cache: "no-store",
    headers: { ...options.headers, "X-API-Key": token },
  });
  if (!response.ok) {
    if (response.status === 401) showDialog("loginDialog");
    const body = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    let message =
      typeof body.detail === "string"
        ? body.detail
        : Array.isArray(body.detail)
          ? body.detail
              .map((e) => (e.loc || []).join(" / ") + "：" + e.msg)
              .join("\n")
          : "请求未完成";
    throw new Error(message);
  }
  return response;
}
function bounds() {
  const t = today(),
    d = day(t);
  let start, end;
  if (range === "month") {
    start = t.slice(0, 7) + "-01";
    end = iso(new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)));
  }
  if (range === "lastmonth") {
    start = iso(new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() - 1, 1)));
    end = add(t.slice(0, 7) + "-01", -1);
  }
  if (range === "week") {
    start = monday(t);
    end = add(start, 6);
  }
  if (range === "lastweek") {
    start = add(monday(t), -7);
    end = add(start, 6);
  }
  if (range === "custom") {
    start = custom.start;
    end = custom.end;
  }
  return { start, end };
}
function inRange(date) {
  const { start, end } = bounds();
  return (!start || date >= start) && (!end || date <= end);
}
function periodInRange(period) {
  const [s, e] = period.replaceAll("/", "-").split(" - "),
    { start, end } = bounds();
  return (!start || e >= start) && (!end || s <= end);
}
function selectedRows() {
  return data.daily.filter((r) => inRange(r.date));
}
function navigate(name) {
  if (name === "overview" && pageName !== "overview") {
    selectedMileage = "";
    mileagePage = 0;
  }
  pageName = name;
  document
    .querySelectorAll(".page-content")
    .forEach((el) => (el.hidden = el.id !== "page-" + name));
  document.querySelectorAll("[data-page]").forEach((b) => {
    b.classList.toggle("active", b.dataset.page === name);
    if (b.dataset.page === name) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  });
  const headings = {
    overview: [
      "YOUR EVERYDAY JOURNEY",
      "每一程，都值得记录。",
      "了解出行的节奏，也看见每一度电的去向。",
    ],
    energy: [
      "A MORE EFFICIENT JOURNEY",
      "让每一度电，都有迹可循。",
      "看看每周的用电表现，以及行车、空调和其他用电。",
    ],
    records: [
      "YOUR JOURNEY ARCHIVE",
      "把走过的路，留在这里。",
      "逐日回看你的行程，记录会随着每次上传不断补全。",
    ],
  };
  const [eyebrow, title, sub] = headings[name];
  $("headingEyebrow").textContent = eyebrow;
  $("pageTitle").textContent = title;
  $("pageSubtitle").textContent = sub;
  render();
  window.scrollTo({ top: 0, behavior: "instant" });
}
function setRange(value) {
  range = value;
  recordsLimit = 60;
  selectedMileage = "";
  mileagePage = 0;
  selectedWeek = "";
  const b = bounds();
  if (b.end) calendar = (b.end > today() ? today() : b.end).slice(0, 7);
  calendarSelection = "";
  render();
}
function coverage(rows) {
  const { start, end } = bounds();
  if (!start)
    return {
      text: rows.length
        ? "累计记录 " + rows.length + " 天 · 从 " + data.daily[0].date + " 开始"
        : "上传第一张截图，开始你的行程手记",
      complete: false,
    };
  const elapsedEnd = end > today() ? today() : end;
  const expected =
    elapsedEnd >= start
      ? Math.round((day(elapsedEnd) - day(start)) / 86400000) + 1
      : 0;
  const recorded = rows.filter((r) => r.date <= elapsedEnd).length;
  return {
    text: expected
      ? "已记录 " +
        recorded +
        " / " +
        expected +
        " 天" +
        (recorded === expected
          ? " · 这段旅程记录完整"
          : " · " + (expected - recorded) + " 天待补全")
      : "这段时间尚未开始",
    complete: expected > 0 && recorded === expected,
  };
}
function render() {
  const rows = selectedRows(),
    sum = rows.reduce((s, r) => s + r.km, 0),
    { start, end } = bounds();
  $("total").textContent = num(sum);
  $("days").textContent = rows.length;
  $("average").textContent = rows.length ? num(sum / rows.length) : "—";
  $("maximum").textContent = rows.length
    ? num(Math.max(...rows.map((r) => r.km)))
    : "—";
  $("lifetimeTotal").textContent = num(
    data.daily.reduce((s, r) => s + r.km, 0),
  );
  $("rangeLabel").textContent = {
    month: "本月里程",
    week: "本周里程",
    lastweek: "上周里程",
    lastmonth: "上月里程",
    all: "累计里程",
    custom: "这段时间的里程",
  }[range];
  $("rangeDates").textContent = start
    ? start.replaceAll("-", ".") + " — " + end.replaceAll("-", ".")
    : "全部已记录日期";
  const c = coverage(rows);
  $("coverageText").textContent = c.text;
  $("coverageText").classList.toggle("incomplete", !c.complete);
  document.querySelectorAll("[data-range]").forEach((b) => {
    b.classList.toggle("active", b.dataset.range === range);
    b.setAttribute("aria-pressed", String(b.dataset.range === range));
  });
  document.querySelectorAll("[data-view]").forEach((b) => {
    b.classList.toggle("active", b.dataset.view === view);
    b.setAttribute("aria-pressed", String(b.dataset.view === view));
  });
  if (pageName === "overview") {
    renderMileage(rows);
    renderCalendar();
    renderInsights(rows);
  }
  if (pageName === "energy") renderEnergy();
  if (pageName === "records") renderRecords(rows);
}
function chartData(rows) {
  const grouped = new Map(),
    { start, end } = bounds();
  rows.forEach((r) => {
    const key =
      view === "weekly"
        ? monday(r.date)
        : view === "monthly"
          ? r.date.slice(0, 7)
          : view === "yearly" ? r.date.slice(0, 4) : r.date;
    const old = grouped.get(key) || { key, value: 0, count: 0 };
    old.value += r.km;
    old.count++;
    grouped.set(key, old);
  });
  if (
    view === "daily" &&
    start &&
    end &&
    Math.round((day(end) - day(start)) / 86400000) <= 90
  ) {
    const last = end > today() ? today() : end;
    for (let d = start; d <= last; d = add(d, 1))
      if (!grouped.has(d)) grouped.set(d, { key: d, value: null, count: 0 });
  }
  return [...grouped.values()].sort((a, b) => b.key.localeCompare(a.key));
}
function axis(svg, W, H, max, left = 36, right = 12, top = 15, bottom = 30) {
  const base = H - bottom,
    plotHeight = base - top;
  [0, 0.5, 1].forEach((f) => {
    const y = base - f * plotHeight;
    svg.append(
      svgNode("line", {
        x1: left,
        y1: y,
        x2: W - right,
        y2: y,
        class: "chart-grid",
      }),
    );
    svg.append(
      svgNode(
        "text",
        { x: left - 8, y: y + 3, "text-anchor": "end", class: "chart-label" },
        num(max * f),
      ),
    );
  });
  return { base, plotHeight, left, right, top };
}
function renderMileage(rows) {
  const all = chartData(rows),
    pageSize = {daily: 31, weekly: 26, monthly: 24, yearly: 10}[view],
    pageCount = Math.max(1, Math.ceil(all.length / pageSize));
  mileagePage = Math.min(mileagePage, pageCount - 1);
  const items = all.slice(mileagePage * pageSize, (mileagePage + 1) * pageSize),
    target = $("mileageChart"),
    readout = $("mileageReadout");
  target.replaceChildren();
  readout.replaceChildren();
  $("averageLegend").textContent = {
    daily: "已记录日均",
    weekly: "已记录周均",
    monthly: "已记录月均",
    yearly: "已记录年均",
  }[view];
  $("chartNote").textContent =
    "最新在左 · 按筛选范围汇总 · 空缺不计为 0";
  $("mileagePager").hidden = pageCount <= 1;
  $("mileageNewer").disabled = mileagePage === 0;
  $("mileageOlder").disabled = mileagePage === pageCount - 1;
  $("mileagePageLabel").textContent = "第 " + (mileagePage + 1) + " / " + pageCount + " 页 · 共 " + all.length + " 项";
  $("mileagePageRange").textContent = items.length
    ? items[0].key + " → " + items[items.length - 1].key : "";
  if (!rows.length) {
    empty(
      target,
      "这段旅程还没有记录",
      "上传截图后，里程会在这里慢慢连成日常。",
    );
    return;
  }
  const width = Math.max(
      target.clientWidth || 600,
      items.length * 12 + 48,
      300,
    ),
    H = 220;
  const svg = svgNode("svg", {
    viewBox: "0 0 " + width + " " + H,
    "aria-label": "可点按的里程柱状图",
    role: "group",
  });
  svg.style.minWidth = (items.length > 45 ? items.length * 12 + 48 : 0) + "px";
  const observed = all.filter((r) => r.value !== null),
    maxRaw = Math.max(...observed.map((r) => r.value), 1);
  const max = Math.ceil(maxRaw / 20) * 20,
    { base, plotHeight, left, right } = axis(svg, width, H, max);
  const step = (width - left - right) / items.length,
    barWidth = Math.max(3, Math.min(25, step * 0.55));
  const avg = observed.reduce((s, r) => s + r.value, 0) / observed.length;
  svg.append(
    svgNode("line", {
      x1: left,
      y1: base - (avg / max) * plotHeight,
      x2: width - right,
      y2: base - (avg / max) * plotHeight,
      class: "average-line",
    }),
  );
  const bars = [];
  let selected = items.findIndex((r) => r.key === selectedMileage);
  if (selected < 0) selected = items.findIndex((r) => r.value !== null);
  if (selected < 0 && items.length) selected = 0;
  function choose(i) {
    selectedMileage = items[i].key;
    bars.forEach((b, j) => {
      b.classList.toggle("selected", j === i);
    });
    const r = items[i],
      label =
        view === "daily"
          ? fullDate(r.key)
          : view === "weekly"
            ? r.key + " 起的这一周"
            : view === "yearly" ? r.key + " 年" : monthName(r.key);
    readout.replaceChildren(
      node("span", "", label),
      node("strong", "", r.value === null ? "未记录" : num(r.value)),
      node(
        "span",
        "",
        r.value === null
          ? "等待补充"
          : "km" + (view === "daily" ? "" : " · " + r.count + " 天有记录"),
      ),
    );
  }
  items.forEach((r, i) => {
    const x = left + step * (i + 0.5),
      height = r.value === null ? 0 : (r.value / max) * plotHeight;
    const bar = svgNode("rect", {
      x: x - barWidth / 2,
      y: base - Math.max(2, height),
      width: barWidth,
      height: Math.max(2, height),
      rx: Math.min(4, barWidth / 2),
      class: "chart-bar",
    });
    if (r.value === null) {
      bar.setAttribute("height", 0);
      svg.append(
        svgNode("line", {
          x1: x - 3,
          y1: base - 2,
          x2: x + 3,
          y2: base - 2,
          class: "missing-mark",
        }),
      );
    }
    bars.push(bar);
    svg.append(bar);
    const labelEvery = Math.max(
      1,
      Math.ceil(items.length / (width < 450 ? 6 : 12)),
    );
    if (i % labelEvery === 0 || i === items.length - 1)
      svg.append(
        svgNode(
          "text",
          { x, y: base + 22, "text-anchor": "middle", class: "chart-label" },
          view === "yearly" ? r.key : view === "monthly"
            ? r.key.slice(2).replace("-", "/")
            : r.key.slice(5).replace("-", "/"),
        ),
      );
    const hit = svgNode("rect", {
      x: x - step / 2,
      y: 5,
      width: step,
      height: base + 4,
      tabindex: 0,
      role: "button",
      "aria-label":
        r.key + "，" + (r.value === null ? "未记录" : num(r.value) + " 公里"),
      class: "chart-hit",
    });
    hit.addEventListener("click", () => choose(i));
    hit.addEventListener("focus", () => choose(i));
    // Selection changes only through deliberate interaction, not incidental hover.
    hit.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        choose(i);
      }
      if (["ArrowLeft", "ArrowRight"].includes(e.key)) {
        e.preventDefault();
        const next = Math.max(
          0,
          Math.min(items.length - 1, i + (e.key === "ArrowRight" ? 1 : -1)),
        );
        svg.querySelectorAll(".chart-hit")[next].focus();
      }
    });
    svg.append(hit);
  });
  target.append(svg);
  if (selected >= 0) choose(selected);
  // Keep the selected (by default latest recorded) period visible on long charts.
  target.scrollLeft = Math.max(
    0,
    ((selected + 0.5) / items.length) * target.scrollWidth - target.clientWidth / 2,
  );
  // Horizontal scrubbing selects a day; vertical swipes remain normal page scrolling.
  if (items.length <= 45) {
    svg.style.touchAction = "pan-y";
    const scrub = (event) => {
      const rect = svg.getBoundingClientRect();
      const x = ((event.clientX - rect.left) / rect.width) * width;
      choose(
        Math.max(0, Math.min(items.length - 1, Math.floor((x - left) / step))),
      );
    };
    svg.addEventListener("pointerdown", (event) => {
      if (event.pointerType === "touch") {
        scrub(event);
        svg.setPointerCapture(event.pointerId);
      }
    });
    svg.addEventListener("pointermove", (event) => {
      if (event.pointerType === "touch" && event.buttons) scrub(event);
    });
  }
}
function renderCalendar() {
  const first = calendar + "-01",
    d = day(first),
    count = new Date(
      Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0),
    ).getUTCDate();
  const map = new Map(data.daily.map((r) => [r.date, r.km]));
  $("calendarMonth").textContent = monthName(calendar);
  $("calendarNext").disabled = calendar >= today().slice(0, 7);
  const grid = $("calendarGrid");
  grid.replaceChildren();
  const offset = (d.getUTCDay() + 6) % 7;
  for (let i = 0; i < offset; i++) grid.append(node("span"));
  const values = data.daily
      .filter((r) => r.date.startsWith(calendar))
      .map((r) => r.km),
    max = Math.max(...values, 1);
  if (!calendarSelection.startsWith(calendar))
    calendarSelection = calendar === today().slice(0, 7) ? today() : first;
  for (let n = 1; n <= count; n++) {
    const date = calendar + "-" + String(n).padStart(2, "0"),
      value = map.get(date),
      future = date > today();
    const cls = future
      ? "future"
      : value === undefined
        ? "missing"
        : value === 0
          ? "zero"
          : value < max / 3
            ? "level1"
            : value < (max * 2) / 3
              ? "level2"
              : "level3";
    const b = node("button", cls + (date === today() ? " today" : ""));
    b.append(node("span", "calendar-day", n),
      node("strong", "calendar-km", future ? "—" : value === undefined ? "待补" : num(value)));
    b.type = "button";
    b.disabled = future;
    b.dataset.date = date;
    b.setAttribute(
      "aria-label",
      fullDate(date) +
        "，" +
        (future
          ? "尚未开始"
          : value === undefined
            ? "未记录"
            : num(value) + " 公里"),
    );
    b.classList.toggle("selected", date === calendarSelection);
    b.onclick = () => {
      calendarSelection = date;
      renderCalendar();
      openDay(date);
    };
    grid.append(b);
  }
  const val = map.get(calendarSelection);
  $("calendarDetail").replaceChildren(
    node("span", "", calendarSelection),
    node("strong", "", val === undefined ? "未记录" : num(val) + " km"),
  );
}
function renderInsights(rows) {
  const target = $("insights");
  target.replaceChildren();
  function insight(icon, title, body) {
    const el = node("div", "insight"),
      text = node("div");
    text.append(node("strong", "", title), node("p", "", body));
    el.append(node("span", "insight-icon", icon), text);
    target.append(el);
  }
  if (!rows.length) {
    insight(
      "↗",
      "从一张截图开始",
      "选择零跑 App 的里程能耗截图，系统会帮你记下这段旅程。",
    );
    return;
  }
  const peak = rows.reduce((a, b) => (a.km >= b.km ? a : b));
  insight(
    "↗",
    "最远的一天 · " + num(peak.km) + " km",
    fullDate(peak.date) + "。日均与最高值均按已记录日期计算。",
  );
  const driven = rows.filter((r) => r.km > 0).length,
    zero = rows.length - driven;
  insight(
    "◷",
    driven + " 天在路上",
    zero
      ? "另有 " + zero + " 天已记录为 0 km；未上传的日期不算停车日。"
      : "每个已记录日都有出行。未记录的日期不会被自动补零。",
  );
  const weeks = data.weekly.filter((r) => periodInRange(r.period));
  if (weeks.length) {
    const latest = weeks.at(-1);
    insight(
      "ϟ",
      "最近一周 · " + num(latest.value) + " kWh / 100km",
      latest.period + "。周期百公里能耗来自原始截图。",
    );
  } else
    insight(
      "ϟ",
      "能耗记录等待补全",
      "上传包含完整周能耗区域的截图，即可查看用电趋势。",
    );
}
function renderEnergy() {
  const weekly = data.weekly.filter((r) => periodInRange(r.period)),
    latest = weekly.at(-1),
    previous = weekly.at(-2);
  $("latestEnergy").textContent = latest ? num(latest.value) : "—";
  $("latestEnergyPeriod").textContent = latest
    ? latest.period
    : "所选范围还没有周能耗记录";
  const change = $("energyChange");
  change.replaceChildren();
  change.classList.remove("higher");
  if (previous && latest) {
    const pct = ((latest.value - previous.value) / previous.value) * 100;
    change.classList.toggle("higher", pct > 0);
    change.append(
      node("strong", "", (pct > 0 ? "+" : "") + num(pct) + "%"),
      node(
        "span",
        "",
        pct === 0
          ? "与上一条周期记录持平"
          : "较上一条周期记录" +
              (pct > 0 ? "上升" : "下降") +
              " · 相同单位对比",
      ),
    );
  } else change.append(node("span", "", "积累两个周期后，可以查看能耗变化。"));
  renderEnergyChart(weekly);
  const energies = data.energy
      .filter((r) => periodInRange(r.period))
      .slice()
      .reverse(),
    select = $("energyPeriod"),
    old = select.value;
  select.replaceChildren(
    ...energies.map((r) => {
      const option = node("option", "", r.period);
      option.value = r.period;
      return option;
    }),
  );
  if (energies.some((r) => r.period === old)) select.value = old;
  select.disabled = !energies.length;
  renderBreakdown();
}
function renderEnergyChart(rows) {
  const target = $("weeklyChart"),
    readout = $("weeklyReadout");
  target.replaceChildren();
  readout.replaceChildren();
  $("weeklyNote").textContent = rows.length + " 个周期 · 点按查看";
  if (!rows.length) {
    empty(target, "还没有能耗曲线", "补充周能耗截图，就能看到每周的变化。");
    return;
  }
  const items = rows.slice(-60),
    W = Math.max(target.clientWidth || 600, items.length * 30 + 65, 300),
    H = 220;
  const svg = svgNode("svg", {
    viewBox: "0 0 " + W + " " + H,
    role: "group",
    "aria-label": "周能耗折线图，横轴按周期开始日期排列",
  });
  svg.style.minWidth = (items.length > 12 ? items.length * 30 + 65 : 0) + "px";
  const max = Math.ceil(Math.max(...items.map((r) => r.value)) / 5) * 5;
  const { base, plotHeight, left, right } = axis(svg, W, H, max);
  const starts = items.map((r) =>
    day(r.period.slice(0, 10).replaceAll("/", "-")).getTime(),
  );
  const delta = starts.at(-1) - starts[0] || 1;
  const points = items.map((r, i) => ({
    x:
      items.length === 1
        ? (W + left - right) / 2
        : left +
          15 +
          ((starts[i] - starts[0]) / delta) * (W - left - right - 30),
    y: base - (r.value / max) * plotHeight,
  }));
  // Gaps in week coverage are not bridged with a continuous line.
  const paths = [];
  let current = "";
  points.forEach((p, i) => {
    if (i && starts[i] - starts[i - 1] !== 7 * 86400000) {
      paths.push(current);
      current = "";
    }
    current += (current ? " L " : "M ") + p.x + " " + p.y;
  });
  if (current) paths.push(current);
  paths.forEach((d) =>
    svg.append(svgNode("path", { d, class: "energy-line" })),
  );
  const selection = svgNode("line", {
    x1: 0,
    x2: 0,
    y1: 10,
    y2: base,
    class: "selection-line",
  });
  svg.append(selection);
  const dots = [];
  const choose = (i) => {
    selectedWeek = items[i].period;
    const p = points[i];
    selection.setAttribute("x1", p.x);
    selection.setAttribute("x2", p.x);
    dots.forEach((dot, j) => {
      dot.classList.toggle("selected", i === j);
      dot.setAttribute("r", i === j ? 6 : 4);
    });
    readout.replaceChildren(
      node("span", "", items[i].period),
      node("strong", "", num(items[i].value)),
      node("span", "", "kWh / 100km"),
    );
  };
  points.forEach((p, i) => {
    const dot = svgNode("circle", {
      cx: p.x,
      cy: p.y,
      r: 4,
      class: "energy-dot",
    });
    dots.push(dot);
    svg.append(dot);
    if (
      i % Math.max(1, Math.ceil(items.length / 5)) === 0 ||
      i === items.length - 1
    )
      svg.append(
        svgNode(
          "text",
          {
            x: p.x,
            y: base + 22,
            "text-anchor": "middle",
            class: "chart-label",
          },
          items[i].period.slice(5, 10),
        ),
      );
    const hit = svgNode("circle", {
      cx: p.x,
      cy: p.y,
      r: 18,
      class: "chart-hit",
      tabindex: 0,
      role: "button",
      "aria-label":
        items[i].period + "，" + num(items[i].value) + " 千瓦时每百公里",
    });
    hit.addEventListener("click", () => choose(i));
    hit.addEventListener("focus", () => choose(i));
    hit.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        choose(i);
      }
    });
    svg.append(hit);
  });
  target.append(svg);
  const i = items.findIndex((r) => r.period === selectedWeek);
  choose(i < 0 ? items.length - 1 : i);
}
function renderBreakdown() {
  const row = data.energy.find((r) => r.period === $("energyPeriod").value),
    target = $("energyBreakdown");
  target.replaceChildren();
  if (!row) {
    empty(
      target,
      "电量去向还未记录",
      "上传包含能耗构成的截图后，可查看行车、空调和其他用电。",
    );
    return;
  }
  const wrapper = node("div", "donut-wrap"),
    svg = svgNode("svg", {
      viewBox: "0 0 200 200",
      role: "group",
      "aria-label": "能耗构成环形图",
    }),
    center = node("div", "donut-center"),
    legend = node("div", "breakdown-legend");
  const value = node("strong", "", num(row.totalKwh)),
    label = node("span", "", "周期总电量 · kWh");
  center.append(value, label);
  svg.append(
    svgNode("circle", { cx: 100, cy: 100, r: 75, class: "donut-base" }),
  );
  const parts = [
      ["行车", row.drive, "--gold-fill"],
      ["空调", row.ac, "--green"],
      ["其他", row.other, "--blue"],
    ],
    circ = 2 * Math.PI * 75;
  let offset = 0;
  const buttons = [];
  const choose = (i) => {
    if (i === null) {
      value.textContent = num(row.totalKwh);
      label.textContent = "周期总电量 · kWh";
    } else {
      value.textContent = parts[i][1] + "%";
      label.textContent =
        parts[i][0] +
        " · 约 " +
        num((row.totalKwh * parts[i][1]) / 100) +
        " kWh";
    }
    buttons.forEach((b, j) => b.classList.toggle("selected", i === j));
  };
  parts.forEach(([name, pct, color], i) => {
    const circle = svgNode("circle", {
      cx: 100,
      cy: 100,
      r: 75,
      class: "donut-segment",
      stroke: "var(" + color + ")",
      "stroke-dasharray": Math.max(0, (circ * pct) / 100 - 2) + " " + circ,
      "stroke-dashoffset": -offset,
      tabindex: 0,
      role: "button",
      "aria-label": name + " " + pct + "%",
    });
    offset += (circ * pct) / 100;
    circle.addEventListener("click", () => choose(i));
    circle.addEventListener("focus", () => choose(i));
    circle.addEventListener("keydown", (e) => {
      if (["Enter", " "].includes(e.key)) {
        e.preventDefault();
        choose(i);
      }
    });
    svg.append(circle);
    const button = node("button", "breakdown-row"),
      left = node("span"),
      dot = node("i", "legend-dot"),
      right = node("div");
    dot.style.background = "var(" + color + ")";
    left.append(dot, node("span", "", name));
    right.append(
      node("strong", "", pct + "%"),
      node("small", "", "约 " + num((row.totalKwh * pct) / 100) + " kWh"),
    );
    button.append(left, right);
    button.onclick = () =>
      choose(button.classList.contains("selected") ? null : i);
    buttons.push(button);
    legend.append(button);
  });
  wrapper.append(svg, center);
  target.append(wrapper, legend);
}
function renderRecords(rows) {
  const target = $("dailyRows");
  target.replaceChildren();
  $("recordCount").textContent = rows.length;
  $("moreRecords").hidden = rows.length <= recordsLimit;
  if (!rows.length) {
    empty(
      target,
      "这里会收好每一天",
      "选择其他日期范围，或上传第一张里程截图。",
    );
    return;
  }
  let lastMonth = "";
  rows
    .slice()
    .reverse()
    .slice(0, recordsLimit)
    .forEach((r) => {
      const month = r.date.slice(0, 7);
      if (month !== lastMonth) {
        target.append(node("p", "record-month", monthName(month)));
        lastMonth = month;
      }
      const button = node("button", "record-row"),
        date = node("span", "record-date"),
        text = node("span"),
        value = node("span", "record-value");
      text.append(
        node("strong", "", fullDate(r.date)),
        node("small", "", r.km === 0 ? "已记录 · 当天暂无行驶里程" : "已记录"),
      );
      date.append(node("span", "date-tile", Number(r.date.slice(-2))), text);
      value.append(
        node("span", "", num(r.km)),
        node("small", "", "km"),
        node("span", "", "›"),
      );
      button.append(date, value);
      button.onclick = () => openDay(r.date);
      target.append(button);
    });
}
function openDay(date) {
  daySelected = date;
  const row = data.daily.find((r) => r.date === date);
  $("dayKm").value = row ? row.km : "";
  $("dayKm").dataset.previous = row ? String(row.km) : "";
  $("dayEditError").textContent = "";
  $("dayTitle").textContent = fullDate(date);
  const target = $("dayDetail");
  target.replaceChildren();
  if (row) {
    const value = node("p", "day-number", num(row.km));
    value.append(node("small", "", " km"));
    target.append(
      value,
      node("p", "muted", "核对当天的实际里程，可在下方补充或修正。"),
    );
  } else
    target.append(
      node("p", "day-number", "未记录"),
      node(
        "p",
        "muted",
        "这一天暂时没有数据，不代表没有出行。请上传能覆盖这一天的原始截图。",
      ),
    );
  $("dayUpload").textContent = row ? "补充里程截图" : "上传覆盖这一天的截图";
  showDialog("dayDialog");
}
async function refresh() {
  if (refreshing) return;
  refreshing = true;
  $("refreshButton").disabled = true;
  try {
    const payload = await (await api("/api/data")).json();
    data = {
      daily: payload.daily.slice().sort((a, b) => a.date.localeCompare(b.date)),
      weekly: payload.weekly
        .slice()
        .sort((a, b) => a.period.localeCompare(b.period)),
      energy: payload.energy
        .slice()
        .sort((a, b) => a.period.localeCompare(b.period)),
    };
    selectedMileage = "";
    mileagePage = 0;
    lastSynced = new Intl.DateTimeFormat("zh-CN", {
      timeZone: "Asia/Shanghai",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date());
    $("connection").textContent = "已同步 · " + lastSynced;
    $("connection").classList.remove("stale");
    $("offlineBanner").hidden = true;
    render();
    // The count concerns the most recent 30 screenshots returned by the existing API.
    try {
      const recent = await (await api("/api/screenshots")).json();
      const pending = recent.filter((s) => s.ocr_status === "review").length;
      $("pendingCount").textContent = pending;
      $("pendingBanner").hidden = !pending;
    } catch (_) {}
  } catch (error) {
    $("connection").textContent = lastSynced
      ? "上次同步 · " + lastSynced
      : "尚未同步";
    $("connection").classList.add("stale");
    $("offlineBanner").hidden = false;
    throw error;
  } finally {
    refreshing = false;
    $("refreshButton").disabled = false;
  }
}
async function checkVersion() {
  try {
    const response = await fetch("/api/version?t=" + Date.now(), {
      cache: "no-store",
    });
    if (!response.ok) return;
    const { build } = await response.json();
    if (build !== BUILD && !busy && !document.querySelector("dialog[open]")) {
      const url = new URL(location.href);
      if (url.searchParams.get("v") === build) return;
      url.searchParams.set("v", build);
      location.replace(url);
    }
  } catch (_) {}
}
function saveBlob(blob, name) {
  const url = URL.createObjectURL(blob),
    link = node("a");
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}
async function download(path, name) {
  saveBlob(await (await api(path)).blob(), name);
}
function syncThemeButtons() {
  document.querySelectorAll("[data-theme-choice]").forEach((b) => {
    const active = b.dataset.themeChoice === window.LeapTheme.get();
    b.classList.toggle("active", active);
    b.setAttribute("aria-pressed", String(active));
  });
}
async function loadAdmin() {
  const [backups, screenshots, logs] = await Promise.all(
    ["/api/admin/backups", "/api/screenshots", "/api/admin/logs"].map(
      async (p) => (await api(p)).json(),
    ),
  );
  $("backupList").replaceChildren();
  backups.slice(0, 10).forEach((b) => {
    const row = node("div", "list-item"),
      text = node("span", "", b.created_at.slice(0, 16).replace("T", " ")),
      button = node("button", "", "下载");
    text.append(
      node("small", "", Math.round(b.bytes / 1024) + " KB · " + b.filename),
    );
    row.append(text, button);
    button.onclick = () =>
      download("/api/admin/backups/" + b.filename, b.filename).catch((e) =>
        notify(e.message),
      );
    $("backupList").append(row);
  });
  if (!backups.length)
    $("backupList").append(
      node("p", "muted", "还没有备份，现在就创建第一份。"),
    );
  if (backups.length > 10)
    $("backupList").append(
      node(
        "p",
        "muted",
        "显示最新 10 份，其余可通过备份 API 或 NAS 目录获取。",
      ),
    );
  $("screenshotList").replaceChildren();
  const labels = {
    done: "已计入手记",
    review: "待确认",
    failed: "识别失败",
    confirmed: "已核对",
    processing: "正在识别",
    done_with_warnings: "已合并，部分数据被拦截",
  };
  screenshots.forEach((s) => {
    const row = node("div", "list-item"),
      text = node(
        "span",
        s.ocr_status === "review" ? "status-review" : "",
        labels[s.ocr_status] || s.ocr_status,
      ),
      button = node(
        "button",
        "",
        s.ocr_status === "review" ? "去核对" : "查看",
      );
    text.append(
      node(
        "small",
        "",
        "#" + s.id + " · " + s.uploaded_at.slice(0, 16).replace("T", " "),
      ),
    );
    row.append(text, button);
    button.onclick = () => openReview(s).catch((e) => notify(e.message));
    $("screenshotList").append(row);
  });
  if (!screenshots.length)
    $("screenshotList").append(
      node("p", "muted", "上传后的截图和识别状态会出现在这里。"),
    );
  $("logList").replaceChildren(
    ...logs
      .slice(0, 30)
      .map((l) =>
        node(
          "p",
          "",
          l.created_at.slice(0, 16) +
            " · " +
            l.action +
            " · " +
            l.status +
            " · " +
            l.message,
        ),
      ),
  );
}
async function openAdmin() {
  showDialog("adminDialog");
  syncThemeButtons();
  try {
    await loadAdmin();
  } catch (e) {
    $("screenshotList").textContent = "暂时无法加载，请稍后再试。";
    notify(e.message);
  }
}
function reviewInput(field, label, value, type = "number") {
  const wrap = node("label", "", label),
    input = node("input");
  input.type = type;
  input.dataset.field = field;
  input.value = value ?? "";
  input.required = true;
  if (type === "number") {
    input.min = "0";
    input.step = "0.01";
  }
  wrap.append(input);
  return wrap;
}
function reviewPayload() {
  const result = { daily: [], weekly: [], energy: [] };
  $("reviewFields")
    .querySelectorAll("[data-kind]")
    .forEach((row) => {
      const obj = {};
      row
        .querySelectorAll("input")
        .forEach(
          (input) =>
            (obj[input.dataset.field] =
              input.type === "number" ? Number(input.value) : input.value),
        );
      if (row.dataset.kind !== "daily") {
        obj.period =
          (obj.start || "").replaceAll("-", "/") +
          " - " +
          (obj.end || "").replaceAll("-", "/");
        delete obj.start;
        delete obj.end;
      }
      result[row.dataset.kind].push(obj);
    });
  return result;
}
function renderReviewForm(draft) {
  $("reviewFields").replaceChildren();
  for (const [kind, title] of [
    ["daily", "每日里程"],
    ["weekly", "周能耗"],
    ["energy", "能耗构成"],
  ]) {
    $("reviewFields").append(node("h3", "", title));
    for (const item of draft[kind] || []) {
      const row = node(
        "div",
        kind === "energy" ? "review-energy" : "review-row",
      );
      row.dataset.kind = kind;
      const remove = node("button", "review-remove", "×");
      remove.type = "button";
      remove.setAttribute("aria-label", "移除此条" + title);
      remove.onclick = () => {
        row.remove();
        syncReviewJson();
      };
      if (kind === "daily") {
        row.append(
          reviewInput("date", "日期", item.date, "date"),
          reviewInput("km", "里程 km", item.km),
          remove,
        );
      } else {
        const [start = "", end = ""] = (item.period || "")
          .replaceAll("/", "-")
          .split(" - ");
        if (kind === "weekly") {
          row.className = "review-energy";
          const dates = node("div", "review-row");
          dates.append(
            reviewInput("start", "开始日期", start, "date"),
            reviewInput("end", "结束日期", end, "date"),
          );
          const values = node("div", "review-row");
          values.append(
            reviewInput("value", "kWh / 100km", item.value),
            remove,
          );
          row.append(dates, values);
        } else {
          const dates = node("div", "review-row");
          dates.append(
            reviewInput("start", "开始日期", start, "date"),
            reviewInput("end", "结束日期", end, "date"),
          );
          row.append(dates);
          const values = node("div", "review-row");
          values.append(
            reviewInput("totalKwh", "总电量 kWh", item.totalKwh),
            reviewInput("drive", "行车 %", item.drive),
            reviewInput("ac", "空调 %", item.ac),
            reviewInput("other", "其他 %", item.other),
          );
          row.append(values, remove);
        }
      }
      $("reviewFields").append(row);
    }
    const addButton = node("button", "review-add", "＋ 补充" + title);
    addButton.type = "button";
    addButton.onclick = () => {
      const current = reviewPayload(),
        start = add(monday(today()), -7),
        period =
          start.replaceAll("-", "/") +
          " - " +
          add(start, 6).replaceAll("-", "/");
      current[kind].push(
        kind === "daily"
          ? { date: today(), km: "" }
          : kind === "weekly"
            ? { period, value: "" }
            : { period, totalKwh: "", drive: "", ac: "", other: "" },
      );
      renderReviewForm(current);
      syncReviewJson();
    };
    $("reviewFields").append(addButton);
  }
}
function syncReviewJson() {
  if (!jsonDirty)
    $("reviewData").value = JSON.stringify(reviewPayload(), null, 2);
}
function applyReviewJson() {
  const obj = JSON.parse($("reviewData").value);
  if (!obj || ["daily", "weekly", "energy"].some((k) => !Array.isArray(obj[k])))
    throw new Error("数据必须包含 daily、weekly、energy 三个数组。");
  for (const [key, fields] of Object.entries({
    daily: ["date", "km"],
    weekly: ["period", "value"],
    energy: ["period", "totalKwh", "drive", "ac", "other"],
  })) {
    if (obj[key].some((r) => !r || fields.some((f) => !(f in r))))
      throw new Error(key + " 中有记录缺少字段。");
  }
  renderReviewForm(obj);
  jsonDirty = false;
  syncReviewJson();
}
async function openReview(s) {
  reviewId = s.id;
  const result = s.ocr_result || s;
  $("reviewWarnings").textContent =
    (result.warnings || []).join("；") ||
    s.error_message ||
    "请对照原图核对数值，确认后按原有保护规则合并。";
  reviewDraft = result.confirmed_data ||
    result.data || { daily: [], weekly: [], energy: [] };
  jsonDirty = false;
  renderReviewForm(reviewDraft);
  syncReviewJson();
  $("reviewResult").textContent = "";
  $("advancedReview").open = false;
  const old = $("reviewImage").src;
  if (old.startsWith("blob:")) URL.revokeObjectURL(old);
  $("reviewImage").src = URL.createObjectURL(
    await (await api("/api/screenshots/" + s.id + "/image")).blob(),
  );
  showDialog("reviewDialog");
}
function continueUploadEntry() {
  if (!pendingUploadEntry || !token || busy || document.querySelector("dialog[open]")) return;
  pendingUploadEntry = false;
  openUpload();
}
function openUpload() {
  if (busy) return;
  if (!token) {
    pendingUploadEntry = true;
    showDialog("loginDialog");
    return;
  }
  $("uploadForm").reset();
  $("captureDate").value = today();
  $("captureDate").max = today();
  $("fileLabel").textContent = "选择里程能耗截图";
  $("uploadResult").textContent = "";
  $("uploadResult").className = "result";
  const old = $("uploadPreview").src;
  if (old.startsWith("blob:")) URL.revokeObjectURL(old);
  $("uploadPreview").removeAttribute("src");
  $("uploadPreview").hidden = true;
  document
    .querySelectorAll(".upload-steps li")
    .forEach((li, i) => li.classList.toggle("active", i === 0));
  showDialog("uploadDialog");
}
function mergeMessage(result) {
  return (
    "已计入手记：新增 " +
    result.inserted +
    " 条，更新 " +
    result.updated +
    " 条，保留 " +
    result.unchanged +
    " 条。" +
    (result.rejected.length
      ? "\n" +
        result.rejected.length +
        " 条周能耗因偏差超过 20% 被拦截，历史值已保留。"
      : "")
  );
}
$("loginForm").onsubmit = async (e) => {
  e.preventDefault();
  const button = $("loginForm").querySelector("button");
  button.disabled = true;
  token = $("tokenInput").value.trim();
  try {
    await refresh();
    storage.clear("leapToken");
    try {
      ($("rememberToken").checked ? localStorage : sessionStorage).setItem(
        "leapToken",
        token,
      );
    } catch (_) {}
    $("tokenInput").value = "";
    $("loginError").textContent = "";
    $("loginDialog").close();
    continueUploadEntry();
  } catch (error) {
    $("loginError").textContent = error.message;
  } finally {
    button.disabled = false;
  }
};
document.querySelectorAll("[data-close]").forEach(
  (b) =>
    (b.onclick = () => {
      if (busy) {
        notify("正在保存，请稍候。");
        return;
      }
      $(b.dataset.close).close();
    }),
);
document.querySelectorAll("dialog").forEach((dialog) =>
  dialog.addEventListener("cancel", (event) => {
    if (busy) event.preventDefault();
  }),
);
document
  .querySelectorAll("[data-page]")
  .forEach((b) => (b.onclick = () => navigate(b.dataset.page)));
document
  .querySelectorAll("[data-go]")
  .forEach((b) => (b.onclick = () => navigate(b.dataset.go)));
document.querySelectorAll("[data-range]").forEach(
  (b) =>
    (b.onclick = () => {
      if (b.dataset.range === "custom") {
        $("dateError").textContent = "";
        showDialog("dateDialog");
      } else setRange(b.dataset.range);
    }),
);
document.querySelectorAll("[data-view]").forEach(
  (b) =>
    (b.onclick = () => {
      view = b.dataset.view;
      selectedMileage = "";
      mileagePage = 0;
      render();
    }),
);
document
  .querySelectorAll("[data-theme-choice]")
  .forEach(
    (b) => (b.onclick = () => window.LeapTheme.set(b.dataset.themeChoice)),
  );
window.addEventListener("appearancechange", syncThemeButtons);
$("applyDates").onclick = () => {
  const start = $("startDate").value,
    end = $("endDate").value;
  if (
    !start ||
    !end ||
    start > end ||
    start < "1900-01-01" ||
    (day(end) - day(start)) / 86400000 > 36600
  ) {
    $("dateError").textContent = "请选择有效的起止日期，范围不超过 100 年。";
    return;
  }
  custom = { start, end };
  setRange("custom");
  $("dateDialog").close();
};
$("calendarPrev").onclick = () => {
  const d = day(calendar + "-01");
  d.setUTCMonth(d.getUTCMonth() - 1);
  calendar = iso(d).slice(0, 7);
  renderCalendar();
};
$("calendarNext").onclick = () => {
  const d = day(calendar + "-01");
  d.setUTCMonth(d.getUTCMonth() + 1);
  calendar = iso(d).slice(0, 7);
  renderCalendar();
};
$("moreRecords").onclick = () => {
  recordsLimit += 60;
  renderRecords(selectedRows());
};
$("energyPeriod").onchange = renderBreakdown;
function turnMileagePage(delta) {
  mileagePage = Math.max(0, mileagePage + delta);
  selectedMileage = "";
  renderMileage(selectedRows());
}
$("mileageNewer").onclick = () => turnMileagePage(-1);
$("mileageOlder").onclick = () => turnMileagePage(1);
$("mileageLatest").onclick = () => {
  mileagePage = 0;
  selectedMileage = "";
  renderMileage(selectedRows());
};
$("dayEditForm").onsubmit = async (event) => {
  event.preventDefault();
  if (busy || !$("dayEditForm").reportValidity()) return;
  const km = Number($("dayKm").value);
  if ($("dayKm").value.trim() === "" || !Number.isFinite(km) || km < 0 || km > 3000) return;
  busy = true;
  $("daySave").disabled = true;
  $("dayEditError").textContent = "";
  try {
    const saved = await (await api("/api/daily/" + daySelected, {
      method: "PUT", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({km, expected_km: $("dayKm").dataset.previous === "" ? null : Number($("dayKm").dataset.previous)}),
    })).json();
    data.daily = data.daily.filter(r => r.date !== saved.date).concat(saved).sort((a,b) => a.date.localeCompare(b.date));
    selectedMileage = "";
    mileagePage = 0;
    render();
    $("dayDialog").close();
    notify("里程已保存，统计与图表已更新");
  } catch (error) {
    $("dayEditError").textContent = error.message;
  } finally {
    busy = false;
    $("daySave").disabled = false;
  }
};
$("dayUpload").onclick = () => {
  if (busy) return;
  $("dayDialog").close();
  openUpload();
  notify("请选择截图实际拍摄日期，不一定是所补记录的日期。");
};
$("uploadButton").onclick = openUpload;
$("mobileUpload").onclick = openUpload;
$("screenshotFile").onchange = () => {
  const file = $("screenshotFile").files[0];
  if (!file) return;
  const preview = $("uploadPreview");
  if (preview.src.startsWith("blob:")) URL.revokeObjectURL(preview.src);
  if (file.size > 15 * 1024 * 1024) {
    $("screenshotFile").value = "";
    preview.hidden = true;
    notify("图片超过 15 MB，请选择原始手机截图。");
    return;
  }
  preview.src = URL.createObjectURL(file);
  preview.hidden = false;
  $("fileLabel").textContent = file.name;
};
$("uploadForm").onsubmit = async (e) => {
  e.preventDefault();
  if (busy) return;
  const file = $("screenshotFile").files[0];
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  form.append("captured_date", $("captureDate").value);
  busy = true;
  Array.from($("uploadForm").elements).forEach((el) => (el.disabled = true));
  $("uploadResult").className = "result working";
  $("uploadResult").textContent = "正在识别与校验，通常需要几秒到半分钟。";
  document
    .querySelectorAll(".upload-steps li")
    .forEach((li, i) => li.classList.toggle("active", i <= 1));
  try {
    const result = await (
      await api("/api/upload", { method: "POST", body: form })
    ).json();
    if (result.status === "review") {
      $("uploadResult").className = "result";
      $("uploadResult").textContent = "有几处需要你核对，数据尚未计入手记。";
      await openReview(result);
    } else {
      $("uploadResult").className = "result success";
      $("uploadResult").textContent = mergeMessage(result.merge);
      document
        .querySelectorAll(".upload-steps li")
        .forEach((li) => li.classList.add("active"));
    }
    await refresh();
  } catch (error) {
    $("uploadResult").className = "result error";
    $("uploadResult").textContent = error.message;
  } finally {
    busy = false;
    Array.from($("uploadForm").elements).forEach((el) => (el.disabled = false));
  }
};
$("reviewFields").onsubmit = (e) => e.preventDefault();
$("reviewFields").oninput = syncReviewJson;
$("reviewData").oninput = () => {
  jsonDirty = true;
};
$("applyReviewJson").onclick = () => {
  try {
    applyReviewJson();
    notify("已更新核对表单");
  } catch (error) {
    $("reviewResult").textContent = error.message;
  }
};
$("confirmButton").onclick = async () => {
  if (busy) return;
  try {
    if (jsonDirty) applyReviewJson();
  } catch (error) {
    $("reviewResult").textContent = error.message;
    return;
  }
  if (!$("reviewFields").reportValidity()) return;
  const dataset = reviewPayload();
  if (!Object.values(dataset).some((rows) => rows.length)) {
    $("reviewResult").textContent = "请至少补充一条可确认的记录。";
    return;
  }
  busy = true;
  $("confirmButton").disabled = true;
  try {
    const result = await (
      await api("/api/screenshots/" + reviewId + "/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(dataset),
      })
    ).json();
    $("reviewResult").textContent = mergeMessage(result);
    $("reviewResult").className = "result success";
    await refresh();
    if ($("adminDialog").open) await loadAdmin();
  } catch (error) {
    $("reviewResult").textContent = error.message;
    $("reviewResult").className = "result error";
  } finally {
    busy = false;
    $("confirmButton").disabled = false;
  }
};
$("settingsButton").onclick = openAdmin;
$("pendingBanner").onclick = async () => {
  await openAdmin();
  $("screenshotsHeading").scrollIntoView({ block: "start" });
};
$("backupButton").onclick = async () => {
  $("backupButton").disabled = true;
  $("backupButton").textContent = "正在备份…";
  try {
    const r = await (await api("/api/admin/backup", { method: "POST" })).json();
    notify(
      r.webdav === "failed"
        ? "本地备份已完成，异地上传失败，请检查配置。"
        : "备份完成，多一份安心。",
    );
    await loadAdmin();
  } catch (error) {
    notify(error.message);
  } finally {
    $("backupButton").disabled = false;
    $("backupButton").textContent = "立即备份";
  }
};
$("exportButton").onclick = () =>
  saveBlob(
    new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
    "leap-" + today() + ".json",
  );
$("logoutButton").onclick = () => {
  token = "";
  storage.clear("leapToken");
  data = { daily: [], weekly: [], energy: [] };
  lastSynced = "";
  $("pendingBanner").hidden = true;
  $("backupList").replaceChildren();
  $("screenshotList").replaceChildren();
  $("logList").replaceChildren();
  $("reviewFields").replaceChildren();
  $("reviewData").value = "";
  const image = $("reviewImage");
  if (image.src.startsWith("blob:")) URL.revokeObjectURL(image.src);
  image.removeAttribute("src");
  document.querySelectorAll("dialog[open]").forEach((d) => d.close());
  navigate("overview");
  $("connection").textContent = "尚未登录";
  showDialog("loginDialog");
};
$("refreshButton").onclick = $("retryButton").onclick = () =>
  refresh().then(continueUploadEntry).catch((e) => notify(e.message));
$("buildLabel").textContent = "行程手记 · " + BUILD;
$("startDate").value = today().slice(0, 7) + "-01";
$("endDate").value = today();
syncThemeButtons();
render();
checkVersion();
if (token) refresh().then(continueUploadEntry).catch(() => {});
else showDialog("loginDialog");
// Live data stays in memory only; no service worker or offline cache.
function resume() {
  if (!document.hidden) {
    checkVersion();
    if (token && !busy) refresh().then(continueUploadEntry).catch(() => {});
  }
}
document.addEventListener("visibilitychange", resume);
window.addEventListener("pageshow", (event) => {
  checkVersion();
  // Restored navigation may reuse the document; never reset a selected screenshot.
  if (event.persisted && uploadEntry && !busy && !document.querySelector("dialog[open]")) {
    pendingUploadEntry = true;
    if (token) refresh().then(continueUploadEntry).catch(() => {});
    else showDialog("loginDialog");
  }
});
setInterval(resume, 60000);
let resizeTimer;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    if (pageName === "overview") renderMileage(selectedRows());
    if (pageName === "energy")
      renderEnergyChart(data.weekly.filter((r) => periodInRange(r.period)));
  }, 150);
});
