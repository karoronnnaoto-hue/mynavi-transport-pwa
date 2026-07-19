const state = {
  items: [],
  users: [],
  activeUserId: "",
  selectedIndustries: new Set(),
  selectedPrefectures: new Set(),
  mapRegion: "",
  view: "all",
  page: 1,
};
const $ = (id) => document.getElementById(id);
const STAGES = {
  checking: "確認中",
  planned: "参加予定",
  confirmed: "確定",
};
const STORAGE = {
  users: "internshipUsers",
  activeUser: "activeInternshipUser",
  legacyFavorites: "favorites",
  legacyStages: "internshipStages",
};
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
const MAP_TILES = {
  沖縄県: [25, 2, 3, 3],
  鹿児島県: [20, 4, 3, 3],
  熊本県: [17, 3, 3, 3],
  宮崎県: [17, 6, 4, 3],
  長崎県: [13, 2, 3, 3],
  佐賀県: [13, 5, 3, 3],
  福岡県: [10, 5, 3, 3],
  大分県: [10, 8, 3, 3],
  山口県: [12, 11, 3, 4],
  島根県: [9, 14, 3, 5],
  広島県: [13, 15, 3, 4],
  鳥取県: [9, 18, 2, 4],
  岡山県: [13, 19, 3, 3],
  愛媛県: [17, 15, 3, 4],
  香川県: [16, 19, 3, 4],
  高知県: [20, 17, 3, 5],
  徳島県: [19, 22, 3, 3],
  兵庫県: [12, 22, 4, 3],
  京都府: [9, 24, 4, 3],
  大阪府: [15, 25, 2, 3],
  和歌山県: [18, 25, 3, 3],
  滋賀県: [10, 27, 3, 3],
  奈良県: [15, 28, 3, 3],
  三重県: [16, 30, 5, 3],
  石川県: [4, 29, 4, 3],
  福井県: [8, 29, 3, 3],
  富山県: [4, 32, 3, 3],
  新潟県: [3, 35, 3, 5],
  岐阜県: [11, 30, 4, 3],
  愛知県: [15, 32, 3, 3],
  長野県: [10, 34, 5, 3],
  山梨県: [15, 37, 3, 3],
  静岡県: [18, 36, 3, 5],
  秋田県: [8, 42, 3, 3],
  山形県: [11, 42, 3, 3],
  福島県: [15, 43, 3, 4],
  青森県: [5, 45, 3, 4],
  岩手県: [8, 46, 4, 3],
  宮城県: [12, 46, 3, 3],
  群馬県: [18, 42, 2, 3],
  栃木県: [18, 46, 2, 3],
  埼玉県: [20, 45, 2, 3],
  東京都: [22, 45, 1, 3],
  神奈川県: [23, 45, 2, 3],
  茨城県: [20, 49, 3, 3],
  千葉県: [22, 49, 4, 2],
  北海道: [1, 48, 5, 7],
};
const MAP_BLOCKS = {
  北海道: [[8, 22, 20, 44], [20, 10, 52, 70], [42, 0, 36, 92], [66, 18, 28, 56]],
  青森県: [[4, 18, 30, 56], [26, 0, 44, 92], [56, 18, 34, 64]],
  岩手県: [[0, 18, 34, 64], [24, 4, 68, 82], [70, 18, 30, 70]],
  宮城県: [[0, 10, 34, 78], [24, 0, 52, 94], [64, 18, 36, 68]],
  秋田県: [[6, 14, 32, 68], [28, 0, 52, 86], [68, 12, 30, 62]],
  山形県: [[0, 18, 30, 68], [22, 0, 56, 88], [70, 12, 30, 66]],
  福島県: [[8, 10, 30, 76], [28, 0, 50, 96], [66, 16, 34, 72]],
  新潟県: [[0, 30, 28, 58], [18, 6, 34, 84], [42, 0, 28, 100], [66, 10, 34, 74]],
  石川県: [[0, 30, 28, 54], [22, 14, 34, 72], [50, 0, 28, 58], [72, 20, 28, 44]],
  静岡県: [[22, 0, 34, 42], [12, 32, 34, 58], [42, 18, 34, 78], [70, 0, 28, 52]],
  三重県: [[0, 34, 30, 54], [24, 24, 34, 68], [52, 8, 34, 76], [78, 0, 22, 50]],
  和歌山県: [[0, 24, 34, 58], [26, 4, 40, 84], [60, 18, 36, 58]],
  島根県: [[18, 0, 36, 46], [6, 30, 34, 70], [42, 20, 34, 68], [68, 0, 28, 44]],
  山口県: [[8, 20, 34, 76], [34, 0, 40, 88], [66, 10, 32, 54]],
  愛媛県: [[10, 0, 34, 54], [0, 36, 34, 64], [36, 18, 38, 76], [68, 6, 30, 52]],
  高知県: [[20, 8, 28, 42], [8, 36, 34, 64], [42, 16, 34, 78], [70, 0, 28, 54]],
  香川県: [[28, 0, 32, 44], [10, 34, 34, 60], [44, 28, 34, 48]],
  長崎県: [[0, 38, 30, 50], [24, 22, 34, 68], [54, 4, 28, 54], [76, 22, 24, 40]],
  鹿児島県: [[0, 18, 30, 72], [24, 4, 44, 82], [62, 22, 38, 50]],
  沖縄県: [[24, 22, 30, 58], [48, 0, 28, 76], [72, 16, 28, 50]],
  千葉県: [[0, 20, 26, 70], [20, 8, 34, 86], [48, 22, 34, 64], [76, 36, 24, 42]],
  茨城県: [[0, 18, 32, 70], [24, 6, 44, 86], [62, 22, 38, 62]],
};

function mapBlocks(prefecture, rowSpan, colSpan) {
  if (MAP_BLOCKS[prefecture]) return MAP_BLOCKS[prefecture];
  if (colSpan > rowSpan) return [[12, 6, 36, 86], [36, 0, 38, 100], [68, 18, 28, 64]];
  if (rowSpan > colSpan) return [[0, 18, 34, 64], [24, 6, 58, 88], [74, 20, 26, 58]];
  return [[8, 18, 34, 68], [28, 0, 48, 96], [66, 16, 30, 70]];
}

function parseJson(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback));
  } catch {
    return fallback;
  }
}

function userId(name) {
  return `u_${Date.now().toString(36)}_${name.replace(/\s+/g, "").slice(0, 10) || "user"}`;
}

function normalizeUser(user) {
  return {
    id: user.id || userId(user.name || "自分"),
    name: user.name || "自分",
    favorites: Array.isArray(user.favorites) ? user.favorites : [],
    stages: user.stages && typeof user.stages === "object" ? user.stages : {},
  };
}

function loadUsers() {
  let users = parseJson(STORAGE.users, []).map(normalizeUser);
  if (!users.length) {
    users = [{
      id: "local_me",
      name: "自分",
      favorites: parseJson(STORAGE.legacyFavorites, []),
      stages: parseJson(STORAGE.legacyStages, {}),
    }];
  }
  state.users = users;
  state.activeUserId = localStorage.getItem(STORAGE.activeUser) || users[0].id;
  if (!state.users.some((user) => user.id === state.activeUserId)) state.activeUserId = users[0].id;
  saveUsers();
}

function saveUsers() {
  localStorage.setItem(STORAGE.users, JSON.stringify(state.users));
  localStorage.setItem(STORAGE.activeUser, state.activeUserId);
}

function activeUser() {
  return state.users.find((user) => user.id === state.activeUserId) || state.users[0];
}

function activeFavorites() {
  return new Set(activeUser()?.favorites || []);
}

function activeStages() {
  return activeUser()?.stages || {};
}

function setActiveUser(userIdValue) {
  if (!state.users.some((user) => user.id === userIdValue)) return;
  state.activeUserId = userIdValue;
  state.page = 1;
  saveUsers();
  renderUserConsole();
  render();
}

function createUser(name) {
  const clean = name.trim();
  if (!clean) return;
  const existing = state.users.find((user) => user.name === clean);
  if (existing) {
    setActiveUser(existing.id);
    return;
  }
  const user = normalizeUser({ id: userId(clean), name: clean });
  state.users.push(user);
  state.activeUserId = user.id;
  saveUsers();
  renderUserConsole();
  render();
}

function yen(n, type) {
  if (type === "unlimited") return "全額・実費";
  if (type === "limit" && Number.isFinite(n) && n > 0) return `上限${n.toLocaleString()}円`;
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

function prefectureMapLabel(prefecture) {
  return prefecture === "北海道" ? "北海道" : prefecture.replace(/[都府県]$/, "");
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
  const visiblePrefectures = region ? REGION_PREFECTURES[region] : PREFECTURES;
  renderRegionRail(counts);
  $("mapHint").textContent = region ? `${region}を拡大中。件数のある都道府県を複数選択できます。` : "地方を押すと拡大、都道府県タイルを押すと複数選択できます。";
  stage.innerHTML = "";

  const positions = visiblePrefectures.map((prefecture) => MAP_TILES[prefecture]);
  const minRow = Math.min(...positions.map(([row]) => row));
  const minCol = Math.min(...positions.map(([, col]) => col));
  const maxRow = Math.max(...positions.map(([row, , rowSpan = 1]) => row + rowSpan - 1));
  const maxCol = Math.max(...positions.map(([, col, , colSpan = 1]) => col + colSpan - 1));
  const rowOffset = region ? minRow - 1 : 0;
  const colOffset = region ? minCol - 1 : 0;
  const rows = region ? maxRow - minRow + 2 : 28;
  const cols = region ? maxCol - minCol + 2 : 60;
  const grid = document.createElement("div");
  grid.className = `tile-map${region ? " zoomed" : ""}`;
  grid.style.setProperty("--tile-rows", rows);
  grid.style.setProperty("--tile-cols", cols);
  stage.appendChild(grid);

  for (const prefecture of PREFECTURES) {
    const count = counts.get(prefecture) || 0;
    const [row, col, rowSpan = 1, colSpan = 1] = MAP_TILES[prefecture];
    const tile = document.createElement("button");
    const selected = state.selectedPrefectures.has(prefecture);
    const currentRegion = PREFECTURE_REGION[prefecture];
    const dimmed = region && currentRegion !== region;
    if (dimmed) continue;
    tile.type = "button";
    tile.className = `map-tile region-${currentRegion} shape-${prefecture}${selected ? " selected" : ""}${count ? "" : " empty"}`;
    tile.style.gridRow = `${row - rowOffset} / span ${rowSpan}`;
    tile.style.gridColumn = `${col - colOffset} / span ${colSpan}`;
    tile.disabled = !count;
    tile.title = `${prefecture} ${count.toLocaleString()}件`;
    const blocks = mapBlocks(prefecture, rowSpan, colSpan)
      .map(([top, left, height, width]) => `<i class="map-block" style="top:${top}%;left:${left}%;height:${height}%;width:${width}%"></i>`)
      .join("");
    tile.innerHTML = `<i class="map-blocks" aria-hidden="true">${blocks}</i><span>${prefectureMapLabel(prefecture)}</span><strong>${count.toLocaleString()}</strong>`;
    tile.onclick = () => togglePrefecture(prefecture);
    grid.appendChild(tile);
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

function setView(view) {
  state.view = view;
  state.page = 1;
  render();
  document.querySelector(".summary")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function setDecision(id, stage) {
  const user = activeUser();
  if (!user) return;
  if (stage) {
    user.stages[id] = stage;
    if (!user.favorites.includes(id)) user.favorites.push(id);
  } else {
    delete user.stages[id];
  }
  saveUsers();
  render();
}

function itemDecision(item) {
  return activeStages()[item.id] || "";
}

function viewMatches(item) {
  if (state.view === "all") return true;
  if (state.view === "favorite") return activeFavorites().has(item.id);
  return itemDecision(item) === state.view;
}

function itemPeople(item) {
  return state.users.flatMap((user) => {
    const stage = user.stages[item.id];
    if (stage) return [{ name: user.name, stage, label: STAGES[stage] }];
    if (user.favorites.includes(item.id)) return [{ name: user.name, stage: "favorite", label: "お気に入り" }];
    return [];
  });
}

function interestSummary(item) {
  const people = itemPeople(item);
  const counts = { favorite: 0, checking: 0, planned: 0, confirmed: 0 };
  for (const person of people) counts[person.stage] += 1;
  return { people, counts, total: people.length };
}

function renderManagementCounts() {
  const ids = new Set(state.items.map((item) => item.id));
  const favorites = activeFavorites();
  const favoriteCount = [...favorites].filter((id) => ids.has(id)).length;
  const stageCounts = { checking: 0, planned: 0, confirmed: 0 };
  for (const item of state.items) {
    const stage = itemDecision(item);
    if (stageCounts[stage] !== undefined) stageCounts[stage] += 1;
  }
  const pairs = [
    ["favorite", favoriteCount],
    ["checking", stageCounts.checking],
    ["planned", stageCounts.planned],
    ["confirmed", stageCounts.confirmed],
  ];
  for (const [key, count] of pairs) {
    const id = key[0].toUpperCase() + key.slice(1);
    const main = $(`${key}Count`);
    const tab = $(`tab${id}Count`);
    if (main) main.textContent = count.toLocaleString();
    if (tab) tab.textContent = count.toLocaleString();
  }
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === state.view);
  });
}

function renderUserConsole() {
  const select = $("userSelect");
  if (!select) return;
  select.innerHTML = "";
  for (const user of state.users) appendOption(select, user.id, user.name);
  select.value = state.activeUserId;
  $("activeUserName").textContent = activeUser()?.name || "未設定";
  $("userCount").textContent = `${state.users.length.toLocaleString()}人`;
}

function renderActiveFilters() {
  const filters = [];
  const min = $("minAmount").value;
  const query = $("query").value.trim();
  if (state.view !== "all") filters.push(`タブ: ${state.view === "favorite" ? "お気に入り" : STAGES[state.view]}`);
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
    if (!viewMatches(i)) return false;
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
  renderManagementCounts();
  for (const i of visibleItems) {
    const node = $("cardTemplate").content.cloneNode(true);
    const stage = itemDecision(i);
    const article = node.querySelector(".card");
    if (stage) article.dataset.stage = stage;
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
    const favorites = activeFavorites();
    fav.textContent = favorites.has(i.id) ? "★" : "☆";
    fav.onclick = () => {
      const user = activeUser();
      if (!user) return;
      user.favorites = favorites.has(i.id) ? user.favorites.filter((id) => id !== i.id) : [...user.favorites, i.id];
      saveUsers();
      render();
    };

    const decision = node.querySelector(".decision-bar");
    decision.querySelectorAll("button").forEach((button) => {
      const buttonStage = button.dataset.stage;
      button.classList.toggle("active", buttonStage && buttonStage === stage);
      button.onclick = () => setDecision(i.id, buttonStage);
    });

    const tags = node.querySelector(".tags");
    const tagValues = [
      ...(stage ? [[STAGES[stage], true]] : []),
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
    const people = node.querySelector(".people");
    const summary = interestSummary(i);
    people.hidden = !summary.total;
    people.innerHTML = "";
    const summaryChip = document.createElement("span");
    summaryChip.className = "person-chip summary";
    summaryChip.textContent = `行きそう ${summary.total.toLocaleString()}人`;
    people.appendChild(summaryChip);
    for (const [stageKey, label] of [["checking", "確認中"], ["planned", "参加予定"], ["confirmed", "確定"], ["favorite", "お気に入り"]]) {
      const count = summary.counts[stageKey];
      if (!count) continue;
      const chip = document.createElement("span");
      chip.className = `person-chip ${stageKey}`;
      chip.textContent = `${label} ${count.toLocaleString()}人`;
      people.appendChild(chip);
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
  for (const id of ["oneDayOnly", "multiDayOnly", "excludeUnknown", "lodgingOnly", "includeUnknownDates", "showClosed"]) $(id).checked = false;
  state.view = "all";
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
    renderUserConsole();
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

for (const id of ["minAmount", "sortBy", "oneDayOnly", "multiDayOnly", "excludeUnknown", "lodgingOnly", "query", "dateFrom", "dateTo", "includeUnknownDates", "showClosed", "pageSize"]) {
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
document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.view));
});
$("userSelect").addEventListener("input", () => setActiveUser($("userSelect").value));
$("userForm").addEventListener("submit", (event) => {
  event.preventDefault();
  createUser($("userNameInput").value);
  $("userNameInput").value = "";
});
$("clearFilters").onclick = clearFilters;
$("refresh").onclick = load;
loadUsers();
renderUserConsole();
if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js?v=11");
load();
