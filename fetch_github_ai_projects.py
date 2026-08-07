"""抓取 GitHub 高 star AI 项目（供小红书选题参考）

用法：python3 fetch_github_ai_projects.py [数量] [最小star]
输出：项目名 / star 数 / 简介 / 语言 / URL，保存到 /tmp/xhs_github_projects.json
"""
import json
import sys
import time
import urllib.request
import urllib.parse

TOPICS = ["ai", "machine-learning", "llm", "agents", "deep-learning"]

def gh_search(query, per_page=10):
    """GitHub search API（无需 token，限速 60/h）"""
    q = urllib.parse.quote(query)
    url = f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page={per_page}"
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "hermes-agent",
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    min_stars = int(sys.argv[2]) if len(sys.argv) > 2 else 5000

    projects = []
    seen = set()
    for topic in TOPICS:
        try:
            data = gh_search(f"topic:{topic} stars:>{min_stars}")
            items = data.get("items", [])
            print(f"[{topic}] {len(items)} 个 (total={data.get('total_count', 0)})")
            for it in items:
                name = it.get("full_name", "")
                if name in seen:
                    continue
                seen.add(name)
                projects.append({
                    "name": name,
                    "stars": it.get("stargazers_count", 0),
                    "description": (it.get("description") or "")[:150],
                    "language": it.get("language") or "",
                    "url": it.get("html_url", ""),
                    "topics": (it.get("topics") or [])[:5],
                })
            time.sleep(1)  # 限速
        except Exception as e:
            print(f"[{topic}] 错误: {str(e)[:80]}")

    # 按 star 排序去重
    projects.sort(key=lambda x: -x["stars"])
    projects = projects[:limit]

    with open("/tmp/xhs_github_projects.json", "w") as f:
        json.dump(projects, f, ensure_ascii=False, indent=2)

    print(f"\n=== 共 {len(projects)} 个高 star AI 项目 ===")
    for p in projects:
        print(f"⭐{p['stars']:>8,} | {p['name']} | {p['language']}")
        print(f"        {(p['description'] or '')[:80]}")
        print(f"        {p['url']}")


if __name__ == "__main__":
    main()
