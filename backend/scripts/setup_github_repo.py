#!/usr/bin/env python3
"""
setup_github_repo.py
--------------------
Creates the pipeline-prophet-demo GitHub repository under your account,
pushes all demo-repo/ files to it, and registers the webhook.

Requirements:
  - GITHUB_TOKEN must have 'repo' scope (classic token)
  - GITHUB_WEBHOOK_SECRET must be set in .env
  - Backend must be accessible at WEBHOOK_TARGET_URL (ngrok or public URL)

Usage:
    python backend/scripts/setup_github_repo.py
    python backend/scripts/setup_github_repo.py --webhook-url https://your-ngrok-url.ngrok.io
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------
_env_path = Path(__file__).parent.parent.parent / ".env"
if _env_path.exists():
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

GITHUB_TOKEN   = os.environ.get("GITHUB_TOKEN", "")
WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "pipeline-prophet-demo-secret")
REPO_NAME      = "pipeline-prophet-demo"
DEMO_REPO_DIR  = Path(__file__).parent.parent.parent / "demo-repo"


def _github_request(method: str, path: str, body: dict | None = None) -> dict:
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "PipelineProphet",
            "Content-Type": "application/json",
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode()
        raise RuntimeError(f"GitHub API {method} {path} -> {e.code}: {body_txt}") from e


def get_username() -> str:
    user = _github_request("GET", "/user")
    return user["login"]


def create_repo(username: str) -> str:
    """Create repo if it doesn't exist. Returns clone URL."""
    try:
        r = _github_request("GET", f"/repos/{username}/{REPO_NAME}")
        print(f"  Repo already exists: {r['html_url']}")
        return r["clone_url"]
    except RuntimeError:
        pass  # doesn't exist — create it

    r = _github_request("POST", "/user/repos", {
        "name": REPO_NAME,
        "description": "Demo repository for Pipeline Prophet — IBM DevDay Hackathon",
        "private": False,
        "auto_init": True,
    })
    print(f"  Created: {r['html_url']}")
    return r["clone_url"]


def push_demo_files(clone_url: str, username: str) -> None:
    """Push demo-repo/ contents to GitHub using git."""
    auth_url = clone_url.replace("https://", f"https://{GITHUB_TOKEN}@")

    # Configure git identity if not set
    subprocess.run(["git", "config", "--global", "user.email", "demo@pipelineprophet.dev"], check=False)
    subprocess.run(["git", "config", "--global", "user.name", "Pipeline Prophet"], check=False)

    tmp_dir = Path(__file__).parent.parent.parent / "_repo_push_tmp"
    tmp_dir.mkdir(exist_ok=True)

    print("  Cloning repo...")
    subprocess.run(["git", "clone", auth_url, str(tmp_dir)], check=True, capture_output=True)

    print("  Copying demo files...")
    import shutil
    for item in DEMO_REPO_DIR.iterdir():
        dest = tmp_dir / item.name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    print("  Committing and pushing...")
    subprocess.run(["git", "-C", str(tmp_dir), "add", "."], check=True, capture_output=True)
    result = subprocess.run(
        ["git", "-C", str(tmp_dir), "commit", "-m", "feat: initial Pipeline Prophet demo app"],
        capture_output=True, text=True
    )
    if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
        print("  Nothing to commit — files already up to date.")
    else:
        subprocess.run(["git", "-C", str(tmp_dir), "push"], check=True, capture_output=True)
        print("  Pushed successfully.")

    shutil.rmtree(tmp_dir, ignore_errors=True)


def create_webhook(username: str, webhook_url: str) -> None:
    """Register the Pipeline Prophet webhook on the repo."""
    # Check if webhook already exists
    try:
        hooks = _github_request("GET", f"/repos/{username}/{REPO_NAME}/hooks")
        for hook in hooks:
            if hook.get("config", {}).get("url", "").startswith(webhook_url.split("//")[-1].split("/")[0]):
                print(f"  Webhook already registered: {hook['config']['url']}")
                return
    except Exception:
        pass

    hook = _github_request("POST", f"/repos/{username}/{REPO_NAME}/hooks", {
        "name": "web",
        "active": True,
        "events": ["push", "pull_request"],
        "config": {
            "url": f"{webhook_url.rstrip('/')}/api/webhook",
            "content_type": "json",
            "secret": WEBHOOK_SECRET,
            "insecure_ssl": "0",
        }
    })
    print(f"  Webhook created: {hook['config']['url']}")
    print(f"  Webhook ID: {hook['id']}")


def main(webhook_url: str) -> None:
    if not GITHUB_TOKEN:
        print("ERROR: GITHUB_TOKEN not set in .env")
        sys.exit(1)

    print("\n=== Step 1: Authenticating ===")
    username = get_username()
    print(f"  Logged in as: {username}")

    print(f"\n=== Step 2: Creating repo '{REPO_NAME}' ===")
    clone_url = create_repo(username)

    print("\n=== Step 3: Pushing demo files ===")
    push_demo_files(clone_url, username)

    if webhook_url:
        print(f"\n=== Step 4: Registering webhook -> {webhook_url} ===")
        create_webhook(username, webhook_url)
    else:
        print("\n=== Step 4: Webhook (skipped — no --webhook-url provided) ===")
        print("  Run with --webhook-url https://your-ngrok-url to register the webhook.")
        print("  Or register manually at:")
        print(f"  https://github.com/{username}/{REPO_NAME}/settings/hooks")
        print(f"  Payload URL: <your-public-url>/api/webhook")
        print(f"  Secret: {WEBHOOK_SECRET}")

    print(f"\n=== Done ===")
    print(f"  Repo URL:  https://github.com/{username}/{REPO_NAME}")
    print(f"  Clone URL: {clone_url}")
    print(f"  Update REPO_ID in App.jsx and backend/app/main.py if needed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--webhook-url", default="", help="Public URL of your backend (e.g. ngrok URL)")
    args = parser.parse_args()
    main(args.webhook_url)
