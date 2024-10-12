import requests
import json
import base64
import os


class JiraGraphQLAPI:
    def __init__(self, username, api_token, jira_url):
        self.jira_url = "https://fourkites.atlassian.net"
        self.username = os.getenv("JIRA_USERNAME")
        self.api_token = os.getenv("JIRA_API_TOKEN")

    def get_ticket_id(self, jira_ticket):
        # Request only the "id" field to minimize response data
        url = f"{self.jira_url}/rest/api/2/issue/{jira_ticket}?fields=id"
        
        # Construct Authorization header
        auth_header = "Basic " + base64.b64encode(f"{self.username}:{self.api_token}".encode("utf-8")).decode("utf-8")
        headers = {
            "Authorization": auth_header,
            "Content-Type": "application/json"
        }
        
        # Send GET request to fetch only the issue ID
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            issue_data = response.json()
            # Extract the issue ID
            issue_id = issue_data.get('id', 'ID not found')
            return issue_id
        else:
            return f"Failed to fetch ticket ID. Status code: {response.status_code}"

    def get_dev_details(self, jira_ticket):
        # Define the GraphQL query to fetch development details
        ticket_id = self.get_ticket_id(jira_ticket)
        graphql_query = {
            "operationName": "DevDetailsDialog",
            "query": """
           query DevDetailsDialog ($issueId: ID!) {
                developmentInformation(issueId: $issueId) {
                    details {
                        instanceTypes {
                            id
                            name
                            type
                            typeName
                            isSingleInstance
                            baseUrl
                            devStatusErrorMessages
                            repository {
                                id
                                name
                                avatarUrl
                                description
                                url
                                pullRequests {
                                    id
                                    url
                                    name
                                    branchName
                                    branchUrl
                                    destinationBranchName
                                    destinationBranchUrl
                                    lastUpdate
                                    status
                                }
                            }
                        }
                    }
                }
            }""",
            "variables": {
                "issueId": ticket_id
            }
        }

        # Convert to JSON string
        graphql_query_json = json.dumps(graphql_query)


        # Construct Authorization header
        auth_header = "Basic " + base64.b64encode(f"{self.username}:{self.api_token}".encode("utf-8")).decode("utf-8")
        headers = {
            "Authorization": auth_header,
            "Content-Type": "application/json"
        }

        # Send the request to the Jira GraphQL endpoint
        graphql_url = f"{self.jira_url}/jsw2/graphql?operation=DevDetailsDialog"
        response = requests.post(graphql_url, data=graphql_query_json, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Failed to fetch development details for {ticket_id}. Status code: {response.status_code}"}
        
    def check_jira_ticket(self, jira_ticket,array):
        # Construct the URL for getting ticket details
        response = self.get_dev_details(jira_ticket)

        # Ensure the response contains the necessary data
        if 'data' not in response or 'developmentInformation' not in response['data']:
            return array  # or handle the error appropriately
        flag1 = True
        # Extract instance types
        instance_types = response['data']['developmentInformation']['details']['instanceTypes']

        # Iterate over each instance type
        for instance in instance_types:
            repositories = instance['repository']
            for repo in repositories:
                prs = repo['pullRequests']
                for pr in prs:
                    if pr['status'] != 'MERGED' and pr['status'] != 'DECLINED':
                        flag1 = False
        
        array[0]=flag1
        flag= False
        for instance in instance_types:
            repositories = instance['repository']
            for repo in repositories:
                if repo['name'] == 'cloudqwest/test-automation':
                    flag=True
                    prs = repo['pullRequests']
                    for pr in prs:
                        if pr['status'] != 'MERGED'  and pr['status'] != 'DECLINED':
                            return array
        array[1]=flag
        return array
        # return True  # Return True if all PRs are merged


# Usage example
# username = "your_jira_username"
# api_token = "your_jira_api_token"
# jira_url = "https://fourkites.atlassian.net"

# jira = JiraGraphQLAPI(username, api_token, jira_url)
# jira_ticket="TRACNG-8736"
# print("TICKET : "+jira_ticket)
# ticket_id=jira.get_ticket_id(jira_ticket)
# print("TICKET_ID : "+ticket_id)
# dev_details = jira.get_dev_details(ticket_id)
# print(json.dumps(dev_details, indent=2))
