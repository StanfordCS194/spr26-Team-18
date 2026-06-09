// Client-side extractors. GitHub uses live REST API (no auth, public repos only).
// CSV + text PRDs are parsed in-browser. PDF PRDs are sent to the backend for
// text extraction, then scored locally by the same deterministic PRD rubric.

const GH = "https://api.github.com";
const RAW_GH = "https://raw.githubusercontent.com";
const MAX_SCANNED_FILES = 35;
const MAX_FILE_BYTES = 90000;

const SCANNABLE_EXTENSIONS = /\.(js|jsx|ts|tsx|py|rb|go|java|kt|php|cs|rs|swift|sql|html|env|yml|yaml|json|md|txt)$/i;
const SCANNABLE_NAMES = /(^|\/)(dockerfile|nginx\.conf|\.env|\.env\.[^/]+|privacy|terms|security|readme)(\.|$)/i;
const SKIP_PATH = /(^|\/)(node_modules|dist|build|coverage|vendor|\.git|__pycache__|target|public\/assets)\//i;

export async function extractGithub(rawUrl) {
  const url = (rawUrl || "").trim();
  if (!url) return null;

  // Accept "owner/repo" shorthand or full URL.
  let owner, repo;
  const fullMatch = url.match(/github\.com[:/]([^/]+)\/([^/?#]+)/i);
  const shortMatch = url.match(/^([^/\s]+)\/([^/\s]+)$/);
  if (fullMatch) {
    [, owner, repo] = fullMatch;
  } else if (shortMatch) {
    [, owner, repo] = shortMatch;
  } else {
    throw new Error("Couldn't parse that — try https://github.com/owner/repo or owner/repo");
  }
  repo = repo.replace(/\.git$/, "");

  const meta = await ghFetch(`/repos/${owner}/${repo}`);
  if (!meta || meta.message === "Not Found") {
    throw new Error(`Repo ${owner}/${repo} not found (or private).`);
  }
  if (meta.message && /rate limit/i.test(meta.message)) {
    throw new Error("GitHub rate-limited us. Try again in a minute, or use a demo preset.");
  }

  // Parallel fetches for the rest.
  const [contents, contributors, workflows, readmeRes, treeRes] = await Promise.all([
    ghFetch(`/repos/${owner}/${repo}/contents`).catch(() => []),
    ghFetch(`/repos/${owner}/${repo}/contributors?per_page=10`).catch(() => []),
    ghFetch(`/repos/${owner}/${repo}/contents/.github/workflows`).catch(() => null),
    ghFetch(`/repos/${owner}/${repo}/readme`).catch(() => null),
    ghFetch(`/repos/${owner}/${repo}/git/trees/${meta.default_branch || "main"}?recursive=1`).catch(() => null),
  ]);

  const filenames = Array.isArray(contents) ? contents.map((c) => c.name) : [];
  const lower = filenames.map((f) => f.toLowerCase());

  let readmeText = "";
  if (readmeRes && readmeRes.content) {
    try {
      readmeText = atob(readmeRes.content.replace(/\n/g, ""));
    } catch {
      readmeText = "";
    }
  }

  const hasCI =
    Array.isArray(workflows) && workflows.length > 0 ||
    lower.some((f) => f === ".circleci" || f === ".travis.yml" || f === "azure-pipelines.yml");

  const hasTests = lower.some((f) =>
    ["tests", "test", "__tests__", "spec", "specs"].includes(f)
  );

  const hasPackageManifest = lower.some((f) =>
    ["package.json", "requirements.txt", "pyproject.toml", "go.mod", "cargo.toml", "gemfile", "pom.xml"].includes(f)
  );

  const hasEnvFile = lower.some(
    (f) => /^\.env($|\..+$)/.test(f) && !["env.example", "env.sample", "env.template"].some((s) => f.endsWith(s))
  );

  const pushedAt = meta.pushed_at ? new Date(meta.pushed_at) : null;
  const daysSincePush = pushedAt ? Math.round((Date.now() - pushedAt.getTime()) / 86400000) : null;
  const repoFiles = selectRepoFiles(treeRes?.tree || []);
  const scannedFiles = await fetchRepoFiles(owner, repo, meta.default_branch || "main", repoFiles);
  const complianceFindings = scanRepoCompliance(scannedFiles);
  const licenseScan = await scanLicenseRisk(meta.html_url || `https://github.com/${owner}/${repo}`);
  const licenseFindings = licenseScan.findings || [];

  return {
    owner,
    repo,
    fullName: meta.full_name,
    description: meta.description || "",
    license: meta.license?.spdx_id || null,
    language: meta.language,
    stars: meta.stargazers_count || 0,
    pushedAt: meta.pushed_at,
    daysSincePush,
    filenames,
    readmeText,
    readmeLength: readmeText.length,
    hasReadme: lower.some((f) => /^readme/.test(f)),
    hasLicense: lower.some((f) => /^license/.test(f)) || !!meta.license,
    hasGitignore: lower.includes(".gitignore"),
    hasPackageManifest,
    hasTests,
    hasEnvFile,
    hasCI,
    contributorCount: Array.isArray(contributors) ? contributors.length : 0,
    defaultBranch: meta.default_branch || "main",
    scannedFileCount: scannedFiles.length,
    scannedFiles: scannedFiles.map((f) => ({ path: f.path, size: f.text.length })),
    complianceFindings,
    highComplianceFindingCount: complianceFindings.filter((f) => f.severity === "high").length,
    mediumComplianceFindingCount: complianceFindings.filter((f) => f.severity === "medium").length,
    licenseScanState: licenseScan.state,
    licenseFindings,
    highLicenseFindingCount: licenseFindings.filter((f) => f.severity === "high").length,
    mediumLicenseFindingCount: licenseFindings.filter((f) => f.severity === "medium").length,
  };
}

async function ghFetch(path) {
  const r = await fetch(GH + path, {
    headers: { Accept: "application/vnd.github+json" },
  });
  if (!r.ok && r.status !== 404) {
    if (r.status === 403) {
      return { message: "rate limit" };
    }
  }
  try {
    return await r.json();
  } catch {
    return null;
  }
}

function selectRepoFiles(tree) {
  if (!Array.isArray(tree)) return [];
  const candidates = tree
    .filter((item) => item.type === "blob")
    .filter((item) => !SKIP_PATH.test(item.path || ""))
    .filter((item) => (item.size || 0) > 0 && (item.size || 0) <= MAX_FILE_BYTES)
    .filter((item) => SCANNABLE_EXTENSIONS.test(item.path || "") || SCANNABLE_NAMES.test(item.path || ""))
    .sort((a, b) => filePriority(a.path) - filePriority(b.path));
  return candidates.slice(0, MAX_SCANNED_FILES);
}

function filePriority(path = "") {
  const p = path.toLowerCase();
  if (/privacy|terms|security|auth|login|signup|account|user|patient|child|minor/.test(p)) return 0;
  if (/api|route|controller|server|app|main|index|middleware/.test(p)) return 1;
  if (/package\.json|requirements\.txt|pyproject\.toml|readme|\.env/.test(p)) return 2;
  return 3;
}

async function fetchRepoFiles(owner, repo, branch, files) {
  const out = [];
  for (const file of files) {
    const url = `${RAW_GH}/${owner}/${repo}/${encodeURIComponent(branch)}/${file.path
      .split("/")
      .map(encodeURIComponent)
      .join("/")}`;
    try {
      const response = await fetch(url);
      if (!response.ok) continue;
      const text = await response.text();
      if (text && text.length <= MAX_FILE_BYTES) {
        out.push({ path: file.path, text });
      }
    } catch {
      // Best-effort scan. Core GitHub grading should still work if raw fetches fail.
    }
  }
  return out;
}

function scanRepoCompliance(files) {
  const findings = [];
  const add = (finding) => {
    const duplicate = findings.some(
      (f) =>
        f.id === finding.id &&
        f.path === finding.path &&
        f.line === finding.line &&
        f.snippet === finding.snippet
    );
    if (!duplicate) findings.push(finding);
  };

  for (const file of files) {
    const lines = file.text.split(/\r?\n/);
    lines.forEach((lineText, index) => {
      const line = index + 1;
      const trimmed = lineText.trim();
      if (!trimmed) return;

      if (/(localStorage|sessionStorage)\.setItem\s*\([^)]*(token|jwt|auth|session)/i.test(trimmed)) {
        add(repoFinding({
          id: "repo_token_storage",
          severity: "high",
          path: file.path,
          line,
          snippet: trimmed,
          title: "Auth token stored in browser storage",
          recommendation:
            "Move auth tokens to secure, HttpOnly, SameSite cookies or a server-side session.",
        }));
      }

      if (/(document\.cookie|setcookie|res\.cookie|response\.set_cookie|cookies\.set)/i.test(trimmed)) {
        const nearby = lines.slice(index, Math.min(lines.length, index + 4)).join(" ");
        if (!/httponly|httpOnly/i.test(nearby) || !/secure/i.test(nearby) || !/samesite|sameSite/i.test(nearby)) {
          add(repoFinding({
            id: "repo_cookie_flags",
            severity: "high",
            path: file.path,
            line,
            snippet: trimmed,
            title: "Cookie appears to be missing security flags",
            recommendation:
              "Set HttpOnly, Secure, and SameSite on session/auth cookies, and document the session lifetime.",
          }));
        }
      }

      if (/(child|children|minor|under.?13|coppa)/i.test(trimmed) && !/coppa|parent|guardian|consent/i.test(trimmed)) {
        add(repoFinding({
          id: "repo_minor_flow",
          severity: "high",
          path: file.path,
          line,
          snippet: trimmed,
          title: "Minor-user flow lacks visible consent handling",
          recommendation:
            "Add an age-aware onboarding branch and parental/guardian consent handling for under-13 users.",
        }));
      }

      if (/(patient|diagnosis|medication|therapy|clinical|health[_-]?data|symptom)/i.test(trimmed)) {
        const nearby = lines.slice(Math.max(0, index - 3), Math.min(lines.length, index + 4)).join(" ");
        if (!/(encrypt|audit|hipaa|phi|baa|retention|access.?control)/i.test(nearby)) {
          add(repoFinding({
            id: "repo_health_data_controls",
            severity: "high",
            path: file.path,
            line,
            snippet: trimmed,
            title: "Health data appears without nearby PHI safeguards",
            recommendation:
              "Add explicit PHI safeguards around this flow: access control, audit logging, encryption, retention, and BAA assumptions.",
          }));
        }
      }

      if (/(api[_-]?key|secret|password|private[_-]?key|access[_-]?token)\s*[:=]\s*['\"][^'\"\s]{12,}/i.test(trimmed)) {
        add(repoFinding({
          id: "repo_hardcoded_secret",
          severity: "high",
          path: file.path,
          line,
          snippet: redactSecret(trimmed),
          title: "Possible hardcoded secret",
          recommendation:
            "Remove this value from source control, rotate it, and load it from a secrets manager or environment variable.",
        }));
      }

      if (/(posthog|mixpanel|amplitude|segment|gtag|google-analytics|facebook pixel|fbq\()/i.test(trimmed)) {
        add(repoFinding({
          id: "repo_tracking_sdk",
          severity: "medium",
          path: file.path,
          line,
          snippet: trimmed,
          title: "Tracking or analytics SDK found",
          recommendation:
            "Gate analytics behind consent where required, disable targeted advertising for minors, and document data sharing.",
        }));
      }

      if (/\b(email|phone|address|birthdate|date_of_birth|dob|ssn|location|geolocation)\b/i.test(trimmed)) {
        const nearby = lines.slice(Math.max(0, index - 3), Math.min(lines.length, index + 4)).join(" ");
        if (!/(delete|deletion|retention|minimi[sz]e|consent|privacy|encrypt)/i.test(nearby)) {
          add(repoFinding({
            id: "repo_personal_data_controls",
            severity: "medium",
            path: file.path,
            line,
            snippet: trimmed,
            title: "Personal data field lacks nearby data-governance handling",
            recommendation:
              "Add a retention/deletion path and privacy rationale for this data field, or remove it from the flow.",
          }));
        }
      }
    });
  }

  return findings
    .sort((a, b) => severityRank(a.severity) - severityRank(b.severity) || a.path.localeCompare(b.path) || a.line - b.line)
    .slice(0, 30);
}

function repoFinding({ id, severity, path, line, snippet, title, recommendation }) {
  return {
    id,
    severity,
    path,
    line,
    snippet: snippet.length > 180 ? snippet.slice(0, 177) + "..." : snippet,
    title,
    recommendation,
    display: `${path}:${line}`,
  };
}

function severityRank(severity) {
  return severity === "high" ? 0 : severity === "medium" ? 1 : 2;
}

function redactSecret(text) {
  return text.replace(/(['\"])[^'\"\s]{8,}(['\"])/g, "$1[redacted]$2");
}

async function scanLicenseRisk(repoUrl) {
  try {
    const response = await fetch("/api/startup/license/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        repo_path: repoUrl,
        options: {
          deterministic_only: true,
        },
      }),
    });
    if (!response.ok) {
      return { state: "unavailable", findings: [] };
    }
    const data = await response.json();
    return {
      state: "ok",
      findings: (data.findings || []).filter((finding) => finding.category === "license_risk"),
      summary: data.summary || null,
    };
  } catch {
    return { state: "error", findings: [] };
  }
}

// ---- PRD ----

export async function extractPRD(file) {
  if (!file) return null;
  const isText = /\.(md|txt|markdown)$/i.test(file.name) || file.type.startsWith("text/");
  const isPdf = /\.pdf$/i.test(file.name) || file.type === "application/pdf";
  if (isPdf) {
    const form = new FormData();
    form.append("file", file);
    const response = await fetch("/api/startup/prd/extract", {
      method: "POST",
      body: form,
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }));
      throw new Error(detail.detail || "Could not extract text from PDF PRD.");
    }
    const data = await response.json();
    return {
      ...analyzePRD(data.text || "", data.filename || file.name),
      parsedFromPdf: true,
    };
  }
  if (!isText) {
    throw new Error("Unsupported PRD type. Upload a PDF, Markdown, or text file.");
  }
  const text = await file.text();
  return analyzePRD(text, file.name);
}

export function analyzePRD(text, filename = "PRD") {
  const len = text.length;
  return {
    filename,
    length: len,
    parsed: true,
    wordCount: text.split(/\s+/).filter(Boolean).length,
    mentionsEU: /\b(eu|european union|gdpr|europe)\b/i.test(text),
    mentionsCalifornia: /\b(california|ccpa|cpra)\b/i.test(text),
    mentionsKids: /\b(child|children|minor|kid|coppa|under 13|teen)\b/i.test(text),
    mentionsCOPPA: /coppa/i.test(text),
    mentionsGDPR: /gdpr/i.test(text),
    mentionsCCPA: /ccpa|cpra/i.test(text),
    mentionsPrivacyPolicy: /privacy policy/i.test(text),
    mentionsToS: /terms of service|terms of use|user agreement/i.test(text),
    mentionsAI: /\b(ai|artificial intelligence|llm|gpt|machine learning|model)\b/i.test(text),
    mentionsDataRetention: /data retention|retention policy|deletion|right to be forgotten/i.test(text),
    mentionsAuth: /\b(auth|authentication|login|sso|oauth|password|2fa|mfa)\b/i.test(text),
    mentionsSOC2: /soc ?2|iso ?27001|hipaa|pci/i.test(text),
    mentionsPII: /\b(pii|personal information|personally identifiable|sensitive data)\b/i.test(text),
    mentionsTargetUser: /\b(target user|persona|target customer|user is a|our user|ICP)\b/i.test(text),
    mentionsMetrics: /\b(metric|kpi|north star|success metric|measure success|conversion rate|MRR|ARR)\b/i.test(text),
    mentionsScope: /\b(scope|out of scope|non-goal|won't|will not|deferred)\b/i.test(text),
    mentionsTimeline: /\b(timeline|milestone|q[1-4] ?(20)?\d{2}|launch date|deadline|by [a-z]+ \d{4})\b/i.test(text),
    mentionsCompetitor: /\b(competitor|competition|alternative|landscape|incumbent|status quo)\b/i.test(text),
    mentionsProblem: /\b(problem|pain point|challenge|user pain|today,|currently)\b/i.test(text),
    mentionsSolution: /\b(solution|approach|how it works|implementation|we will build)\b/i.test(text),
    mentionsTrademark: /\b(trademark|tm|copyright|intellectual property|\bIP\b)/i.test(text),
    mentionsEntity: /\b(inc\.?|llc|corp\.?|corporation|delaware c-?corp)\b/i.test(text),
    excerpt: text.slice(0, 280),
    text,
  };
}

function emptyPRDFlags() {
  return {
    wordCount: 0,
    mentionsEU: false, mentionsCalifornia: false, mentionsKids: false, mentionsCOPPA: false,
    mentionsGDPR: false, mentionsCCPA: false, mentionsPrivacyPolicy: false, mentionsToS: false,
    mentionsAI: false, mentionsDataRetention: false, mentionsAuth: false, mentionsSOC2: false,
    mentionsPII: false, mentionsTargetUser: false, mentionsMetrics: false, mentionsScope: false,
    mentionsTimeline: false, mentionsCompetitor: false, mentionsProblem: false, mentionsSolution: false,
    mentionsTrademark: false, mentionsEntity: false, excerpt: "",
  };
}

// ---- CSV / Spreadsheet ----

export async function extractSpreadsheet(file) {
  if (!file) return null;
  const text = await file.text();
  return analyzeCSV(text, file.name);
}

export function analyzeCSV(text, filename = "spreadsheet") {
  const csv = parseCSV(text);
  if (!csv || csv.rows.length === 0) {
    return { filename, rowCount: 0, parsed: false, note: "Couldn't parse — needs a header row + at least 1 data row." };
  }
  const { headers, rows } = csv;

  const amountCol = headers.find((h) => /^(amount|value|debit|credit|cost|spend|total)$/i.test(h)) || headers.find((h) => /amount|value|spend/i.test(h));
  const dateCol = headers.find((h) => /^(date|month|posted|transaction date)$/i.test(h)) || headers.find((h) => /date|month/i.test(h));
  const categoryCol = headers.find((h) => /^(category|type|description|merchant|vendor)$/i.test(h));
  const balanceCol = headers.find((h) => /balance|cash on hand|ending balance/i.test(h));

  const amounts = amountCol
    ? rows.map((r) => parseFloat(String(r[amountCol] || "").replace(/[$,()\s]/g, ""))).filter((n) => !isNaN(n))
    : [];

  const totalSpend = amounts.filter((a) => a < 0).reduce((s, a) => s + Math.abs(a), 0);
  const totalRevenue = amounts.filter((a) => a > 0).reduce((s, a) => s + a, 0);

  const dates = dateCol
    ? rows.map((r) => new Date(r[dateCol])).filter((d) => !isNaN(d.getTime()))
    : [];
  const monthsCovered =
    dates.length > 1
      ? Math.max(
          0.5,
          (Math.max(...dates.map((d) => d.getTime())) - Math.min(...dates.map((d) => d.getTime()))) /
            (1000 * 60 * 60 * 24 * 30)
        )
      : Math.max(0.5, rows.length / 30);

  const monthlyBurn = totalSpend / monthsCovered;
  const monthlyRevenue = totalRevenue / monthsCovered;
  const netBurn = Math.max(0, monthlyBurn - monthlyRevenue);

  let cashOnHand = null;
  if (balanceCol && rows.length) {
    const last = parseFloat(String(rows[rows.length - 1][balanceCol] || "").replace(/[$,()\s]/g, ""));
    if (!isNaN(last)) cashOnHand = last;
  }

  const runway = cashOnHand && netBurn > 0 ? cashOnHand / netBurn : null;

  let largestExpense = null;
  if (amountCol && categoryCol) {
    const buckets = {};
    for (const r of rows) {
      const v = parseFloat(String(r[amountCol] || "").replace(/[$,()\s]/g, ""));
      if (isNaN(v) || v >= 0) continue;
      const cat = (r[categoryCol] || "uncategorized").toString().slice(0, 40);
      buckets[cat] = (buckets[cat] || 0) + Math.abs(v);
    }
    const top = Object.entries(buckets).sort((a, b) => b[1] - a[1])[0];
    if (top) largestExpense = { category: top[0], amount: Math.round(top[1]) };
  }

  return {
    filename,
    parsed: true,
    rowCount: rows.length,
    headers,
    monthsCovered: Math.round(monthsCovered * 10) / 10,
    monthlyBurn: Math.round(monthlyBurn),
    monthlyRevenue: Math.round(monthlyRevenue),
    netBurn: Math.round(netBurn),
    cashOnHand,
    runway: runway ? Math.round(runway * 10) / 10 : null,
    hasCategories: !!categoryCol,
    hasDates: dates.length > 0,
    hasBalance: !!balanceCol,
    largestExpense,
  };
}

// Minimal RFC-4180-ish CSV parser. Handles quoted fields with commas + escaped quotes.
function parseCSV(text) {
  const lines = [];
  let cur = "";
  let inQ = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === '"' && text[i + 1] === '"' && inQ) {
      cur += '"';
      i++;
    } else if (c === '"') {
      inQ = !inQ;
      cur += c;
    } else if ((c === "\n" || c === "\r") && !inQ) {
      if (cur.length) lines.push(cur);
      cur = "";
      if (c === "\r" && text[i + 1] === "\n") i++;
    } else {
      cur += c;
    }
  }
  if (cur.length) lines.push(cur);
  if (lines.length < 2) return null;

  const splitLine = (line) => {
    const out = [];
    let f = "";
    let q = false;
    for (let i = 0; i < line.length; i++) {
      const c = line[i];
      if (c === '"' && line[i + 1] === '"') {
        f += '"';
        i++;
      } else if (c === '"') {
        q = !q;
      } else if (c === "," && !q) {
        out.push(f);
        f = "";
      } else {
        f += c;
      }
    }
    out.push(f);
    return out.map((s) => s.trim());
  };

  const headers = splitLine(lines[0]).map((h) => h.toLowerCase());
  const rows = lines.slice(1).map((line) => {
    const vals = splitLine(line);
    const obj = {};
    headers.forEach((h, i) => (obj[h] = vals[i] ?? ""));
    return obj;
  });
  return { headers, rows };
}
