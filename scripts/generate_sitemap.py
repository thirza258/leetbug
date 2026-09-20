#!/usr/bin/env python3
"""Generate frontend/public/sitemap.xml and frontend/public/robots.txt."""
import argparse
from pathlib import Path
import sys

# Ensure backend app package is importable
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "backend"))

from app.sitemap import DEFAULT_SITE_URL, generate_robots_txt, generate_sitemap_xml


def main():
    parser = argparse.ArgumentParser(description="Generate sitemap.xml and robots.txt for LeetBug")
    parser.add_argument("--base-url", default=DEFAULT_SITE_URL, help="Base canonical URL (default from settings)")
    parser.add_argument("--output-dir", default=str(repo_root / "frontend" / "public"), help="Output directory")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sitemap_path = out_dir / "sitemap.xml"
    robots_path = out_dir / "robots.txt"

    sitemap_content = generate_sitemap_xml(args.base_url)
    robots_content = generate_robots_txt(args.base_url)

    sitemap_path.write_text(sitemap_content, encoding="utf-8")
    robots_path.write_text(robots_content, encoding="utf-8")

    url_count = sitemap_content.count("<url>")
    print(f"Generated {sitemap_path} ({url_count} URLs, {len(sitemap_content)} bytes)")
    print(f"Generated {robots_path} ({len(robots_content)} bytes)")


if __name__ == "__main__":
    main()
