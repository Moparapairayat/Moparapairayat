#!/usr/bin/env python3
import json
import math
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROFILE_USER = os.getenv("PROFILE_USER", "Moparapairayat")
UTC_OFFSET_HOURS = int(os.getenv("UTC_OFFSET_HOURS", "6"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "dist"))
OUTPUT_FILE = OUTPUT_DIR / "github-nextzen-activity.svg"
OUTPUT_DASHBOARD_FILE = OUTPUT_DIR / "github-command-dashboard.svg"


QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    login
    name
    followers {
      totalCount
    }
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
            weekday
          }
        }
      }
    }
    repositories(
      first: 100
      ownerAffiliations: OWNER
      orderBy: {field: UPDATED_AT, direction: DESC}
      privacy: PUBLIC
    ) {
      totalCount
      nodes {
        stargazerCount
        forkCount
        primaryLanguage {
          name
          color
        }
      }
    }
  }
}
"""


def request_github_graphql(token, login):
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=365)
    variables = {
        "login": login,
        "from": start.isoformat().replace("+00:00", "Z"),
        "to": now.isoformat().replace("+00:00", "Z"),
    }
    payload = json.dumps({"query": QUERY, "variables": variables}).encode("utf-8")
    request = Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "nextzen-github-signal-generator",
        },
        method="POST",
    )
    with urlopen(request, timeout=25) as response:
        result = json.loads(response.read().decode("utf-8"))
    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"], indent=2))
    return result["data"]["user"]


def fallback_user(login):
    today = datetime.now(timezone.utc).date()
    days = []
    for index in range(365):
        date = today - timedelta(days=364 - index)
        wave = math.sin(index / 8) + math.sin(index / 19) + 1.5
        count = max(0, int(wave * 2 + (index % 11 == 0) * 5 + (index % 29 == 0) * 8))
        days.append(
            {
                "date": date.isoformat(),
                "weekday": date.weekday(),
                "contributionCount": count,
            }
        )
    weeks = [{"contributionDays": days[i : i + 7]} for i in range(0, len(days), 7)]
    total = sum(day["contributionCount"] for day in days)
    return {
        "login": login,
        "name": "Mopara Pair Ayat",
        "followers": {"totalCount": 0},
        "contributionsCollection": {
            "totalCommitContributions": int(total * 0.72),
            "totalIssueContributions": int(total * 0.08),
            "totalPullRequestContributions": int(total * 0.13),
            "totalPullRequestReviewContributions": int(total * 0.07),
            "restrictedContributionsCount": 0,
            "contributionCalendar": {
                "totalContributions": total,
                "weeks": weeks,
            },
        },
        "repositories": {
            "totalCount": 2050,
            "nodes": [
                {"stargazerCount": 0, "forkCount": 0, "primaryLanguage": {"name": "Python", "color": "#3572A5"}},
                {"stargazerCount": 0, "forkCount": 0, "primaryLanguage": {"name": "TypeScript", "color": "#3178C6"}},
                {"stargazerCount": 0, "forkCount": 0, "primaryLanguage": {"name": "JavaScript", "color": "#F1E05A"}},
                {"stargazerCount": 0, "forkCount": 0, "primaryLanguage": {"name": "Go", "color": "#00ADD8"}},
            ],
        },
    }


def load_user():
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token:
        print("GITHUB_TOKEN is not set; generating fallback preview data.", file=sys.stderr)
        return fallback_user(PROFILE_USER)
    try:
        return request_github_graphql(token, PROFILE_USER)
    except (HTTPError, URLError, TimeoutError, RuntimeError, KeyError) as error:
        print(f"GitHub data fetch failed; generating fallback preview data: {error}", file=sys.stderr)
        return fallback_user(PROFILE_USER)


def flatten_days(user):
    calendar = user["contributionsCollection"]["contributionCalendar"]
    days = []
    for week in calendar["weeks"]:
        days.extend(week["contributionDays"])
    return sorted(days, key=lambda day: day["date"])[-365:]


def contribution_color(count, maximum):
    if count <= 0:
        return "#111827"
    ratio = count / max(maximum, 1)
    if ratio < 0.18:
        return "#0E7490"
    if ratio < 0.36:
        return "#38BDF8"
    if ratio < 0.58:
        return "#7C3AED"
    if ratio < 0.78:
        return "#10B981"
    return "#F97316"


def points_for_line(values, left, top, width, height):
    maximum = max(values) if values else 1
    if len(values) <= 1:
        return f"{left},{top + height}"
    points = []
    for index, value in enumerate(values):
        x = left + (index / (len(values) - 1)) * width
        y = top + height - (value / max(maximum, 1)) * height
        points.append(f"{x:.1f},{y:.1f}")
    return " ".join(points)


def streaks(days):
    longest = 0
    current = 0
    running = 0
    for day in days:
        if day["contributionCount"] > 0:
            running += 1
            longest = max(longest, running)
        else:
            running = 0
    current = running
    return current, longest


def metric_card(x, y, label, value, color):
    return f"""
    <g transform="translate({x},{y})">
      <rect width="245" height="58" rx="16" fill="#0B1220" stroke="{color}" stroke-opacity="0.55"/>
      <text x="18" y="24" fill="#94A3B8" font-size="13" font-weight="700" letter-spacing="1.3">{escape(label.upper())}</text>
      <text x="18" y="49" fill="#F8FAFC" font-size="25" font-weight="900">{escape(str(value))}</text>
    </g>"""


def chip(x, y, text, color):
    return f"""
    <g transform="translate({x},{y})">
      <rect width="158" height="28" rx="14" fill="{color}" fill-opacity="0.18" stroke="{color}" stroke-opacity="0.75"/>
      <text x="79" y="19" fill="#F8FAFC" text-anchor="middle" font-size="12" font-weight="900" letter-spacing="1.1">{escape(text.upper())}</text>
    </g>"""


def dashboard_card(x, y, label, value, color):
    return f"""
    <g transform="translate({x},{y})">
      <rect width="294" height="94" rx="20" fill="#090E1B" stroke="{color}" stroke-opacity="0.7"/>
      <text x="24" y="33" fill="#94A3B8" font-size="14" font-weight="800" letter-spacing="1.2">{escape(label.upper())}</text>
      <text x="24" y="73" fill="#F8FAFC" font-size="34" font-weight="900">{escape(str(value))}</text>
    </g>"""


def render_dashboard_svg(user):
    days = flatten_days(user)
    collection = user["contributionsCollection"]
    repos = user["repositories"]
    repo_nodes = repos.get("nodes", [])
    total_contributions = collection["contributionCalendar"]["totalContributions"]
    commits = collection["totalCommitContributions"]
    prs = collection["totalPullRequestContributions"]
    issues = collection["totalIssueContributions"]
    reviews = collection["totalPullRequestReviewContributions"]
    current_streak, longest_streak = streaks(days)
    active_days = sum(1 for day in days if day["contributionCount"] > 0)
    repo_count = repos["totalCount"]
    stars = sum(repo.get("stargazerCount", 0) for repo in repo_nodes)
    forks = sum(repo.get("forkCount", 0) for repo in repo_nodes)
    languages = Counter(
        repo["primaryLanguage"]["name"]
        for repo in repo_nodes
        if repo.get("primaryLanguage") and repo["primaryLanguage"].get("name")
    )
    top_languages = languages.most_common(6)
    max_language = max((count for _, count in top_languages), default=1)
    bdt_now = datetime.now(timezone.utc) + timedelta(hours=UTC_OFFSET_HOURS)
    updated = bdt_now.strftime("%Y-%m-%d %H:%M BDT")

    language_rows = []
    palette = ["#38BDF8", "#7C3AED", "#10B981", "#F97316", "#EF4444", "#A3E635"]
    for index, (name, count) in enumerate(top_languages):
        y = 402 + index * 25
        width = 300 * count / max(max_language, 1)
        color = palette[index % len(palette)]
        language_rows.append(
            f'<text x="884" y="{y}" fill="#E2E8F0" font-size="15" font-weight="900">{escape(name)}</text>'
            f'<rect x="1048" y="{y - 14}" width="300" height="15" rx="8" fill="#111827"/>'
            f'<rect x="1048" y="{y - 14}" width="{width:.1f}" height="15" rx="8" fill="{color}"/>'
            f'<text x="1368" y="{y}" fill="{color}" font-size="14" font-weight="900" text-anchor="end">{count}</text>'
        )

    flow_items = [
        ("COMMITS", commits, "#38BDF8"),
        ("PULL REQUESTS", prs, "#10B981"),
        ("ISSUES", issues, "#F97316"),
        ("REVIEWS", reviews, "#7C3AED"),
    ]
    max_flow = max((value for _, value, _ in flow_items), default=1)
    flow_rows = []
    for index, (label, value, color) in enumerate(flow_items):
        y = 405 + index * 38
        width = 438 * value / max(max_flow, 1)
        flow_rows.append(
            f'<text x="66" y="{y}" fill="#E2E8F0" font-size="18" font-weight="900">{escape(label)}</text>'
            f'<rect x="275" y="{y - 17}" width="438" height="18" rx="9" fill="#111827"/>'
            f'<rect x="275" y="{y - 17}" width="{width:.1f}" height="18" rx="9" fill="{color}"/>'
            f'<text x="742" y="{y}" fill="{color}" font-size="17" font-weight="900" text-anchor="end">{value:,}</text>'
        )

    return f"""<svg width="1400" height="620" viewBox="0 0 1400 620" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">GitHub Command Dashboard</title>
  <desc id="desc">Workflow generated GitHub command dashboard for {escape(user.get("login", PROFILE_USER))}.</desc>
  <defs>
    <style>
      text {{ font-family: Inter, Segoe UI, Arial, sans-serif; }}
    </style>
    <linearGradient id="dash-border" x1="0" y1="0" x2="1400" y2="620">
      <stop offset="0" stop-color="#38BDF8"/>
      <stop offset="0.36" stop-color="#7C3AED"/>
      <stop offset="0.7" stop-color="#10B981"/>
      <stop offset="1" stop-color="#F97316"/>
      <animate attributeName="x2" values="1100;1400;1100" dur="8s" repeatCount="indefinite"/>
    </linearGradient>
    <linearGradient id="dash-surface" x1="0" y1="0" x2="1400" y2="620">
      <stop offset="0" stop-color="#071827"/>
      <stop offset="0.55" stop-color="#080B1D"/>
      <stop offset="1" stop-color="#071D16"/>
    </linearGradient>
    <filter id="dash-glow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="4" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>

  <rect x="10" y="10" width="1380" height="600" rx="28" fill="url(#dash-surface)" stroke="url(#dash-border)" stroke-width="3"/>
  <path d="M55 105 C240 38 410 152 600 86 S945 42 1328 125" stroke="#38BDF8" stroke-width="3" opacity="0.28"/>
  <path d="M72 525 C290 430 466 557 690 465 S1005 413 1320 515" stroke="#10B981" stroke-width="3" opacity="0.25"/>
  <circle cx="160" cy="86" r="96" fill="#38BDF8" opacity="0.07"/>
  <circle cx="760" cy="70" r="120" fill="#7C3AED" opacity="0.09"/>
  <circle cx="1190" cy="475" r="115" fill="#10B981" opacity="0.08"/>

  <text x="58" y="66" fill="#7DD3FC" font-size="14" font-weight="900" letter-spacing="4">WORKFLOW GENERATED</text>
  <text x="58" y="118" fill="#F8FAFC" font-size="46" font-weight="900">GitHub Command Dashboard</text>
  <text x="60" y="158" fill="#CBD5E1" font-size="19" font-weight="700">Stats, languages, streaks, and contribution mix from GitHub Actions | Updated {escape(updated)}</text>

  {dashboard_card(58, 190, "365d contributions", f"{total_contributions:,}", "#38BDF8")}
  {dashboard_card(382, 190, "current streak", f"{current_streak} days", "#10B981")}
  {dashboard_card(706, 190, "longest streak", f"{longest_streak} days", "#F97316")}
  {dashboard_card(1030, 190, "public repos", f"{repo_count:,}", "#7C3AED")}

  <rect x="42" y="330" width="746" height="215" rx="22" fill="#060A16" stroke="#1E293B"/>
  <text x="66" y="372" fill="#F8FAFC" font-size="24" font-weight="900">Contribution Mix</text>
  {''.join(flow_rows)}

  <rect x="820" y="330" width="540" height="215" rx="22" fill="#060A16" stroke="#1E293B"/>
  <text x="884" y="372" fill="#F8FAFC" font-size="24" font-weight="900">Language Radar</text>
  {''.join(language_rows)}

  <g transform="translate(60,570)">
    <rect width="170" height="28" rx="14" fill="#38BDF8" fill-opacity="0.18" stroke="#38BDF8"/>
    <text x="85" y="19" fill="#E0F2FE" text-anchor="middle" font-size="13" font-weight="900">ACTIVE {active_days}/365</text>
    <rect x="188" width="150" height="28" rx="14" fill="#7C3AED" fill-opacity="0.18" stroke="#7C3AED"/>
    <text x="263" y="19" fill="#EDE9FE" text-anchor="middle" font-size="13" font-weight="900">STARS {stars:,}</text>
    <rect x="356" width="150" height="28" rx="14" fill="#10B981" fill-opacity="0.18" stroke="#10B981"/>
    <text x="431" y="19" fill="#D1FAE5" text-anchor="middle" font-size="13" font-weight="900">FORKS {forks:,}</text>
    <rect x="524" width="175" height="28" rx="14" fill="#F97316" fill-opacity="0.18" stroke="#F97316"/>
    <text x="611" y="19" fill="#FFEDD5" text-anchor="middle" font-size="13" font-weight="900">PROJECTS 2050+</text>
    <rect x="717" width="205" height="28" rx="14" fill="#22C55E" fill-opacity="0.18" stroke="#22C55E"/>
    <text x="819" y="19" fill="#DCFCE7" text-anchor="middle" font-size="13" font-weight="900">TECH DOMAINS 50+</text>
    <rect x="940" width="150" height="28" rx="14" fill="#EF4444" fill-opacity="0.18" stroke="#EF4444"/>
    <text x="1015" y="19" fill="#FEE2E2" text-anchor="middle" font-size="13" font-weight="900">DEVSECOPS</text>
  </g>

  <g filter="url(#dash-glow)">
    <circle cx="778" cy="104" r="7" fill="#38BDF8"/>
    <circle cx="1120" cy="72" r="6" fill="#10B981"/>
    <circle cx="1308" cy="132" r="6" fill="#F97316"/>
  </g>
</svg>
"""


def render_svg(user):
    days = flatten_days(user)
    collection = user["contributionsCollection"]
    repos = user["repositories"]
    repo_nodes = repos.get("nodes", [])
    total_contributions = collection["contributionCalendar"]["totalContributions"]
    commits = collection["totalCommitContributions"]
    prs = collection["totalPullRequestContributions"]
    issues = collection["totalIssueContributions"]
    reviews = collection["totalPullRequestReviewContributions"]
    restricted = collection.get("restrictedContributionsCount", 0)
    repo_count = repos["totalCount"]
    stars = sum(repo.get("stargazerCount", 0) for repo in repo_nodes)
    forks = sum(repo.get("forkCount", 0) for repo in repo_nodes)
    languages = Counter(
        repo["primaryLanguage"]["name"]
        for repo in repo_nodes
        if repo.get("primaryLanguage") and repo["primaryLanguage"].get("name")
    )
    top_languages = languages.most_common(5)
    max_day = max((day["contributionCount"] for day in days), default=1)
    last_90 = [day["contributionCount"] for day in days[-90:]]
    last_30 = [day["contributionCount"] for day in days[-30:]]
    bdt_now = datetime.now(timezone.utc) + timedelta(hours=UTC_OFFSET_HOURS)
    updated = bdt_now.strftime("%Y-%m-%d %H:%M BDT")

    heatmap = []
    cell = 12
    gap = 4
    left = 58
    top = 282
    for index, day in enumerate(days[-364:]):
        week = index // 7
        weekday = index % 7
        x = left + week * (cell + gap)
        y = top + weekday * (cell + gap)
        color = contribution_color(day["contributionCount"], max_day)
        heatmap.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{color}">'
            f'<title>{escape(day["date"])}: {day["contributionCount"]} contributions</title></rect>'
        )

    bar_items = [
        ("COMMITS", commits, "#38BDF8"),
        ("PRS", prs, "#10B981"),
        ("ISSUES", issues, "#F97316"),
        ("REVIEWS", reviews, "#7C3AED"),
    ]
    bar_total = max(sum(item[1] for item in bar_items), 1)
    bar_x = 960
    stacked = []
    cursor = bar_x
    for label, value, color in bar_items:
        width = max(8, (value / bar_total) * 330)
        stacked.append(f'<rect x="{cursor:.1f}" y="284" width="{width:.1f}" height="16" rx="8" fill="{color}"/>')
        stacked.append(
            f'<text x="{cursor:.1f}" y="326" fill="{color}" font-size="13" font-weight="900">{escape(label)} {value}</text>'
        )
        cursor += width

    line_points = points_for_line(last_90, 930, 112, 380, 100)
    area_points = f"930,212 {line_points} 1310,212"
    bars = []
    max_30 = max(last_30) if last_30 else 1
    for index, value in enumerate(last_30):
        height = 56 * value / max(max_30, 1)
        x = 933 + index * 12
        y = 390 - height
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="7" height="{height:.1f}" rx="3" fill="#38BDF8" opacity="0.75"/>')

    language_chips = []
    language_colors = ["#38BDF8", "#7C3AED", "#10B981", "#F97316", "#EF4444"]
    for index, (name, count) in enumerate(top_languages):
        language_chips.append(chip(58 + index * 170, 214, f"{name} {count}", language_colors[index % len(language_colors)]))

    svg = f"""<svg width="1400" height="455" viewBox="0 0 1400 455" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">Next Zen GitHub Activity Graph</title>
  <desc id="desc">Generated GitHub analytics graph for {escape(user.get("login", PROFILE_USER))}, updated by GitHub Actions.</desc>
  <defs>
    <linearGradient id="border" x1="0" y1="0" x2="1400" y2="455">
      <stop offset="0" stop-color="#38BDF8"/>
      <stop offset="0.32" stop-color="#7C3AED"/>
      <stop offset="0.64" stop-color="#10B981"/>
      <stop offset="1" stop-color="#F97316"/>
      <animate attributeName="x1" values="0;300;0" dur="7s" repeatCount="indefinite"/>
    </linearGradient>
    <linearGradient id="surface" x1="0" y1="0" x2="1400" y2="455">
      <stop offset="0" stop-color="#061625"/>
      <stop offset="0.5" stop-color="#080B1F"/>
      <stop offset="1" stop-color="#071A14"/>
    </linearGradient>
    <linearGradient id="area" x1="930" y1="110" x2="1310" y2="212">
      <stop offset="0" stop-color="#38BDF8" stop-opacity="0.35"/>
      <stop offset="1" stop-color="#10B981" stop-opacity="0.08"/>
    </linearGradient>
    <filter id="glow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="5" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>

  <rect x="10" y="10" width="1380" height="435" rx="28" fill="url(#surface)" stroke="url(#border)" stroke-width="3"/>
  <path d="M55 120 C210 50 330 165 490 82 S735 75 860 132 S1110 235 1338 88" stroke="#38BDF8" stroke-width="3" opacity="0.32"/>
  <path d="M70 382 C280 315 450 425 645 330 S940 238 1320 347" stroke="#10B981" stroke-width="3" opacity="0.28"/>
  <circle cx="125" cy="104" r="94" fill="#38BDF8" opacity="0.08"/>
  <circle cx="694" cy="82" r="108" fill="#7C3AED" opacity="0.10"/>
  <circle cx="1188" cy="338" r="118" fill="#10B981" opacity="0.08"/>

  <text x="58" y="62" fill="#7DD3FC" font-size="14" font-weight="900" letter-spacing="4">GITHUB ACTIONS LIVE OPS</text>
  <text x="58" y="106" fill="#F8FAFC" font-size="42" font-weight="900">Next-Zen GitHub Signal Graph</text>
  <text x="60" y="137" fill="#CBD5E1" font-size="18" font-weight="700">Near real-time contribution telemetry | Updated {escape(updated)}</text>
  <text x="1048" y="62" fill="#94A3B8" font-size="14" font-weight="800" letter-spacing="2">PROFILE</text>
  <text x="1048" y="96" fill="#F8FAFC" font-size="30" font-weight="900">{escape(user.get("name") or user.get("login") or PROFILE_USER)}</text>
  <text x="1049" y="126" fill="#7DD3FC" font-size="16" font-weight="800">@{escape(user.get("login", PROFILE_USER))}</text>

  {metric_card(58, 148, "365d contributions", f"{total_contributions:,}", "#38BDF8")}
  {metric_card(315, 148, "public repos", f"{repo_count:,}", "#7C3AED")}
  {metric_card(572, 148, "stars / forks", f"{stars:,} / {forks:,}", "#10B981")}
  {metric_card(829, 148, "private signal", f"{restricted:,}", "#F97316")}

  {''.join(language_chips)}

  <rect x="42" y="258" width="878" height="154" rx="22" fill="#060A16" stroke="#1E293B"/>
  <text x="58" y="250" fill="#F8FAFC" font-size="19" font-weight="900">Contribution Heatmap</text>
  {''.join(heatmap)}

  <rect x="930" y="84" width="400" height="150" rx="22" fill="#060A16" stroke="#1E293B"/>
  <text x="952" y="118" fill="#F8FAFC" font-size="19" font-weight="900">90-Day Velocity Curve</text>
  <polygon points="{area_points}" fill="url(#area)"/>
  <polyline points="{line_points}" fill="none" stroke="#38BDF8" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" filter="url(#glow)"/>
  <line x1="930" y1="212" x2="1310" y2="212" stroke="#334155" stroke-width="1"/>

  <rect x="930" y="252" width="400" height="94" rx="22" fill="#060A16" stroke="#1E293B"/>
  <text x="952" y="276" fill="#F8FAFC" font-size="19" font-weight="900">Contribution Mix</text>
  {''.join(stacked)}

  <rect x="930" y="362" width="400" height="60" rx="22" fill="#060A16" stroke="#1E293B"/>
  <text x="952" y="390" fill="#F8FAFC" font-size="18" font-weight="900">30-Day Spark Bars</text>
  {''.join(bars)}

  <g transform="translate(58,424)">
    <text fill="#38BDF8" font-size="14" font-weight="900">PROJECTS 2050+</text>
    <text x="160" fill="#7C3AED" font-size="14" font-weight="900">TECH DOMAINS 50+</text>
    <text x="350" fill="#10B981" font-size="14" font-weight="900">AI AGENTS ACTIVE</text>
    <text x="535" fill="#F97316" font-size="14" font-weight="900">LLMOPS READY</text>
    <text x="700" fill="#EF4444" font-size="14" font-weight="900">DEVSECOPS HARDENED</text>
  </g>
</svg>
"""
    return svg


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    user = load_user()
    OUTPUT_DASHBOARD_FILE.write_text(render_dashboard_svg(user), encoding="utf-8")
    OUTPUT_FILE.write_text(render_svg(user), encoding="utf-8")
    print(f"Wrote {OUTPUT_DASHBOARD_FILE}")
    print(f"Wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
