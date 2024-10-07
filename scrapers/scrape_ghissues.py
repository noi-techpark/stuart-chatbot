# --------------------------------------------------------------------------------------------------
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
#   - summary file '../log_ghissues/00_summary_scraped_repo_and_issues.txt' contains stats of scraped issues,
#     also used to compare if issue is updated
# --------------------------------------------------------------------------------------------------


import urllib.request
import json
import time
import sys
import os
import re
import textwrap
import logging

# --- logging ---

logging.basicConfig(
    level=logging.DEBUG,  
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'  
)
logger = logging.getLogger(__name__)

# --- configuration ---

try:
    conf = open("secrets_gh.json", "r")
    gh_param = json.load(conf)
    conf.close()
except FileNotFoundError:
    logger.error("scrape_ghissues: cannot read credentials file")
    sys.exit(1)

token = gh_param.get("github_token")
project_owner = gh_param.get("project_owner")

base_url = "https://api.github.com"
query_params = "?per_page=100" # per_page for number of entries
dev = False # param for development to break while loop

config_ghissues = "config_ghissues.txt"
config_ghissues_comments = "config_ghissues_comments.txt"
format_attributes = ["Body"]
out_dir = "../data_ghissues"
log_dir = "../log_ghissues"
summary_file_name = f"{log_dir}/00_summary_scraped_repo_and_issues.txt"
request_count = 0

# --- functions ---

def load_config(config_file):
    with open(config_file, 'r') as file:
        return [line.strip() for line in file]
    
def make_github_request(url, function_name):
    global request_count
    req = urllib.request.Request(url)
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    with urllib.request.urlopen(req) as response:
        if response.getcode() != 200:
            logger.warning("%s got response %s.", function_name, response.getcode())
            return []
        data = response.read()
        header_link = response.headers.get("Link")
        request_count += 1
        if request_count % 1 == 0:
            logger.debug("Executing: %s", url)
    json_data = json.loads(data.decode('utf-8'))
    return json_data, header_link

def extract_next_link(header):
    links = header.split(',')
    for link in links:
        parts = link.split('; ')
        if 'rel="next"' in parts[1]:
            link = parts[0].strip('<> ')
            break
    return link

def get_repositories(): 
    json_data, header = make_github_request(f"{base_url}/orgs/{project_owner}/repos{query_params}", "get_repositories()")
    list_repos = [item['name'] for item in json_data]
    while header and "next" in header:
        link = extract_next_link(header)
        json_data, header = make_github_request(link, "get_repositories()")
        list_repos.extend([item['name'] for item in json_data])
        if dev: break
    return list_repos

def get_repo_issues(repo):
    json_data, header  = make_github_request(f"{base_url}/repos/{project_owner}/{repo}/issues{query_params}", "get_repo_issues()")
    list_issue_numbers = [item['number'] for item in json_data]
    while header and "next" in header:
        link = extract_next_link(header)
        json_data, header = make_github_request(link, "get_repo_issues()")
        list_issue_numbers.extend([item['number'] for item in json_data])
        if dev: break
    return list_issue_numbers

def get_issue(repo, issue_number):
    json_data, header  = make_github_request(f"{base_url}/repos/{project_owner}/{repo}/issues/{issue_number}", "get_issue()")
    return json_data

def get_comments(repo, issue_number):
    json_data, header  = make_github_request(f"{base_url}/repos/{project_owner}/{repo}/issues/{issue_number}/comments{query_params}", "get_comments()")
    while header and "next" in header:
        link = extract_next_link(header)
        more_json_data, header = make_github_request(link, "get_comments()")
        json_data.append(more_json_data)
        if dev: break
    return json_data

def extract_and_format(attributes, extracted_data, data):
    for attr in attributes:
        try:
            if "." in attr:
                extracted_data[attr] = extract_nested(data, attr)
            else:
                extracted_data[attr] = data[attr]
        except (KeyError, TypeError) as err:
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
        if not value:
            value = "None"
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

def check_updated(records, repo, json_issues, last_update):
    issue_number = json_issues["number"]
    comment_count = json_issues["comments"]
    updated_at = json_issues["updated_at"]
    for record in records:
        if record["Repository"] == repo and record["Issue number"] == issue_number:
            if record["Comment count"] == comment_count and last_update > updated_at :
                return True
    return False
    
def read_previous_content(content):
    if not content:
        return "", 0
    lines = content.split("\n")
    headers = lines[0].split(", ")
    records = []
    for line in lines[1:-2]:
        values = line.split(", ")
        values[1] = int(values[1])  # Issue number
        values[2] = int(values[2])  # Comment count
        records.append(dict(zip(headers, values)))
    last_update = lines[-1].split(": ", 1)[1]
    return records, last_update


# --- main program ---

def main():
    t0 = time.time()
    issue_attributes = load_config(config_ghissues)
    comment_attributes = load_config(config_ghissues_comments)

    updated_issues = 0
    total_issues = 0
    
    try:
        summary_file = open(summary_file_name, 'r')
        previous_content = summary_file.read()
        summary_file.close()
        logger.info("previous summary file found and read")
    except FileNotFoundError:
        logger.info("previous summary file not found")
        previous_content = ""
    records, last_update = read_previous_content(previous_content)
    temp_file_name = f"{log_dir}/01_temp_summary_file.txt"
    temp_summary_file = open(temp_file_name, 'w')
    temp_summary_file.write(f"Repository, Issue number, Comment count\n")

    list_repos = get_repositories()

    for repo in list_repos:
        list_issue_numbers = get_repo_issues(repo)
        
        for issue_number in list_issue_numbers:
            json_issues = get_issue(repo, issue_number)
            updated = check_updated(records, repo, json_issues, last_update)
            
            comment_count = json_issues["comments"]
            
            if not records or not updated: 
                text = extract_and_format(issue_attributes, {}, json_issues)

                json_comments = get_comments(repo, issue_number)
                comment_count = len(json_comments)
                extracted_data = {}
                comment_count = 0
                for comment in json_comments:
                    comment_count += 1
                    extracted_data["comment"] = comment_count
                    text += extract_and_format(comment_attributes, extracted_data, comment)
                    
                file_name = "%s/%s-issue-%d.txt" % (out_dir, repo, int(issue_number))
                file = open(file_name, 'w')
                file.write(text)
                file.close()
                updated_issues += 1
            
            total_issues += 1                
            temp_summary_file.write(f"{repo}, {issue_number}, {comment_count}\n")
            temp_summary_file.flush()
            
    t1 = time.time()
    temp_summary_file.write(f"Total number of issues: {total_issues}\n")
    local_time = time.localtime()
    formatted_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", local_time)
    temp_summary_file.write(f"Updated on: {formatted_time}")
    temp_summary_file.close()
    
    os.replace(temp_file_name, summary_file_name)

    print("%d issues (%d old, %d updated) scraped in %.3f seconds" %
          (total_issues, total_issues-updated_issues, updated_issues, t1 - t0))

main()
