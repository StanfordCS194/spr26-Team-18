// Client-side extractors. GitHub uses live REST API (no auth, public repos only).
// CSV + PRD parsed in-browser. PDF parsing intentionally out of scope for MVP —
// drop a .md or .txt PRD instead.

const GH = "https://api.github.com";

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
  const [contents, contributors, workflows, readmeRes] = await Promise.all([
    ghFetch(`/repos/${owner}/${repo}/contents`).catch(() => []),
    ghFetch(`/repos/${owner}/${repo}/contributors?per_page=10`).catch(() => []),
    ghFetch(`/repos/${owner}/${repo}/contents/.github/workflows`).catch(() => null),
    ghFetch(`/repos/${owner}/${repo}/readme`).catch(() => null),
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

// ---- PRD ----

export async function extractPRD(file) {
  if (!file) return null;
  const isText = /\.(md|txt|markdown)$/i.test(file.name) || file.type.startsWith("text/");
  if (!isText) {
    return {
      filename: file.name,
      length: 0,
      parsed: false,
      note: "PDF parsing not in MVP — upload .md or .txt for full grading.",
      ...emptyPRDFlags(),
    };
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
