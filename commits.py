from flask import Flask, jsonify, request,render_template
from config import REDIS_CONFIG
import requests
from flask_cors import CORS
from JiraGraphQLAPI import JiraGraphQLAPI
import re
import json
import redis
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()



r = redis.Redis(
    host=REDIS_CONFIG['host'],
    port=REDIS_CONFIG['port'],
    db=REDIS_CONFIG['db']
)
# Initialize Flask application
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Load the repos.json globally at the start of the app
with open('static/repos.json') as f:
    repos_data = json.load(f)


github_token = os.getenv('GITHUB_TOKEN')
# GitHub API base URL
GITHUB_API_URL = os.getenv('GITHUB_API_URL')

def get_repo_object(team, repo_name):
    """
    Helper function to get the repo object based on the team and repo name.
    """
    if team in repos_data['teams']:
        team_repos = repos_data['teams'][team]
        if repo_name in team_repos:
            return team_repos[repo_name]
    return None

def extract_pr_number(commit_message):
    """
    Extracts the pull request number from the commit message if it exists.
    Matches both 'Merge pull request #113' and 'RAIL-2107 Fix (#8388)'.
    Returns None if no PR number is found.
    """
    match = re.search(r'pull request #(\d+)|\(#(\d+)\)', commit_message, re.IGNORECASE)
    if match:
        return match.group(1) or match.group(2)
    return None


def get_diff_commits(repo_owner, repo_name, branch_a, branch_b,repo_object):
    """
    Compare two branches and get the list of differing commits.
    """
    url = f"{GITHUB_API_URL}/repos/{repo_owner}/{repo_name}/compare/{branch_b}...{branch_a}"
    
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        commits = data['commits']
        if commits:
            commit_map = {}
    
            # Populate the commit_map with SHA and associate them with 'develop' branch
            for commit in commits:
                commit_map[commit['sha']] = repo_object['base_branch']

            track_pr(commit_map,repo_name,repo_owner,repo_object)

            commit_details = []
            for commit in commits:
                commit_message = commit['commit']['message'].splitlines()[0]
                pr_number = extract_pr_number(commit_message)
                print("PR_NUMBER : ",pr_number)
                
                if pr_number:
                    # If a PR number is present, fetch PR details using GitHub API
                    pr_details = get_pr_for_commit(repo_owner,repo_name,commit['sha'])
                    if pr_details:
                        commit_details.append({
                            "author": pr_details['user']['login'],  # PR author
                            "message": pr_details['title'] +" #("+pr_number+")",  # PR title
                            "url": pr_details['html_url'],  # PR URL
                            "date": pr_details['merged_at'],  # PR merge date
                            "state": validate_commit_message(pr_details['title']),  # PR state (open/closed/merged)
                            "jira_ticket": strip_jira_ticket(pr_details['title']),
                            "branch": commit_map[commit['sha']]  # Branch associated with the commit
                        })
            return commit_details
        else:
            return None
    else:
        raise Exception(f"Error {response.status_code}: Unable to fetch diff commits")
    
def get_pr_for_commit(repo_owner,repo_name,commit_sha):
    """Get the parent PR associated with a commit"""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits/{commit_sha}/pulls"
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

def track_pr(commit_map,repo_name,repo_owner,repo_object):
    """
    Track PR process across different branches: production, staging, and qat-release-branch.
    """
    # Step 1: Compare production and staging
    staging_sha_list = get_commit_diff_as_list( repo_owner, repo_name, repo_object['staging_branch'],repo_object['production_branch'])
    update_commit_map(commit_map, staging_sha_list,repo_object['staging_branch'])

    # Step 2: Compare staging and qat-release-branch
    qat_sha_list = get_commit_diff_as_list(repo_owner, repo_name, repo_object['release_branch'], repo_object['staging_branch'])
    update_commit_map(commit_map, qat_sha_list, repo_object['release_branch'])

    return commit_map

def get_commit_diff_as_list(repo_owner, repo_name, branch_a, branch_b):
    """
    Compare two branches and get the list of differing commits.
    """
    url = f"{GITHUB_API_URL}/repos/{repo_owner}/{repo_name}/compare/{branch_b}...{branch_a}"
    
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        comparison_data = response.json()
        return [commit['sha'] for commit in comparison_data['commits']]
    else:
        raise Exception(f"Error {response.status_code}: Unable to fetch diff commits")

def update_commit_map(commit_map, sha_list, branch):
    """
    Update the commit_map with given SHAs and the branch they're in.
    """
    for sha in sha_list:
        commit_map[sha] = branch
        
def create_pull_request(repo_owner, repo_name, branch_a, branch_b, token):
    """
    Create a pull request from branch_a to branch_b.
    """
    url = f"{GITHUB_API_URL}/repos/{repo_owner}/{repo_name}/pulls"
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    data = {
        "title": f"Merge {branch_a} into {branch_b}",
        "head": branch_a,
        "base": branch_b,
        "body": f"This PR merges the changes from {branch_a} into {branch_b}.",
        "maintainer_can_modify": True
    }
    
    response = requests.post(url, json=data, headers=headers)
    
    if response.status_code == 201:
        pr = response.json()
        return pr['html_url'], pr['number']
    else:
        raise Exception(f"Error {response.status_code}: Unable to create pull request")

def get_pr_commits(repo_owner, repo_name, pr_number, token):
    """
    Get the commits in the given pull request.
    """
    url = f"{GITHUB_API_URL}/repos/{repo_owner}/{repo_name}/pulls/{pr_number}/commits"
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        commits = response.json()
        commit_messages = [f"{commit['sha'][:7]}: {commit['commit']['message']}" for commit in commits]
        return commit_messages
    else:
        raise Exception(f"Error {response.status_code}: Unable to fetch PR commits")


@app.route('/')
def index():
    return render_template('front_commit.html')

@app.route('/commits', methods=['GET'])

def get_commits():
    """
    API endpoint to get the list of commits between two branches.
    """
    repo_owner = "cloudqwest"  # Replace with your GitHub username or organization
    repo_name = request.args.get('repo_name')
    team = request.args.get('team')
    repo_object = get_repo_object(team, repo_name)
    branch_a = repo_object['base_branch']                # Replace with the source branch name
    branch_b = repo_object['production_branch']                # Replace with the target branch name
    token = github_token          # Replace with your GitHub personal access token
    print("Fetching Commits for ",repo_name)

    if not all([repo_owner, repo_name, branch_a, branch_b, token]):
        return jsonify({"error": "Missing required parameters"}), 400
    
    
    redis_key = f"commits:{repo_owner}:{repo_name}:{branch_a}:{branch_b}"

    try:
        # Check if the result is already cached in Redis
        cached_commits = r.get(redis_key)
        if cached_commits:
            # Return the cached response if available
            print("Returning cached commits")
            return jsonify(json.loads(cached_commits)), 200
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # If not in cache, fetch the commits from the actual source
        commits = get_diff_commits(repo_owner, repo_name, branch_a, branch_b,repo_object)
        data_to_return = {
            "commits": commits,
            "timeStamp": current_time  # Add the current timestamp
        }
        
        if commits:
            # Store the result in Redis for future requests
            r.set(redis_key, json.dumps(data_to_return))  # Cache for 1 hour (3600 seconds)
            print("Commits are cached")
            return jsonify(data_to_return), 200
        else:
            return jsonify({"message": f"No new commits from {branch_a} to {branch_b}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/refresh', methods=['POST'])
def refresh_repo():
    repo_owner = "cloudqwest"  # Replace with your GitHub username or organization
    repo_name = request.args.get('repo_name')
    team = request.args.get('team')
    repo_object = get_repo_object(team, repo_name)
    branch_a = repo_object['base_branch']                # Replace with the source branch name
    branch_b = repo_object['production_branch']                # Replace with the target branch name
    token = github_token          # Replace with your GitHub personal access token

    print("Updating Commits for ",repo_name)

    if not all([repo_owner, repo_name, branch_a, branch_b, token]):
        return jsonify({"error": "Missing required parameters"}), 400
    
    
    redis_key = f"commits:{repo_owner}:{repo_name}:{branch_a}:{branch_b}"
    try:
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # If not in cache, fetch the commits from the actual source
        commits = get_diff_commits(repo_owner, repo_name, branch_a, branch_b,repo_object)
        data_to_return = {
            "commits": commits,
            "timeStamp": current_time  # Add the current timestamp
        }
        
        if commits:
            # Store the result in Redis for future requests
            r.set(redis_key, json.dumps(data_to_return), ex=3600)  # Cache for 1 hour (3600 seconds)
            print("Commits are cached")
            return jsonify(data_to_return), 200
        else:
            return jsonify({"message": f"No new commits from {branch_a} to {branch_b}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def validate_commit_message(message):
    """
    Validate the commit message.
    """
    jira_ticket = strip_jira_ticket(message)
    array = [False,False]
    print("TICKET_ID : " ,jira_ticket)
    jira = JiraGraphQLAPI("your_username", "your_api_token","https://fourkites.atlassian.net")
    if jira_ticket==None:
        return array
    return jira.check_jira_ticket(jira_ticket,array)
    #     array[0]=True
    
    
def strip_jira_ticket(message):
    """
    Extract the Jira ticket key from the commit message.
    """
    jira_ticket = re.search(r'[A-Z]{2,}-\d+', message)
    return jira_ticket.group() if jira_ticket else None

if __name__ == '__main__':
    app.run(debug=True)