#!/usr/bin/python3

import os,sys
import json
import re
import requests
import datetime

from acmdownload import PageParser
from acmdownload import CitationParser

def generateEntryForDoi(doi, apiKey = ''):
    # find the correct date string to be able to read and write the correct files
    current_date = datetime.datetime.now()
    current_year = current_date.year

    # first part copied from the acmdownloads script
    r = requests.get('https://dl.acm.org/doi/' + doi)
    page_parser = PageParser()

    page_parser.feed(r.text)

    doc = {'references': page_parser.refs}

    if page_parser.title:
        doc['title'] = page_parser.title

    if page_parser.cbu:
        r = requests.get('https://dl.acm.org' + page_parser.cbu)
        citation_parser = CitationParser()
        citation_parser.feed(r.text)
        doc['citedby'] = citation_parser.links
    else:
        doc['citedby'] = []

    r = requests.post('https://dl.acm.org/action/exportCiteProcCitation', data={
        'dois': doi,
        'targetFile': 'custom-bibtex',
        'format': 'bibTex'
    })
    
    # rest my own processing
    text = r.text

    # with open('acm-test.txt', 'w', encoding='utf-8') as f:
    #     f.write(text)
    
    if "ACM Error: IP blocked" in text: print("WARNING: We got IP-blocked by ACM, try again later or use VPN.")

    data = json.loads(text)
    values = list(data["items"][0].values())[0]

    dataItem = {}
    dataItem["doi"] = values["DOI"].lower()
    dataItem["authors"] = []
    for author in values["author"]: dataItem["authors"].append(author)
    dataItem["title"] = values["title"]
    dataItem["journal"] = values["container-title"].replace("ACM Trans. Graph.", "ACM Transactions on Graphics")
    dataItem["journal"] = re.sub(pattern=r"SIGGRAPH Asia \d\d\d\d Conference Papers", repl=r"ACM SIGGRAPH Asia Conference Papers", string=dataItem["journal"])
    dataItem["journal"] = re.sub(pattern=r"ACM SIGGRAPH \d\d\d\d Conference Proceedings", repl=r"ACM SIGGRAPH Conference Papers", string=dataItem["journal"])
    if "source" in values.keys():
        dataItem["publication_year"] = int(values["source"].split(" ")[1])
    elif "issued" in values.keys():
        dataItem["publication_year"] = values["issued"]["date-parts"][0][0]
    if "volume" in values.keys():
        dataItem["volume"] = values["volume"]
    else:
        dataItem["volume"] = "0" # for conference entries
    if "issue" in values.keys():
        dataItem["number"] = values["issue"]
    else:
        dataItem["number"] = "0" # for conference entries
    dataItem["pages"] = values["page"]
    dataItem["article_number"] = values["collection-number"]
    dataItem["number_of_pages"] = int(values["number-of-pages"])
    dataItem["abstract"] = values["abstract"]

    if ( (not(':' in dataItem["pages"])) and (len(dataItem["article_number"]) > 0)):
        newPages = dataItem["article_number"] + ":" + dataItem["pages"].replace("\u2013", "\u2013" + dataItem["article_number"] + ":")
        # print("replacing " + dataItem["pages"] + " with " + newPages)
        dataItem["pages"] = newPages
    
    return(dataItem)

def manualProcessing():
    #####################################
    # change to directory of the script
    #####################################
    pathOfTheScript = os.path.dirname(sys.argv[0])
    os.chdir(pathOfTheScript)

    #####################################
    # query ACM
    #####################################
    doi = '10.1145/2956233'

    print("processing " + doi)

    dataItem = generateEntryForDoi(doi)

    # print(dataItem)

    # load the existing database
    with open("extended paper data.json", "r", encoding='utf-8') as f:
        paperList = json.load(f)

    if doi in paperList.keys(): print("WARNING: DOI ALREADY IN DATA!!!!!!!!!!!!!!!")

    # add the new data to the list (potentially overwriting what was there before)
    paperList[doi] = dataItem

    # save the appended database
    with open("extended paper data.json", "w", encoding='utf-8') as f:
        json.dump(paperList, f, indent=4)

# manualProcessing()