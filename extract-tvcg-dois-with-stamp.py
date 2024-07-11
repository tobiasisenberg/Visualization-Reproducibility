#!/usr/bin/python3

#####################################
# This script simply extracts a list of TVCG papers
# with GRSI stamp from the stored data and outputs it to
# ./tvcg-dois-with-stamp.csv
#####################################

import os,sys
import csv
import json

#####################################
# change to directory of the script
#####################################
pathOfTheScript = os.path.dirname(sys.argv[0])
if pathOfTheScript != "": os.chdir(pathOfTheScript)

paperListExtended = []

# first check if we have all extra data updated, and if not try to update it
with open("publication_data/extended_paper_data.json", "r", encoding='utf-8') as f:
    paperListExtended = json.load(f)
    f.close()

tvcgPapersWithStamp = []

for doi in paperListExtended.keys():
    entry = paperListExtended[doi]
    doi2 = entry["doi"].lower()
    title = entry["title"]

    if "10.1109/tvcg." in doi2:
        paper = {}
        paper["doi"] = doi2
        paper["title"] = title
        tvcgPapersWithStamp.append(paper)

with open("tvcg-dois-with-stamp.csv", 'w', encoding='utf-8', newline='') as myfile:
    dict_writer = csv.DictWriter(myfile, tvcgPapersWithStamp[0].keys())
    dict_writer.writeheader()
    dict_writer.writerows(tvcgPapersWithStamp)