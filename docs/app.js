const state = {
  items: [],
  favorites: new Set(JSON.parse(localStorage.getItem("favorites") || "[]")),
  selectedIndustries: new Set(),
  selectedPrefectures: new Set(),
  mapRegion: "",
  page: 1,
};
const $ = (id) => document.getElementById(id);
const REGION_PREFECTURES = {
  北海道: ["北海道"],
  東北: ["青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県"],
  関東: ["茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県"],
  中部: ["新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県", "静岡県", "愛知県"],
  近畿: ["三重県", "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県"],
  中国: ["鳥取県", "島根県", "岡山県", "広島県", "山口県"],
  四国: ["徳島県", "香川県", "愛媛県", "高知県"],
  九州: ["福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"],
};
const PREFECTURES = Object.values(REGION_PREFECTURES).flat();
const PREFECTURE_REGION = Object.fromEntries(Object.entries(REGION_PREFECTURES).flatMap(([region, prefectures]) => prefectures.map((prefecture) => [prefecture, region])));
const MAP_POINTS = {
  北海道: [82, 9],
  青森県: [72, 21], 岩手県: [75, 28], 宮城県: [74, 36], 秋田県: [68, 29], 山形県: [69, 38], 福島県: [70, 46],
  茨城県: [72, 55], 栃木県: [68, 52], 群馬県: [63, 52], 埼玉県: [66, 58], 千葉県: [74, 62], 東京都: [68, 63], 神奈川県: [65, 68],
  新潟県: [58, 43], 富山県: [47, 47], 石川県: [42, 47], 福井県: [39, 54], 山梨県: [58, 61], 長野県: [55, 54], 岐阜県: [48, 60], 静岡県: [57, 69], 愛知県: [49, 68],
  三重県: [45, 73], 滋賀県: [39, 65], 京都府: [35, 65], 大阪府: [34, 70], 兵庫県: [29, 68], 奈良県: [38, 72], 和歌山県: [35, 78],
  鳥取県: [22, 61], 島根県: [16, 62], 岡山県: [24, 68], 広島県: [18, 70], 山口県: [10, 73],
  徳島県: [28, 80], 香川県: [27, 74], 愛媛県: [19, 81], 高知県: [23, 86],
  福岡県: [6, 81], 佐賀県: [2, 84], 長崎県: [0, 90], 熊本県: [7, 90], 大分県: [13, 86], 宮崎県: [12, 96], 鹿児島県: [6, 99], 沖縄県: [10, 116],
};
const REGION_VIEWBOX = {
  北海道: [70, 0, 30, 24],
  東北: [64, 16, 16, 35],
  関東: [60, 48, 18, 24],
  中部: [36, 39, 28, 36],
  近畿: [26, 60, 24, 23],
  中国: [6, 57, 23, 19],
  四国: [16, 72, 16, 18],
  九州: [-2, 78, 20, 25],
};

function yen(n, type) {
  if (type === "unlimited") return "全額・実費";
  if (Number.isFinite(n) && n > 0) return `${n.toLocaleString()}円`;
  if (n === 0) return "支給なし";
  return "金額不明";
}

function score(i) {
  return i.transport_type === "unlimited" ? 99999999 : (i.transport_amount ?? -1);
}

function fmtDate(v) {
  if (!v) return "不明";
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? v : d.toLocaleString("ja-JP", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function fmtEventDate(v) {
  const d = new Date(`${v}T00:00:00`);
  return Number.isNaN(d.getTime()) ? v : d.toLocaleDateString("ja-JP", { month: "numeric", day: "numeric" });
}

function formatEventDates(dates = [], limit = 4) {
  if (!dates.length) return "日付未定";
  const visible = dates.slice(0, limit).map(fmtEventDate);
  return `${visible.join("・")}${dates.length > limit ? ` +${dates.length - limit}` : ""}`;
}

function formatSchedule(i) {
  const dates = i.event_dates || [];
  const original = i.schedule_text || "開催日の明示なし";
  if (!dates.length) return original;
  return `抽出日: ${formatEventDates(dates, 8)} / ${original}`;
}

function dateMatches(i, from, to, includeUnknown) {
  const dates = i.event_dates || [];
  if (!from && !to) return true;
  if (!dates.length) return includeUnknown;
  return dates.some((v) => (!from || v >= from) && (!to || v <= to));
}

function durationFlags(i) {
  const text = [i.course, i.schedule_text].join(" ").replace(/\s+/g, " ");
  const oneDay = /実施日数\s*[：:]?\s*(1|１)\s*日/.test(text)
    || /(1|１)\s*day/i.test(text)
    || /ワンデー|半日/.test(text)
    || /(1|１)\s*日(?:開催|仕事体験|体験)/.test(text);
  const multiDay = /実施日数[^。]*((2|２|3|３|4|４|5|５|6|６|7|７|8|８|9|９|10|１０)\s*日|数日|複数日|連日|週間|週|カ月|ヶ月|ヵ月|か月|月未満)/.test(text)
    || /(?:^|[^0-9０-９])(2|２|3|３|4|４|5|５|6|６|7|７|8|８|9|９|10|１０)\s*(?:日|days?)(?:\s|開催|間|程度|以上|以内|～|〜|-|・|、|,)/i.test(text)
    || /(?:2|２)\s*週間|(?:1|１)\s*週間|(?:1|１)\s*(?:カ月|ヶ月|ヵ月|か月)|長期|連続/.test(text);
  return { oneDay, multiDay, unknown: !oneDay && !multiDay };
}

function isOneDay(i) {
  return durationFlags(i).oneDay;
}

function isMultiDay(i) {
  return durationFlags(i).multiDay;
}

function durationTags(i) {
  const flags = durationFlags(i);
  const tags = [];
  if (flags.oneDay) tags.push("1Dayあり");
  if (flags.multiDay) tags.push("複数日あり");
  if (!tags.length) tags.push("日数不明");
  return tags;
}

function countByLocation() {
  const counts = new Map();
  for (const item of state.items) {
    for (const location of item.locations || []) {
      counts.set(location, (counts.get(location) || 0) + 1);
    }
  }
  return counts;
}

function regionCount(region, counts) {
  return REGION_PREFECTURES[region].reduce((sum, prefecture) => sum + (counts.get(prefecture) || 0), 0);
}

function setRegion(region) {
  state.mapRegion = region;
  $("regionFilter").value = region;
  state.page = 1;
  populateLocationFilters();
  render();
}

function togglePrefecture(prefecture) {
  state.selectedPrefectures.has(prefecture) ? state.selectedPrefectures.delete(prefecture) : state.selectedPrefectures.add(prefecture);
  state.page = 1;
  populatePrefectureOptions();
  renderMap();
  render();
}

function renderRegionRail(counts) {
  const rail = $("regionRail");
  rail.innerHTML = "";
  for (const region of Object.keys(REGION_PREFECTURES)) {
    const count = regionCount(region, counts);
    if (!count) continue;
    const button = document.createElement("button");
    button.type = "button";
    button.className = `region-pill${state.mapRegion === region ? " active" : ""}`;
    button.innerHTML = `<span>${region}</span><strong>${count.toLocaleString()}</strong>`;
    button.onclick = () => setRegion(region);
    rail.appendChild(button);
  }
}

function renderMap() {
  const stage = $("mapStage");
  const counts = countByLocation();
  const region = state.mapRegion || $("regionFilter").value;
  const focus = region ? REGION_VIEWBOX[region] : null;
  const [x, y, width, height] = focus || [-3, 0, 106, 122];
  const visiblePrefectures = region ? REGION_PREFECTURES[region] : PREFECTURES;
  const max = Math.max(1, ...visiblePrefectures.map((prefecture) => counts.get(prefecture) || 0));
  renderRegionRail(counts);
  $("mapHint").textContent = region ? `${region}を拡大中。件数バッジ付きの都道府県を複数選択できます。` : "地方を押すと拡大、都道府県を押すと複数選択できます。";
  stage.style.setProperty("--map-x", `${x}`);
  stage.style.setProperty("--map-y", `${y}`);
  stage.style.setProperty("--map-w", `${width}`);
  stage.style.setProperty("--map-h", `${height}`);
  const scale = Math.min(5.2, 100 / width);
  stage.style.setProperty("--map-scale", `${scale}`);
  stage.style.setProperty("--node-scale", `${1 / scale}`);
  stage.style.setProperty("--map-cx", `${x + width / 2}`);
  stage.style.setProperty("--map-cy", `${y + height / 2}`);
  stage.innerHTML = "";

  const plane = document.createElement("div");
  plane.className = "map-plane";
  stage.appendChild(plane);

  for (const prefecture of PREFECTURES) {
    const count = counts.get(prefecture) || 0;
    const [px, py] = MAP_POINTS[prefecture];
    const node = document.createElement("button");
    const selected = state.selectedPrefectures.has(prefecture);
    const currentRegion = PREFECTURE_REGION[prefecture];
    const dimmed = region && currentRegion !== region;
    const size = 28 + Math.round((count / max) * 18);
    node.type = "button";
    node.className = `map-node${selected ? " selected" : ""}${dimmed ? " dimmed" : ""}`;
    node.style.left = `${px}%`;
    node.style.top = `${py}%`;
    node.style.width = `${size}px`;
    node.style.height = `${size}px`;
    node.style.setProperty("--pulse", String(Math.max(0.12, count / max)));
    node.disabled = !count;
    node.title = `${prefecture} ${count.toLocaleString()}件`;
    node.innerHTML = `<span>${prefecture.replace(/[都道府県]/g, "")}</span><strong>${count.toLocaleString()}</strong>`;
    node.onclick = () => togglePrefecture(prefecture);
    plane.appendChild(node);
  }
}

function countByIndustry() {
  const counts = new Map();
  for (const item of state.items) {
    for (const industry of item.industries || []) {
      counts.set(industry, (counts.get(industry) || 0) + 1);
    }
  }
  return counts;
}

function createFacetOption(value, count, checked, onChange) {
  const label = document.createElement("label");
  label.className = "facet-option";
  const input = document.createElement("input");
  input.type = "checkbox";
  input.value = value;
  input.checked = checked;
  input.addEventListener("input", onChange);
  const name = document.createElement("span");
  name.textContent = value;
  const badge = document.createElement("small");
  badge.textContent = count.toLocaleString();
  label.append(input, name, badge);
  return label;
}

function populateIndustryOptions() {
  const root = $("industryOptions");
  const counts = countByIndustry();
  const industries = [...counts.keys()].sort((a, b) => a.localeCompare(b, "ja"));
  state.selectedIndustries = new Set([...state.selectedIndustries].filter((industry) => counts.has(industry)));
  root.innerHTML = "";
  for (const industry of industries) {
    root.appendChild(createFacetOption(industry, counts.get(industry), state.selectedIndustries.has(industry), (event) => {
      event.target.checked ? state.selectedIndustries.add(industry) : state.selectedIndustries.delete(industry);
      state.page = 1;
      render();
    }));
  }
}

function appendOption(select, value, label) {
  const option = document.createElement("option");
  option.value = value;
  option.textContent = label;
  select.appendChild(option);
}

function populateLocationFilters() {
  const regionSelect = $("regionFilter");
  const selectedRegion = regionSelect.value;
  const counts = countByLocation();

  regionSelect.innerHTML = '<option value="">すべての地方</option>';
  for (const region of Object.keys(REGION_PREFECTURES)) {
    const count = REGION_PREFECTURES[region].reduce((sum, prefecture) => sum + (counts.get(prefecture) || 0), 0);
    if (!count) continue;
    appendOption(regionSelect, region, `${region} (${count})`);
  }
  regionSelect.value = [...regionSelect.options].some((option) => option.value === selectedRegion) ? selectedRegion : "";
  state.mapRegion = regionSelect.value;
  populatePrefectureOptions();
  renderMap();
}

function populatePrefectureOptions() {
  const root = $("prefectureOptions");
  const counts = countByLocation();
  const region = $("regionFilter").value;
  const basePrefectures = region ? REGION_PREFECTURES[region] : PREFECTURES;
  const availablePrefectures = basePrefectures.filter((prefecture) => counts.has(prefecture));
  const otherLocations = region ? [] : [...counts.keys()].filter((location) => !PREFECTURES.includes(location)).sort((a, b) => a.localeCompare(b, "ja"));
  const available = new Set([...availablePrefectures, ...otherLocations]);
  state.selectedPrefectures = new Set([...state.selectedPrefectures].filter((prefecture) => available.has(prefecture)));

  root.innerHTML = "";
  for (const location of [...availablePrefectures, ...otherLocations]) {
    root.appendChild(createFacetOption(location, counts.get(location), state.selectedPrefectures.has(location), (event) => {
      event.target.checked ? state.selectedPrefectures.add(location) : state.selectedPrefectures.delete(location);
      state.page = 1;
      renderMap();
      render();
    }));
  }
}

function locationMatches(i, region, prefectures) {
  const locations = i.locations || [];
  if (region && !locations.some((location) => REGION_PREFECTURES[region]?.includes(location))) return false;
  if (prefectures.size && !locations.some((location) => prefectures.has(location))) return false;
  return true;
}

function filterLabel(id) {
  const el = $(id);
  if (!el) return "";
  if (el.tagName === "SELECT") return el.selectedOptions[0]?.textContent.replace(/\s\(\d+\)$/, "") || "";
  return el.value;
}

function summarizeSet(values, limit = 3) {
  const list = [...values];
  if (list.length <= limit) return list.join("・");
  return `${list.slice(0, limit).join("・")} +${list.length - limit}`;
}

function renderActiveFilters() {
  const filters = [];
  const min = $("minAmount").value;
  const query = $("query").value.trim();
  if (query) filters.push(`検索: ${query}`);
  if (min !== "0") filters.push(`支給額: ${filterLabel("minAmount")}`);
  if (state.selectedIndustries.size) filters.push(`業種: ${summarizeSet(state.selectedIndustries)}`);
  if ($("regionFilter").value) filters.push(`地方: ${filterLabel("regionFilter")}`);
  if (state.selectedPrefectures.size) filters.push(`都道府県: ${summarizeSet(state.selectedPrefectures)}`);
  if ($("dateFrom").value || $("dateTo").value) filters.push(`日付: ${$("dateFrom").value || "指定なし"} - ${$("dateTo").value || "指定なし"}`);
  if ($("oneDayOnly").checked) filters.push("1Dayあり");
  if ($("multiDayOnly").checked) filters.push("複数日あり");
  if ($("excludeUnknown").checked) filters.push("金額不明を除外");
  if ($("lodgingOnly").checked) filters.push("宿泊費あり");
  if ($("favoritesOnly").checked) filters.push("お気に入り");
  if ($("includeUnknownDates").checked) filters.push("日付未定も含める");
  if ($("showClosed").checked) filters.push("終了・満席も表示");

  $("activeFilters").innerHTML = "";
  if (!filters.length) {
    const span = document.createElement("span");
    span.className = "filter-chip muted";
    span.textContent = "条件なし";
    $("activeFilters").appendChild(span);
    return;
  }
  for (const filter of filters) {
    const span = document.createElement("span");
    span.className = "filter-chip";
    span.textContent = filter;
    $("activeFilters").appendChild(span);
  }
}

function updatePager(pageCount) {
  const status = `${state.page.toLocaleString()} / ${pageCount.toLocaleString()}`;
  $("pageStatus").textContent = status;
  $("pageStatusBottom").textContent = status;
  for (const id of ["prevPage", "prevPageBottom"]) $(id).disabled = state.page <= 1;
  for (const id of ["nextPage", "nextPageBottom"]) $(id).disabled = state.page >= pageCount;
}

function movePage(delta) {
  state.page += delta;
  render();
  document.querySelector(".summary").scrollIntoView({ behavior: "smooth", block: "start" });
}

function render() {
  const q = $("query").value.trim().toLowerCase();
  const min = +$("minAmount").value;
  const region = $("regionFilter").value;
  const from = $("dateFrom").value;
  const to = $("dateTo").value;
  let items = state.items.filter((i) => {
    const text = [i.company, i.course, i.schedule_text, i.eligibility_text, ...(i.locations || []), ...(i.industries || [])].join(" ").toLowerCase();
    if (q && !text.includes(q)) return false;
    if (state.selectedIndustries.size && !(i.industries || []).some((industry) => state.selectedIndustries.has(industry))) return false;
    if (!locationMatches(i, region, state.selectedPrefectures)) return false;
    if ($("oneDayOnly").checked && !isOneDay(i)) return false;
    if ($("multiDayOnly").checked && !isMultiDay(i)) return false;
    if (!$("showClosed").checked && i.status && i.status !== "open") return false;
    if (min === 99999999 && i.transport_type !== "unlimited") return false;
    if (min > 0 && min !== 99999999 && score(i) < min) return false;
    if ($("excludeUnknown").checked && ["unknown", "conditional"].includes(i.transport_type)) return false;
    if ($("lodgingOnly").checked && !i.lodging_provided) return false;
    if ($("favoritesOnly").checked && !state.favorites.has(i.id)) return false;
    if (!dateMatches(i, from, to, $("includeUnknownDates").checked)) return false;
    return true;
  });

  const sort = $("sortBy").value;
  items.sort((a, b) => (
    sort === "amount" ? score(b) - score(a)
      : sort === "date" ? ((a.event_dates?.[0] || "9999").localeCompare(b.event_dates?.[0] || "9999"))
      : sort === "company" ? a.company.localeCompare(b.company, "ja")
      : new Date(b.last_checked) - new Date(a.last_checked)
  ));

  $("results").innerHTML = "";
  const total = items.length;
  const pageSize = +$("pageSize").value;
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  state.page = Math.min(Math.max(1, state.page), pageCount);
  const start = total ? (state.page - 1) * pageSize : 0;
  const visibleItems = items.slice(start, start + pageSize);
  const end = start + visibleItems.length;
  $("count").textContent = `${total.toLocaleString()}件`;
  $("range").textContent = total ? `${(start + 1).toLocaleString()}-${end.toLocaleString()}件を表示` : "表示なし";
  updatePager(pageCount);
  $("empty").hidden = total !== 0;
  renderActiveFilters();
  for (const i of visibleItems) {
    const node = $("cardTemplate").content.cloneNode(true);
    node.querySelector("h2").textContent = i.company;
    node.querySelector(".course").textContent = i.course || "コース名不明";
    node.querySelector(".status").textContent = i.status === "closed" ? "終了・満席" : i.status === "cancelled" ? "中止" : i.is_new ? "新着" : "掲載中";
    node.querySelector(".transport").textContent = yen(i.transport_amount, i.transport_type);
    node.querySelector(".industries").textContent = (i.industries || []).join("・") || "記載なし";
    node.querySelector(".lodging").textContent = i.lodging_text || "記載なし";
    node.querySelector(".locations").textContent = (i.locations || []).join("・") || "記載なし";
    node.querySelector(".dates").textContent = formatSchedule(i);
    node.querySelector(".checked").textContent = fmtDate(i.last_checked);
    node.querySelector(".original").textContent = i.transport_original || "交通費の原文を取得できませんでした。";

    const a = node.querySelector(".open");
    a.href = i.url;
    const fav = node.querySelector(".favorite");
    fav.textContent = state.favorites.has(i.id) ? "★" : "☆";
    fav.onclick = () => {
      state.favorites.has(i.id) ? state.favorites.delete(i.id) : state.favorites.add(i.id);
      localStorage.setItem("favorites", JSON.stringify([...state.favorites]));
      render();
    };

    const tags = node.querySelector(".tags");
    const tagValues = [
      [yen(i.transport_amount, i.transport_type), true],
      ...durationTags(i).map((tag) => [tag, false]),
      [(i.industries || [])[0] || "業種不明", false],
      [formatEventDates(i.event_dates, 3), false],
      [i.lodging_provided ? "宿泊費あり" : "宿泊費不明", false],
      ...(i.locations || []).slice(0, 2).map((x) => [x, false]),
    ];
    for (const [txt, strong] of tagValues) {
      const s = document.createElement("span");
      s.className = `tag${strong ? " strong" : ""}`;
      s.textContent = txt;
      tags.appendChild(s);
    }
    $("results").appendChild(node);
  }
}

function clearFilters() {
  for (const id of ["query", "dateFrom", "dateTo"]) $(id).value = "";
  for (const id of ["minAmount", "regionFilter"]) $(id).value = "";
  $("minAmount").value = "0";
  state.selectedIndustries.clear();
  state.selectedPrefectures.clear();
  state.mapRegion = "";
  for (const id of ["oneDayOnly", "multiDayOnly", "excludeUnknown", "lodgingOnly", "favoritesOnly", "includeUnknownDates", "showClosed"]) $(id).checked = false;
  $("pageSize").value = "50";
  state.page = 1;
  populateIndustryOptions();
  populateLocationFilters();
  render();
}

async function load() {
  try {
    const r = await fetch(`data/jobs.json?t=${Date.now()}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    state.items = data.items || [];
    populateIndustryOptions();
    populateLocationFilters();
    const stats = data.stats || {};
    const supported = stats.transport_supported_courses ?? stats.displayed_courses ?? state.items.length;
    const displayed = stats.displayed_courses ?? state.items.length;
    const known = (stats.amount_known_courses ?? 0) + (stats.amount_unlimited_courses ?? 0);
    const scienceExcluded = stats.excluded_science_only_courses ?? 0;
    const kantoExcluded = stats.excluded_kanto_only_courses ?? 0;
    const oneDayCount = state.items.filter(isOneDay).length;
    const multiDayCount = state.items.filter(isMultiDay).length;
    $("updatedAt").textContent = `更新 ${fmtDate(data.generated_at)} / 表示 ${displayed.toLocaleString()}件 / 交通費あり ${supported.toLocaleString()}件 / 1Day ${oneDayCount.toLocaleString()}件 / 複数日 ${multiDayCount.toLocaleString()}件 / 関東のみ除外 ${kantoExcluded.toLocaleString()}件 / 理系除外 ${scienceExcluded.toLocaleString()}件 / 金額判定 ${known.toLocaleString()}件`;
    render();
  } catch (e) {
    $("empty").hidden = false;
    $("empty").textContent = `データ読込に失敗しました: ${e.message}`;
  }
}

for (const id of ["minAmount", "sortBy", "oneDayOnly", "multiDayOnly", "excludeUnknown", "lodgingOnly", "favoritesOnly", "query", "dateFrom", "dateTo", "includeUnknownDates", "showClosed", "pageSize"]) {
  $(id).addEventListener("input", () => {
    state.page = 1;
    render();
  });
}
$("regionFilter").addEventListener("input", () => {
  state.page = 1;
  state.mapRegion = $("regionFilter").value;
  populateLocationFilters();
  render();
});
$("clearIndustries").onclick = () => {
  state.selectedIndustries.clear();
  state.page = 1;
  populateIndustryOptions();
  render();
};
$("clearPrefectures").onclick = () => {
  state.selectedPrefectures.clear();
  state.page = 1;
  populatePrefectureOptions();
  renderMap();
  render();
};
$("mapReset").onclick = () => {
  state.mapRegion = "";
  $("regionFilter").value = "";
  state.page = 1;
  populateLocationFilters();
  render();
};
$("prevPage").onclick = () => {
  movePage(-1);
};
$("nextPage").onclick = () => {
  movePage(1);
};
$("prevPageBottom").onclick = () => movePage(-1);
$("nextPageBottom").onclick = () => movePage(1);
$("clearFilters").onclick = clearFilters;
$("refresh").onclick = load;
if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js");
load();
