from app.catalog import CATALOG

DEFAULT_SITE_URL = "https://leetbug.nevatal.id"

try:
    from app.config import settings
    DEFAULT_SITE_URL = getattr(settings, "site_url", DEFAULT_SITE_URL)
except Exception:
    pass

COURSES = [
    {
        "slug": "finding-the-bug",
        "lessons": ["reproduce-the-failure", "shrink-the-example", "trace-first-divergence"],
    },
    {
        "slug": "proving-the-fix",
        "lessons": ["test-a-hypothesis", "regression-neighbors", "check-state-and-sequences"],
    },
    {
        "slug": "runtime-crash-investigation",
        "lessons": ["read-the-crash", "optional-input-shapes", "parsing-boundaries"],
    },
    {
        "slug": "runtime-state-and-termination",
        "lessons": ["safe-collection-updates", "cycles-and-termination", "serialization-boundary"],
    },
    {
        "slug": "logic-control-flow",
        "lessons": ["loop-invariants", "boolean-decision-tables", "sorting-and-ties"],
    },
    {
        "slug": "logic-state-and-algorithms",
        "lessons": ["shared-references", "recurrence-update-order", "discovery-versus-finality"],
    },
    {
        "slug": "business-rules-and-invariants",
        "lessons": ["business-invariants", "independent-policy-gates", "business-calculation-order"],
    },
    {
        "slug": "business-workflows-and-retries",
        "lessons": ["allowed-transitions", "atomic-workflows", "duplicate-business-actions"],
    },
    {
        "slug": "edge-case-discovery",
        "lessons": ["boundary-test-matrix", "absence-versus-zero", "duplicates-and-order"],
    },
    {
        "slug": "boundaries-and-representation",
        "lessons": ["exact-numeric-representations", "unicode-units", "time-offset-boundaries"],
    },
    {
        "slug": "choosing-an-architecture",
        "lessons": ["requirements-first", "architecture-styles", "defend-the-decision"],
    },
    {
        "slug": "data-consistency-and-caching",
        "lessons": ["access-patterns", "concurrent-updates", "cache-freshness"],
    },
    {
        "slug": "queues-and-reliability",
        "lessons": ["queues-and-bursts", "safe-retries", "bounded-recovery"],
    },
    {
        "slug": "system-design-failure-analysis",
        "lessons": ["cache-read-write-traces", "worker-loss-and-leases", "circuit-recovery-boundaries"],
    },
]

STATIC_PAGES = [
    ("", "daily", "1.0"),
    ("courses", "weekly", "0.9"),
    ("guide", "monthly", "0.8"),
    ("leaderboard", "daily", "0.7"),
    ("discussions", "daily", "0.7"),
    ("incidents", "weekly", "0.8"),
    ("assessments", "weekly", "0.7"),
]


def generate_robots_txt(base_url: str | None = None) -> str:
    url = (base_url or DEFAULT_SITE_URL).rstrip("/")
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /login\n"
        "Disallow: /register\n"
        "Disallow: /progress\n"
        "Disallow: /submissions\n"
        "Disallow: /discussions/new\n"
        "Disallow: /assessment-sessions/\n"
        "Disallow: /assessment-invitations/\n"
        "Disallow: /admin\n\n"
        f"Sitemap: {url}/sitemap.xml\n"
    )


def generate_sitemap_xml(base_url: str | None = None) -> str:
    url = (base_url or DEFAULT_SITE_URL).rstrip("/")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    for path, changefreq, priority in STATIC_PAGES:
        loc = f"{url}/{path}" if path else f"{url}/"
        lines.append("  <url>")
        lines.append(f"    <loc>{loc}</loc>")
        lines.append(f"    <changefreq>{changefreq}</changefreq>")
        lines.append(f"    <priority>{priority}</priority>")
        lines.append("  </url>")

    for course in COURSES:
        c_slug = course["slug"]
        lines.append("  <url>")
        lines.append(f"    <loc>{url}/courses/{c_slug}</loc>")
        lines.append("    <changefreq>weekly</changefreq>")
        lines.append("    <priority>0.8</priority>")
        lines.append("  </url>")
        for l_slug in course["lessons"]:
            lines.append("  <url>")
            lines.append(f"    <loc>{url}/courses/{c_slug}/{l_slug}</loc>")
            lines.append("    <changefreq>weekly</changefreq>")
            lines.append("    <priority>0.7</priority>")
            lines.append("  </url>")

    for prob in CATALOG:
        p_slug = prob["slug"]
        lines.append("  <url>")
        lines.append(f"    <loc>{url}/problems/{p_slug}</loc>")
        lines.append("    <changefreq>weekly</changefreq>")
        lines.append("    <priority>0.8</priority>")
        lines.append("  </url>")

    lines.append("</urlset>")
    return "\n".join(lines) + "\n"
