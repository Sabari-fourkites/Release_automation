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
    
    try:
        # Attempt to send the GET request
        response = requests.get(url, headers=headers)

        # If successful (status code 200), return the JSON content
        if response.status_code == 200:
            return response.json()
        else:
            # If not successful, raise a general exception with a custom message
            raise Exception(f"Error {response.status_code}: Unable to fetch diff commits")

    except Exception as e:
        # Handle all exceptions and print a custom error message
        print(f"An error occurred: {e}")
        return e

def pr_for_commit(repo_owner,repo_name,commit_sha,github_token,github_url):
    
    """Get the parent PR associated with a commit"""

    url = f"{github_url}/repos/{repo_owner}/{repo_name}/commits/{commit_sha}/pulls"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.groot-preview+json"  # Special preview header for PRs linked to commits
    }

    try:
        # Attempt to send the GET request
        response = requests.get(url, headers=headers)
        
        # Check for successful response
        if response.status_code == 200:
            pulls = response.json()
            if pulls:
                # Returning the first PR (there can be multiple if commits are cherry-picked)
                return pulls[0]
            else:
                return None
        else:
            raise Exception(f"Error {response.status_code}: Failed to fetch PR for commit {commit_sha}")


    except Exception as e:
        # Handle all exceptions and print a custom error message
        print(f"An error occurred: {e}")
        return e  # Return the exception object