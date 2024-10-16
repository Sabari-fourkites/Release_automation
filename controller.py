import service
import json
import redis
import os
import generic_functions as gf

from flask import Flask, jsonify, request,render_template
from config import REDIS_CONFIG
from dotenv import load_dotenv
from flask_cors import CORS

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
github_url = os.getenv('GITHUB_API_URL')

def get_repo_object(team, repo_name):
    """
    Helper function to get the repo object based on the team and repo name.
    """
    if team in repos_data['teams']:
        team_repos = repos_data['teams'][team]
        if repo_name in team_repos:
            return team_repos[repo_name]
    return None

def process_data(repo_owner, repo_name, team,cache=True):
    """
    API endpoint to get the list of commits between two branches.
    """
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
        if cache and cached_commits:
            # Return the cached response if available
            print("Returning cached commits")
            return jsonify(json.loads(cached_commits)), 200

        # If not in cache, fetch the commits from the actual source
        commits = service.get_diff_prs(repo_owner, repo_name, branch_a, branch_b,repo_object,github_token,github_url)
        data_to_return = {
            "commits": commits,
            "timeStamp": gf.get_current_time()  # Add the current timestamp
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
    
    return process_data(repo_owner, repo_name, team,True)
    
@app.route('/refresh', methods=['POST'])
def refresh_repo():
    """
    API endpoint to refresh the cache for a specific repository.
    """
    repo_owner = "cloudqwest"  # Replace with your GitHub username or organization
    repo_name = request.args.get('repo_name')
    team = request.args.get('team')
    
    return process_data(repo_owner, repo_name, team,False)
    
if __name__ == '__main__':
    app.run(debug=True)