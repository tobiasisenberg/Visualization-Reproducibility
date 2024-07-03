#!/usr/bin/python3

import os,sys
from xploreapi import XPLORE
import json
import time # max 10 calls per second, 200 per day
import datetime

def generateEntryForDoi(doi, apiKey = ''):
    # find the correct date string to be able to read and write the correct files
    current_date = datetime.datetime.now()
    current_year = current_date.year

    query = XPLORE(apiKey)
    query.dataType('JSON')
    query.maximumResults(2)
    query.doi(doi)
    dataText = query.callAPI()

    # with open("ieee-test.txt", "w", encoding='utf-8') as f:
    #     f.write(dataText)
    #     f.close()

    # make sure that we actually got data
    if 'IEEE <i>Xplore</i> is temporarily unavailable' in dataText: return {}

    data = json.loads(dataText)

    if (len(data['articles']) != 1): print("We did not received exactly one data item in return, but " + str(len(data['articles'])))

    values = data['articles'][0]

    # with open("ieee-test.json", "w", encoding='utf-8') as f:
    #     json.dump(values, f, indent=4)

    dataItem = {}
    dataItem["doi"] = values["doi"].lower()
    dataItem["authors"] = []
    for author in values["authors"]["authors"]:
        authorData = {}
        authorStringList = author['full_name'].split(' ')
        authorElementCount = len(authorStringList)
        authorElementSplit = authorElementCount - 1
        if " Jr." in author['full_name']: authorElementSplit -= 1
        authorData["family"] = ' '.join(authorStringList[authorElementSplit:])
        authorData["given"] = ' '.join(authorStringList[:authorElementSplit])
        dataItem["authors"].append(authorData)
    dataItem["title"] = values["title"]
    dataItem["journal"] = values["publication_title"]
    dataItem["publication_year"] = int(values["publication_year"])
    dataItem["volume"] = values["volume"]
    dataItem["number"] = values["issue"]
    dataItem["pages"] = values["start_page"] + '\u2013' + values["end_page"]
    if (values["volume"] == 'PP') or (values["issue"] == '99') or (values['content_type'] == 'Early Access Articles'):
        dataItem["volume"] = ''
        dataItem["number"] = ''
        dataItem["pages"] = ''
        dataItem["publication_year"] = current_year + 1000 # because it has not been published yet, it has to be this year or later; but let's just add a bit to be able to distinguish things
    dataItem["article_number"] = '' # for now IEEE TVCG does not use article numbers
    dataItem["number_of_pages"] = int(values["end_page"]) - int(values["start_page"]) + 1
    dataItem["abstract"] = values["abstract"]
    return dataItem

def manualProcessing():
    #####################################
    # change to directory of the script
    #####################################
    pathOfTheScript = os.path.dirname(sys.argv[0])
    os.chdir(pathOfTheScript)

    #####################################
    # API access
    #####################################
    with open("api-keys.json", "r", encoding='utf-8') as f:
        config = json.load(f)
        f.close()
    apiKey = config['apikey-ieee']
    # API documentation: https://developer.ieee.org/Python3_Software_Development_Kit
    # example web query https://ieeexploreapi.ieee.org/api/v1/search/articles?parameter&apikey=xxxxxxxxxxxxxxxxxxxxxxxx&publication_title=IEEE%20Transactions%20on%20Visualization%20and%20Computer%20Graphics&is_number=9663056&max_records=200&sort_field=article_number

    # doiList = '10.1109/tvcg.2023.3341990 10.1109/tvcg.2023.3341453 10.1109/tvcg.2023.3337642 10.1109/tvcg.2023.3345340 10.1109/tvcg.2023.3302308 10.1109/tvcg.2022.3229017 10.1109/tvcg.2023.3251648 10.1109/tvcg.2023.3261981 10.1109/tvcg.2023.3250166 10.1109/tvcg.2023.3238008 10.1109/tvcg.2023.3235277 10.1109/tvcg.2022.3232591'.lower().split(' ')
    # doiList = '10.1109/tvcg.2024.3355884 10.1109/tvcg.2023.3341990 10.1109/tvcg.2023.3341453 10.1109/tvcg.2023.3337642 10.1109/tvcg.2023.3345340 10.1109/tvcg.2023.3302308 10.1109/tvcg.2022.3229017 10.1109/tvcg.2023.3251648 10.1109/tvcg.2023.3261981 10.1109/tvcg.2023.3250166 10.1109/tvcg.2023.3238008 10.1109/tvcg.2023.3235277 10.1109/tvcg.2022.3232591'.lower().split(' ')
    doiList = '10.1109/tvcg.2024.3355884'.lower().split(' ')

    # load the existing database
    with open("extended paper data.json", "r", encoding='utf-8') as f:
        paperList = json.load(f)

    for doi in doiList:
        time.sleep(0.2)
        print("processing " + doi)

        dataItem = generateEntryForDoi(doi, apiKey)

        # print(dataItem)

        if doi in paperList.keys(): print("WARNING: DOI ALREADY IN DATA!!!!!!!!!!!!!!!")

        # add the new data to the list (potentially overwriting what was there before)
        paperList[doi] = dataItem

    # save the appended database
    with open("extended paper data.json", "w", encoding='utf-8') as f:
        json.dump(paperList, f, indent=4)

# manualProcessing()