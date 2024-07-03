#!/usr/bin/python3

import os,sys
import json
import re
import time # if the calls are limited somehow
import datetime
from habanero import Crossref

def generateEntryForDoi(doi, apiKey = ''):
    # find the correct date string to be able to read and write the correct files
    current_date = datetime.datetime.now()
    current_year = current_date.year

    cr = Crossref()
    values = cr.works(ids = doi)["message"]

    # with open("crossref-test.json", "w", encoding='utf-8') as f:
    #     json.dump(values, f, indent=4)

    dataItem = {}
    dataItem["doi"] = values["DOI"].lower()
    dataItem["authors"] = []
    for author in values["author"]:
        authorData = {}
        authorData["family"] = author["family"].replace("\u2010", "-")
        authorData["given"] = author["given"].replace("\u2010", "-")
        if "ORCID" in author.keys(): authorData["orcid"] = author["ORCID"].split("/")[-1]
        dataItem["authors"].append(authorData)
    dataItem["title"] = values["title"][0]
    dataItem["journal"] = values["container-title"][0].replace("&amp;", "&")
    dataItem["journal"] = re.sub(pattern=r"SIGGRAPH Asia \d\d\d\d Conference Papers", repl=r"ACM SIGGRAPH Asia Conference Papers", string=dataItem["journal"])
    dataItem["journal"] = re.sub(pattern=r"ACM SIGGRAPH \d\d\d\d Conference Proceedings", repl=r"ACM SIGGRAPH Conference Papers", string=dataItem["journal"])
    dataItem["publication_year"] = values["published"]["date-parts"][0][0]
    if "volume" in values.keys(): dataItem["volume"] = values["volume"]
    else: dataItem["volume"] = ""
    if "journal-issue" in values.keys(): dataItem["number"] = values["journal-issue"]["issue"]
    else: dataItem["number"] = ""
    if "page" in values.keys():
        dataItem["pages"] = values["page"].replace("-", "\u2013") #+ ":1\u2013"
    else:
        dataItem["pages"] = "e" + values["DOI"].lower().split("/")[1].split(".")[1] # this is a hack for the newer CGF articles
    
    # account for proceedings
    if values["type"] == "proceedings-article":
        dataItem["volume"] = '0'
        dataItem["number"] = '0'
    
    if dataItem["pages"][0] == 'e' and dataItem["journal"][0:12] == "ACM SIGGRAPH": # Siggraph does not report proper page numbers in Crossref
        dataItem["pages"] = ''

    # if we do not have volume/number yet for articles, it is still in press so mark it as such
    if (dataItem["volume"] == ''):
        dataItem["volume"] = ''
        dataItem["number"] = ''
        dataItem["pages"] = ''
        dataItem["publication_year"] = current_year + 1000 # because it has not been published yet, it has to be this year or later; but let's just add a bit to be able to distinguish things

    if dataItem["journal"] == "ACM Transactions on Graphics" or dataItem["journal"] == "ACM SIGGRAPH Asia Conference Papers" or dataItem["journal"] == "ACM SIGGRAPH Conference Papers":
        dataItem["article_number"] = '0' # for now ACM apparently does not report its article numbers via crossref, so we put (the incorrect) 0
    else:
        dataItem["article_number"] = '' # I don't know if Crossref would know about article numbers anyway, and other journals don't seem to use them yet
    
    dataItem["number_of_pages"] = -1 # int(values["end_page"]) - int(values["start_page"]) + 1
    if ("\u2013" in dataItem["pages"]): dataItem["number_of_pages"] = int(dataItem["pages"].split("\u2013")[1]) - int(dataItem["pages"].split("\u2013")[0]) + 1
    if "abstract" in values.keys():
        dataItem["abstract"] = values["abstract"]
        # take out the formatting xml
        dataItem["abstract"] = dataItem["abstract"].replace("<jats:title>Abstract</jats:title><jats:p>", "").replace("</jats:p>", "")
        dataItem["abstract"] = dataItem["abstract"].replace("<jats:italic>", "").replace("</jats:italic>", "")
        dataItem["abstract"] = dataItem["abstract"].replace("<jats:sc>", "").replace("</jats:sc>", "")
        dataItem["abstract"] = dataItem["abstract"].replace("<jats:sub>", "").replace("</jats:sub>", "")
        dataItem["abstract"] = dataItem["abstract"].replace("<jats:bold>", "").replace("</jats:bold>", "")
        dataItem["abstract"] = dataItem["abstract"].replace("<jats:sup>", "").replace("</jats:sup>", "")
        dataItem["abstract"] = dataItem["abstract"].replace("<jats:p>", " ")
        dataItem["abstract"] = dataItem["abstract"].replace("\u2010", "-")
        dataItem["abstract"] = dataItem["abstract"].strip()
    else: dataItem["abstract"] = ""
    return dataItem

def manualProcessing():
    #####################################
    # change to directory of the script
    #####################################
    pathOfTheScript = os.path.dirname(sys.argv[0])
    os.chdir(pathOfTheScript)

    # API documentation: https://github.com/sckott/habanero

    # doiList = '10.1111/cgf.14550 10.1111/cgf.14533 10.1111/cgf.14747 10.1111/cgf.14784 10.1111/cgf.14734 10.1111/cgf.14693 10.1111/cgf.14487 10.1111/cgf.14609 10.1111/cgf.14615 10.1111/cgf.14550 10.1111/cgf.14607 10.1111/cgf.14533 10.1111/cgf.14402 10.1111/cgf.14420 10.1111/cgf.14488 10.1111/cgf.13815 10.1111/cgf.13951 10.1111/cgf.14460 10.1111/cgf.142632 10.1111/cgf.14367 10.1111/cgf.14368 10.1111/cgf.142625 10.1111/cgf.142659 10.1111/cgf.142654 10.1111/cgf.13910 10.1111/cgf.14061 10.1111/cgf.13592 10.1111/cgf.13934 10.1111/cgf.13492 10.1111/cgf.13395 10.1111/cgf.13253 10.1111/cgf.12979 10.1111/cgf.12974 10.1111/cgf.12970 10.1111/cgf.12975 10.1111/cgf.12973 10.1111/cgf.12962'.lower().split(' ')
    # doiList = '10.1016/j.cag.2024.01.001 10.1016/j.cag.2023.08.012 10.1016/j.cag.2023.08.009 10.1016/j.cag.2023.08.014 10.1016/j.cag.2023.07.034 10.1016/j.cag.2023.06.013 10.1016/j.cag.2023.05.025 10.1016/j.cag.2023.07.035 10.1016/j.cag.2023.08.008 10.1016/j.cag.2023.06.023 10.1016/j.cag.2023.07.001 10.1016/j.cag.2023.07.021 10.1016/j.cag.2023.07.028 10.1016/j.cag.2023.05.006 10.1016/j.cag.2023.06.031 10.1016/j.cag.2023.06.014 10.1016/j.cag.2023.06.012 10.1016/j.cag.2023.06.017 10.1016/j.cag.2023.06.015 10.1016/j.cag.2023.04.007 10.1016/j.cag.2022.10.008 10.1016/j.cag.2022.09.003 10.1016/j.cag.2022.08.003 10.1016/j.cag.2022.07.018 10.1016/j.cag.2022.07.020 10.1016/j.cag.2022.07.011 10.1016/j.cag.2022.07.004 10.1016/j.cag.2022.07.015 10.1016/j.cag.2022.06.008 10.1016/j.cag.2022.07.005 10.1016/j.simpa.2022.100367 10.1016/j.cag.2022.06.007 10.1016/j.cag.2022.06.001 10.1016/j.cag.2022.05.009 10.1016/j.cag.2021.10.017 10.1016/j.cag.2021.11.005 10.1016/j.cag.2021.10.021 10.1016/j.cag.2021.07.010 10.1016/j.cag.2021.06.010 10.1016/j.cag.2021.09.005 10.1016/j.cag.2021.09.013 10.1016/j.cag.2021.07.001 10.1016/j.cag.2021.07.022 10.1016/j.cad.2021.103069 10.1016/j.cag.2021.07.018 10.1016/j.cag.2021.06.015 10.1016/j.cag.2021.02.003 10.1016/j.cag.2021.01.014 10.1016/j.cag.2020.09.007 10.1016/j.cag.2020.09.001 10.1016/j.cag.2020.08.008 10.1016/j.cag.2020.07.007 10.1016/j.cag.2020.08.001 10.1016/j.cag.2020.06.001 10.1016/j.cag.2020.05.029 10.1016/j.cag.2020.05.028 10.1016/j.cag.2020.05.024 10.1016/j.gvc.2020.200013 10.1016/j.cag.2019.05.024 10.1016/j.cag.2018.05.015 10.1016/j.cag.2018.05.016 10.1016/j.cag.2018.05.014 10.1016/j.cad.2017.05.014 10.1016/j.cag.2017.05.006 10.1016/j.cad.2017.05.004 10.1016/j.cag.2016.05.015 10.1016/j.cag.2016.05.017 10.1016/j.cag.2016.05.009 10.1016/j.cag.2016.05.020 10.1016/j.cad.2016.05.001 10.1016/j.cad.2016.05.010'.lower().split(' ')
    # doiList = '10.1016/j.cag.2023.08.012'.lower().split(' ')
    doiList = '10.1145/3592145'.lower().split(' ')

    # load the existing database
    with open("extended paper data.json", "r", encoding='utf-8') as f:
        paperList = json.load(f)

    for doi in doiList:
        time.sleep(0.2)
        print("processing " + doi)

        if doi in paperList.keys(): print("WARNING: DOI ALREADY IN DATA!!!!!!!!!!!!!!!")

        dataItem = generateEntryForDoi(doi)

        # print(dataItem)

        # add the new data to the list (potentially overwriting what was there before)
        paperList[doi] = dataItem

    # save the appended database
    with open("extended paper data.json", "w", encoding='utf-8') as f:
        json.dump(paperList, f, indent=4)

# manualProcessing()