#!/usr/bin/python3

import os,sys
import json
import time # if the calls are limited somehow
import datetime
from elsapy.elsclient import ElsClient
from elsapy.elsdoc import FullDoc

def generateEntryForDoi(doi, apiKey = ''):
    # find the correct date string to be able to read and write the correct files
    current_date = datetime.datetime.now()
    current_year = current_date.year

    client = ElsClient(apiKey)
    scp_doc = FullDoc(doi = doi)
    if scp_doc.read(client):
        values = scp_doc.data["coredata"]

        # with open("elsevier-test.json", "w", encoding='utf-8') as f:
        #     json.dump(scp_doc.data["coredata"], f, indent=4)

        # with open("elsevier-test2.json", "w", encoding='utf-8') as f:
        #     json.dump(scp_doc.data, f, indent=4)

        dataItem = {}
        dataItem["doi"] = values["prism:doi"].lower()

        dataItem["authors"] = []
        for author in values["dc:creator"]:
            authorData = {}
            authorData["family"] = author["$"].split(", ")[0]
            authorData["given"] = author["$"].split(", ")[1]
        #     if "ORCID" in author.keys(): authorData["orcid"] = author["ORCID"].split("/")[-1]
            dataItem["authors"].append(authorData)

        dataItem["title"] = values["dc:title"].strip()
        dataItem["journal"] = values["prism:publicationName"].replace("&amp;", "&")
        dataItem["publication_year"] = int(values["prism:coverDate"].split("-")[0])

        if "prism:volume" in values.keys(): dataItem["volume"] = values["prism:volume"]
        else: dataItem["volume"] = ""

        if "prism:number" in values.keys(): dataItem["number"] = values["prism:number"]
        else: dataItem["number"] = "" # usually Elsevier does not have numbers anymore

        if "prism:pageRange" in values.keys():
            dataItem["pages"] = values["prism:pageRange"].replace("-", "\u2013")
            if ("prism:startingPage" in values.keys()) and ("prism:endingPage" in values.keys()):
                dataItem["number_of_pages"] = int(values["prism:endingPage"]) - int(values["prism:startingPage"]) + 1
            else:
                dataItem["number_of_pages"] = -1
        elif ("prism:startingPage" in values.keys()) and ("prism:endingPage" in values.keys()):
            dataItem["pages"] = values["prism:startingPage"] + "\u2013" + values["prism:endingPage"]
            dataItem["number_of_pages"] = int(values["prism:endingPage"]) - int(values["prism:startingPage"]) + 1
        else:
            dataItem["pages"] = ""
            dataItem["number_of_pages"] = -1

        if "articleNumber" in values.keys():
            dataItem["article_number"] = values['articleNumber']
        else:
            dataItem["article_number"] = '' # for now Elsevier does not use article numbers

        if (dataItem["volume"] == '') or ('Available online' in values['prism:coverDisplayDate']): # then it is not fully published yet
            dataItem["volume"] = ''
            dataItem["number"] = ''
            dataItem["pages"] = ''
            dataItem["publication_year"] = current_year + 1000 # because it has not been published yet, it has to be this year or later; but let's just add a bit to be able to distinguish things

        if "abstract" in values.keys(): dataItem["abstract"] = values["abstract"].replace("<jats:title>Abstract</jats:title><jats:p>", "").replace("</jats:p>", "")
        else: dataItem["abstract"] = values["dc:description"].strip()
        while '  ' in dataItem["abstract"]: dataItem["abstract"] = dataItem["abstract"].replace('  ', ' ')

        return(dataItem)
    
    else:
        print ("Reading of document from API failed.")
        return None

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
    apiKey = config['apikey-elsevier']
    # API documentation: https://dev.elsevier.com/ and https://github.com/ElsevierDev/elsapy

    # doiList = '10.1016/j.cag.2024.01.001 10.1016/j.cag.2023.08.012 10.1016/j.cag.2023.08.009 10.1016/j.cag.2023.08.014 10.1016/j.cag.2023.07.034 10.1016/j.cag.2023.06.013 10.1016/j.cag.2023.05.025 10.1016/j.cag.2023.07.035 10.1016/j.cag.2023.08.008 10.1016/j.cag.2023.06.023 10.1016/j.cag.2023.07.001 10.1016/j.cag.2023.07.021 10.1016/j.cag.2023.07.028 10.1016/j.cag.2023.05.006 10.1016/j.cag.2023.06.031 10.1016/j.cag.2023.06.014 10.1016/j.cag.2023.06.012 10.1016/j.cag.2023.06.017 10.1016/j.cag.2023.06.015 10.1016/j.cag.2023.04.007 10.1016/j.cag.2022.10.008 10.1016/j.cag.2022.09.003 10.1016/j.cag.2022.08.003 10.1016/j.cag.2022.07.018 10.1016/j.cag.2022.07.020 10.1016/j.cag.2022.07.011 10.1016/j.cag.2022.07.004 10.1016/j.cag.2022.07.015 10.1016/j.cag.2022.06.008 10.1016/j.cag.2022.07.005 10.1016/j.simpa.2022.100367 10.1016/j.cag.2022.06.007 10.1016/j.cag.2022.06.001 10.1016/j.cag.2022.05.009 10.1016/j.cag.2021.10.017 10.1016/j.cag.2021.11.005 10.1016/j.cag.2021.10.021 10.1016/j.cag.2021.07.010 10.1016/j.cag.2021.06.010 10.1016/j.cag.2021.09.005 10.1016/j.cag.2021.09.013 10.1016/j.cag.2021.07.001 10.1016/j.cag.2021.07.022 10.1016/j.cad.2021.103069 10.1016/j.cag.2021.07.018 10.1016/j.cag.2021.06.015 10.1016/j.cag.2021.02.003 10.1016/j.cag.2021.01.014 10.1016/j.cag.2020.09.007 10.1016/j.cag.2020.09.001 10.1016/j.cag.2020.08.008 10.1016/j.cag.2020.07.007 10.1016/j.cag.2020.08.001 10.1016/j.cag.2020.06.001 10.1016/j.cag.2020.05.029 10.1016/j.cag.2020.05.028 10.1016/j.cag.2020.05.024 10.1016/j.gvc.2020.200013 10.1016/j.cag.2019.05.024 10.1016/j.cag.2018.05.015 10.1016/j.cag.2018.05.016 10.1016/j.cag.2018.05.014 10.1016/j.cad.2017.05.014 10.1016/j.cag.2017.05.006 10.1016/j.cad.2017.05.004 10.1016/j.cag.2016.05.015 10.1016/j.cag.2016.05.017 10.1016/j.cag.2016.05.009 10.1016/j.cag.2016.05.020 10.1016/j.cad.2016.05.001 10.1016/j.cad.2016.05.010'.lower().split(' ')
    doiList = '10.1016/j.cag.2022.09.003'.lower().split(' ')

    # print("This script is still incomplete (still need to figure out the API).\nThe crossref does not provide complete Elsevier data.")

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