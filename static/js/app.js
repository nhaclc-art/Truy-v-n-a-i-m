// Điều phối giao diện GeoRank: tìm kiếm, vị trí gốc (tham chiếu / thật / mô phỏng), danh sách và
// bản đồ, bảng giải thích, chỉ đường và geofence. Dữ liệu nguồn chỉ được render dạng text.
import { getJSON } from "./api.js";
import { Geofence, haversineM } from "./geofence.js";
import { GpsTracker } from "./location.js";
import { ResultMap, safeCategory } from "./map.js";
import { BottomSheet } from "./sheet.js";
import { VOICE_ERRORS, VoiceSearch, voiceSupport } from "./voice.js";
import { OcrMissingError, readImage } from "./ocr.js";

const $ = (id) => document.getElementById(id);

const SORT_LABELS = { distance: "Gần nhất", bm25: "Đúng từ khóa (BM25)", combined: "Kết hợp văn bản + khoảng cách" };
const MODE_BADGES = { reference: "Tham chiếu", gps: "Vị trí thật", simulated: "Mô phỏng", custom: "Tùy chỉnh" };
const MODE_WORDS = { gps: "vị trí thật", simulated: "mô phỏng" };
const SOURCE_LABELS = { osm: "OpenStreetMap", listing: "Tin đăng" };
const VERIFICATION_LABELS = {
  source_only: "chưa đối chiếu",
  cross_checked: "đã đối chiếu",
  field_checked: "đã kiểm tra thực địa",
};
const REASON_CLASS = { TEXT: 1, CATEGORY: 1, RADIUS: 1, RANK: 1, IN_TOP_K: 1 };
const SPELL_KINDS = { edit: "sửa chữ", split: "tách từ dính", merge: "gộp từ" };
const FENCE_STATE_LABELS ={ UNKNOWN: "Chưa rõ", OUTSIDE: "Ngoài vùng", INSIDE: "Trong vùng" };
const MAX_LOG = 50;
const ROUTE_STALE_M = 10;

const state = {
  config: null,
  origin: null, // {lat, lon, mode, accuracy, timestamp}
  // alpha: trọng số văn bản của chế độ kết hợp khi áp dụng đề xuất why-not; null = theo cấu hình.
  // spell: sửa lỗi gõ; tắt cho riêng câu đang gõ khi người dùng bấm "Tìm đúng như đã gõ".
  // match: "all" = nối AND như người gõ; "any" = nối OR khi tìm theo chữ đọc từ ảnh biển hiệu.
  filters: { category: "", radius: 1000, sort: "distance", alpha: null, spell: true, match: "all" },
  selectedId: null,
  pois: [],
  whyNot: null, // {status: "pick" | "loading" | "ok" | "error", poiId, data, error}
  pendingWhyNot: null, // {poiId, k}: hỏi lại sau khi áp dụng đề xuất để xác nhận
  pendingSelect: null,
  voice: null, // {transcript, confidence, alternatives, at}: câu vừa nói, xóa khi người dùng gõ tay
  voiceLog: [], // nhật ký các lần nói trong phiên, tải về dạng CSV để đánh giá
  ocr: null, // {status, previewUrl, stage, progress, result, query, matches, error}: lần đọc ảnh đang hiện
  ocrLog: [], // nhật ký các lần đọc ảnh trong phiên (chỉ chữ, không lưu ảnh)
  itinerary: null, // {status: "form" | "loading" | "ok" | "error", legs, maxDistanceM, dwellMin, data, chosen, realRoute, error}
  route: null, // {poi, origin, status, data | error, fallbackUrl, stale}
  fence: null, // {target, geofence, last}
  events: [],
  // Nhật ký geofence mở sẵn trên màn hình rộng, thu gọn trên điện thoại để thẻ nổi không che bản đồ.
  logOpen: !window.matchMedia("(max-width: 900px)").matches,
  gpsStatus: null,
};

let map;
let gps;
let sheet;
let geofenceViewKey = "";
let searchSeq = 0;
let searchController = null;
let searchTimer = null;
let lastSearchAt = 0;
let routeController = null;
let whyNotController = null;
let itineraryController = null;
let itineraryRouteAbort = [];
let voice = null;

// ---------- Tiện ích DOM và định dạng ----------

// Tạo phần tử; chuỗi con luôn thành text node nên dữ liệu nguồn không bị hiểu là HTML.
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "className") node.className = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : String(child));
  }
  return node;
}

const fmtDistance = (m) => (m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(2)} km`);
const fmtRadius = (m) => (m >= 1000 ? `${m / 1000} km` : `${m} m`);
const fmtNum = (x) => (x === null || x === undefined ? "—" : Number(x).toPrecision(4));
const fmtCoords = (lat, lon) => `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
const fmtTime = (ts) => new Date(ts).toLocaleTimeString("vi-VN", { hour12: false });
const fmtMinutes = (s) => `${Math.max(1, Math.round(s / 60))} phút`;

function safeLink(url, text, className) {
  if (!/^https?:\/\//i.test(url || "")) return text;
  return el("a", { href: url, target: "_blank", rel: "noopener noreferrer", className }, text);
}

function setStatus(message, isError = false) {
  const status = $("status");
  status.textContent = message;
  status.classList.toggle("error", isError);
}

function toast(title, body, kind = "info") {
  const node = el("div", { className: `toast toast-${kind}`, role: "status" }, el("strong", {}, title), el("div", {}, body));
  $("toasts").append(node);
  setTimeout(() => node.remove(), 6000);
}

// ---------- Bộ lọc ----------

function radioGroup(container, name, options, current, onChange) {
  for (const opt of options) {
    const id = `${name}-${opt.value || "all"}`;
    const input = el("input", { type: "radio", name, id, value: opt.value });
    input.checked = String(opt.value) === String(current);
    input.addEventListener("change", () => onChange(opt.value));
    const dot = opt.dot ? el("span", { className: `cat-dot cat-${opt.dot}` }) : null;
    container.append(input, el("label", { for: id, title: opt.hint }, dot, opt.label));
  }
}

function fillControls() {
  const cfg = state.config;
  $("campus-name").textContent = `${cfg.campus.name} · ${cfg.campus.site_name}`;
  $("dataset-version").textContent = cfg.dataset_version ? `Dữ liệu ${cfg.dataset_version}` : "Chưa import dữ liệu";
  $("help-dataset").textContent = cfg.dataset_version ? `Phiên bản dữ liệu đang dùng: ${cfg.dataset_version}.` : "";
  state.filters = { category: "", radius: cfg.search.default_radius_m, sort: cfg.search.default_sort, alpha: null, spell: true, match: "all" };

  const categories = cfg.categories.map((c) => ({ value: c.id, label: c.label, dot: safeCategory(c.id) }));
  radioGroup($("category-group"), "category", [{ value: "", label: "Tất cả" }, ...categories], "", (value) => {
    state.filters.category = value;
    scheduleSearch(0);
  });

  const radii = cfg.search.allowed_radii_m.map((r) => ({ value: r, label: fmtRadius(r) }));
  radioGroup($("radius-group"), "radius", radii, state.filters.radius, (value) => {
    state.filters.radius = Number(value);
    map.setRadius(state.filters.radius);
    map.fitToRadius();
    scheduleSearch(0);
  });

  const w = cfg.ranking.combined_weights;
  const sorts = [
    { value: "distance", label: "Gần nhất", hint: "Sắp theo khoảng cách đường chim bay" },
    { value: "bm25", label: "Đúng từ khóa", hint: "Sắp theo điểm BM25 của SQLite FTS5" },
    { value: "combined", label: "Kết hợp", hint: `${w.text} × điểm văn bản + ${w.geo} × điểm khoảng cách (trọng số đặt tay)` },
  ];
  radioGroup($("sort-group"), "sort", sorts, state.filters.sort, (value) => {
    state.filters.sort = value;
    scheduleSearch(0);
  });
}

// ---------- Vị trí gốc ----------

// Mọi nguồn vị trí (tham chiếu, định vị thật, mô phỏng) đều đi qua hàm này.
function handlePositionUpdate(position) {
  const modeChanged = state.origin !== null && state.origin.mode !== position.mode;
  state.origin = position;
  map.setOrigin(position);
  map.setPicking(position.mode === "simulated");
  if (modeChanged) resetGeofence("đổi chế độ vị trí");
  if (position.mode === "gps") feedGeofence(position);
  const route = state.route;
  if (route && route.status !== "loading" && !route.stale) {
    if (haversineM(route.origin.lat, route.origin.lon, position.lat, position.lon) > ROUTE_STALE_M) {
      route.stale = true;
      renderRoute();
    }
  }
  renderOrigin();
  renderGeofence();
  // Định vị thật có thể gửi mẫu dày; giới hạn khoảng 1 lượt tìm mỗi giây.
  scheduleSearch(position.mode === "gps" ? Math.max(0, 1000 - (Date.now() - lastSearchAt)) : 0);
}

function referencePosition() {
  const p = state.config.campus.reference_point;
  return { lat: p.lat, lon: p.lon, mode: "reference", accuracy: null, timestamp: Date.now() };
}

function useReference() {
  gps.stop();
  state.gpsStatus = null;
  handlePositionUpdate(referencePosition());
}

function toggleGps() {
  if (gps.active) {
    useReference();
    return;
  }
  // Trong lúc chờ mẫu đầu, vị trí gốc là tâm khuôn viên (có nhãn), không giữ mô phỏng.
  if (state.origin.mode !== "reference") handlePositionUpdate(referencePosition());
  gps.start();
  renderOrigin();
}

function toggleSimulate() {
  if (state.origin.mode === "simulated") {
    useReference();
    return;
  }
  gps.stop();
  state.gpsStatus = null;
  handlePositionUpdate({ lat: state.origin.lat, lon: state.origin.lon, mode: "simulated", accuracy: null, timestamp: Date.now() });
  // Trên điện thoại hạ bảng trượt để có chỗ bấm/kéo chấm cam trên bản đồ.
  if (sheet.enabled) sheet.set("peek");
}

function renderOrigin() {
  const { lat, lon, mode, accuracy, timestamp } = state.origin;
  const cfg = state.config;
  let title;
  let sub;
  if (mode === "gps") {
    title = "Vị trí từ trình duyệt";
    const low = accuracy > cfg.geofence.max_accuracy_m ? " · độ chính xác thấp" : "";
    sub = `${fmtCoords(lat, lon)} · sai số ±${Math.round(accuracy)} m · cập nhật ${fmtTime(timestamp)}${low}`;
  } else if (mode === "simulated") {
    title = "Vị trí mô phỏng";
    sub = `${fmtCoords(lat, lon)}. Bấm lên bản đồ hoặc kéo chấm cam để di chuyển.`;
  } else {
    title = "Tâm khuôn viên";
    sub = `${cfg.campus.reference_point.label}; không phải vị trí của bạn. (${fmtCoords(lat, lon)})`;
  }
  $("origin-card").dataset.mode = mode;
  $("origin-badge").textContent = MODE_BADGES[mode] ?? mode;
  $("origin-title").textContent = title;
  $("origin-sub").textContent = sub;

  const status = $("origin-status");
  status.hidden = !state.gpsStatus;
  status.textContent = state.gpsStatus?.message ?? "";
  status.className = `origin-status ${state.gpsStatus?.type ?? ""}`;
  $("btn-gps").setAttribute("aria-pressed", String(gps.active));
  $("btn-simulate").setAttribute("aria-pressed", String(mode === "simulated"));
  $("fab-locate").setAttribute("aria-pressed", String(gps.active));
}

// ---------- Tìm kiếm và kết quả ----------

// Tham số truy vấn hiện tại, dùng chung cho tìm kiếm và câu hỏi why-not.
function currentQueryParams() {
  const { lat, lon, mode } = state.origin;
  const { category, radius, sort, alpha, spell, match } = state.filters;
  const params = new URLSearchParams({ q: $("q").value.trim(), lat, lon, origin_mode: mode, radius_m: radius, sort });
  if (category) params.set("category", category);
  if (alpha !== null) params.set("alpha", alpha);
  if (!spell) params.set("spell", "0");
  if (match !== "all") params.set("match", match);
  return params;
}

function renderAlphaChip() {
  const chip = $("alpha-chip");
  const { alpha, sort } = state.filters;
  chip.hidden = alpha === null;
  if (alpha === null) {
    chip.replaceChildren();
    return;
  }
  const note = sort === "combined" ? "" : " (chỉ có tác dụng ở chế độ Kết hợp)";
  chip.replaceChildren(
    `Trọng số văn bản α = ${alpha} (khoảng cách ${Number((1 - alpha).toFixed(6))}) từ đề xuất why-not${note}. `,
    el("button", { type: "button", className: "btn-link", "data-action": "reset-alpha" }, "Về mặc định"),
  );
}

function scheduleSearch(delayMs = 300) {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(runSearch, delayMs);
}

async function runSearch() {
  searchController?.abort();
  searchController = new AbortController();
  const seq = ++searchSeq;
  lastSearchAt = Date.now();
  const params = currentQueryParams();
  params.set("limit", state.config.search.default_limit);
  renderAlphaChip();

  setStatus("Đang tìm…");
  try {
    const data = await getJSON(`/api/search?${params}`, { signal: searchController.signal });
    if (seq !== searchSeq) return; // phản hồi của truy vấn cũ không được ghi đè kết quả mới
    renderResults(data);
  } catch (err) {
    if (err.name === "AbortError" || seq !== searchSeq) return;
    $("result-list").replaceChildren();
    map.showResults([]);
    $("explain-body").replaceChildren();
    setStatus(`Không tìm được: ${err.message}`, true);
  }
}

// Báo chỗ đã sửa lỗi gõ, kèm lựa chọn tìm đúng như đã gõ (hoặc bật lại sửa lỗi).
function renderSpellNote(meta) {
  const note = $("spell-note");
  if (meta.corrections?.length) {
    const parts = meta.corrections.map((c) => `“${c.from}” là “${c.to}”`).join(", ");
    note.replaceChildren(
      `Đã hiểu ${parts}. `,
      el("button", { type: "button", className: "btn-link", "data-action": "spell-off" }, `Tìm đúng như đã gõ`),
    );
    note.hidden = false;
  } else if (!meta.spell && meta.query_as_typed) {
    note.replaceChildren(
      "Đang tìm đúng như đã gõ, không sửa lỗi gõ. ",
      el("button", { type: "button", className: "btn-link", "data-action": "spell-on" }, "Bật sửa lỗi gõ"),
    );
    note.hidden = false;
  } else {
    note.replaceChildren();
    note.hidden = true;
  }
}

function renderResults({ items, meta }) {
  const list = $("result-list");
  if (items.length === 0) {
    const title = meta.query_normalized ? `Không có kết quả cho “${meta.query}”` : "Không có địa điểm nào";
    list.replaceChildren(
      el(
        "li",
        { className: "empty" },
        el("strong", {}, title),
        `trong bán kính ${fmtRadius(meta.radius_m)}. Thử bán kính lớn hơn, bỏ lọc danh mục hoặc dùng từ khóa khác. `,
        el("button", { type: "button", className: "btn-link", "data-action": "open-whynot" }, "Hỏi vì sao không thấy một chỗ cụ thể"),
      ),
    );
    setStatus(`0 địa điểm trong ${fmtRadius(meta.radius_m)}`);
  } else {
    list.replaceChildren(...items.map(renderCard));
    const shown = meta.returned_count < meta.radius_match_count ? `, hiển thị ${meta.returned_count}` : "";
    setStatus(`${meta.radius_match_count} địa điểm trong ${fmtRadius(meta.radius_m)}${shown} · ${SORT_LABELS[meta.sort_effective]}`);
  }
  $("sheet-summary").textContent = `${meta.radius_match_count} địa điểm trong ${fmtRadius(meta.radius_m)}`;
  renderVoiceNote(meta);
  renderOcrNote(meta);
  renderSpellNote(meta);
  map.showResults(items);
  renderExplain(meta, items);
  const pending = state.pendingSelect;
  state.pendingSelect = null;
  if (pending && items.some((i) => i.id === pending)) {
    select(pending, "list");
  } else if (items.some((i) => i.id === state.selectedId)) {
    highlightCard(state.selectedId, false);
    map.highlight(state.selectedId, true);
  } else {
    state.selectedId = null;
  }
  finishOcrSearch(items, meta);
  if (state.pendingWhyNot) {
    const { poiId, k } = state.pendingWhyNot;
    state.pendingWhyNot = null;
    askWhyNot(poiId, k);
  }
}

function sourceLink(item) {
  return safeLink(item.source_url, SOURCE_LABELS[item.source_type] ?? item.source_type);
}

function watchLabel(watching) {
  return watching ? "Đang theo dõi" : `Theo dõi ${state.config.geofence.enter_m} m`;
}

function renderCard(item) {
  const cat = safeCategory(item.category);
  const watching = state.fence?.target.id === item.id;
  const card = el(
    "li",
    { className: "card", dataset: { id: item.id } },
    el("span", { className: `rank cat-${cat}`, "aria-hidden": "true" }, item.rank),
    el(
      "div",
      { className: "card-body" },
      el(
        "div",
        { className: "card-head" },
        el("h3", {}, el("button", { type: "button", className: "card-title", "data-action": "select" }, item.name)),
        el("span", { className: "dist", title: "Khoảng cách đường chim bay" }, fmtDistance(item.distance_m)),
      ),
      el(
        "p",
        { className: "card-meta" },
        el("span", { className: `cat-dot cat-${cat}` }),
        item.category_label,
        item.address ? ` · ${item.address}` : " · chưa có địa chỉ",
      ),
      el(
        "p",
        { className: "card-source" },
        "Nguồn: ",
        sourceLink(item),
        " ",
        el(
          "span",
          { className: `verify verify-${safeCategory(item.verification_status)}` },
          VERIFICATION_LABELS[item.verification_status] ?? item.verification_status,
        ),
      ),
      el(
        "div",
        { className: "card-actions" },
        el("button", { type: "button", className: "btn btn-sm btn-primary", "data-action": "route" }, "Chỉ đường"),
        el(
          "button",
          { type: "button", className: watching ? "btn btn-sm watching" : "btn btn-sm", "data-action": "watch", "aria-pressed": String(watching) },
          watchLabel(watching),
        ),
      ),
    ),
  );
  card.addEventListener("click", (e) => {
    if (e.target.closest("a")) return;
    const action = e.target.closest("[data-action]")?.dataset.action;
    if (action === "route") requestRoute(item);
    else if (action === "watch") toggleWatch(item.id);
    else select(item.id, "list");
  });
  card.addEventListener("mouseenter", () => map.highlight(item.id, true));
  card.addEventListener("mouseleave", () => map.highlight(item.id, state.selectedId === item.id));
  return card;
}

function select(id, source) {
  const previous = state.selectedId;
  state.selectedId = id;
  if (previous && previous !== id) map.highlight(previous, false);
  if (source === "list") {
    // Trên điện thoại: hạ bảng trượt để thấy bản đồ, rồi đưa marker vào giữa phần còn nhìn thấy.
    if (sheet.enabled) sheet.set("peek");
    highlightCard(id, false);
    map.focus(id);
  } else {
    if (sheet.enabled && sheet.state === "peek") sheet.set("half");
    highlightCard(id, true);
    map.highlight(id, true);
  }
}

function highlightCard(id, scroll) {
  let target = null;
  for (const card of document.querySelectorAll(".card")) {
    const match = card.dataset.id === id;
    card.classList.toggle("selected", match);
    if (match) target = card;
  }
  if (scroll) target?.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function renderExplain(meta, items) {
  const textQuery = Boolean(meta.query_normalized);
  const sortText =
    meta.sort_requested === meta.sort_effective
      ? SORT_LABELS[meta.sort_effective]
      : `${SORT_LABELS[meta.sort_requested]} → ${SORT_LABELS[meta.sort_effective]} (query rỗng không có điểm văn bản)`;
  const categoryLabel = state.config.categories.find((c) => c.id === meta.category)?.label ?? "Tất cả";
  const rows = [
    ["Query gốc", meta.query || "(rỗng)"],
    ["Query chuẩn hóa", textQuery ? meta.query_normalized : "(rỗng): duyệt theo vị trí"],
    ["Cách nối từ", meta.match === "any" ? "bất kỳ từ nào (OR), tìm theo chữ trên ảnh" : "tất cả các từ (AND)"],
    ["Nguồn truy vấn", state.voice && state.voice.transcript === meta.query ? voiceSummary(state.voice) : "bàn phím"],
    [
      "Sửa lỗi gõ",
      !meta.spell
        ? "tắt (tìm đúng như đã gõ)"
        : meta.corrections.length
          ? meta.corrections.map((c) => `${c.from} → ${c.to} (${SPELL_KINDS[c.kind] ?? c.kind})`).join("; ")
          : "không cần sửa",
    ],
    ["Biểu thức FTS5", meta.fts_match ? el("code", {}, meta.fts_match) : "không dùng"],
    ["Vị trí gốc", `${MODE_BADGES[meta.origin.mode] ?? meta.origin.mode} · ${fmtCoords(meta.origin.lat, meta.origin.lon)}`],
    ["Bán kính", fmtRadius(meta.radius_m)],
    ["Danh mục", categoryLabel],
    ["Xếp hạng", sortText],
    ["Khớp văn bản (toàn corpus)", meta.text_match_count ?? "— (không lọc văn bản)"],
    ["Sau lọc danh mục", meta.category_match_count],
    ["Sau lọc bán kính", meta.radius_match_count],
    ["Hiển thị", `${meta.returned_count} (limit ${meta.limit})`],
    ["Thời gian xử lý server", `${meta.elapsed_ms} ms`],
    ["Dataset", meta.dataset_version ?? "—"],
  ];
  const dl = el("dl");
  for (const [term, value] of rows) dl.append(el("dt", {}, term), el("dd", {}, value));

  const w = meta.weights.combined;
  const note = el(
    "p",
    { className: "fineprint" },
    `Điểm kết hợp = ${w.text} × text_norm + ${w.geo} × geo_norm. text_norm = (−BM25) / max(−BM25) trong lần truy vấn này; ` +
      "geo_norm = max(0, 1 − khoảng cách / bán kính). Trọng số đặt tay, chưa huấn luyện. " +
      "BM25 của SQLite FTS5 càng âm càng khớp. Ba chế độ xếp hạng dùng cùng tập ứng viên.",
  );
  const header = ["#", "Tên", "BM25 thô", "text_norm", "Khoảng cách (m)", "geo_norm", "Điểm kết hợp"];
  const table = el(
    "table",
    {},
    el("thead", {}, el("tr", {}, header.map((h) => el("th", { scope: "col" }, h)))),
    el(
      "tbody",
      {},
      items.map((i) =>
        el(
          "tr",
          {},
          el("td", {}, i.rank),
          el("td", {}, i.name),
          el("td", {}, fmtNum(i.bm25_raw)),
          el("td", {}, fmtNum(i.text_norm)),
          el("td", {}, i.distance_m.toFixed(1)),
          el("td", {}, fmtNum(i.geo_norm)),
          el("td", {}, fmtNum(i.score)),
        ),
      ),
    ),
  );
  $("explain-body").replaceChildren(dl, note, el("div", { className: "table-wrap" }, table));
}

// ---------- Tìm bằng giọng nói ----------

const fmtConfidence = (c) => (c > 0 ? `${Math.round(c * 100)}%` : "không rõ");
const voiceSummary = (v) => `giọng nói, độ tin cậy ${fmtConfidence(v.confidence)}`;

function setupVoice() {
  const support = voiceSupport();
  const button = $("btn-mic");
  if (support === "unsupported") return; // Firefox…: ẩn nút, vẫn gõ phím bình thường
  button.hidden = false;
  if (support === "insecure") {
    button.title = "Nhận giọng nói cần mở trang qua HTTPS hoặc localhost";
    return;
  }
  voice = new VoiceSearch({
    onInterim: (text) => {
      $("q").value = text;
    },
    onFinal: (alternatives) => {
      const best = alternatives[0];
      state.voice = { ...best, alternatives, at: new Date().toISOString() };
      state.voiceLog.push(state.voice);
      $("q").value = best.transcript;
      state.filters.spell = true;
      scheduleSearch(0);
    },
    onError: (code) => toast("Không nhận được giọng nói", VOICE_ERRORS[code] ?? `Lỗi: ${code}`, "error"),
    onStateChange: (listening) => {
      button.setAttribute("aria-pressed", String(listening));
      button.title = listening ? "Đang nghe… bấm để dừng" : "Tìm bằng giọng nói";
      $("q").placeholder = listening ? "Đang nghe, hãy nói…" : "Tìm quán ăn, photocopy, Circle K…";
    },
  });
}

function toggleVoice() {
  if (!voice) {
    toast("Chưa dùng được giọng nói", "Mở trang qua HTTPS hoặc localhost (trên điện thoại cần đường dẫn HTTPS).", "error");
    return;
  }
  if (voice.listening) voice.stop();
  else voice.start();
}

function renderVoiceNote(meta) {
  const note = $("voice-note");
  const v = state.voice;
  if (!v || v.transcript !== meta.query) {
    note.hidden = true;
    note.replaceChildren();
    return;
  }
  const others = v.alternatives.slice(1);
  note.replaceChildren(
    `Nghe được “${v.transcript}” (độ tin cậy ${fmtConfidence(v.confidence)}). `,
    others.length ? "Hay là: " : null,
    others.flatMap((a, i) => [
      el("button", { type: "button", className: "btn-link", "data-action": "voice-alt", "data-index": i + 1 }, `“${a.transcript}”`),
      " ",
    ]),
    el("button", { type: "button", className: "btn-link voice-log-link", "data-action": "voice-log" }, `Tải nhật ký giọng nói (${state.voiceLog.length})`),
  );
  note.hidden = false;
}

function useVoiceAlternative(index) {
  const alt = state.voice?.alternatives[index];
  if (!alt) return;
  // Giữ nguyên danh sách cách nghe, chỉ đổi câu đang dùng.
  state.voice = { ...state.voice, transcript: alt.transcript, confidence: alt.confidence, chosen: index };
  state.voiceLog.push(state.voice);
  $("q").value = alt.transcript;
  scheduleSearch(0);
}

// CSV dùng để điền eval/voice_queries.csv (thêm base_query_id, người nói, thiết bị).
function downloadVoiceLog() {
  const quote = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  const rows = [["at", "transcript", "confidence", "alternatives"]];
  for (const v of state.voiceLog) {
    rows.push([v.at, v.transcript, v.confidence, v.alternatives.map((a) => a.transcript).join(" | ")]);
  }
  const csv = "\uFEFF" + rows.map((r) => r.map(quote).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const link = el("a", { href: url, download: "voice_log.csv" });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ---------- Tìm bằng ảnh biển hiệu (OCR) ----------

function startPhoto() {
  $("photo-input").click();
}

async function startOcr(file) {
  if (state.ocr?.previewUrl) URL.revokeObjectURL(state.ocr.previewUrl);
  const ocr = { status: "reading", previewUrl: URL.createObjectURL(file), stage: "Đang chuẩn bị", progress: 0 };
  state.ocr = ocr;
  renderOcr();
  if (sheet.enabled) sheet.set("peek");
  try {
    ocr.result = await readImage(file, ({ stage, progress }) => {
      if (state.ocr !== ocr) return;
      ocr.stage = stage;
      ocr.progress = progress;
      renderOcr();
    });
    if (state.ocr !== ocr) return;
    if (!ocr.result.text.trim()) {
      ocr.status = "done";
      ocr.matches = [];
      renderOcr();
      return;
    }
    ocr.status = "building";
    renderOcr();
    const text = ocr.result.text.slice(0, state.config.ocr.max_text_chars);
    ocr.query = await getJSON(`/api/ocr-query?${new URLSearchParams({ text })}`);
    if (state.ocr !== ocr) return;
    if (!ocr.query.query) {
      ocr.status = "done";
      ocr.matches = [];
      logOcr(ocr, []);
      renderOcr();
      return;
    }
    applyOcrQuery(ocr);
  } catch (err) {
    if (state.ocr !== ocr) return;
    ocr.status = "error";
    ocr.error = err instanceof OcrMissingError ? err.message : `Không đọc được ảnh: ${err.message}`;
    renderOcr();
  }
}

// Tìm theo chữ trên ảnh: nối OR, xếp BM25, bỏ lọc danh mục, bán kính rộng (người chụp có thể không đứng gần).
function applyOcrQuery(ocr) {
  const radius = state.config.ocr.search_radius_m;
  $("q").value = ocr.query.query;
  state.voice = null;
  state.filters = { ...state.filters, category: "", radius, sort: "bm25", alpha: null, match: "any" };
  $("category-all").checked = true;
  $(`radius-${radius}`).checked = true;
  $("sort-bm25").checked = true;
  map.setRadius(radius);
  map.fitToRadius();
  ocr.status = "searching";
  renderOcr();
  scheduleSearch(0);
}

// Gọi từ renderResults: nhận kết quả của đúng truy vấn từ ảnh.
function finishOcrSearch(items, meta) {
  const ocr = state.ocr;
  if (!ocr || ocr.status !== "searching" || meta.match !== "any" || meta.query !== ocr.query.query) return;
  ocr.status = "done";
  ocr.matches = items.slice(0, 3);
  logOcr(ocr, ocr.matches);
  renderOcr();
  if (ocr.matches.length) select(ocr.matches[0].id, "list");
}

function logOcr(ocr, matches) {
  state.ocrLog.push({
    at: new Date().toISOString(),
    text: ocr.result.text.trim(),
    confidence: Math.round(ocr.result.confidence),
    ms: ocr.result.ms,
    query: ocr.query?.query ?? "",
    top: matches.map((m) => m.id),
    topNames: matches.map((m) => m.name),
  });
}

function closeOcr() {
  if (state.ocr?.previewUrl) URL.revokeObjectURL(state.ocr.previewUrl);
  state.ocr = null;
  renderOcr();
}

function renderOcrNote(meta) {
  const note = $("ocr-note");
  note.hidden = meta.match !== "any";
  note.replaceChildren(
    ...(meta.match === "any"
      ? [
          "Đang tìm theo chữ trên ảnh: khớp bất kỳ từ nào, xếp theo độ khớp từ khóa. ",
          el("button", { type: "button", className: "btn-link", "data-action": "match-all" }, "Tìm như bình thường"),
        ]
      : []),
  );
}

function renderOcr() {
  const card = $("ocr-card");
  const ocr = state.ocr;
  card.hidden = !ocr;
  if (!ocr) {
    card.replaceChildren();
    return;
  }
  const parts = [
    el(
      "div",
      { className: "activity-head" },
      el("h2", {}, "Đọc biển hiệu"),
      el("button", { type: "button", className: "btn-icon", "data-action": "close-ocr", "aria-label": "Đóng" }, "×"),
    ),
    el("img", { className: "ocr-preview", src: ocr.previewUrl, alt: "Ảnh đã chọn" }),
  ];
  if (ocr.status === "reading") {
    parts.push(
      el("p", { className: "muted" }, `${ocr.stage}…`),
      el("progress", { className: "ocr-progress", max: "1", value: String(ocr.progress || 0) }),
      el("p", { className: "fineprint" }, "Chữ được đọc ngay trên máy, ảnh không gửi đi đâu."),
    );
  } else if (ocr.status === "building" || ocr.status === "searching") {
    parts.push(el("p", { className: "muted" }, "Đang tìm địa điểm khớp…"));
  } else if (ocr.status === "error") {
    parts.push(el("p", { className: "error-text" }, ocr.error));
  } else {
    const r = ocr.result;
    const q = ocr.query;
    parts.push(
      el(
        "details",
        { className: "whynot-more" },
        el("summary", {}, `Chữ đọc được (độ tin cậy ${Math.round(r.confidence)}%, ${(r.ms / 1000).toFixed(1)} giây)`),
        el("pre", { className: "ocr-text" }, r.text.trim() || "(không đọc được chữ nào)"),
      ),
    );
    if (q?.kept.length) {
      parts.push(
        el("p", { className: "ocr-query" }, "Tìm theo: ", q.kept.map((k) => el("span", { className: "token-chip", title: `có trong ${k.df} địa điểm` }, k.token))),
      );
    }
    if (q?.dropped.length || q?.corrections.length) {
      parts.push(
        el(
          "details",
          { className: "whynot-more" },
          el("summary", {}, `Đã bỏ ${q.dropped.length} từ, sửa ${q.corrections.length} chỗ`),
          el(
            "ul",
            { className: "fineprint tech-list" },
            q.corrections.map((c) => el("li", {}, `${c.from} → ${c.to}`)),
            q.dropped.map((d) => el("li", {}, `${d.token}: ${d.reason}`)),
          ),
        ),
      );
    }
    if (ocr.matches.length) {
      parts.push(
        el("h3", {}, "Có thể là"),
        el(
          "ol",
          { className: "suggestion-list" },
          ocr.matches.map((m) =>
            el(
              "li",
              { className: "suggestion" },
              el("div", { className: "suggestion-text" }, el("strong", {}, m.name), el("span", { className: "muted" }, ` · ${m.category_label} · cách ${fmtDistance(m.distance_m)}`)),
              el("button", { type: "button", className: "btn btn-sm", "data-action": "ocr-select", "data-id": m.id }, "Xem"),
            ),
          ),
        ),
      );
    } else {
      parts.push(
        el(
          "p",
          { className: "warn-text" },
          "Không khớp địa điểm nào trong dữ liệu. Quán có thể chưa có trong dữ liệu, hoặc chữ trên ảnh khó đọc: thử chụp gần, thẳng và đủ sáng.",
        ),
      );
    }
    parts.push(
      el(
        "div",
        { className: "activity-links" },
        el("button", { type: "button", className: "btn btn-sm", "data-action": "ocr-again" }, "Chụp ảnh khác"),
        el("button", { type: "button", className: "btn-link voice-log-link", "data-action": "ocr-log" }, `Tải nhật ký ảnh (${state.ocrLog.length})`),
      ),
    );
  }
  card.replaceChildren(...parts);
}

// CSV dùng để điền eval/ocr_cases.csv (thêm case_id, target_poi_id, thiết bị).
function downloadOcrLog() {
  const quote = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  const rows = [["at", "ocr_text", "ocr_confidence", "ocr_ms", "query", "top_ids", "top_names"]];
  for (const o of state.ocrLog) rows.push([o.at, o.text, o.confidence, o.ms, o.query, o.top.join(" | "), o.topNames.join(" | ")]);
  const csv = "﻿" + rows.map((r) => r.map(quote).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const link = el("a", { href: url, download: "ocr_log.csv" });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ---------- Lộ trình nhiều chặng ----------
// Ba chặng mặc định (cà phê → ăn tối → phim), nhưng chấp nhận 2–4 chặng bất kỳ (config/app.json
// itinerary.min_legs/max_legs). Đây là bài toán tối ưu không gian theo chuỗi, không phải top-k đơn
// như tìm kiếm chính: vét cạn tổ hợp ứng viên khớp từ khóa mỗi chặng trên backend (src/itinerary.py),
// lọc theo tổng quãng đường ước tính. "Chỉ đường thật" gọi lại đúng /api/route (OSRM) cho từng chặng,
// không thêm lệnh gọi máy chủ ngoài mới.

function itineraryDefaults() {
  const icfg = state.config.itinerary;
  return { legs: [...icfg.default_legs_hint], maxDistanceM: icfg.default_max_distance_m, dwellMin: icfg.default_dwell_min };
}

function openItinerary() {
  itineraryController?.abort();
  cancelItineraryRealRoutes();
  map.clearItinerary();
  state.itinerary = { status: "form", ...itineraryDefaults(), error: null };
  renderItinerary();
  if (sheet.enabled) sheet.set("peek");
}

function closeItinerary() {
  itineraryController?.abort();
  cancelItineraryRealRoutes();
  state.itinerary = null;
  map.clearItinerary();
  renderItinerary();
}

function readItineraryForm() {
  const card = $("itinerary-card");
  const legs = [...card.querySelectorAll('[data-role="leg-input"]')].map((i) => i.value);
  const checked = card.querySelector('input[name="itinerary-max-distance"]:checked');
  const maxDistanceM = checked ? Number(checked.value) : itineraryDefaults().maxDistanceM;
  const dwellInput = card.querySelector("#itinerary-dwell");
  const dwellMin = dwellInput ? Number(dwellInput.value) : itineraryDefaults().dwellMin;
  return { legs, maxDistanceM, dwellMin };
}

function addLeg() {
  const it = state.itinerary;
  const icfg = state.config.itinerary;
  if (!it || it.legs.length >= icfg.max_legs) return;
  const read = readItineraryForm();
  const hint = icfg.default_legs_hint[read.legs.length] ?? "";
  state.itinerary = { status: "form", legs: [...read.legs, hint], maxDistanceM: read.maxDistanceM, dwellMin: read.dwellMin, error: null };
  renderItinerary();
}

function removeLeg() {
  const it = state.itinerary;
  const icfg = state.config.itinerary;
  if (!it || it.legs.length <= icfg.min_legs) return;
  const read = readItineraryForm();
  state.itinerary = { status: "form", legs: read.legs.slice(0, -1), maxDistanceM: read.maxDistanceM, dwellMin: read.dwellMin, error: null };
  renderItinerary();
}

function cancelItineraryRealRoutes() {
  for (const c of itineraryRouteAbort) c.abort();
  itineraryRouteAbort = [];
}

async function submitItinerary(e) {
  e.preventDefault();
  const { legs, maxDistanceM, dwellMin } = readItineraryForm();
  const cleaned = legs.map((s) => s.trim());
  if (cleaned.some((s) => !s)) {
    state.itinerary = { status: "form", legs, maxDistanceM, dwellMin, error: "Mỗi chặng cần một từ khóa." };
    renderItinerary();
    return;
  }
  itineraryController?.abort();
  itineraryController = new AbortController();
  cancelItineraryRealRoutes();
  map.clearItinerary();
  state.itinerary = { status: "loading", legs: cleaned, maxDistanceM, dwellMin };
  renderItinerary();

  const { lat, lon, mode } = state.origin;
  const params = new URLSearchParams({ lat, lon, origin_mode: mode, max_distance_m: maxDistanceM, dwell_min: dwellMin });
  for (const leg of cleaned) params.append("stop", leg);
  try {
    const data = await getJSON(`/api/itinerary?${params}`, { signal: itineraryController.signal });
    state.itinerary = { status: "ok", legs: cleaned, maxDistanceM, dwellMin, data, chosen: 0, realRoute: null };
    if (data.routes.length) map.showItineraryStops([lat, lon], data.routes[0].stops);
  } catch (err) {
    if (err.name === "AbortError") return;
    state.itinerary = { status: "error", legs: cleaned, maxDistanceM, dwellMin, error: `Không lập được lộ trình: ${err.message}` };
  }
  renderItinerary();
}

function chooseRoute(index) {
  const it = state.itinerary;
  if (!it?.data?.routes[index]) return;
  cancelItineraryRealRoutes();
  state.itinerary = { ...it, chosen: index, realRoute: null };
  const { lat, lon } = state.origin;
  map.showItineraryStops([lat, lon], it.data.routes[index].stops);
  renderItinerary();
}

// Gọi /api/route (OSRM) lần lượt cho từng chặng của lộ trình đang xem; máy chủ tự giãn ≥ 1 giây/lần
// (src/routing.py), nên các lệnh gọi vẫn tôn trọng điều khoản dù bấm liên tiếp nhiều lộ trình.
async function computeRealRoute() {
  const it = state.itinerary;
  const route = it?.data?.routes[it.chosen ?? 0];
  if (!route) return;
  cancelItineraryRealRoutes();
  const { lat, lon } = state.origin;
  map.clearItinerary();
  map.showItineraryStops([lat, lon], route.stops);

  const legs = route.stops.map((s, i) => ({ from: i === 0 ? { lat, lon } : route.stops[i - 1], to: s }));
  const results = legs.map(() => ({ status: "loading" }));
  state.itinerary = { ...it, realRoute: { status: "loading", legs: results } };
  renderItinerary();

  for (let i = 0; i < legs.length; i++) {
    const controller = new AbortController();
    itineraryRouteAbort.push(controller);
    const params = new URLSearchParams({ from_lat: legs[i].from.lat, from_lon: legs[i].from.lon, poi_id: legs[i].to.id });
    try {
      const data = await getJSON(`/api/route?${params}`, { signal: controller.signal });
      results[i] = { status: "ok", data };
      map.showItineraryLegPath(data.route.path);
    } catch (err) {
      if (err.name === "AbortError") return;
      results[i] = { status: "error", error: err.message, fallbackUrl: err.body?.google_maps_url ?? null };
    }
    state.itinerary = { ...state.itinerary, realRoute: { status: "loading", legs: [...results] } };
    renderItinerary();
  }
  const ok = results.every((r) => r.status === "ok");
  state.itinerary = { ...state.itinerary, realRoute: { status: ok ? "ok" : "partial", legs: results } };
  renderItinerary();
}

function itineraryForm(it) {
  const icfg = state.config.itinerary;
  const legInputs = it.legs.map((value, i) =>
    el(
      "label",
      { className: "itinerary-leg" },
      `Chặng ${i + 1}`,
      el("input", { type: "text", "data-role": "leg-input", maxlength: "120", value, placeholder: icfg.default_legs_hint[i] ?? "" }),
    ),
  );
  const distanceField = el("fieldset", { className: "segmented itinerary-distance" }, el("legend", {}, "Tổng quãng đường tối đa"));
  radioGroup(
    distanceField,
    "itinerary-max-distance",
    icfg.allowed_max_distance_m.map((m) => ({ value: m, label: fmtRadius(m) })),
    it.maxDistanceM,
    () => {},
  );
  return el(
    "form",
    { className: "itinerary-form", "data-role": "plan" },
    el("div", { className: "itinerary-legs" }, legInputs),
    el(
      "div",
      { className: "itinerary-leg-buttons" },
      it.legs.length > icfg.min_legs ? el("button", { type: "button", className: "btn btn-sm", "data-action": "remove-leg" }, "− Bớt chặng") : null,
      it.legs.length < icfg.max_legs ? el("button", { type: "button", className: "btn btn-sm", "data-action": "add-leg" }, "+ Thêm chặng") : null,
    ),
    distanceField,
    el(
      "label",
      { className: "itinerary-dwell" },
      "Thời gian mỗi chặng (phút, ước tính) ",
      el("input", { type: "number", id: "itinerary-dwell", min: "0", max: "600", step: "5", value: it.dwellMin }),
    ),
    it.error ? el("p", { className: "error-text" }, it.error) : null,
    el("button", { type: "submit", className: "btn btn-sm btn-primary" }, "Lập lộ trình"),
  );
}

function itineraryLegSummary(leg) {
  const text = leg.empty
    ? `Chặng “${leg.query}”: không khớp địa điểm nào trong ${fmtRadius(leg.whynot_params.radius_m)}.`
    : `Chặng “${leg.query}”: xét ${leg.candidates_considered} địa điểm khớp tốt nhất` +
      (leg.corrections.length ? ` (đã hiểu ${leg.corrections.map((c) => `“${c.from}” là “${c.to}”`).join(", ")})` : "") +
      ".";
  // Chặng không rỗng: cho hỏi vì sao một chỗ khác (không nằm trong top ứng viên) không có ở đây,
  // tái dùng đúng /api/whynot với truy vấn và bán kính của chính chặng này.
  const button = leg.empty
    ? null
    : el("button", { type: "button", className: "btn-link", "data-action": "whynot-leg", "data-leg": leg.index }, "Vì sao thiếu chỗ khác ở chặng này?");
  return el("li", { className: leg.empty ? "warn-text" : "muted" }, text, button ? [" ", button] : null);
}

function routeCard(route, index, it) {
  const chosen = (it.chosen ?? 0) === index;
  const stopsText = route.stops
    .map((s, i) => `${i + 1}. ${s.name}${i === 0 ? "" : ` (cách chặng trước ${fmtDistance(s.distance_from_prev_m)})`}`)
    .join(" → ");
  return el(
    "li",
    { className: chosen ? "suggestion suggestion-chosen" : "suggestion" },
    el("div", { className: "suggestion-text" }, stopsText),
    el(
      "div",
      { className: "suggestion-meta" },
      el("span", {}, `Tổng ${fmtDistance(route.total_distance_m)} ước tính · khoảng ${Math.round(route.total_time_min)} phút`),
      el(
        "button",
        { type: "button", className: chosen ? "btn btn-sm watching" : "btn btn-sm", "data-action": "choose-route", "data-index": index },
        chosen ? "Đang xem" : "Xem trên bản đồ",
      ),
    ),
  );
}

function renderItineraryRealRoute(it) {
  const r = it.realRoute;
  const items = r.legs.map((leg, i) => {
    if (leg.status === "loading") return el("li", {}, `Chặng ${i + 1}: đang tính…`);
    if (leg.status === "ok") {
      const d = leg.data;
      return el("li", {}, `Chặng ${i + 1}: ${fmtDistance(d.route.distance_m)} · ${fmtMinutes(d.route.duration_s)} (đi bộ, đường chim bay ${fmtDistance(d.straight_distance_m)})`);
    }
    return el(
      "li",
      { className: "error-text" },
      `Chặng ${i + 1}: không lấy được tuyến (${leg.error}).`,
      leg.fallbackUrl ? [" ", safeLink(leg.fallbackUrl, "Mở Google Maps ↗")] : null,
    );
  });
  const ok = r.legs.filter((l) => l.status === "ok");
  const totalReal = ok.length === r.legs.length ? ok.reduce((sum, l) => sum + l.data.route.distance_m, 0) : null;
  return el(
    "div",
    { className: "itinerary-real-route" },
    el("h3", {}, "Chỉ đường thật (OSRM)"),
    el("ol", { className: "fineprint tech-list" }, items),
    totalReal != null ? el("p", { className: "fineprint" }, `Tổng quãng đường đi bộ thật (từng chặng cộng lại): ${fmtDistance(totalReal)}.`) : null,
  );
}

function renderItinerary() {
  const card = $("itinerary-card");
  const it = state.itinerary;
  card.hidden = !it;
  if (!it) {
    card.replaceChildren();
    return;
  }
  const head = (title) =>
    el(
      "div",
      { className: "activity-head" },
      el("h2", {}, title),
      el("button", { type: "button", className: "btn-icon", "data-action": "close-itinerary", "aria-label": "Đóng" }, "×"),
    );

  if (it.status === "form" || it.status === "error") {
    card.replaceChildren(
      head("Lộ trình nhiều chặng"),
      el("p", { className: "activity-sub" }, "Nhập từ khóa cho mỗi chặng, theo đúng thứ tự sẽ đi qua."),
      itineraryForm(it),
    );
    return;
  }
  if (it.status === "loading") {
    card.replaceChildren(head("Lộ trình nhiều chặng"), el("p", { className: "muted" }, "Đang thử các tổ hợp địa điểm…"));
    return;
  }

  const d = it.data;
  const parts = [head("Lộ trình nhiều chặng"), el("ul", { className: "itinerary-legs-summary" }, d.legs.map(itineraryLegSummary))];

  if (d.routes.length === 0) {
    parts.push(
      el(
        "p",
        { className: "warn-text" },
        d.min_total_distance_m == null
          ? "Không có tổ hợp hợp lệ: một chặng không khớp địa điểm nào, hoặc hai chặng chỉ khớp đúng cùng một địa điểm."
          : `Không có lộ trình nào trong ${fmtRadius(it.maxDistanceM)}. Lộ trình ngắn nhất tìm được khoảng ${fmtDistance(d.min_total_distance_m)}; thử nới ngân sách quãng đường.`,
      ),
    );
  } else {
    parts.push(
      el("h3", {}, `${d.routes.length} lộ trình tốt nhất`),
      el("ol", { className: "suggestion-list" }, d.routes.map((r, i) => routeCard(r, i, it))),
      el(
        "div",
        { className: "activity-links" },
        el("button", { type: "button", className: "btn btn-sm btn-primary", "data-action": "real-route" }, "Chỉ đường thật cho lộ trình đang xem"),
      ),
    );
    if (it.realRoute) parts.push(renderItineraryRealRoute(it));
  }

  parts.push(
    el("details", { className: "whynot-more" }, el("summary", {}, "Đổi chặng hoặc ngân sách"), itineraryForm(it)),
    el(
      "p",
      { className: "fineprint" },
      `Đã xét ${d.combos_considered} tổ hợp (${d.combos_within_distance} trong ngân sách) trong ${d.elapsed_ms} ms. ` +
        `Quãng đường ước tính = đường chim bay × ${d.config.detour_factor} (hệ số quanh co, đặt tay), tốc độ đi bộ ${d.config.walking_speed_mps} m/s. ` +
        "Không xử lý giờ chiếu phim, giờ mở cửa hay tình trạng còn chỗ.",
    ),
  );
  card.replaceChildren(...parts);
}

// ---------- Vì sao không có? (why-not) ----------

const STEP_ICONS = { pass: "✓", fail: "✗", skip: "–", blocked: "…" };
const STEP_HINTS = { pass: "qua bước này", fail: "bị loại ở bước này", skip: "không áp dụng", blocked: "chưa tới bước này" };
const SHOWN_SUGGESTIONS = 3;
let whyNotChoices = [];

// Nhãn duy nhất cho từng địa điểm trong ô gõ tên (datalist cần giá trị khác nhau: có nhiều "Pizza Hut").
function poiChoices() {
  const { lat, lon } = state.origin;
  const seen = new Map();
  return state.pois.map((p) => {
    let label = `${p.name} · ${p.address || p.category_label} · ${fmtDistance(haversineM(lat, lon, p.lat, p.lon))}`;
    const n = (seen.get(label) ?? 0) + 1;
    seen.set(label, n);
    if (n > 1) label += ` (${n})`;
    return { id: p.id, label };
  });
}

// whyNotOverride: khác null khi đang hỏi cho một chặng của lộ trình nhiều chặng (không phải ô tìm
// kiếm chính). openWhyNot() bình thường xóa cờ này; openWhyNotForLeg() đặt cờ rồi mở như thường.
let whyNotOverride = null;

function openWhyNot(error = null, keepOverride = false) {
  if (!keepOverride) whyNotOverride = null;
  whyNotController?.abort();
  state.whyNot = { status: "pick", error };
  renderWhyNot();
  if (sheet.enabled) sheet.set("peek");
  $("whynot-input")?.focus();
}

function openWhyNotForLeg(leg) {
  whyNotOverride = { q: leg.query, radius_m: leg.whynot_params.radius_m };
  openWhyNot(null, true);
}

// overrideParams: {q, radius_m, category} dùng khi hỏi vì sao thiếu một chặng của lộ trình nhiều
// chặng, thay cho tham số của ô tìm kiếm chính (currentQueryParams()).
async function askWhyNot(poiId, k = state.config.whynot.k, overrideParams = null) {
  whyNotController?.abort();
  whyNotController = new AbortController();
  state.whyNot = { status: "loading", poiId };
  renderWhyNot();
  if (sheet.enabled) sheet.set("peek");
  const { lat, lon, mode } = state.origin;
  const params = overrideParams
    ? new URLSearchParams({ ...overrideParams, lat, lon, origin_mode: mode, sort: "distance" })
    : currentQueryParams();
  params.set("poi_id", poiId);
  params.set("k", k);
  try {
    const data = await getJSON(`/api/whynot?${params}`, { signal: whyNotController.signal });
    state.whyNot = { status: "ok", poiId, data };
    map.showWhyNotTarget(data.target);
  } catch (err) {
    if (err.name === "AbortError") return;
    state.whyNot = { status: "error", poiId, error: `Không phân tích được: ${err.message}` };
  }
  renderWhyNot();
}

function clearWhyNot() {
  whyNotController?.abort();
  state.whyNot = null;
  whyNotOverride = null;
  map.clearWhyNotTarget();
  renderWhyNot();
}

function applySuggestion(index) {
  const data = state.whyNot?.data;
  const s = data?.suggestions[index];
  if (!s) return;
  const p = s.params;
  $("q").value = p.q;
  const radiusChanged = p.radius_m !== state.filters.radius;
  state.filters = { category: p.category ?? "", radius: p.radius_m, sort: p.sort, alpha: p.alpha, spell: state.filters.spell, match: state.filters.match };
  $(`category-${p.category || "all"}`).checked = true;
  $(`radius-${p.radius_m}`).checked = true;
  $(`sort-${p.sort}`).checked = true;
  if (radiusChanged) {
    map.setRadius(p.radius_m);
    map.fitToRadius();
  }
  state.pendingSelect = data.target.id;
  // Hỏi lại với k' của đề xuất để người xem thấy địa điểm đã vào kết quả.
  state.pendingWhyNot = { poiId: data.target.id, k: p.k };
  scheduleSearch(0);
}

function showInList(poiId) {
  if (document.querySelector(`.card[data-id="${CSS.escape(poiId)}"]`)) select(poiId, "list");
  else toast("Không có trong danh sách đang hiện", "Danh sách chỉ hiện tối đa 50 kết quả đầu.");
}

function whyNotPicker() {
  whyNotChoices = poiChoices();
  return el(
    "form",
    { className: "whynot-form", "data-role": "picker" },
    el("input", {
      type: "search",
      id: "whynot-input",
      list: "whynot-options",
      placeholder: "Gõ tên chỗ bạn mong thấy, ví dụ Circle K",
      "aria-label": "Tên địa điểm mong đợi",
      autocomplete: "off",
    }),
    el("datalist", { id: "whynot-options" }, whyNotChoices.map((c) => el("option", { value: c.label }))),
    el("button", { type: "submit", className: "btn btn-sm btn-primary" }, "Hỏi"),
  );
}

// Khớp chữ người dùng gõ với một địa điểm: đúng nhãn trong danh sách gợi ý, hoặc tên duy nhất.
function resolvePoiChoice(text) {
  const value = text.trim().toLowerCase();
  if (!value) return null;
  const exact = whyNotChoices.find((c) => c.label.toLowerCase() === value);
  if (exact) return exact.id;
  const byName = state.pois.filter((p) => p.name.toLowerCase() === value);
  return byName.length === 1 ? byName[0].id : null;
}

function suggestionItem(s, index, d) {
  const k = d.query.k;
  const onlyK = s.family === "k";
  const text = onlyK ? "Giữ nguyên truy vấn, kéo xuống danh sách" : s.changes.filter((c) => c.dim !== "k").map((c) => c.text).join(" + ");
  const outcome = s.rank <= k ? `→ vào ${k} kết quả đầu (hạng ${s.rank})` : `→ đứng hạng ${s.rank}`;
  const button = onlyK
    ? el("button", { type: "button", className: "btn btn-sm", "data-action": "show-in-list", "data-id": d.target.id }, "Xem trong danh sách")
    : el("button", { type: "button", className: "btn btn-sm btn-primary", "data-action": "apply-suggestion", "data-index": index }, "Áp dụng");
  return el(
    "li",
    { className: "suggestion" },
    el("div", { className: "suggestion-text" }, el("strong", {}, text), el("span", { className: "muted" }, ` ${outcome}`)),
    button,
  );
}

function renderWhyNot() {
  const card = $("whynot-card");
  const w = state.whyNot;
  card.hidden = !w;
  if (!w) {
    card.replaceChildren();
    return;
  }
  const head = (title) =>
    el(
      "div",
      { className: "activity-head" },
      el("h2", {}, title),
      el("button", { type: "button", className: "btn-icon", "data-action": "close-whynot", "aria-label": "Đóng" }, "×"),
    );
  const k = state.config.whynot.k;

  if (w.status === "pick" || w.status === "error") {
    const scope = whyNotOverride
      ? `Đang hỏi theo chặng “${whyNotOverride.q}” của lộ trình nhiều chặng (bán kính ${fmtRadius(whyNotOverride.radius_m)}), không theo ô tìm kiếm chính.`
      : `Chọn chỗ bạn mong thấy trong ${k} kết quả đầu của truy vấn hiện tại. Ứng dụng cho biết nó bị loại ở bước nào và cách sửa truy vấn ít nhất.`;
    card.replaceChildren(
      head("Vì sao không thấy?"),
      el("p", { className: "activity-sub" }, scope),
      whyNotPicker(),
      w.error ? el("p", { className: "error-text" }, w.error) : null,
    );
    return;
  }
  if (w.status === "loading") {
    card.replaceChildren(head("Vì sao không thấy?"), el("p", { className: "muted" }, "Đang phân tích…"));
    return;
  }

  const d = w.data;
  const t = d.target;
  const parts = [
    head(d.in_top_k ? `“${t.name}” đã có trong ${d.query.k} kết quả đầu` : `Vì sao không thấy “${t.name}”?`),
    el(
      "p",
      { className: "activity-sub" },
      `${t.category_label} · cách ${fmtDistance(t.distance_m)} · `,
      el("button", { type: "button", className: "btn-link", "data-action": "pick-again" }, "Hỏi chỗ khác"),
    ),
    el(
      "ol",
      { className: "steps", "aria-label": "Các bước xử lý truy vấn" },
      d.steps.map((s) =>
        el(
          "li",
          { className: `step step-${s.status}`, title: STEP_HINTS[s.status] },
          el("span", { className: "step-icon", "aria-hidden": "true" }, STEP_ICONS[s.status]),
          s.label,
        ),
      ),
    ),
    ...d.reasons.map((r) => el("p", { className: `reason reason-${r.code in REASON_CLASS ? r.code : "other"}` }, r.short)),
  ];

  if (d.reasons.some((r) => r.code === "TEXT")) {
    const doc = t.indexed_text;
    parts.push(
      el(
        "details",
        { className: "whynot-more" },
        el("summary", {}, "Dữ liệu của địa điểm (đúng thứ được tìm kiếm)"),
        el(
          "p",
          { className: "fineprint" },
          "Tên ",
          el("code", {}, doc.name || "—"),
          " · danh mục ",
          el("code", {}, doc.category || "—"),
          " · thẻ ",
          el("code", {}, doc.tags || "—"),
          doc.description ? [" · mô tả ", el("code", {}, doc.description)] : null,
          ". Nếu từ bạn gõ đúng mà dữ liệu thiếu, đây là chỗ nên bổ sung dữ liệu.",
        ),
      ),
    );
  }

  if (!d.in_top_k) {
    if (d.suggestions.length === 0) {
      parts.push(el("p", { className: "warn-text" }, "Không tìm được cách sửa truy vấn trong giới hạn cho phép."));
    } else {
      parts.push(el("h3", {}, "Cách để thấy nó"));
      const items = d.suggestions.map((s, i) => suggestionItem(s, i, d));
      parts.push(el("ol", { className: "suggestion-list" }, items.slice(0, SHOWN_SUGGESTIONS)));
      if (items.length > SHOWN_SUGGESTIONS) {
        parts.push(
          el(
            "details",
            { className: "whynot-more" },
            el("summary", {}, `Cách khác (${items.length - SHOWN_SUGGESTIONS})`),
            el("ol", { className: "suggestion-list", start: SHOWN_SUGGESTIONS + 1 }, items.slice(SHOWN_SUGGESTIONS)),
          ),
        );
      }
    }
    parts.push(
      el(
        "details",
        { className: "whynot-more" },
        el("summary", {}, "Chi tiết kỹ thuật"),
        el(
          "ul",
          { className: "fineprint tech-list" },
          d.suggestions.map((s) =>
            el(
              "li",
              {},
              `${s.family}: penalty ${s.penalty.toFixed(3)} (Δk ${s.delta_k}, Δq ${s.delta_q}), giữ ${
                s.retained === null ? "—" : `${Math.round(s.retained * 100)}%`
              } kết quả cũ`,
            ),
          ),
        ),
        el(
          "p",
          { className: "fineprint" },
          `${d.query.k} kết quả đầu hiện tại: ${d.original_top_k.map((i) => i.name).join(", ") || "(trống)"}. ` +
            `Penalty = λ·Δk + (1 − λ)·Δq, λ = ${d.penalty.lambda} (đặt tay). Mỗi đề xuất đã được chạy lại bằng chính bộ tìm kiếm. ` +
            `Đã xét ${d.options_considered} phương án trong ${d.elapsed_ms} ms.`,
        ),
      ),
    );
  }
  card.replaceChildren(...parts);
}

// ---------- Chỉ đường ----------

function originPhrase(origin) {
  if (origin.mode === "gps") return "vị trí thật của bạn";
  if (origin.mode === "simulated") return "vị trí mô phỏng";
  return "tâm khuôn viên";
}

const stat = (value, label) => el("div", { className: "stat" }, el("b", {}, value), el("span", {}, label));

async function requestRoute(poi) {
  select(poi.id, "list");
  routeController?.abort();
  routeController = new AbortController();
  const origin = { ...state.origin };
  state.route = { poi: { id: poi.id, name: poi.name }, origin, status: "loading", stale: false };
  map.clearRoute();
  renderRoute();

  const params = new URLSearchParams({ from_lat: origin.lat, from_lon: origin.lon, poi_id: poi.id });
  try {
    const data = await getJSON(`/api/route?${params}`, { signal: routeController.signal });
    state.route = { ...state.route, status: "ok", data };
    map.showRoute(data.route.path);
  } catch (err) {
    if (err.name === "AbortError") return;
    state.route = { ...state.route, status: "error", error: err.message, fallbackUrl: err.body?.google_maps_url ?? null };
  }
  renderRoute();
}

function clearRoute() {
  routeController?.abort();
  state.route = null;
  map.clearRoute();
  renderRoute();
}

function renderRoute() {
  const card = $("route-card");
  const r = state.route;
  card.hidden = !r;
  if (!r) {
    card.replaceChildren();
    return;
  }
  const parts = [
    el(
      "div",
      { className: "activity-head" },
      el("h2", {}, "Chỉ đường đi bộ"),
      el("button", { type: "button", className: "btn-icon", "data-action": "close-route", "aria-label": "Đóng chỉ đường" }, "×"),
    ),
    el("p", { className: "activity-sub" }, `Từ ${originPhrase(r.origin)} đến `, el("strong", {}, r.poi.name)),
  ];
  if (r.status === "loading") {
    parts.push(el("p", { className: "muted" }, "Đang lấy tuyến đường…"));
  } else if (r.status === "ok") {
    const d = r.data;
    parts.push(
      el(
        "div",
        { className: "route-stats" },
        stat(fmtDistance(d.route.distance_m), `theo tuyến ${d.mode_label}`),
        stat(fmtMinutes(d.route.duration_s), "máy chủ ước tính"),
        stat(fmtDistance(d.straight_distance_m), "đường chim bay"),
      ),
      el(
        "p",
        { className: "fineprint" },
        `Tuyến và thời gian do ${d.provider} tính cho người ${d.mode_label}. ${d.attribution}. `,
        safeLink(d.fix_the_map_url, "Báo lỗi bản đồ"),
      ),
    );
  } else {
    parts.push(el("p", { className: "error-text" }, `Không lấy được tuyến trong ứng dụng: ${r.error}. Ứng dụng không vẽ đường thay thế.`));
  }
  if (r.stale) {
    parts.push(
      el(
        "p",
        { className: "warn-text" },
        "Vị trí gốc đã thay đổi. ",
        el("button", { type: "button", className: "btn-link", "data-action": "reroute" }, "Tính lại tuyến"),
      ),
    );
  }
  const fallback = r.data?.google_maps_url ?? r.fallbackUrl;
  if (fallback) {
    parts.push(
      el(
        "div",
        { className: "activity-links" },
        safeLink(fallback, "Mở Google Maps ↗", "btn btn-sm"),
        el("span", { className: "fineprint" }, "chỉ đường ngoài ứng dụng"),
      ),
    );
  }
  card.replaceChildren(...parts);
}

// ---------- Geofence ----------

function addLog(type, text, mode = null, at = Date.now()) {
  state.events.unshift({ type, text, mode, at });
  state.events.length = Math.min(state.events.length, MAX_LOG);
}

async function toggleWatch(poiId) {
  if (state.fence?.target.id === poiId) {
    stopGeofence();
    return;
  }
  let poi;
  try {
    // POI theo dõi lấy riêng, không phụ thuộc danh sách kết quả hiện tại.
    poi = await getJSON(`/api/pois/${encodeURIComponent(poiId)}`);
  } catch (err) {
    toast("Không bật được theo dõi", err.message, "error");
    return;
  }
  if (state.fence) addLog("stop", `Dừng theo dõi ${state.fence.target.name}`);
  const cfg = state.config.geofence;
  state.fence = { target: poi, geofence: new Geofence({ id: poi.id, name: poi.name, lat: poi.lat, lon: poi.lon }, cfg), last: null };
  map.showGeofence(poi, cfg.enter_m, cfg.exit_m);
  map.setGeofenceState("UNKNOWN");
  addLog("start", `Bắt đầu theo dõi ${poi.name}`);
  if (state.origin.mode === "gps") feedGeofence(state.origin);
  renderGeofence();
  refreshWatchButtons();
  if (sheet.enabled) sheet.set("peek");
}

function stopGeofence() {
  if (!state.fence) return;
  addLog("stop", `Dừng theo dõi ${state.fence.target.name}`);
  state.fence = null;
  map.clearGeofence();
  renderGeofence();
  refreshWatchButtons();
}

function resetGeofence(reason) {
  if (!state.fence) return;
  state.fence.geofence.reset();
  state.fence.last = null;
  map.setGeofenceState("UNKNOWN");
  addLog("reset", `Đặt lại trạng thái (${reason})`);
}

function feedGeofence(sample) {
  const fence = state.fence;
  if (!fence || (sample.mode !== "gps" && sample.mode !== "simulated")) return;
  const result = fence.geofence.update(sample);
  fence.last = result;
  map.setGeofenceState(result.state);
  if (result.initialized) {
    const where = FENCE_STATE_LABELS[result.state].toLowerCase();
    addLog("init", `Khởi tạo: ${where} (${Math.round(result.distance_m)} m), không tính là sự kiện`, sample.mode, sample.timestamp);
  }
  if (result.event) {
    const ev = result.event;
    const verb = ev.type === "enter" ? "Vào vùng" : "Ra khỏi vùng";
    const suffix = ev.notified ? "" : ", không thông báo do cooldown";
    addLog(ev.type, `${verb} ${ev.poiName} (${Math.round(ev.distance_m)} m)${suffix}`, ev.mode, ev.at);
    if (ev.notified) toast(`${verb} ${ev.poiName}`, `${Math.round(ev.distance_m)} m · ${MODE_WORDS[ev.mode]} · ${fmtTime(ev.at)}`, ev.type);
  }
}

// Mô phỏng hoạt động như một thiết bị gửi 1 mẫu/giây tại vị trí chấm cam.
function simulationTick() {
  if (!state.fence || state.origin?.mode !== "simulated") return;
  feedGeofence({ lat: state.origin.lat, lon: state.origin.lon, accuracy: null, timestamp: Date.now(), mode: "simulated" });
  renderGeofence();
}

function refreshWatchButtons() {
  for (const button of document.querySelectorAll('[data-action="watch"]')) {
    const watching = state.fence?.target.id === button.closest(".card")?.dataset.id;
    button.classList.toggle("watching", watching);
    button.setAttribute("aria-pressed", String(watching));
    button.textContent = watchLabel(watching);
  }
}

// Chỉ vẽ lại khi nội dung hiển thị đổi. Bộ mô phỏng gọi hàm này mỗi giây; vẽ lại toàn bộ mỗi lần
// làm nhật ký nhảy về đầu và làm trang giật khi đang cuộn.
function renderGeofence() {
  const card = $("geofence-card");
  const fence = state.fence;
  const last = fence?.last;
  const viewKey = JSON.stringify([
    fence?.target.id ?? null,
    fence?.geofence.state ?? null,
    last ? Math.round(last.distance_m) : null,
    last?.pending?.count ?? 0,
    Boolean(last?.lowAccuracy),
    state.origin?.mode ?? null,
    state.events.length,
    state.events[0]?.at ?? null,
  ]);
  if (viewKey === geofenceViewKey) return;
  geofenceViewKey = viewKey;
  card.hidden = !fence && state.events.length === 0;
  if (card.hidden) {
    card.replaceChildren();
    return;
  }
  const cfg = state.config.geofence;
  const action = fence
    ? el("button", { type: "button", className: "btn btn-sm", "data-action": "stop-fence" }, "Dừng theo dõi")
    : el("button", { type: "button", className: "btn-icon", "data-action": "clear-log", "aria-label": "Xóa nhật ký" }, "×");
  const parts = [el("div", { className: "activity-head" }, el("h2", {}, "Geofence"), action)];

  if (fence) {
    parts.push(
      el(
        "p",
        { className: "activity-sub" },
        "Đang theo dõi ",
        el("strong", {}, fence.target.name),
        ` · vào khi ≤ ${cfg.enter_m} m, ra khi ≥ ${cfg.exit_m} m, cần ${cfg.confirm_samples} mẫu liên tiếp`,
      ),
    );
    const current = fence.geofence.state;
    const row = [el("span", { className: `state-pill ${current}` }, FENCE_STATE_LABELS[current])];
    if (fence.last) row.push(el("span", { className: "muted" }, `cách ${Math.round(fence.last.distance_m)} m`));
    if (fence.last?.pending) row.push(el("span", { className: "muted" }, `đang xác nhận ${fence.last.pending.count}/${fence.last.pending.needed}`));
    parts.push(el("div", { className: "fence-state" }, row));
    if (fence.last?.lowAccuracy) {
      parts.push(el("p", { className: "warn-text" }, `Mẫu định vị sai số > ${cfg.max_accuracy_m} m nên giữ nguyên trạng thái.`));
    }
    if (state.origin.mode === "simulated") {
      parts.push(el("p", { className: "fineprint" }, "Mô phỏng gửi 1 mẫu/giây tại chấm cam. Kéo chấm vào hoặc ra vòng tròn để thử."));
    } else if (state.origin.mode === "reference") {
      parts.push(el("p", { className: "warn-text" }, "Tâm khuôn viên không phải vị trí di chuyển. Bật Vị trí của tôi hoặc Mô phỏng để theo dõi."));
    }
  } else {
    parts.push(el("p", { className: "activity-sub" }, "Không theo dõi điểm nào."));
  }

  const logScroll = card.querySelector(".event-log")?.scrollTop ?? 0;
  if (state.events.length) {
    const log = el(
      "details",
      { className: "event-log-wrap", open: state.logOpen },
      el("summary", {}, `Nhật ký sự kiện (${state.events.length})`),
      el(
        "ol",
        { className: "event-log" },
        state.events.map((ev) =>
          el("li", {}, el("time", {}, fmtTime(ev.at)), el("span", { className: ev.type }, ev.text, ev.mode ? ` · ${MODE_WORDS[ev.mode]}` : "")),
        ),
      ),
    );
    log.addEventListener("toggle", () => {
      state.logOpen = log.open;
    });
    parts.push(log);
  }
  parts.push(el("p", { className: "fineprint" }, "Chỉ hoạt động khi trang đang mở; không gửi thông báo nền."));
  card.replaceChildren(...parts);
  const newLog = card.querySelector(".event-log");
  if (newLog) newLog.scrollTop = logScroll;
}

// ---------- Khởi động ----------

function bindEvents() {
  $("search-form").addEventListener("submit", (e) => {
    e.preventDefault();
    scheduleSearch(0);
  });
  $("q").addEventListener("input", () => {
    // Câu mới: bật lại sửa lỗi gõ (lựa chọn "tìm đúng như đã gõ" chỉ áp cho câu trước).
    state.filters.spell = true;
    state.filters.match = "all";
    state.voice = null;
    scheduleSearch(300);
  });
  $("q").addEventListener("focus", () => {
    if (sheet.enabled) sheet.set("full");
  });
  $("fab-locate").addEventListener("click", toggleGps);

  const help = $("help-dialog");
  $("btn-help").addEventListener("click", () => help.showModal());
  $("help-close").addEventListener("click", () => help.close());
  // Bấm vào vùng nền mờ quanh hộp thoại (sự kiện nhắm vào chính <dialog>) để đóng.
  help.addEventListener("click", (e) => {
    if (e.target === help) help.close();
  });
  $("btn-gps").addEventListener("click", toggleGps);
  $("btn-simulate").addEventListener("click", toggleSimulate);
  $("btn-reference").addEventListener("click", useReference);
  $("route-card").addEventListener("click", (e) => {
    const action = e.target.closest("[data-action]")?.dataset.action;
    if (action === "close-route") clearRoute();
    else if (action === "reroute" && state.route) requestRoute(state.route.poi);
  });
  $("btn-whynot").addEventListener("click", () => openWhyNot());
  $("btn-itinerary").addEventListener("click", () => openItinerary());
  const itineraryCard = $("itinerary-card");
  itineraryCard.addEventListener("submit", (e) => {
    if (e.target.dataset.role === "plan") submitItinerary(e);
  });
  itineraryCard.addEventListener("click", (e) => {
    const target = e.target.closest("[data-action]");
    const action = target?.dataset.action;
    if (action === "close-itinerary") closeItinerary();
    else if (action === "add-leg") addLeg();
    else if (action === "remove-leg") removeLeg();
    else if (action === "choose-route") chooseRoute(Number(target.dataset.index));
    else if (action === "real-route") computeRealRoute();
    else if (action === "whynot-leg") openWhyNotForLeg(state.itinerary.data.legs[Number(target.dataset.leg)]);
  });
  $("result-list").addEventListener("click", (e) => {
    if (e.target.closest("[data-action]")?.dataset.action === "open-whynot") openWhyNot();
  });
  const whyNotCard = $("whynot-card");
  whyNotCard.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = $("whynot-input")?.value ?? "";
    const poiId = resolvePoiChoice(text);
    if (poiId) askWhyNot(poiId, state.config.whynot.k, whyNotOverride);
    else openWhyNot(text.trim() ? `Không tìm thấy “${text.trim()}”. Chọn một dòng trong danh sách gợi ý.` : null, true);
  });
  // Chọn một dòng gợi ý là hỏi luôn, không cần bấm "Hỏi".
  whyNotCard.addEventListener("change", (e) => {
    if (e.target.id !== "whynot-input") return;
    const poiId = resolvePoiChoice(e.target.value);
    if (poiId) askWhyNot(poiId, state.config.whynot.k, whyNotOverride);
  });
  whyNotCard.addEventListener("click", (e) => {
    const target = e.target.closest("[data-action]");
    const action = target?.dataset.action;
    if (action === "close-whynot") clearWhyNot();
    else if (action === "pick-again") openWhyNot(null, true);
    else if (action === "apply-suggestion") applySuggestion(Number(target.dataset.index));
    else if (action === "show-in-list") showInList(target.dataset.id);
  });
  $("btn-mic").addEventListener("click", toggleVoice);
  $("btn-photo").addEventListener("click", startPhoto);
  $("photo-input").addEventListener("change", (e) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // chọn lại cùng ảnh vẫn kích hoạt
    if (file) startOcr(file);
  });
  $("ocr-card").addEventListener("click", (e) => {
    const target = e.target.closest("[data-action]");
    const action = target?.dataset.action;
    if (action === "close-ocr") closeOcr();
    else if (action === "ocr-again") startPhoto();
    else if (action === "ocr-log") downloadOcrLog();
    else if (action === "ocr-select") showInList(target.dataset.id);
  });
  $("ocr-note").addEventListener("click", (e) => {
    if (e.target.closest("[data-action]")?.dataset.action !== "match-all") return;
    state.filters.match = "all";
    scheduleSearch(0);
  });
  $("voice-note").addEventListener("click", (e) => {
    const target = e.target.closest("[data-action]");
    if (target?.dataset.action === "voice-alt") useVoiceAlternative(Number(target.dataset.index));
    else if (target?.dataset.action === "voice-log") downloadVoiceLog();
  });
  $("spell-note").addEventListener("click", (e) => {
    const action = e.target.closest("[data-action]")?.dataset.action;
    if (action !== "spell-off" && action !== "spell-on") return;
    state.filters.spell = action === "spell-on";
    scheduleSearch(0);
  });
  $("alpha-chip").addEventListener("click", (e) => {
    if (e.target.closest("[data-action]")?.dataset.action !== "reset-alpha") return;
    state.filters.alpha = null;
    scheduleSearch(0);
  });
  $("geofence-card").addEventListener("click", (e) => {
    const action = e.target.closest("[data-action]")?.dataset.action;
    if (action === "stop-fence") stopGeofence();
    else if (action === "clear-log") {
      state.events = [];
      renderGeofence();
    }
  });
}

async function init() {
  try {
    state.config = await getJSON("/api/config");
  } catch (err) {
    setStatus(`Không tải được cấu hình: ${err.message}`, true);
    return;
  }
  fillControls();
  try {
    state.pois = (await getJSON("/api/pois")).items;
  } catch {
    state.pois = []; // chỉ ảnh hưởng ô chọn địa điểm của why-not; nút trên thẻ kết quả vẫn dùng được
  }
  const origin = referencePosition();
  map = new ResultMap($("map"), {
    mapConfig: state.config.map,
    categories: state.config.categories,
    origin,
    radius: state.filters.radius,
    onSelect: select,
    onOriginPick: (lat, lon) => handlePositionUpdate({ lat, lon, mode: "simulated", accuracy: null, timestamp: Date.now() }),
  });
  gps = new GpsTracker({
    onPosition: (position) => {
      state.gpsStatus = null;
      handlePositionUpdate(position);
    },
    onStatus: (status) => {
      state.gpsStatus = status;
      renderOrigin();
    },
  });
  sheet = new BottomSheet($("panel"), $("sheet-handle"), $("category-group"), (height) => map.setBottomInset(height));
  setupVoice();
  map.fitToRadius();
  bindEvents();
  handlePositionUpdate(origin);
  setInterval(simulationTick, 1000);
}

init();
