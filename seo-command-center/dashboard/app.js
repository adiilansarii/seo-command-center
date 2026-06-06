/* app.js — SEO Command Center live cockpit. Plain DOM + SSE, no build step. */
const $ = (id) => document.getElementById(id);
let totals = { High: 0, Medium: 0, Low: 0, total: 0 };
// fixMap: url -> { old, new } built from fixes events
let fixMap = {};

function log(msg) {
  const l = $("log"); if (l.querySelector(".empty")) l.innerHTML = "";
  const d = document.createElement("div"); d.textContent = "› " + msg; l.appendChild(d); l.scrollTop = l.scrollHeight;
}

function buildFixMap(fixes) {
  fixMap = {};
  (fixes.titles || []).forEach(f => { fixMap[f.url] = { old: f.old || "", fix: f.new || "" }; });
  (fixes.redirect_map || []).forEach(f => { fixMap[f.from] = { old: f.from, fix: "→ " + f.to }; });
}

function urlListHTML(urls) {
  return urls.map(u => {
    const fm = fixMap[u];
    const fixCell = fm
      ? `<td class="fix-cell"><span class="fix-tag">✓ Fix</span><span class="fix-val">${fm.fix}</span></td>`
      : `<td class="fix-cell"><span class="fix-none">—</span></td>`;
    const short = u.replace(/^https?:\/\/[^/]+/, '') || '/';
    return `<tr class="url-row">
      <td colspan="2" class="url-cell"><a href="${u}" target="_blank" title="${u}">${short}</a></td>
      ${fixCell}
    </tr>`;
  }).join("");
}

function addIssue(i) {
  const tb = $("tbody"); if (tb.querySelector(".empty")) tb.innerHTML = "";
  const urls = i.affected_urls || [];
  // Main issue row — clickable to expand/collapse URL list
  const rowId = "r-" + i.type.replace(/[^a-z]/g, "-");
  const tr = document.createElement("tr");
  tr.className = "issue-row";
  tr.dataset.rowId = rowId;
  tr.innerHTML = `
    <td><span class="sev ${i.severity.toLowerCase()}">${i.severity}</span></td>
    <td class="issue-type">${i.type}</td>
    <td class="url-count">${i.count}</td>
    <td class="fix-col-header">${urls.length > 0 ? '<span class="expand-btn" data-id="'+rowId+'">▶ show URLs &amp; fixes</span>' : '—'}</td>`;
  tb.appendChild(tr);

  // URL sub-rows (hidden by default)
  const urlBlock = document.createElement("tbody");
  urlBlock.id = rowId;
  urlBlock.style.display = "none";
  urlBlock.innerHTML = urlListHTML(urls);
  tb.parentElement.insertBefore(urlBlock, tb.nextSibling);

  // Wire expand toggle
  tr.querySelector(".expand-btn")?.addEventListener("click", function() {
    const block = document.getElementById(this.dataset.id);
    const open = block.style.display !== "none";
    block.style.display = open ? "none" : "";
    this.textContent = open ? "▶ show URLs & fixes" : "▼ hide";
  });

  // Update KPI counters
  totals[i.severity] = (totals[i.severity] || 0) + i.count;
  totals.total += i.count;
  $("c-total").textContent = totals.total;
  $("c-high").textContent = totals.High;
  $("c-med").textContent = totals.Medium;
  $("c-low").textContent = totals.Low;
}

function refreshUrlBlocks() {
  // After fixes arrive, refresh all already-rendered URL sub-rows
  document.querySelectorAll("tbody[id^='r-']").forEach(block => {
    const urls = Array.from(block.querySelectorAll("tr.url-row")).map(r => {
      const a = r.querySelector("a"); return a ? a.href : null;
    }).filter(Boolean);
    if (urls.length) block.innerHTML = urlListHTML(urls);
  });
}

function handle({ event, data }) {
  if (event === "snapshot") {
    if (data.site) { $("meta").textContent = "· " + data.site; $("urls").textContent = (data.urls||0) + " URLs"; }
    if (data.summary) {
      const s = data.summary.by_severity || {};
      totals = { High: s.High||0, Medium: s.Medium||0, Low: s.Low||0, total: data.summary.total_issues||0 };
      $("c-total").textContent = totals.total; $("c-high").textContent = totals.High;
      $("c-med").textContent = totals.Medium; $("c-low").textContent = totals.Low;
    }
    if (data.fixes) { buildFixMap(data.fixes); }
    (data.issues || []).forEach(i => {
      const tb = $("tbody"); if (tb.querySelector(".empty")) tb.innerHTML = "";
      addIssue(i);
    });
  } else if (event === "loaded") {
    $("meta").textContent = "· " + data.site; $("urls").textContent = data.urls + " URLs";
    log(`Loaded ${data.urls} URLs from ${data.site}`);
    $("tbody").innerHTML = "";
    // clear all url sub-tbodies
    document.querySelectorAll("tbody[id^='r-']").forEach(e => e.remove());
    fixMap = {};
    totals = { High:0, Medium:0, Low:0, total:0 };
    $("c-total").textContent = 0; $("c-high").textContent = 0;
    $("c-med").textContent = 0; $("c-low").textContent = 0;
  } else if (event === "issue") {
    addIssue(data);
    log(`Found ${data.count} × ${data.type}`);
  } else if (event === "summary") {
    const s = data.by_severity || {};
    totals = { High: s.High||0, Medium: s.Medium||0, Low: s.Low||0, total: data.total_issues||0 };
    $("c-total").textContent = totals.total; $("c-high").textContent = totals.High;
    $("c-med").textContent = totals.Medium; $("c-low").textContent = totals.Low;
    log(`Audit complete — ${data.total_issues} total issues`);
  } else if (event === "fixes") {
    buildFixMap(data);
    refreshUrlBlocks();
    log(`Fixes ready: ${(data.titles||[]).length} title/meta, ${(data.redirect_map||[]).length} redirects`);
  } else if (event === "exported") {
    $("export").innerHTML = "<b>report.html written ✓</b><br><span style='color:#c8c5be;font-size:12px'>Open or email outputs/report.html to the client.</span>";
  } else if (event === "saved") {
    log("report.json saved");
  } else if (event === "recommendations") {
    const recs = data.recommendations || [];
    if (recs.length) log("Recs: " + recs[0]);
  }
}

const es = new EventSource("/events");
es.onmessage = (m) => { try { handle(JSON.parse(m.data)); } catch (e) {} };
