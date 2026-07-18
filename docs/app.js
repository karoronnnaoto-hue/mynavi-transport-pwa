const state = { items: [], favorites: new Set(JSON.parse(localStorage.getItem("favorites") || "[]")) };
const $ = (id) => document.getElementById(id);

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

function dateMatches(i, from, to, includeUnknown) {
  const dates = i.event_dates || [];
  if (!from && !to) return true;
  if (!dates.length) return includeUnknown;
  return dates.some((v) => (!from || v >= from) && (!to || v <= to));
}

function populateIndustryFilter() {
  const select = $("industryFilter");
  const selected = select.value;
  const industries = [...new Set(state.items.flatMap((i) => i.industries || []))].sort((a, b) => a.localeCompare(b, "ja"));
  select.innerHTML = '<option value="">すべて</option>';
  for (const industry of industries) {
    const option = document.createElement("option");
    option.value = industry;
    option.textContent = industry;
    select.appendChild(option);
  }
  select.value = industries.includes(selected) ? selected : "";
}

function render() {
  const q = $("query").value.trim().toLowerCase();
  const min = +$("minAmount").value;
  const industry = $("industryFilter").value;
  const from = $("dateFrom").value;
  const to = $("dateTo").value;
  let items = state.items.filter((i) => {
    const text = [i.company, i.course, i.schedule_text, i.eligibility_text, ...(i.locations || []), ...(i.industries || [])].join(" ").toLowerCase();
    if (q && !text.includes(q)) return false;
    if (industry && !(i.industries || []).includes(industry)) return false;
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
  $("count").textContent = `${items.length}件`;
  $("empty").hidden = items.length !== 0;
  for (const i of items) {
    const node = $("cardTemplate").content.cloneNode(true);
    node.querySelector("h2").textContent = i.company;
    node.querySelector(".course").textContent = i.course || "コース名不明";
    node.querySelector(".status").textContent = i.status === "closed" ? "終了・満席" : i.status === "cancelled" ? "中止" : i.is_new ? "新着" : "掲載中";
    node.querySelector(".transport").textContent = yen(i.transport_amount, i.transport_type);
    node.querySelector(".industries").textContent = (i.industries || []).join("・") || "記載なし";
    node.querySelector(".lodging").textContent = i.lodging_text || "記載なし";
    node.querySelector(".locations").textContent = (i.locations || []).join("・") || "記載なし";
    node.querySelector(".dates").textContent = i.schedule_text || "開催日の明示なし";
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
      [(i.industries || [])[0] || "業種不明", false],
      [i.event_dates?.[0] || "日付未定", false],
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

async function load() {
  try {
    const r = await fetch(`data/jobs.json?t=${Date.now()}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    state.items = data.items || [];
    populateIndustryFilter();
    const stats = data.stats || {};
    const supported = stats.transport_supported_courses ?? stats.displayed_courses ?? state.items.length;
    const displayed = stats.displayed_courses ?? state.items.length;
    const known = (stats.amount_known_courses ?? 0) + (stats.amount_unlimited_courses ?? 0);
    const scienceExcluded = stats.excluded_science_only_courses ?? 0;
    $("updatedAt").textContent = `更新 ${fmtDate(data.generated_at)}・表示 ${displayed}件・交通費あり ${supported}件・理系除外 ${scienceExcluded}件・金額判定 ${known}件`;
    render();
  } catch (e) {
    $("empty").hidden = false;
    $("empty").textContent = `データ読込に失敗しました: ${e.message}`;
  }
}

for (const id of ["minAmount", "industryFilter", "sortBy", "excludeUnknown", "lodgingOnly", "favoritesOnly", "query", "dateFrom", "dateTo", "includeUnknownDates", "showClosed"]) {
  $(id).addEventListener("input", render);
}
$("clearDates").onclick = () => {
  $("dateFrom").value = "";
  $("dateTo").value = "";
  render();
};
$("refresh").onclick = load;
if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js");
load();
