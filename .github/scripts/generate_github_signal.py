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
OUTPUT_ENGINEERING_FILE = OUTPUT_DIR / "github-engineering-signal-cards.svg"


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
      <rect width="245" height="68" rx="17" fill="#0B1220" stroke="{color}" stroke-opacity="0.55"/>
      <text x="18" y="27" fill="#94A3B8" font-size="14" font-weight="800" letter-spacing="1.3">{escape(label.upper())}</text>
      <text x="18" y="58" fill="#F8FAFC" font-size="30" font-weight="900">{escape(str(value))}</text>
    </g>"""


def chip(x, y, text, color):
    return f"""
    <g transform="translate({x},{y})">
      <rect width="164" height="32" rx="16" fill="{color}" fill-opacity="0.18" stroke="{color}" stroke-opacity="0.75"/>
      <text x="82" y="21" fill="#F8FAFC" text-anchor="middle" font-size="13" font-weight="900" letter-spacing="1.05">{escape(text.upper())}</text>
    </g>"""


def dashboard_card(x, y, label, value, color):
    return f"""
    <g transform="translate({x},{y})">
      <rect width="294" height="104" rx="20" fill="#090E1B" stroke="{color}" stroke-opacity="0.7"/>
      <text x="24" y="36" fill="#94A3B8" font-size="15" font-weight="800" letter-spacing="1.2">{escape(label.upper())}</text>
      <text x="24" y="80" fill="#F8FAFC" font-size="38" font-weight="900">{escape(str(value))}</text>
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
    language_rows = []
    palette = ["#38BDF8", "#7C3AED", "#10B981", "#F97316", "#EF4444", "#A3E635"]
    for index, (name, count) in enumerate(top_languages):
        y = 366 + index * 30
        width = 300 * count / max(max_language, 1)
        color = palette[index % len(palette)]
        language_rows.append(
            f'<text x="884" y="{y}" fill="#E2E8F0" font-size="17" font-weight="900">{escape(name)}</text>'
            f'<rect x="1048" y="{y - 16}" width="300" height="18" rx="9" fill="#111827"/>'
            f'<rect x="1048" y="{y - 16}" width="{width:.1f}" height="18" rx="9" fill="{color}"/>'
            f'<text x="1368" y="{y}" fill="{color}" font-size="16" font-weight="900" text-anchor="end">{count}</text>'
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
        y = 370 + index * 44
        width = 428 * value / max(max_flow, 1)
        flow_rows.append(
            f'<text x="66" y="{y}" fill="#E2E8F0" font-size="20" font-weight="900">{escape(label)}</text>'
            f'<rect x="285" y="{y - 18}" width="428" height="20" rx="10" fill="#111827"/>'
            f'<rect x="285" y="{y - 18}" width="{width:.1f}" height="20" rx="10" fill="{color}"/>'
            f'<text x="742" y="{y}" fill="{color}" font-size="19" font-weight="900" text-anchor="end">{value:,}</text>'
        )

    return f"""<svg width="1400" height="620" viewBox="0 0 1400 620" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">GitHub Command Dashboard</title>
  <desc id="desc">GitHub command dashboard for {escape(user.get("login", PROFILE_USER))}.</desc>
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

  <text x="58" y="86" fill="#F8FAFC" font-size="52" font-weight="900">GitHub Command Dashboard</text>

  {dashboard_card(58, 138, "365d contributions", f"{total_contributions:,}", "#38BDF8")}
  {dashboard_card(382, 138, "current streak", f"{current_streak} days", "#10B981")}
  {dashboard_card(706, 138, "longest streak", f"{longest_streak} days", "#F97316")}
  {dashboard_card(1030, 138, "public repos", f"{repo_count:,}", "#7C3AED")}

  <rect x="42" y="286" width="746" height="252" rx="22" fill="#060A16" stroke="#1E293B"/>
  <text x="66" y="330" fill="#F8FAFC" font-size="28" font-weight="900">Contribution Mix</text>
  {''.join(flow_rows)}

  <rect x="820" y="286" width="540" height="252" rx="22" fill="#060A16" stroke="#1E293B"/>
  <text x="884" y="330" fill="#F8FAFC" font-size="28" font-weight="900">Language Radar</text>
  {''.join(language_rows)}

  <g transform="translate(60,562)">
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


def render_engineering_cards_svg(user):
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
    language_rows = []
    palette = ["#38BDF8", "#7C3AED", "#10B981", "#F97316", "#EF4444", "#A3E635"]
    for index, (name, count) in enumerate(top_languages):
        y = 410 + index * 34
        width = 290 * count / max(max_language, 1)
        color = palette[index % len(palette)]
        language_rows.append(
            f'<text x="92" y="{y}" fill="#E2E8F0" font-size="18" font-weight="900">{escape(name)}</text>'
            f'<rect x="260" y="{y - 19}" width="290" height="20" rx="10" fill="#111827"/>'
            f'<rect x="260" y="{y - 19}" width="{width:.1f}" height="20" rx="10" fill="{color}"/>'
            f'<text x="580" y="{y}" fill="{color}" text-anchor="end" font-size="17" font-weight="900">{count}</text>'
        )

    contribution_rows = [
        ("Commits", commits, "#38BDF8"),
        ("Pull Requests", prs, "#10B981"),
        ("Issues", issues, "#F97316"),
        ("Reviews", reviews, "#7C3AED"),
    ]
    max_contribution = max((value for _, value, _ in contribution_rows), default=1)
    contribution_bars = []
    for index, (label, value, color) in enumerate(contribution_rows):
        y = 414 + index * 48
        width = 300 * value / max(max_contribution, 1)
        contribution_bars.append(
            f'<text x="764" y="{y}" fill="#E2E8F0" font-size="19" font-weight="900">{escape(label)}</text>'
            f'<rect x="954" y="{y - 20}" width="300" height="22" rx="11" fill="#111827"/>'
            f'<rect x="954" y="{y - 20}" width="{max(width, 5):.1f}" height="22" rx="11" fill="{color}"/>'
            f'<text x="1280" y="{y}" fill="{color}" text-anchor="end" font-size="18" font-weight="900">{value:,}</text>'
        )

    last_30 = [day["contributionCount"] for day in days[-30:]]
    max_30 = max(last_30) if last_30 else 1
    spark_bars = []
    for index, value in enumerate(last_30):
        height = 72 * value / max(max_30, 1)
        x = 778 + index * 15
        y = 262 - height
        spark_bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="10" height="{height:.1f}" rx="5" fill="#38BDF8" opacity="0.82"/>')

    return f"""<svg width="1400" height="700" viewBox="0 0 1400 700" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">Engineering Signal Cards</title>
  <desc id="desc">Engineering signal cards for {escape(user.get("login", PROFILE_USER))}.</desc>
  <defs>
    <style>
      text {{ font-family: Inter, Segoe UI, Arial, sans-serif; }}
    </style>
    <linearGradient id="eng-border" x1="0" y1="0" x2="1400" y2="700">
      <stop offset="0" stop-color="#38BDF8"/>
      <stop offset="0.33" stop-color="#7C3AED"/>
      <stop offset="0.66" stop-color="#10B981"/>
      <stop offset="1" stop-color="#F97316"/>
    </linearGradient>
    <linearGradient id="eng-surface" x1="0" y1="0" x2="1400" y2="700">
      <stop offset="0" stop-color="#061625"/>
      <stop offset="0.55" stop-color="#070B1D"/>
      <stop offset="1" stop-color="#071A14"/>
    </linearGradient>
    <filter id="eng-glow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="4" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>

  <rect x="10" y="10" width="1380" height="680" rx="28" fill="url(#eng-surface)" stroke="url(#eng-border)" stroke-width="3"/>
  <path d="M62 118 C242 48 432 160 620 92 S930 55 1325 130" stroke="#38BDF8" stroke-width="3" opacity="0.25"/>
  <path d="M75 600 C270 528 470 628 675 552 S1010 490 1318 590" stroke="#10B981" stroke-width="3" opacity="0.22"/>
  <circle cx="158" cy="98" r="98" fill="#38BDF8" opacity="0.07"/>
  <circle cx="720" cy="82" r="118" fill="#7C3AED" opacity="0.08"/>
  <circle cx="1175" cy="580" r="120" fill="#10B981" opacity="0.07"/>

  <text x="58" y="86" fill="#F8FAFC" font-size="52" font-weight="900">{escape(user.get("name") or "Mopara Pair Ayat")}</text>

  <rect x="58" y="140" width="600" height="142" rx="22" fill="#090E1B" stroke="#38BDF8" stroke-opacity="0.62"/>
  <text x="88" y="179" fill="#94A3B8" font-size="17" font-weight="800" letter-spacing="1.4">PROFILE TELEMETRY</text>
  <text x="88" y="219" fill="#F8FAFC" font-size="28" font-weight="900">{total_contributions:,} contributions</text>
  <text x="88" y="255" fill="#7DD3FC" font-size="28" font-weight="900">{repo_count:,} public repos</text>
  <text x="352" y="255" fill="#CBD5E1" font-size="21" font-weight="800">{active_days}/365 active days</text>

  <rect x="720" y="140" width="620" height="142" rx="22" fill="#090E1B" stroke="#10B981" stroke-opacity="0.62"/>
  <text x="750" y="179" fill="#94A3B8" font-size="17" font-weight="800" letter-spacing="1.4">30-DAY DELIVERY PULSE</text>
  {''.join(spark_bars)}

  <rect x="58" y="320" width="600" height="282" rx="22" fill="#060A16" stroke="#1E293B"/>
  <text x="88" y="365" fill="#F8FAFC" font-size="30" font-weight="900">Language Radar</text>
  {''.join(language_rows)}

  <rect x="720" y="320" width="620" height="282" rx="22" fill="#060A16" stroke="#1E293B"/>
  <text x="750" y="365" fill="#F8FAFC" font-size="30" font-weight="900">Contribution Matrix</text>
  {''.join(contribution_bars)}

  <g transform="translate(58,632)">
    <rect width="170" height="30" rx="15" fill="#38BDF8" fill-opacity="0.18" stroke="#38BDF8"/>
    <text x="85" y="20" fill="#E0F2FE" text-anchor="middle" font-size="13" font-weight="900">STARS {stars:,}</text>
    <rect x="190" width="170" height="30" rx="15" fill="#10B981" fill-opacity="0.18" stroke="#10B981"/>
    <text x="275" y="20" fill="#D1FAE5" text-anchor="middle" font-size="13" font-weight="900">FORKS {forks:,}</text>
    <rect x="380" width="190" height="30" rx="15" fill="#7C3AED" fill-opacity="0.18" stroke="#7C3AED"/>
    <text x="475" y="20" fill="#EDE9FE" text-anchor="middle" font-size="13" font-weight="900">CURRENT {current_streak} DAYS</text>
    <rect x="590" width="185" height="30" rx="15" fill="#F97316" fill-opacity="0.18" stroke="#F97316"/>
    <text x="682" y="20" fill="#FFEDD5" text-anchor="middle" font-size="13" font-weight="900">LONGEST {longest_streak} DAYS</text>
    <rect x="795" width="180" height="30" rx="15" fill="#EF4444" fill-opacity="0.18" stroke="#EF4444"/>
    <text x="885" y="20" fill="#FEE2E2" text-anchor="middle" font-size="13" font-weight="900">DEVSECOPS READY</text>
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
    heatmap = []
    cell = 13
    gap = 3
    left = 58
    top = 366
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
    bar_x = 954
    stacked = []
    cursor = bar_x
    stacked.append('<rect x="954" y="532" width="332" height="18" rx="9" fill="#111827"/>')
    for index, (label, value, color) in enumerate(bar_items):
        width = (value / bar_total) * 332
        if value > 0:
            stacked.append(f'<rect x="{cursor:.1f}" y="532" width="{max(width, 5):.1f}" height="18" rx="9" fill="{color}"/>')
        stacked.append(
            f'<text x="{954 + index * 96}" y="566" fill="{color}" font-size="14" font-weight="900">{escape(label.replace("PULL REQUESTS", "PRS"))} {value}</text>'
        )
        cursor += width

    line_points = points_for_line(last_90, 954, 346, 350, 92)
    area_points = f"954,438 {line_points} 1304,438"
    bars = []
    max_30 = max(last_30) if last_30 else 1
    for index, value in enumerate(last_30):
        height = 42 * value / max(max_30, 1)
        x = 956 + index * 11
        y = 692 - height
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="7" height="{height:.1f}" rx="3" fill="#38BDF8" opacity="0.78"/>')

    language_chips = []
    language_colors = ["#38BDF8", "#7C3AED", "#10B981", "#F97316", "#EF4444"]
    for index, (name, count) in enumerate(top_languages):
        language_chips.append(chip(58 + index * 176, 238, f"{name} {count}", language_colors[index % len(language_colors)]))

    svg = f"""<svg width="1400" height="760" viewBox="0 0 1400 760" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">Next Zen GitHub Activity Graph</title>
  <desc id="desc">GitHub analytics graph for {escape(user.get("login", PROFILE_USER))}.</desc>
  <defs>
    <style>
      text {{ font-family: Inter, Segoe UI, Arial, sans-serif; }}
    </style>
    <linearGradient id="border" x1="0" y1="0" x2="1400" y2="760">
      <stop offset="0" stop-color="#38BDF8"/>
      <stop offset="0.32" stop-color="#7C3AED"/>
      <stop offset="0.64" stop-color="#10B981"/>
      <stop offset="1" stop-color="#F97316"/>
      <animate attributeName="x1" values="0;300;0" dur="7s" repeatCount="indefinite"/>
    </linearGradient>
    <linearGradient id="surface" x1="0" y1="0" x2="1400" y2="760">
      <stop offset="0" stop-color="#061625"/>
      <stop offset="0.5" stop-color="#080B1F"/>
      <stop offset="1" stop-color="#071A14"/>
    </linearGradient>
    <linearGradient id="area" x1="954" y1="386" x2="1304" y2="464">
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

  <rect x="10" y="10" width="1380" height="740" rx="28" fill="url(#surface)" stroke="url(#border)" stroke-width="3"/>
  <path d="M55 120 C210 50 330 165 490 82 S735 75 860 132 S1110 235 1338 88" stroke="#38BDF8" stroke-width="3" opacity="0.32"/>
  <path d="M70 640 C280 548 450 675 645 575 S940 500 1320 610" stroke="#10B981" stroke-width="3" opacity="0.28"/>
  <circle cx="125" cy="104" r="94" fill="#38BDF8" opacity="0.08"/>
  <circle cx="694" cy="82" r="108" fill="#7C3AED" opacity="0.10"/>
  <circle cx="1188" cy="590" r="118" fill="#10B981" opacity="0.08"/>

  <text x="58" y="86" fill="#F8FAFC" font-size="52" font-weight="900">Next-Zen GitHub Signal Graph</text>

  {metric_card(58, 140, "365d contributions", f"{total_contributions:,}", "#38BDF8")}
  {metric_card(384, 140, "public repos", f"{repo_count:,}", "#7C3AED")}
  {metric_card(710, 140, "stars / forks", f"{stars:,} / {forks:,}", "#10B981")}
  {metric_card(1036, 140, "private signal", f"{restricted:,}", "#F97316")}

  {''.join(language_chips)}

  <rect x="42" y="304" width="878" height="252" rx="22" fill="#060A16" stroke="#1E293B"/>
  <text x="58" y="345" fill="#F8FAFC" font-size="30" font-weight="900">Contribution Heatmap</text>
  {''.join(heatmap)}

  <rect x="930" y="304" width="400" height="150" rx="22" fill="#060A16" stroke="#1E293B"/>
  <text x="952" y="340" fill="#F8FAFC" font-size="22" font-weight="900">90-Day Velocity Curve</text>
  <polygon points="{area_points}" fill="url(#area)"/>
  <polyline points="{line_points}" fill="none" stroke="#38BDF8" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" filter="url(#glow)"/>
  <line x1="954" y1="438" x2="1304" y2="438" stroke="#334155" stroke-width="1"/>

  <rect x="930" y="476" width="400" height="108" rx="22" fill="#060A16" stroke="#1E293B"/>
  <text x="952" y="516" fill="#F8FAFC" font-size="22" font-weight="900">Contribution Mix</text>
  {''.join(stacked)}

  <rect x="930" y="606" width="400" height="104" rx="22" fill="#060A16" stroke="#1E293B"/>
  <text x="952" y="646" fill="#F8FAFC" font-size="22" font-weight="900">30-Day Spark Bars</text>
  {''.join(bars)}

  <g transform="translate(58,590)">
    <rect width="130" height="30" rx="15" fill="#38BDF8" fill-opacity="0.18" stroke="#38BDF8"/>
    <text x="65" y="20" fill="#E0F2FE" text-anchor="middle" font-size="12" font-weight="900">PROJECTS 2050+</text>
    <rect x="145" width="168" height="30" rx="15" fill="#7C3AED" fill-opacity="0.18" stroke="#7C3AED"/>
    <text x="229" y="20" fill="#EDE9FE" text-anchor="middle" font-size="12" font-weight="900">TECH DOMAINS 50+</text>
    <rect x="328" width="150" height="30" rx="15" fill="#10B981" fill-opacity="0.18" stroke="#10B981"/>
    <text x="403" y="20" fill="#D1FAE5" text-anchor="middle" font-size="12" font-weight="900">AI AGENTS ACTIVE</text>
    <rect x="493" width="128" height="30" rx="15" fill="#F97316" fill-opacity="0.18" stroke="#F97316"/>
    <text x="557" y="20" fill="#FFEDD5" text-anchor="middle" font-size="12" font-weight="900">LLMOPS READY</text>
    <rect x="636" width="170" height="30" rx="15" fill="#EF4444" fill-opacity="0.18" stroke="#EF4444"/>
    <text x="721" y="20" fill="#FEE2E2" text-anchor="middle" font-size="12" font-weight="900">DEVSECOPS HARDENED</text>
  </g>
</svg>
"""
    return svg


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    user = load_user()
    OUTPUT_DASHBOARD_FILE.write_text(render_dashboard_svg(user), encoding="utf-8")
    OUTPUT_ENGINEERING_FILE.write_text(render_engineering_cards_svg(user), encoding="utf-8")
    OUTPUT_FILE.write_text(render_svg(user), encoding="utf-8")
    print(f"Wrote {OUTPUT_DASHBOARD_FILE}")
    print(f"Wrote {OUTPUT_ENGINEERING_FILE}")
    print(f"Wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
