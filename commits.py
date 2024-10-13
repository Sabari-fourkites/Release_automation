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
load_dotenv()



r = redis.Redis(
    host=REDIS_CONFIG['host'],
    port=REDIS_CONFIG['port'],
    db=REDIS_CONFIG['db']
)
# Initialize Flask application
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

github_token = os.getenv('GITHUB_TOKEN')
# GitHub API base URL
GITHUB_API_URL = os.getenv('GITHUB_API_URL')

def get_diff_commits(repo_owner, repo_name, branch_a, branch_b, token):
    """
    Compare two branches and get the list of differing commits.
    """
    url = f"{GITHUB_API_URL}/repos/{repo_owner}/{repo_name}/compare/{branch_b}...{branch_a}"
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        commits = data['commits']
        if commits:
            commit_details = [
                {
                    "sha": commit['sha'],
                    "author": commit['commit']['author']['name'],
                    "message": commit['commit']['message'],
                    "url": commit['html_url'],
                    "date": commit['commit']['author']['date'],
                    "state": validate_commit_message(commit['commit']['message']),
                    "jira_ticket": strip_jira_ticket(commit['commit']['message'])
                }
                for commit in commits
            ]
            return commit_details
        else:
            return None
    else:
        raise Exception(f"Error {response.status_code}: Unable to fetch diff commits")


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
    branch_a = "develop"                # Replace with the source branch name
    branch_b = "staging"                # Replace with the target branch name
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
            return jsonify({"commits": json.loads(cached_commits)}), 200
        
        # If not in cache, fetch the commits from the actual source
        commits = get_diff_commits(repo_owner, repo_name, branch_a, branch_b, token)
        
        if commits:
            # Store the result in Redis for future requests
            r.set(redis_key, json.dumps(commits), ex=3600)  # Cache for 1 hour (3600 seconds)
            print("Commits are cached")
            return jsonify({"commits": commits}), 200
        else:
            return jsonify({"message": f"No new commits from {branch_a} to {branch_b}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/clear-cache', methods=['POST'])
def clear_cache():
    try:
        r.flushdb()  # Clears all keys in the Redis database
        print("Redis cache cleared!")
        return jsonify({"message": "Redis cache cleared!"}), 200
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