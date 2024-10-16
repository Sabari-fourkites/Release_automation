import github_helper
import generic_functions as gf

def get_diff_prs(repo_owner, repo_name, branch_a, branch_b,repo_object,github_token,github_url):
    data = github_helper.commits_diff_branch(repo_owner, repo_name, branch_a, branch_b,github_token,github_url)
    commits = data['commits']
    if commits:
        commit_map = {}
        # Populate the commit_map with SHA and associate them with 'develop' branch
        for commit in commits:
            commit_map[commit['sha']] = repo_object['base_branch']

        commit_map = track_pr(commit_map,repo_name,repo_owner,repo_object,github_token,github_url)

        commit_details = []
        for commit in commits:
            commit_message = commit['commit']['message'].splitlines()[0]
            pr_number = gf.extract_pr_number(commit_message)
            print("PR_NUMBER : ",pr_number)
            
            if pr_number:
                # If a PR number is present, fetch PR details using GitHub API
                pr_details = github_helper.pr_for_commit(repo_owner,repo_name,commit['sha'],github_token,github_url)
                if pr_details:
                    commit_details.append({
                        "author": pr_details['user']['login'],  # PR author
                        "message": pr_details['title'] +" #("+pr_number+")",  # PR title
                        "url": pr_details['html_url'],  # PR URL
                        "date": pr_details['merged_at'],  # PR merge date
                        "state": gf.validate_commit_message(pr_details['title']),  # PR state (open/closed/merged)
                        "jira_ticket": gf.strip_jira_ticket(pr_details['title']),
                        "branch": commit_map[commit['sha']]  # Branch associated with the commit
                    })
        return commit_details
    else:
        return None

def track_pr(commit_map,repo_name,repo_owner,repo_object,github_token,github_url):
    """
    Track PR process across different branches: production, staging, and qat-release-branch.
    """
    # Step 1: Compare production and staging
    staging_sha_list = get_commit_diff_as_list( repo_owner, repo_name, repo_object['staging_branch'],repo_object['production_branch'],github_token,github_url)
    gf.update_commit_map(commit_map, staging_sha_list,repo_object['staging_branch'])

    # Step 2: Compare staging and qat-release-branch
    qat_sha_list = get_commit_diff_as_list(repo_owner, repo_name, repo_object['release_branch'], repo_object['staging_branch'],github_token,github_url)
    gf.update_commit_map(commit_map, qat_sha_list, repo_object['release_branch'])

    return commit_map

def get_commit_diff_as_list(repo_owner, repo_name, branch_a, branch_b,github_token,github_url):
    """
    Compare two branches and get the list of differing commits.
    """
    comparison_data = github_helper.commits_diff_branch(repo_owner, repo_name, branch_a, branch_b,github_token,github_url)
    return [commit['sha'] for commit in comparison_data['commits']]