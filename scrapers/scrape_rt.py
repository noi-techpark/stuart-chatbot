# ------------------------------------------------------------------------------
# Scrape all relevant transaction bodies for all tickets in the given queue
# from a Request Tracker ticketing system.
#
# Note:
#   - location and credentials are read from 'scrape_rt.json',
#   - works incrementally (skips previously downloaded transaction bodies),
#   - removes lines starting with '>' from the bodies,
#   - considers only transactions of type 'Ticket created', 'Correspondence
#     added' or 'Comments added'
#   - bodies are stored in '../data_rt/ticket-X-Y.txt', where X is the
#     ticket ID and Y is the transaction ID
# ------------------------------------------------------------------------------


import urllib.request
import json
import time
import sys
import os
import re


# --- configuration ---

try:
    conf = open("secrets_rt.json", "r")
    rt_parameters = json.load(conf)
    conf.close()
except FileNotFoundError:
    print("ERROR: scrape_rt: cannot read credentials file.")
    sys.exit(1)

base_url = rt_parameters.get("base_url")
auth_parameters = rt_parameters.get("auth_parameters")
queue_name = rt_parameters.get("queue_name")
out_dir = "../data_rt"


# --- functions ---

def get_ticket_ids():
    response = urllib.request.urlopen("%s/search/ticket?query=Queue='%s'&orderby=+Created&%s"
                                      % (base_url, queue_name, auth_parameters))
    if response.getcode() != 200:
        print("WARNING: get_ticket_ids() got response %s." % response.getcode())
        return []
    data = response.read()
    data_text = data.decode('utf-8').split("\n")
    ret = []
    # we're interested in lines starting with a ticket ID followed by a colon
    pattern = re.compile(r"^(\d+):")
    for line in data_text:
        match = pattern.match(line)
        if match:
            ret.append(match.group(1))
    return ret


def get_tx_for_ticket(ticket_id):
    response = urllib.request.urlopen("%s/ticket/%d/history/?%s" % (base_url, int(ticket_id), auth_parameters))
    if response.getcode() != 200:
        print("WARNING: get_tx_for_ticket(%d): got response %s." % (int(ticket_id), response.getcode()))
        return []
    data = response.read()
    text = data.decode('utf-8').split("\n")
    ret = []
    # we're interested in lines starting with a ticket ID followed by certain text patterns
    pattern = re.compile(r"^(\d+):\s+(Ticket created|Correspondence added|Comments added)")
    for line in text:
        match = pattern.match(line)
        if match:
            ret.append(match.group(1))
    return ret


def get_ticket(ticket_id, tx_id):
    url = "%s/ticket/%d/history/id/%d?%s" % (base_url, int(ticket_id), int(tx_id), auth_parameters)
    response = urllib.request.urlopen(url)
    if response.getcode() != 200:
        print("WARNING: get_ticket(%d, %d) got response %s." % (int(ticket_id), int(tx_id), response.getcode()))
        return ""
    data = response.read()
    text = data.decode('utf-8').split("\n")
    ret = ["%s/ticket/%d/history/id/%d" % (base_url, int(ticket_id), int(tx_id))]
    # filter out lines starting with ">"
    pattern = re.compile(r"^\s*>")
    for line in text:
        if not pattern.match(line):
            ret.append(line)
    return "\n".join(ret)


# --- main program ---

def main():
    t0 = time.time()

    old_count = 0
    new_count = 0
    nil_count = 0
    for ticket_id in get_ticket_ids():
        for tx_id in get_tx_for_ticket(ticket_id):
            file_name = "%s/ticket-%d-%d.txt" % (out_dir, int(ticket_id), int(tx_id))
            if os.path.exists(file_name):
                old_count += 1
                continue
            text = get_ticket(ticket_id, tx_id)
            if text == "":
                nil_count += 1
                continue
            file = open(file_name, 'w')
            file.write(text)
            file.close()
            new_count += 1

    t1 = time.time()

    print("%d ticket bodies (%d old, %d new, %d nil) scraped in %.3f seconds" %
          (old_count + new_count + nil_count, old_count, new_count, nil_count, t1 - t0))


main()
