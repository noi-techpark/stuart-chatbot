# ------------------------------------------------------------------------------
# Scrape all relevant issues in repositories of the given Github account.
#
# Note:
#   - github issue layer:
#     1. all project repositories
#     2. all repository issues
#     3. specific issue
#     4. all issue comments
#   - github token can be added in 'secrets_gh.json', 
#     to make more api requests per hour, otherwise leave blank and request as public user.
#   - attributes to extract from issues are configured in 'config_ghissues.txt'.
#   - attributes to extract from comments are configured in 'config_ghissues_comments.txt'.
#   - scraped texts are stored in '../data_ghissues/X-issue-Y.txt',
#     where X is the repository and Y is the issue ID
# ------------------------------------------------------------------------------


import urllib.request
import json
import time
import sys
import os
import re
import textwrap


# --- configuration ---

try:
    conf = open("secrets_gh.json", "r")
    gh_param = json.load(conf)
    conf.close()
except FileNotFoundError:
    print("ERROR: scrape_ghissues: cannot read credentials file.")
    sys.exit(1)

token = gh_param.get("github_token")
config_ghissues = "config_ghissues.txt"
config_ghissues_comments = "config_ghissues_comments.txt"
format_attributes = ["Body"]
base_url = "https://api.github.com"
project_owner = "noi-techpark"
out_dir = "../data_ghissues"
test_param = "?per_page=1&page=1" # per_page for number of entries, page for number of pages

# --- functions ---

def load_config(config_file):
    with open(config_file, 'r') as file:
        return [line.strip() for line in file]
    
def make_github_request(url):
    req = urllib.request.Request(f"{url}{test_param}")
    if token:
        req.add_header('Authorization', f'Bearer {token}')
        print("github token used")
    return req

def get_repositories():
    req = make_github_request(f"{base_url}/orgs/{project_owner}/repos")
    with urllib.request.urlopen(req) as response:
        if response.getcode() != 200:
            print("WARNING: get_repository() got response %s." % response.getcode())
            return []
        data = response.read()
    json_data = json.loads(data.decode('utf-8'))
    return json_data

def get_repo_issues(repo):
    req = make_github_request(f"{base_url}/repos/{project_owner}/{repo}/issues")
    with urllib.request.urlopen(req) as response:
        if response.getcode() != 200:
            print("WARNING: get_repo_issues() got response %s." % response.getcode())
            return []
        data = response.read()
    json_data = json.loads(data.decode('utf-8'))
    return json_data

def get_issue(repo, issue_number):
    req = make_github_request(f"{base_url}/repos/{project_owner}/{repo}/issues/{issue_number}")
    with urllib.request.urlopen(req) as response:
        if response.getcode() != 200:
            print("WARNING: get_issue() got response %s." % response.getcode())
            return []
        data = response.read()
    json_data = json.loads(data.decode('utf-8'))
    return json_data

def get_comments(repo, issue_number):
    req = make_github_request(f"{base_url}/repos/{project_owner}/{repo}/issues/{issue_number}/comments")
    with urllib.request.urlopen(req) as response:
        if response.getcode() != 200:
            print("WARNING: get_comments() got response %s." % response.getcode())
            return []
        data = response.read()
    json_data = json.loads(data.decode('utf-8'))
    return json_data

def extract_and_format(attributes, extracted_data, data):
    for attr in attributes:
        try:
            if "." in attr:
                extracted_data[attr] = extract_nested(data, attr)
            else:
                extracted_data[attr] = data[attr]
        except (KeyError, TypeError):
            extracted_data[attr] = None
    return format_issue(extracted_data)

def extract_nested(value, attr):
    keys = attr.split('.') 
    for key in keys:
        if isinstance(value, list): 
            value = [item[key] for item in value]
        else: 
            value = value[key]
    return value

def format_issue(data):
    pretty_text = ""
    for key, value in data.items():
        formatted_key = to_sentence_case(key)
        if formatted_key in format_attributes:
            pretty_text += f"{formatted_key}:\n"
            pretty_text += textwrap.indent(value, '    ')
            pretty_text += f"\n\n"
        else:
            pretty_text += f"{formatted_key}: {value}\n"
    return pretty_text
    
def to_sentence_case(key):
    words = re.split(r'[_.]', key) # Split by _ and .
    if len(words) == 1:
        return words[0].capitalize()
    return words[0].capitalize() + ' ' + ' '.join(word.lower() for word in words[1:])



# --- main program ---

def main():
    t0 = time.time()
    issue_attributes = load_config(config_ghissues)
    comment_attributes = load_config(config_ghissues_comments)

    # old_count = 0
    # new_count = 0
    # nil_count = 0
    
    json_repo = get_repositories()
    list_repos = [item['name'] for item in json_repo]

    for repo in list_repos:
        json_repo_issues = get_repo_issues(repo)
        list_issue_numbers = [item['number'] for item in json_repo_issues]
        
        for issue_number in list_issue_numbers:
            json_issues = get_issue(repo, issue_number)
            text = extract_and_format(issue_attributes, {}, json_issues)

            json_comments = get_comments(repo, issue_number)
            extracted_data = {}
            for count, comment in enumerate(json_comments):
                extracted_data["comment"] = count+1
                text += extract_and_format(comment_attributes, extracted_data, comment)
            
            file_name = "%s/%s-issue-%d.txt" % (out_dir, repo, int(issue_number))
            file = open(file_name, 'w')
            file.write(text)
            file.close()

    t1 = time.time()

    # print("%d ticket bodies (%d old, %d new, %d nil) scraped in %.3f seconds" %
    #       (old_count + new_count + nil_count, old_count, new_count, nil_count, t1 - t0))


main()
