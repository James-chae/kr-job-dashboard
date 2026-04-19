const state = {
  jobs: [],
  meta: {},
  tab: "all",
  region: "all",
  keyword: "",
  sort: "latest",
};

const TAB_LABELS = {
  all: "전체",
  public: "공공",
  short: "단기/알바",
  clinical: "임상병리",
  cabin: "승무원",
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function text(value, fallback = "-") {
  return String(value ?? "").trim() || fallback;
}

function dateValue(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const t = Date.parse(raw);
  return Number.isNaN(t) ? "" : t;
}

function compact(value, max = 110) {
  const s = String(value || "").replace(/\s+/g, " ").trim();
  if (!s) return "";
  return s.length > max ? s.slice(0, max - 1).trim() + "…" : s;
}

function escapeHtml(str) {
  return String(str ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function matchesKeyword(job, keyword) {
  if (!keyword) return true;
  const blob = [
    job.title,
    job.organization,
    job.region,
    job.description,
    job.source,
    job.employmentType,
  ].join(" ").toLowerCase();
  return blob.includes(keyword.toLowerCase());
}

function jobSort(a, b) {
  if (state.sort === "deadline") {
    const ad = dateValue(a.deadline) || Number.MAX_SAFE_INTEGER;
    const bd = dateValue(b.deadline) || Number.MAX_SAFE_INTEGER;
    if (ad !== bd) return ad - bd;
  }
  const ap = dateValue(a.postedAt) || 0;
  const bp = dateValue(b.postedAt) || 0;
  if (ap !== bp) return bp - ap;
  return String(a.title || "").localeCompare(String(b.title || ""), "ko");
}

function getFilteredJobs() {
  return [...state.jobs]
    .filter((job) => state.tab === "all" || job.track === state.tab)
    .filter((job) => state.region === "all" || job.region === state.region)
    .filter((job) => matchesKeyword(job, state.keyword))
    .sort(jobSort);
}

function renderButtons() {
  $$("[data-tab]").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.tab === state.tab);
  });

  $$("[data-region]").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.region === state.region);
  });

  $$(".run-btn").forEach((btn) => {
    const region = btn.dataset.runRegion || "all";
    const active = btn.dataset.runTab === state.tab && region === state.region;
    btn.classList.toggle("is-run-active", active);
  });
}

function renderSummary(filtered) {
  $("#currentTabLabel").textContent = TAB_LABELS[state.tab] || "전체";
  $("#currentRegionLabel").textContent = state.region === "all" ? "전체" : state.region;
  $("#currentSortLabel").textContent = state.sort === "deadline" ? "마감임박순" : "최신순";
  $("#visibleCountLabel").textContent = `${filtered.length}건`;

  const chips = [
    `<span class="chip active-chip">탭: ${TAB_LABELS[state.tab] || "전체"}</span>`,
    `<span class="chip active-chip">지역: ${state.region === "all" ? "전체" : state.region}</span>`,
    `<span class="chip active-chip">정렬: ${state.sort === "deadline" ? "마감임박순" : "최신순"}</span>`,
  ];
  if (state.keyword) {
    chips.push(`<span class="chip active-chip">검색: ${escapeHtml(state.keyword)}</span>`);
  }
  $("#activeChips").innerHTML = chips.join("");

  $("#listSummary").textContent =
    `${TAB_LABELS[state.tab] || "전체"} / ${state.region === "all" ? "전체" : state.region} / ${state.sort === "deadline" ? "마감임박순" : "최신순"}`;

  const total = state.meta.jobCount ?? state.jobs.length;
  $("#countInfo").textContent = `전체 ${total}건 / 현재 ${filtered.length}건`;
  $("#metaInfo").textContent = `generated: ${text(state.meta.generatedAt)}`;
  $("#datasetBadge").textContent = `데이터 ${total}건`;
}

function renderList() {
  const filtered = getFilteredJobs();
  renderButtons();
  renderSummary(filtered);

  if (!filtered.length) {
    $("#jobList").innerHTML = `<div class="empty-state">조건에 맞는 공고가 없습니다.</div>`;
    return;
  }

  $("#jobList").innerHTML = filtered.map((job) => {
    const posted = text(job.postedAt, "미상");
    const deadline = text(job.deadline, "미상");
    const desc = compact(job.description || "");
    return `
      <article class="job-card">
        <div class="job-top">
          <div class="job-track">${escapeHtml(TAB_LABELS[job.track] || job.track || "기타")}</div>
          <div class="job-region">${escapeHtml(text(job.region))}</div>
        </div>
        <h3 class="job-title">${escapeHtml(text(job.title))}</h3>
        <div class="job-org">${escapeHtml(text(job.organization))}</div>
        <div class="job-meta">
          <span>고용형태: ${escapeHtml(text(job.employmentType))}</span>
          <span>등록: ${escapeHtml(posted)}</span>
          <span>마감: ${escapeHtml(deadline)}</span>
        </div>
        <p class="job-desc">${escapeHtml(desc || "상세 내용은 원문보기를 확인하세요.")}</p>
        <div class="job-footer">
          <span class="job-source">${escapeHtml(text(job.source))}</span>
          <a class="job-link" href="${escapeHtml(job.url || "#")}" target="_blank" rel="noopener noreferrer">원문보기</a>
        </div>
      </article>
    `;
  }).join("");
}

function bindEvents() {
  $$("[data-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.tab = btn.dataset.tab;
      renderList();
    });
  });

  $$("[data-region]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.region = btn.dataset.region;
      renderList();
    });
  });

  $$(".run-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.tab = btn.dataset.runTab;
      state.region = btn.dataset.runRegion || "all";
      $("#runStatus").textContent = `${btn.textContent.trim()} 완료`;
      renderList();
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  });

  $("#keywordInput").addEventListener("input", (e) => {
    state.keyword = e.target.value.trim();
    renderList();
  });

  $("#sortSelect").addEventListener("change", (e) => {
    state.sort = e.target.value;
    renderList();
  });
}

async function loadData() {
  try {
    const res = await fetch("./dashboard_index.json?ts=" + Date.now(), { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const payload = await res.json();
    state.jobs = Array.isArray(payload.jobs) ? payload.jobs : [];
    state.meta = payload.meta || {};
    $("#runStatus").textContent = "ready";
    renderList();
  } catch (err) {
    console.error(err);
    $("#runStatus").textContent = "error";
    $("#jobList").innerHTML = `<div class="empty-state">dashboard_index.json 을 불러오지 못했습니다.</div>`;
  }
}

bindEvents();
loadData();
