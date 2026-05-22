// Deterministic rubric: features (from extractors) -> 5 sub-grades + actions.
// Each rule = { id, axis, weight, check(features), evidence, fix, dollarImpact }
// score = 100 - (sum of failed weights / sum of evaluated weights * 100)
// Composite = equal-weight average of axes with at least one evaluated rule.

export const AXES = ["engineering", "legal", "financial", "compliance", "product", "custom"];

export const AXIS_LABELS = {
  engineering: "Engineering Health",
  legal: "Legal Health",
  financial: "Financial Health",
  compliance: "Compliance Health",
  product: "Product Coherence",
  custom: "Custom (AI-tailored)",
};

export const AXIS_BLURBS = {
  engineering: "Repo hygiene, CI, tests, bus factor, secret leakage.",
  legal: "License risk, IP exposure, ToS/Privacy presence, claim grounding.",
  financial: "Runway, burn trajectory, revenue, expense discipline.",
  compliance: "GDPR/CCPA/COPPA posture, data handling, certifications.",
  product: "PRD completeness — problem, users, metrics, scope, timeline.",
  custom: "Rules an LLM wrote specifically for this product, then graded.",
};

function repoFindingSummary(findings = []) {
  if (!findings.length) return "no repo compliance findings";
  const high = findings.filter((f) => f.severity === "high").length;
  const medium = findings.filter((f) => f.severity === "medium").length;
  return `${high} high, ${medium} medium repo findings`;
}

function repoFindingLocations(findings = [], limit = 5) {
  return findings.slice(0, limit).map((finding) => ({
    path: finding.path,
    line: finding.line,
    snippet: finding.snippet,
    title: finding.title,
    recommendation: finding.recommendation,
    severity: finding.severity,
  }));
}

// ---- Rules ----
// Every rule returns { passed: bool, observed?: string }
// `observed` shows up in the drill-down so the user sees WHAT we found.

export const RULES = [
  // ---------- Engineering ----------
  {
    id: "eng_readme",
    axis: "engineering",
    title: "README exists and is substantive",
    weight: 8,
    check: (f) => {
      const len = f.github?.readmeLength || 0;
      return { passed: len >= 200, observed: len ? `README is ${len} chars` : "no README found" };
    },
    fix: "Write a real README — 1 paragraph on what it does, 1 on how to run it.",
    dollarImpact: 0,
  },
  {
    id: "eng_license",
    axis: "engineering",
    title: "Repo has an explicit LICENSE",
    weight: 12,
    check: (f) => ({
      passed: !!f.github?.hasLicense,
      observed: f.github?.license ? `${f.github.license}` : "no LICENSE file",
    }),
    fix: "Add a LICENSE — without one your code is legally untouchable by anyone.",
    dollarImpact: 0,
  },
  {
    id: "eng_ci",
    axis: "engineering",
    title: "CI is configured",
    weight: 12,
    check: (f) => ({
      passed: !!f.github?.hasCI,
      observed: f.github?.hasCI ? ".github/workflows present" : "no CI workflows",
    }),
    fix: "Add a GitHub Actions workflow that runs your tests on every PR.",
    dollarImpact: 0,
  },
  {
    id: "eng_tests",
    axis: "engineering",
    title: "Tests directory exists",
    weight: 12,
    check: (f) => ({
      passed: !!f.github?.hasTests,
      observed: f.github?.hasTests ? "tests/ directory present" : "no tests/ directory",
    }),
    fix: "Create a tests/ directory and write at least one smoke test.",
    dollarImpact: 0,
  },
  {
    id: "eng_recent",
    axis: "engineering",
    title: "Active in the last 30 days",
    weight: 6,
    check: (f) => {
      const d = f.github?.daysSincePush;
      return { passed: d != null && d <= 30, observed: d != null ? `last push ${d}d ago` : "unknown" };
    },
    fix: "Repo looks stale. Investors flag this in diligence.",
    dollarImpact: 0,
  },
  {
    id: "eng_buspeople",
    axis: "engineering",
    title: "More than one contributor (bus factor > 1)",
    weight: 8,
    check: (f) => ({
      passed: (f.github?.contributorCount || 0) >= 2,
      observed: `${f.github?.contributorCount || 0} contributors`,
    }),
    fix: "Bus factor of 1 is a diligence red flag. Add at least one teammate as a committer.",
    dollarImpact: 0,
  },
  {
    id: "eng_secrets",
    axis: "engineering",
    title: "No raw .env file committed",
    weight: 18,
    check: (f) => ({
      passed: !f.github?.hasEnvFile,
      observed: f.github?.hasEnvFile ? "found a committed .env file" : "no committed .env",
    }),
    fix: "CRITICAL: a committed .env can leak API keys + DB credentials. git-rm and rotate.",
    dollarImpact: 50000,
  },
  {
    id: "eng_manifest",
    axis: "engineering",
    title: "Has a package manifest",
    weight: 4,
    check: (f) => ({
      passed: !!f.github?.hasPackageManifest,
      observed: f.github?.hasPackageManifest ? "manifest present" : "no manifest detected",
    }),
    fix: "Pin your dependencies in package.json / requirements.txt / similar.",
    dollarImpact: 0,
  },

  // ---------- Legal ----------
  {
    id: "legal_license_safe",
    axis: "legal",
    title: "License compatible with proprietary SaaS",
    weight: 25,
    check: (f) => {
      const lic = (f.github?.license || "").toUpperCase();
      const bad = ["GPL", "AGPL", "SSPL", "GPL-2.0", "GPL-3.0", "AGPL-3.0"];
      const isBad = bad.some((b) => lic.includes(b));
      return {
        passed: !isBad,
        observed: lic ? `license = ${lic}` : "no license declared",
      };
    },
    fix: "AGPL/GPL/SSPL contaminate proprietary SaaS. Switch to MIT/Apache-2.0 or wall this off.",
    dollarImpact: 100000,
  },
  {
    id: "legal_tos",
    axis: "legal",
    title: "Terms of Service exists",
    weight: 12,
    check: (f) => ({
      passed: !!f.prd?.mentionsToS,
      observed: f.prd?.mentionsToS ? "PRD references ToS" : "no ToS reference in PRD",
    }),
    fix: "Draft a ToS. Without one, your liability cap is whatever a court decides.",
    dollarImpact: 5000,
  },
  {
    id: "legal_privacy",
    axis: "legal",
    title: "Privacy Policy exists",
    weight: 14,
    check: (f) => ({
      passed: !!f.prd?.mentionsPrivacyPolicy,
      observed: f.prd?.mentionsPrivacyPolicy ? "PRD references Privacy Policy" : "no Privacy Policy reference",
    }),
    fix: "Required by law in CA + EU + many states. Generate one against your actual data flow.",
    dollarImpact: 7500,
  },
  {
    id: "legal_entity",
    axis: "legal",
    title: "Operating entity named",
    weight: 8,
    check: (f) => ({
      passed: !!f.prd?.mentionsEntity,
      observed: f.prd?.mentionsEntity ? "entity referenced" : "no Inc/LLC/Corp reference",
    }),
    fix: "Sign nothing without a formed entity. DE C-corp via Clerky is ~$500.",
    dollarImpact: 0,
  },
  {
    id: "legal_ip",
    axis: "legal",
    title: "IP / trademark posture mentioned",
    weight: 6,
    check: (f) => ({
      passed: !!f.prd?.mentionsTrademark,
      observed: f.prd?.mentionsTrademark ? "IP/TM mentioned" : "no IP/TM consideration",
    }),
    fix: "Run a USPTO + .com check on your name. 5 minutes; saves a forced rebrand later.",
    dollarImpact: 0,
  },
  {
    id: "legal_kids",
    axis: "legal",
    title: "If product touches minors, COPPA acknowledged",
    weight: 12,
    check: (f) => {
      if (!f.prd?.mentionsKids) return { passed: true, observed: "no minors in product" };
      return {
        passed: f.prd?.mentionsCOPPA,
        observed: f.prd?.mentionsCOPPA ? "COPPA acknowledged" : "kids/minors mentioned without COPPA",
      };
    },
    fix: "COPPA fines start at $51,744 PER VIOLATION. If users under 13 → parental consent flow required.",
    dollarImpact: 50000,
  },

  // ---------- Financial ----------
  {
    id: "fin_data",
    axis: "financial",
    title: "Financial data uploaded",
    weight: 10,
    check: (f) => ({
      passed: (f.spreadsheet?.rowCount || 0) > 0,
      observed: f.spreadsheet ? `${f.spreadsheet.rowCount} rows parsed` : "no spreadsheet uploaded",
    }),
    fix: "Upload a bank or expense CSV so we can compute real runway.",
    dollarImpact: 0,
  },
  {
    id: "fin_runway_known",
    axis: "financial",
    title: "Runway is computable",
    weight: 15,
    check: (f) => ({
      passed: f.spreadsheet?.runway != null,
      observed:
        f.spreadsheet?.runway != null
          ? `${f.spreadsheet.runway} months runway`
          : "no balance column to compute runway",
    }),
    fix: "Add a 'balance' or 'cash' column to your CSV so we can forecast.",
    dollarImpact: 0,
  },
  {
    id: "fin_runway_safe",
    axis: "financial",
    title: "Runway is at least 6 months",
    weight: 25,
    check: (f) => {
      const r = f.spreadsheet?.runway;
      if (r == null) return { passed: false, observed: "runway unknown" };
      return { passed: r >= 6, observed: `${r}mo runway` };
    },
    fix: "Below 6mo runway = start raising NOW. Cut burn or open the round.",
    dollarImpact: 0,
  },
  {
    id: "fin_categorized",
    axis: "financial",
    title: "Expenses are categorized",
    weight: 10,
    check: (f) => ({
      passed: !!f.spreadsheet?.hasCategories,
      observed: f.spreadsheet?.hasCategories ? "category column found" : "no category column",
    }),
    fix: "Categorize transactions (vendor type, expense class). Auditors and the R&D credit need this.",
    dollarImpact: 0,
  },
  {
    id: "fin_revenue",
    axis: "financial",
    title: "Has revenue line items",
    weight: 12,
    check: (f) => ({
      passed: (f.spreadsheet?.monthlyRevenue || 0) > 0,
      observed:
        (f.spreadsheet?.monthlyRevenue || 0) > 0
          ? `~$${f.spreadsheet.monthlyRevenue.toLocaleString()}/mo revenue`
          : "no positive line items detected",
    }),
    fix: "Pre-revenue is fine for pre-seed but flag this for seed conversations.",
    dollarImpact: 0,
  },
  {
    id: "fin_history",
    axis: "financial",
    title: "At least 3 months of data",
    weight: 8,
    check: (f) => ({
      passed: (f.spreadsheet?.monthsCovered || 0) >= 3,
      observed: f.spreadsheet ? `${f.spreadsheet.monthsCovered}mo covered` : "no history",
    }),
    fix: "Forecasts on <3mo of data are noise. Export more history.",
    dollarImpact: 0,
  },

  // ---------- Compliance ----------
  {
    id: "comp_gdpr",
    axis: "compliance",
    title: "GDPR addressed if EU users",
    weight: 18,
    check: (f) => {
      if (!f.prd?.mentionsEU) return { passed: true, observed: "no EU users mentioned" };
      return {
        passed: f.prd?.mentionsGDPR,
        observed: f.prd?.mentionsGDPR ? "GDPR addressed" : "EU mentioned but no GDPR plan",
      };
    },
    fix: "GDPR fines = up to 4% of global revenue. Need DPA, data map, deletion flow before EU launch.",
    dollarImpact: 100000,
  },
  {
    id: "comp_ccpa",
    axis: "compliance",
    title: "CCPA addressed if CA users",
    weight: 14,
    check: (f) => {
      if (!f.prd?.mentionsCalifornia) return { passed: true, observed: "no CA-specific scope" };
      return {
        passed: f.prd?.mentionsCCPA,
        observed: f.prd?.mentionsCCPA ? "CCPA addressed" : "CA users mentioned without CCPA",
      };
    },
    fix: "If you have CA residents and >$25M revenue (or 100k+ users), CCPA applies. Add a 'Do Not Sell' link.",
    dollarImpact: 25000,
  },
  {
    id: "comp_data_handling",
    axis: "compliance",
    title: "Data handling described",
    weight: 12,
    check: (f) => ({
      passed: !!(f.prd?.mentionsPII || f.prd?.mentionsDataRetention),
      observed: f.prd?.mentionsPII ? "PII handling discussed" : "no data-handling section",
    }),
    fix: "Document what PII you collect, why, where it lives, and how long.",
    dollarImpact: 0,
  },
  {
    id: "comp_auth",
    axis: "compliance",
    title: "Authentication strategy mentioned",
    weight: 10,
    check: (f) => ({
      passed: !!f.prd?.mentionsAuth,
      observed: f.prd?.mentionsAuth ? "auth mentioned" : "no auth strategy in PRD",
    }),
    fix: "Specify auth (SSO? OAuth? passwords?). Hand-rolled auth is the #1 startup security incident.",
    dollarImpact: 0,
  },
  {
    id: "comp_retention",
    axis: "compliance",
    title: "Data retention policy mentioned",
    weight: 8,
    check: (f) => ({
      passed: !!f.prd?.mentionsDataRetention,
      observed: f.prd?.mentionsDataRetention ? "retention discussed" : "no retention policy",
    }),
    fix: "State a retention period per data class. Required by GDPR; expected by enterprise buyers.",
    dollarImpact: 0,
  },
  {
    id: "comp_certs",
    axis: "compliance",
    title: "Security certifications path mentioned (bonus)",
    weight: 4,
    check: (f) => ({
      passed: !!f.prd?.mentionsSOC2,
      observed: f.prd?.mentionsSOC2 ? "certifications acknowledged" : "no cert path",
    }),
    fix: "Most enterprise contracts > $50k/yr will ask for SOC2. Plan it for ~12mo before you need it.",
    dollarImpact: 0,
  },
  {
    id: "comp_repo_high_risk",
    axis: "compliance",
    title: "Repo scan has no high-risk compliance findings",
    weight: 18,
    check: (f) => {
      const findings = f.github?.complianceFindings || [];
      const high = findings.filter((finding) => finding.severity === "high");
      return {
        passed: high.length === 0,
        observed: f.github ? repoFindingSummary(findings) : "no GitHub repo scanned",
        locations: repoFindingLocations(high),
      };
    },
    fix: "Fix the high-risk repo findings first. They point to specific files/lines where auth, minors, health data, cookies, or secrets need remediation.",
    dollarImpact: 75000,
  },
  {
    id: "comp_repo_personal_data",
    axis: "compliance",
    title: "Personal-data code paths have governance controls",
    weight: 12,
    check: (f) => {
      const findings = (f.github?.complianceFindings || []).filter((finding) =>
        ["repo_personal_data_controls", "repo_tracking_sdk"].includes(finding.id)
      );
      return {
        passed: findings.length === 0,
        observed: f.github
          ? findings.length
            ? `${findings.length} personal-data/tracking code findings`
            : "no ungoverned personal-data code paths found"
          : "no GitHub repo scanned",
        locations: repoFindingLocations(findings),
      };
    },
    fix: "Add consent, retention, deletion, and data-sharing controls next to the code that collects or tracks personal data.",
    dollarImpact: 25000,
  },

  // ---------- Product Coherence ----------
  {
    id: "prod_exists",
    axis: "product",
    title: "PRD is substantive (≥ 500 chars)",
    weight: 10,
    check: (f) => {
      const len = f.prd?.length || 0;
      return { passed: len >= 500, observed: len ? `PRD is ${len} chars` : "no PRD uploaded" };
    },
    fix: "Write a real PRD. Even 1 page beats none.",
    dollarImpact: 0,
  },
  {
    id: "prod_problem",
    axis: "product",
    title: "Problem statement present",
    weight: 14,
    check: (f) => ({
      passed: !!f.prd?.mentionsProblem,
      observed: f.prd?.mentionsProblem ? "problem framed" : "no clear problem statement",
    }),
    fix: "Open the PRD with: 'Today, [user] does [task] by [painful workaround] because [root cause].'",
    dollarImpact: 0,
  },
  {
    id: "prod_user",
    axis: "product",
    title: "Target user named",
    weight: 12,
    check: (f) => ({
      passed: !!f.prd?.mentionsTargetUser,
      observed: f.prd?.mentionsTargetUser ? "target user described" : "no persona / target user",
    }),
    fix: "Name the persona. 'Founders' is not a persona; '2-person YC pre-seed founder' is.",
    dollarImpact: 0,
  },
  {
    id: "prod_metrics",
    axis: "product",
    title: "Success metrics defined",
    weight: 14,
    check: (f) => ({
      passed: !!f.prd?.mentionsMetrics,
      observed: f.prd?.mentionsMetrics ? "metrics defined" : "no success metrics",
    }),
    fix: "Pick 1 north-star metric and 2-3 input metrics. Without them you can't tell if you shipped value.",
    dollarImpact: 0,
  },
  {
    id: "prod_scope",
    axis: "product",
    title: "Scope / non-goals stated",
    weight: 12,
    check: (f) => ({
      passed: !!f.prd?.mentionsScope,
      observed: f.prd?.mentionsScope ? "scope or non-goals stated" : "no explicit scope cuts",
    }),
    fix: "List 3 things this PRD is NOT doing. Saves a week of arguments.",
    dollarImpact: 0,
  },
  {
    id: "prod_timeline",
    axis: "product",
    title: "Timeline / milestones",
    weight: 8,
    check: (f) => ({
      passed: !!f.prd?.mentionsTimeline,
      observed: f.prd?.mentionsTimeline ? "timeline present" : "no timeline / milestones",
    }),
    fix: "Add 3 milestones with dates. 'Eventually' is not a plan.",
    dollarImpact: 0,
  },
  {
    id: "prod_competition",
    axis: "product",
    title: "Competitive landscape acknowledged",
    weight: 8,
    check: (f) => ({
      passed: !!f.prd?.mentionsCompetitor,
      observed: f.prd?.mentionsCompetitor ? "competition discussed" : "no competitive analysis",
    }),
    fix: "Name 2-3 alternatives (real competitors + status quo). Investors ask in the first meeting.",
    dollarImpact: 0,
  },
];

// ---- Scoring ----
// `customAxis` (optional) is the LLM-generated axis:
//   { results: [{ id, title, weight, passed, observed, fix }] }
// When omitted, the custom axis is excluded from the composite entirely
// (so an A startup without a custom scan still grades as an A).
export function scoreFeatures(features, customAxis = null) {
  const byAxis = {};
  for (const axis of AXES) {
    byAxis[axis] = {
      score: null,
      totalWeight: 0,
      failedWeight: 0,
      skippedWeight: 0,
      evaluatedCount: 0,
      skippedCount: 0,
      results: [],
    };
  }

  for (const rule of RULES) {
    const missingInput = missingRequiredInput(rule, features);
    if (missingInput) {
      byAxis[rule.axis].skippedWeight += rule.weight;
      byAxis[rule.axis].skippedCount += 1;
      byAxis[rule.axis].results.push({
        id: rule.id,
        title: rule.title,
        weight: rule.weight,
        passed: null,
        status: "skipped",
        observed: `${missingInput} not provided`,
        locations: [],
        fix: "",
        dollarImpact: 0,
      });
      continue;
    }

    let res;
    try {
      res = rule.check(features);
    } catch {
      res = { passed: false, observed: "check failed" };
    }
    const passed = !!res.passed;
    byAxis[rule.axis].totalWeight += rule.weight;
    byAxis[rule.axis].evaluatedCount += 1;
    if (!passed) byAxis[rule.axis].failedWeight += rule.weight;
    byAxis[rule.axis].results.push({
      id: rule.id,
      title: rule.title,
      weight: rule.weight,
      passed,
      status: passed ? "passed" : "failed",
      observed: res.observed || "",
      locations: res.locations || [],
      fix: rule.fix,
      dollarImpact: rule.dollarImpact || 0,
    });
  }

  if (customAxis && Array.isArray(customAxis.results)) {
    for (const r of customAxis.results) {
      const weight = r.weight || 8;
      byAxis.custom.totalWeight += weight;
      if (!r.passed) byAxis.custom.failedWeight += weight;
      byAxis.custom.results.push({
        id: r.id,
        title: r.title,
        weight,
        passed: !!r.passed,
        observed: r.observed || "",
        fix: r.fix || "",
        dollarImpact: 0,
      });
    }
  }

  for (const axis of AXES) {
    const a = byAxis[axis];
    a.score = a.totalWeight > 0 ? Math.round(((a.totalWeight - a.failedWeight) / a.totalWeight) * 100) : null;
  }

  // Composite: average of axes that actually have rules. If the user skipped
  // the custom scan, drop the custom axis from the composite so it doesn't
  // unfairly tank the grade as a permanent 0.
  const scoredAxes = AXES.filter((a) => byAxis[a].totalWeight > 0);
  const composite =
    scoredAxes.length > 0
      ? Math.round(scoredAxes.reduce((s, a) => s + byAxis[a].score, 0) / scoredAxes.length)
      : 0;
  const grade = letterGrade(composite);

  // Top 5 actions: failed rules sorted by (dollarImpact desc, weight desc).
  // Includes both deterministic and custom failed rules.
  const failed = [];
  for (const axis of AXES) {
    for (const r of byAxis[axis].results) {
      if (!r.passed) failed.push({ ...r, axis });
    }
  }
  const topActions = failed
    .sort((a, b) => (b.dollarImpact || 0) - (a.dollarImpact || 0) || b.weight - a.weight)
    .slice(0, 5);

  return { axes: byAxis, composite, grade, topActions, scoredAxes };
function missingRequiredInput(rule, features) {
  const required = requiredInputForRule(rule);
  if (required === "github" && !features.github) return "GitHub repo";
  if (required === "prd" && !features.prd) return "PRD";
  if (required === "spreadsheet" && !features.spreadsheet) return "finance spreadsheet";
  return null;
}

function requiredInputForRule(rule) {
  if (rule.axis === "engineering") return "github";
  if (rule.axis === "financial") return "spreadsheet";
  if (rule.axis === "product") return "prd";
  if (rule.id === "legal_license_safe") return "github";
  if (rule.axis === "legal") return "prd";
  if (rule.id.startsWith("comp_repo_")) return "github";
  if (rule.axis === "compliance") return "prd";
  return null;
}

export function letterGrade(score) {
  if (score >= 93) return "A";
  if (score >= 88) return "A-";
  if (score >= 82) return "B+";
  if (score >= 75) return "B";
  if (score >= 68) return "B-";
  if (score >= 60) return "C+";
  if (score >= 50) return "C";
  if (score >= 40) return "C-";
  if (score >= 30) return "D";
  return "F";
}

export function gradeColor(grade) {
  if (!grade) return "text-text-primary";
  const c = grade[0];
  if (c === "A") return "text-emerald-600";
  if (c === "B") return "text-action-dark";
  if (c === "C") return "text-orange-500";
  return "text-red-600";
}
