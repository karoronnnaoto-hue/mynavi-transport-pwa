const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const ROOT = path.resolve(__dirname, "..");
const CATALOG_PATH = path.join(ROOT, "data", "catalog.json");
const STATE_PATH = path.join(ROOT, "data", "crawl_state.json");
const SEARCH_SEEDS = [
  "https://job.mynavi.jp/28/pc/search/is_it1.html",
  "https://job.mynavi.jp/28/pc/search/is_it2.html",
  "https://job.mynavi.jp/28/pc/search/is_it3.html",
];
const IMPLEMENTATION_TYPES = {
  "is_it1": "インターンシップ",
  "is_it2": "仕事体験",
  "is_it3": "オープン・カンパニー等",
};

function parseArgs(argv) {
  const args = {
    maxPages: 3,
    delayMs: 1500,
    dryRun: false,
    headed: false,
    trafficOnly: true,
    output: CATALOG_PATH,
    state: STATE_PATH,
    seeds: SEARCH_SEEDS,
  };
  for (let i = 2; i < argv.length; i += 1) {
    const arg = argv[i];
    const next = argv[i + 1];
    if (arg === "--max-pages") {
      args.maxPages = Number(next);
      i += 1;
    } else if (arg === "--delay-ms") {
      args.delayMs = Number(next);
      i += 1;
    } else if (arg === "--dry-run") {
      args.dryRun = true;
    } else if (arg === "--headed") {
      args.headed = true;
    } else if (arg === "--no-traffic-filter") {
      args.trafficOnly = false;
    } else if (arg === "--output") {
      args.output = path.resolve(next);
      i += 1;
    } else if (arg === "--state") {
      args.state = path.resolve(next);
      i += 1;
    } else if (arg === "--seeds") {
      args.seeds = next.split(",").map((x) => x.trim()).filter(Boolean);
      i += 1;
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }
  if (!Number.isFinite(args.maxPages) || args.maxPages < 0) throw new Error("--max-pages must be 0 or more");
  if (!Number.isFinite(args.delayMs) || args.delayMs < 0) throw new Error("--delay-ms must be 0 or more");
  return args;
}

function loadJson(filePath, fallback) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch {
    return fallback;
  }
}

function saveJson(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function jstNow() {
  return new Date(Date.now() + 9 * 60 * 60 * 1000).toISOString().replace("Z", "+09:00");
}

function canonicalUrl(rawUrl, baseUrl = "https://job.mynavi.jp") {
  const url = new URL(rawUrl, baseUrl);
  if (url.hostname !== "job.mynavi.jp") return null;
  if (!url.pathname.includes("/corpinfo/displayInternship/index")) return null;
  const allowed = [];
  for (const [key, value] of url.searchParams.entries()) {
    if (["corpid", "optno", "courseid", "id"].includes(key.toLowerCase())) {
      allowed.push([key, value]);
    }
  }
  const hasCorpId = allowed.some(([key]) => key.toLowerCase() === "corpid");
  if (!hasCorpId) return null;
  allowed.sort((a, b) => a[0].toLowerCase().localeCompare(b[0].toLowerCase()));
  const params = new URLSearchParams(allowed);
  const pathname = url.pathname.replace(/\/+/g, "/").replace(/\/$/, "");
  return `https://job.mynavi.jp${pathname}?${params.toString()}`;
}

function courseKey(rawUrl) {
  const url = new URL(rawUrl);
  const query = {};
  for (const [key, value] of url.searchParams.entries()) query[key.toLowerCase()] = value;
  const corp = query.corpid;
  const course = query.optno || query.courseid;
  if (corp && course) return `corp:${corp}:course:${course}`;
  return `url:${Buffer.from(rawUrl).toString("base64url").slice(0, 24)}`;
}

function implementationTypeForSeed(seed) {
  for (const [token, label] of Object.entries(IMPLEMENTATION_TYPES)) {
    if (seed.includes(token)) return label;
  }
  return "実施形式不明";
}

async function bodyText(page) {
  return page.locator("body").innerText({ timeout: 10000 }).catch(() => "");
}

async function assertNotInvalid(page, label) {
  const text = await bodyText(page);
  if (/不正な操作|不正操作|エラーが発生しました|再度お試し/.test(text)) {
    throw new Error(`${label}: invalid-operation page detected`);
  }
}

async function firstVisible(locator) {
  const count = await locator.count().catch(() => 0);
  for (let i = 0; i < count; i += 1) {
    const item = locator.nth(i);
    if (await item.isVisible().catch(() => false)) return item;
  }
  return null;
}

async function clickAndSettle(page, locator, delayMs) {
  await Promise.all([
    page.waitForNavigation({ waitUntil: "domcontentloaded", timeout: 45000 }).catch(() => null),
    locator.click({ timeout: 15000 }),
  ]);
  await page.waitForLoadState("domcontentloaded", { timeout: 45000 }).catch(() => null);
  if (delayMs) await page.waitForTimeout(delayMs);
}

async function openSearchConditions(page, delayMs) {
  const candidates = [
    page.locator("a[href$='#modalSearch']"),
    page.locator("a").filter({ hasText: "検索条件を変更" }),
  ];
  for (const locator of candidates) {
    const target = await firstVisible(locator);
    if (!target) continue;
    await clickAndSettle(page, target, delayMs);
    return true;
  }
  return false;
}

async function submitSearchConditions(page, delayMs) {
  const submittedByPage = await page.evaluate(() => {
    if (typeof window.doSearchConditionAbove === "function") {
      window.doSearchConditionAbove();
      return true;
    }
    return false;
  }).catch(() => false);
  if (submittedByPage) {
    await page.waitForLoadState("domcontentloaded", { timeout: 45000 }).catch(() => null);
    if (delayMs) await page.waitForTimeout(delayMs);
    await assertNotInvalid(page, "search conditions submit");
    return true;
  }

  const candidates = [
    page.locator("button").filter({ hasText: /^検索$/ }),
    page.locator("input[type='button'][value='検索'], input[type='submit'][value='検索']"),
  ];
  for (const locator of candidates) {
    const target = await firstVisible(locator);
    if (!target) continue;
    await clickAndSettle(page, target, delayMs);
    await assertNotInvalid(page, "search conditions submit");
    return true;
  }
  return false;
}

async function closeSearchConditions(page) {
  await page.keyboard.press("Escape").catch(() => null);
  await page.evaluate(() => {
    document.querySelectorAll("#modalSearch, .modalContent, .modalBg, .modalOverlay").forEach((node) => {
      node.classList.remove("show", "active", "open");
      if (node.id === "modalSearch") node.style.display = "none";
    });
  }).catch(() => null);
}

async function applyTrafficFilter(page, delayMs) {
  const opened = await openSearchConditions(page, delayMs);
  const clicked = await page.evaluate(() => {
    const pattern = /説明会・選考にて交通費支給あり|交通費支給あり/;
    const nodes = [...document.querySelectorAll("a, button, input, label, span")];
    const target = nodes.find((node) => pattern.test((node.textContent || node.value || "").replace(/\s+/g, " ")));
    if (!target) return false;
    target.click();
    return true;
  }).catch(() => false);
  if (clicked) {
    await page.waitForLoadState("domcontentloaded", { timeout: 45000 }).catch(() => null);
    if (delayMs) await page.waitForTimeout(delayMs);
    await assertNotInvalid(page, "traffic filter");
    await submitSearchConditions(page, delayMs);
    return true;
  }
  if (opened) await closeSearchConditions(page);
  return false;
}

async function collectDetailLinks(page) {
  return page.evaluate(() => {
    return [...document.querySelectorAll("a[href]")].map((a) => ({
      href: a.href,
      hint: a.textContent.replace(/\s+/g, " ").trim(),
    }));
  }).then((anchors) => {
    const byUrl = new Map();
    for (const anchor of anchors) {
      const url = canonicalUrl(anchor.href);
      if (!url) continue;
      if (!byUrl.has(url)) byUrl.set(url, anchor.hint);
    }
    return [...byUrl.entries()].map(([url, hint]) => ({ url, hint }));
  });
}

async function findNextButton(page) {
  const candidates = [
    page.locator("a#nextPageLink").filter({ hasText: "次の30社" }),
    page.locator("a#nextPageLink"),
    page.locator("a").filter({ hasText: "次の30社" }),
    page.locator("a").filter({ hasText: "次へ" }),
  ];
  for (const locator of candidates) {
    const target = await firstVisible(locator);
    if (target) return target;
  }
  return null;
}

async function crawlSeed(browser, seed, args) {
  const context = await browser.newContext({
    locale: "ja-JP",
    userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
  });
  const page = await context.newPage();
  const discovered = new Map();
  const signatures = new Set();
  const pages = [];
  try {
    await page.goto(seed, { waitUntil: "domcontentloaded", timeout: 60000 });
    await assertNotInvalid(page, "seed");
    const trafficFiltered = args.trafficOnly ? await applyTrafficFilter(page, args.delayMs) : false;
    if (args.trafficOnly && !trafficFiltered) {
      console.log(`traffic filter not found: ${seed}`);
    }

    let pageNo = 1;
    while (args.maxPages === 0 || pageNo <= args.maxPages) {
      await assertNotInvalid(page, `list page ${pageNo}`);
      const links = await collectDetailLinks(page);
      const signature = links.map((link) => courseKey(link.url)).slice(0, 12).join("|");
      if (signature && signatures.has(signature)) {
        console.log(`same page repeated, stopping seed: ${seed}`);
        break;
      }
      if (signature) signatures.add(signature);

      for (const link of links) discovered.set(link.url, link.hint);
      pages.push({ pageNo, url: page.url(), links: links.length });
      console.log(`seed ${seed} page ${pageNo}: ${links.length} links`);

      const next = await findNextButton(page);
      if (!next) break;
      pageNo += 1;
      await closeSearchConditions(page);
      try {
        await clickAndSettle(page, next, args.delayMs);
      } catch (error) {
        console.error(`next page failed, keeping collected links: ${seed}: ${error.message}`);
        break;
      }
    }
  } finally {
    await context.close();
  }
  return { seed, discovered, pages };
}

async function launchBrowser(headed) {
  const options = { headless: !headed };
  if (process.platform === "win32") {
    try {
      return await chromium.launch({ ...options, channel: "chrome" });
    } catch (error) {
      console.warn(`Chrome channel launch failed, falling back to bundled Chromium: ${error.message}`);
    }
  }
  return chromium.launch(options);
}

async function main() {
  const args = parseArgs(process.argv);
  const browser = await launchBrowser(args.headed);
  const allDiscovered = new Map();
  const seedReports = [];
  const failedSeeds = [];
  try {
    for (const seed of args.seeds) {
      try {
        const result = await crawlSeed(browser, seed, args);
        const implementationType = implementationTypeForSeed(seed);
        for (const [url, hint] of result.discovered.entries()) {
          const record = allDiscovered.get(url) || { hint, implementationTypes: new Set() };
          if (hint && !record.hint) record.hint = hint;
          record.implementationTypes.add(implementationType);
          allDiscovered.set(url, record);
        }
        seedReports.push({ seed, pages: result.pages.length, links: result.discovered.size, page_details: result.pages });
      } catch (error) {
        failedSeeds.push({ seed, error: error.message });
        console.error(`seed failed: ${seed}: ${error.message}`);
      }
    }
  } finally {
    await browser.close();
  }

  const now = jstNow();
  const catalog = loadJson(args.output, { urls: {} });
  let newCount = 0;
  for (const [url, discoveredRecord] of allDiscovered.entries()) {
    const key = courseKey(url);
    if (!catalog.urls[key]) newCount += 1;
    const existingTypes = catalog.urls[key]?.implementation_types || [];
    const implementationTypes = [...new Set([...existingTypes, ...discoveredRecord.implementationTypes])];
    catalog.urls[key] = {
      ...(catalog.urls[key] || {}),
      url,
      last_discovered: now,
      discovery_method: args.trafficOnly ? "browser_click_traffic_filter" : "browser_click",
      implementation_types: implementationTypes,
    };
    if (discoveredRecord.hint) catalog.urls[key].course_title_hint = discoveredRecord.hint;
  }

  const crawlState = loadJson(args.state, {});
  crawlState.browser_discovery = {
    last_run: now,
    max_pages_per_seed: args.maxPages,
    traffic_only: args.trafficOnly,
    discovered_courses: allDiscovered.size,
    new_courses: newCount,
    failed_seeds: failedSeeds,
    seeds: seedReports,
  };

  if (!args.dryRun) {
    saveJson(args.output, catalog);
    saveJson(args.state, crawlState);
  }

  console.log(JSON.stringify({
    dryRun: args.dryRun,
    trafficOnly: args.trafficOnly,
    discovered: allDiscovered.size,
    newCourses: newCount,
    failedSeeds,
  }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
