import json
import os
import sys
import urllib.error
import urllib.request

# Configuration
REPO_OWNER = "DmitrL-dev"
REPO_NAME = "1cai-public" 
GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"

def get_json(url, token):
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Python-CI-Checker"
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                return json.loads(response.read().decode())
            else:
                print(f"Error fetching {url}: HTTP {response.status}")
                return None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def get_workflow_runs(token):
    return get_json(f"{GITHUB_API_URL}/actions/runs?per_page=5", token)

def get_jobs(run_id, token):
    return get_json(f"{GITHUB_API_URL}/actions/runs/{run_id}/jobs", token)

def main():
    token = os.getenv("GH_TOKEN")
    if not token:
        if len(sys.argv) > 1:
            token = sys.argv[1]
        else:
            print("Error: GH_TOKEN required.")
            sys.exit(1)

    print(f"Checking CI status for {REPO_OWNER}/{REPO_NAME}...")
    
    runs = get_workflow_runs(token)
    if not runs or "workflow_runs" not in runs:
        print("No workflow runs found.")
        sys.exit(1)
        
    print(f"\nAnalyzing Failures:")
    print("=" * 60)
    
    # Process only the most recent runs (top 3)
    for run in runs["workflow_runs"][:3]:
        # Show all recent runs, not just failures, to see progress
        status_icon = "X" if run["conclusion"] == "failure" else ("v" if run["conclusion"] == "success" else "?")
        print(f"[{status_icon}] Run: {run['name']} (ID: {run['id']})")
        print(f"    Commit: {run['head_sha'][:7]} - {run['head_commit']['message'].splitlines()[0] if run.get('head_commit') else 'N/A'}")
        print(f"    Status: {run['status']}, Conclusion: {run['conclusion']}")
        print(f"    Branch: {run['head_branch']}")
        print(f"    URL: {run['html_url']}")
        
        if run["conclusion"] == "failure" or run["status"] == "in_progress":
            jobs = get_jobs(run["id"], token)
            if jobs and "jobs" in jobs:
                for job in jobs["jobs"]:
                    if job["conclusion"] == "failure":
                        print(f"    -> JOB FAILED: {job['name']} (ID: {job['id']})")
                        for step in job["steps"]:
                            if step["conclusion"] == "failure":
                                print(f"       -> STEP FAILED: {step['name']}")
            print("-" * 60)
        else:
            print("-" * 60)

if __name__ == "__main__":
    main()
