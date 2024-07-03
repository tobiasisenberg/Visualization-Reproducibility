#!/usr/bin/python3

import os,sys
import json
import time # if the calls are limited somehow
import datetime

def generateEntryForDoi(doi, apiKey = ''):
    # find the correct date string to be able to read and write the correct files
    current_date = datetime.datetime.now()
    current_year = current_date.year

    # values = cr.works(ids = doi)["message"]

    # with open("wiley-test.json", "w", encoding='utf-8') as f:
    #     json.dump(values, f, indent=4)

    dataItem = {}
#     dataItem["doi"] = values["DOI"].lower()
#     dataItem["authors"] = []
#     for author in values["author"]:
#         authorData = {}
#         authorData["family"] = author["family"]
#         authorData["given"] = author["given"]
#         if "ORCID" in author.keys(): authorData["orcid"] = author["ORCID"].split("/")[-1]
#         dataItem["authors"].append(authorData)
#     dataItem["title"] = values["title"][0]
#     dataItem["journal"] = values["container-title"][0].replace("&amp;", "&")
#     dataItem["publication_year"] = values["published"]["date-parts"][0][0]
#     if "volume " in values.keys(): dataItem["volume"] = values["volume"]
#     else: dataItem["volume"] = ""
#     if "journal-issue " in values.keys(): dataItem["number"] = values["journal-issue"]["issue"]
#     else: dataItem["number"] = ""
#     if "page" in values.keys():
#         dataItem["pages"] = values["page"].replace("-", "\u2013") #+ ":1\u2013"
#     else:
#         dataItem["pages"] = "e" + values["DOI"].lower().split("/")[1].split(".")[1] #+ ":1\u2013"
# #     if (values["volume"] == 'PP') or (values["issue"] == '99') or (values['content_type'] == 'Early Access Articles'):
# #         # FIXME: year is also only preliminary and needs to be updated
# #         dataItem["volume"] = ''
# #         dataItem["number"] = ''
# #         dataItem["pages"] = ''
# #         dataItem["publication_year"] = current_year + 1000 # because it has not been published yet, it has to be this year or later; but let's just add a bit to be able to distinguish things
#     dataItem["article_number"] = '' # for now IEEE TVCG does not use article numbers
#     dataItem["number_of_pages"] = -1 # int(values["end_page"]) - int(values["start_page"]) + 1
#     if ("\u2013" in dataItem["pages"]): dataItem["number_of_pages"] = int(dataItem["pages"].split("\u2013")[1]) - int(dataItem["pages"].split("\u2013")[0]) + 1
#     if "abstract" in values.keys(): dataItem["abstract"] = values["abstract"].replace("<jats:title>Abstract</jats:title><jats:p>", "").replace("</jats:p>", "")
#     else: dataItem["abstract"] = ""
    
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
    apiKey = config['apikey-wiley'] # this does not seem to be a metadata key, but one for text and data mining (TDM) from PDFs

    # API documentation: https://onlinelibrary.wiley.com/library-info/resources/text-and-datamining
    # Wiley really seems to re-direct people to the crossref API, including:
    # https://api.crossref.org/swagger-ui/
    # and the Python API I am already using:
    # https://www.crossref.org/blog/python-and-ruby-libraries-for-accessing-the-crossref-api/

    # doiList = '10.1111/cgf.14550 10.1111/cgf.14533 10.1111/cgf.14747 10.1111/cgf.14784 10.1111/cgf.14734 10.1111/cgf.14693 10.1111/cgf.14487 10.1111/cgf.14609 10.1111/cgf.14615 10.1111/cgf.14550 10.1111/cgf.14607 10.1111/cgf.14533 10.1111/cgf.14402 10.1111/cgf.14420 10.1111/cgf.14488 10.1111/cgf.13815 10.1111/cgf.13951 10.1111/cgf.14460 10.1111/cgf.142632 10.1111/cgf.14367 10.1111/cgf.14368 10.1111/cgf.142625 10.1111/cgf.142659 10.1111/cgf.142654 10.1111/cgf.13910 10.1111/cgf.14061 10.1111/cgf.13592 10.1111/cgf.13934 10.1111/cgf.13492 10.1111/cgf.13395 10.1111/cgf.13253 10.1111/cgf.12979 10.1111/cgf.12974 10.1111/cgf.12970 10.1111/cgf.12975 10.1111/cgf.12973 10.1111/cgf.12962'.lower().split(' ')
    doiList = '10.1111/cgf.14550'.lower().split(' ')

    print("This script is still incomplete (still need to figure out the API).")
    print("But the crossref script seems to work more or less for Wiley data.")
    print("Hunch: Is the Wiley API only for downloading the paper PDF?")
    print("But even the example from Wiley's TDM API does not work, not even with a correct key.")

    # load the existing database
    with open("extended paper data.json", "r", encoding='utf-8') as f:
        paperList = json.load(f)

    for doi in doiList:
        time.sleep(0.2)
        print("processing " + doi)

        if doi in paperList.keys():
            print("WARNING: DOI ALREADY IN DATA!!!!!!!!!!!!!!!")
            print("existing entry: " + str(paperList[doi]))

        dataItem = generateEntryForDoi(doi, apiKey)

        print("new entry: " + str(dataItem))

        # add the new data to the list (potentially overwriting what was there before)
        paperList[doi] = dataItem

    # # save the appended database
    # with open("extended paper data.json", "w", encoding='utf-8') as f:
    #     json.dump(paperList, f, indent=4)
    
# manualProcessing()