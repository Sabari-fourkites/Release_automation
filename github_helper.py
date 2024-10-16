import requests


def commits_diff_branch(repo_owner, repo_name, branch_a, branch_b,github_token,github_url):
    """
    Compare two branches and get the list of differing commits.
    """
    url = f"{github_url}/repos/{repo_owner}/{repo_name}/compare/{branch_b}...{branch_a}"
    
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Error {response.status_code}: Unable to fetch diff commits")

def pr_for_commit(repo_owner,repo_name,commit_sha,github_token,github_url):
    
    """Get the parent PR associated with a commit"""

    url = f"{github_url}/repos/{repo_owner}/{repo_name}/commits/{commit_sha}/pulls"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.groot-preview+json"  # Special preview header for PRs linked to commits
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        pulls = response.json()
        if pulls:
            # Returning the first PR (there can be multiple if commits are cherry-picked)
            return pulls[0]
        else:
            return None
    else:
        print(f"Failed to fetch PR for commit {commit_sha}: {response.status_code}")
        return None