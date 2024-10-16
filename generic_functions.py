import re

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

def update_commit_map(commit_map, sha_list, branch):
    """
    Update the commit_map with given SHAs and the branch they're in.
    """
    for sha in sha_list:
        commit_map[sha] = branch

def strip_jira_ticket(message):
    """
    Extract the Jira ticket key from the commit message.
    """
    jira_ticket = re.search(r'[A-Z]{2,}-\d+', message)
    return jira_ticket.group() if jira_ticket else None
