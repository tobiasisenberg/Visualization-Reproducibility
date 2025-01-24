#!/usr/bin/python3

from urllib.request import urlopen
from bs4 import BeautifulSoup
import re
import os,sys
import csv
import datetime
import json
import pandas as pd
import altair as alt
import time # to be able to wait if the calls are limited somehow
from colorsys import rgb_to_hls, hls_to_rgb
from math import nan
import math
import glob
import shutil

# settings of how to do things and what extra stuff to do
useLocalDataOnly = True # FIXME: should be True for submission
exportVisualizations = True
doNameChecking = False
doAbstractCheckingForKeywords = False
doVerifyCountryInformation = True
doPrintTVCGInPressDetails = False
doExportNumbersForPaper = True
doCopyPlotsAccordingToFugureNumbers = True
downloadAcmFromCrossref = True # if True, then use the Crossref API to get ACM metadata, otherwise the acmdownload tool; FIXME: should be True for submission

# other configuration
visPadding = 0 # the padding in pixels to be applied to the exported visualizations, set to 0 for use in paper, otherwise 5 is good
visPaddingBottomExtra = 1 # some extra padding on the bottom due to font parts being below the baseline
makeMainPieChartsComparable = True # if the main paie charts should use a single color scale such that each country always has the same color
graphOutputSubdirectury = "graphs/"
paperFiguresOutputSubdirectury = "paper_figures/"
dataOutputSubdirectury = "publication_data/"
paperNumbersOutputFile = "paper/numbersFromScript.tex"
paperNumbersOutputString = ""
paperKeywordPapersOutputFile = "paper/keywordPapersFromScript.tex"
paperKeywordPapersOutputString = ""
numberOfAuhorHistogramBins = 11
countryPieChartThreshold = 2.5 # in percent (1--100)
neutralGray = "#a9a9a9"
paperNumbersOutputString += "\\newcommand{\\GrsiCountryPieChartThreshold}{" + str(countryPieChartThreshold) + "}\n"
myLabelLimit = 500 # this is a weird issue: technically a value of 0 should mean no limit, but sometimes it literally means a limit of 0; so a sufficiently large number is needed here to avoid label cropping, 500 should work
topLimitAuthorPlots = 1100 # to adjust all the author count plots in a similar way

#####################################
# change to directory of the script
#####################################
pathOfTheScript = os.path.dirname(sys.argv[0])
if pathOfTheScript != "": os.chdir(pathOfTheScript)

#####################################
# create some output directories if they do not exist yet
#####################################
if (graphOutputSubdirectury != "") and not (os.path.isdir(graphOutputSubdirectury)):
    os.mkdir(graphOutputSubdirectury) 
if (doCopyPlotsAccordingToFugureNumbers) and (paperFiguresOutputSubdirectury != "") and not (os.path.isdir(paperFiguresOutputSubdirectury)):
    os.mkdir(paperFiguresOutputSubdirectury) 
if (dataOutputSubdirectury != "") and not (os.path.isdir(dataOutputSubdirectury)):
    os.mkdir(dataOutputSubdirectury) 

#####################################
# pre-load some data to avoid loading it multiple times
#####################################
vegaPalletData = {}
with open('palettes.js', 'r') as file:
    for line in file:
        if ':' in line:
            lineData = line.split(":")
            label = lineData[0].strip()
            colorDataString = lineData[1].replace("'", "").replace(",", "").strip()
            colorDataArray = ["#" + colorDataString[i:i+6] for i in range(0, len(colorDataString), 6)]
            vegaPalletData[label] = colorDataArray

#####################################
# find the correct date string to be able to read and write the correct files (this will be the default, need to replace it with the old data potentially)
#####################################
current_date = datetime.datetime.now()
grsiMetaData = {}
current_year = datetime.datetime.now().year
current_month = datetime.datetime.now().month
current_day = datetime.datetime.now().day
grsiMetaData["data_download_year"] = current_year
grsiMetaData["data_download_month"] = current_month
grsiMetaData["data_download_day"] = current_day
formatted_date = f"{current_year}{current_month:02d}{current_day:02d}"

#####################################
# now the main script, starting with some functions
#####################################
def hex_to_rgb(hex_color):
    return [int(hex_color[x:x+2],16) for x in [1, 3, 5]]

def rgb_to_hex(r,g,b):
    return "#%02x%02x%02x" % (r,g,b)

def adjust_color_lightness(r, g, b, factor):
    h, l, s = rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    l = max(min(l * factor, 1.0), 0.0)
    r, g, b = hls_to_rgb(h, l, s)
    return [int(r * 255), int(g * 255), int(b * 255)]

def lighten_color(r, g, b, factor=0.1):
    return adjust_color_lightness(r, g, b, 1 + factor)

def darken_color(r, g, b, factor=0.1):
    return adjust_color_lightness(r, g, b, 1 - factor)

def numberExtension(number):
    numberString = str(number)
    lastChar = numberString[-1]
    if (lastChar == '1'): return 'st'
    if (lastChar == '2'): return 'nd'
    if (lastChar == '3'): return 'rd'
    return "th"

def intToRoman(num):
    # storing Roman values of digits from 0-9 when placed at different places
    m = ["", "M", "MM", "MMM"]
    c = ["", "C", "CC", "CCC", "CD", "D",
         "DC", "DCC", "DCCC", "CM"]
    x = ["", "X", "XX", "XXX", "XL", "L",
         "LX", "LXX", "LXXX", "XC"]
    i = ["", "I", "II", "III", "IV", "V",
         "VI", "VII", "VIII", "IX"]
 
    # converting to Roman
    thousands = m[num // 1000]
    hundreds = c[(num % 1000) // 100]
    tens = x[(num % 100) // 10]
    ones = i[num % 10]
    ans = (thousands + hundreds + tens + ones)
 
    return ans

def unmarkPapers(paperList, labels = ["is_vis", "type"], targets = [False, None]):
    for label, target in zip(labels, targets):
        if target == None:
            for paper in paperList: 
                if label in paper.keys():
                    del paper[label]
        else:
            for paper in paperList: paper[label] = target

def markPapersByDoi(paperList, doiList, label = "is_vis", type = ""):
    for paper in paperList:
        if (paper["doi"] in doiList):
            paper[label] = True
            if len(type) > 0:
                paper["type"] = type

def markVisPapersByKeywords(paperList):
    for paper in paperList:
        # general keywords
        oldStatus = paper["is_vis"]

        if ("visualization" in paper["title"].lower()): paper["is_vis"] = True
        if ("visualisation" in paper["title"].lower()): paper["is_vis"] = True
        if ("visualizing" in paper["title"].lower()): paper["is_vis"] = True
        if ("visualising" in paper["title"].lower()): paper["is_vis"] = True
        if ( ("visual" in paper["title"].lower()) and ("analytics" in paper["title"].lower()) ): paper["is_vis"] = True
        if ( ("visual" in paper["title"].lower()) and ("analysis" in paper["title"].lower()) ): paper["is_vis"] = True
        if ("visual representation" in paper["title"].lower()): paper["is_vis"] = True
        if ("data exploration" in paper["title"].lower()): paper["is_vis"] = True
        if ("visual exploration" in paper["title"].lower()): paper["is_vis"] = True
        if ("graph drawing" in paper["title"].lower()): paper["is_vis"] = True
        if ("parallel coordinates" in paper["title"].lower()): paper["is_vis"] = True
        if ("scatterplot" in paper["title"].lower()): paper["is_vis"] = True
        if ("choropleth" in paper["title"].lower()): paper["is_vis"] = True
        if ("cartogram" in paper["title"].lower()): paper["is_vis"] = True
        if ("star glyph" in paper["title"].lower()): paper["is_vis"] = True
        if ("glyph design" in paper["title"].lower()): paper["is_vis"] = True
        if ("line graph" in paper["title"].lower()): paper["is_vis"] = True
        if ("streamgraph" in paper["title"].lower()): paper["is_vis"] = True
        if ("focus+context" in paper["title"].lower()): paper["is_vis"] = True
        # if ("topology" in paper["title"].lower()): paper["is_vis"] = True # not good: some graphics papers also captured
        if ("t-sne" in paper["title"].lower()): paper["is_vis"] = True
        if ("high-dimensional data" in paper["title"].lower()): paper["is_vis"] = True

        # assign the right type
        if (paper["is_vis"] == True) and (oldStatus == False): paper["type"] = "keyword"
        oldStatus = paper["is_vis"]

        # manual selections of specific papers for which we know more
        if ("10.1109/tvcg.2022.3214821" in paper["doi"]): paper["is_vis"] = True # visualization author keyword
        if ("10.1109/tvcg.2021.3101418" in paper["doi"]): paper["is_vis"] = True # visualization author keyword
        #if ("10.1109/tvcg.2023.3237768" in paper["doi"]): paper["is_vis"] = True # visual analysis author keyword, but automatically found by keyword search
        if ("10.1109/tvcg.2021.3067820" in paper["doi"]): paper["is_vis"] = True # visualization in the abstract
        if ("10.1109/tvcg.2020.2966702" in paper["doi"]): paper["is_vis"] = True # is on flattening of 3D surfaces from data
        if ("10.1016/j.cag.2024.01.001" in paper["doi"]): paper["is_vis"] = True # visualization in the abstract
        if ("10.1016/j.cag.2023.06.023" in paper["doi"]): paper["is_vis"] = True # talks about molecular channel datasets
        if ("10.1145/3528223.3530102" in paper["doi"]): paper["is_vis"] = True # talks about simulation and visualization of stellar atmospheres
        if ("10.1111/cgf.14784" in paper["doi"]): paper["is_vis"] = True # talks about topology, graphs, and scalar fields
        if ("10.1111/cgf.13910" in paper["doi"]): paper["is_vis"] = True # talks about point clouds and topology
        if ("10.1109/tvcg.2024.3491504" in paper["doi"]): paper["is_vis"] = True # data visualization author keyword
        if ("10.1109/tvcg.2024.3513275" in paper["doi"]): paper["is_vis"] = True # visualization author keyword

        if ("10.1109/tvcg.2024.3514858" in paper["doi"]): paper["is_vis"] = True # will be presented at VIS 2025

        # assign the right type
        if (paper["is_vis"] == True) and (oldStatus == False): paper["type"] = "manual"

        # hacking some types where we know more for the manually or keyword-selected
        if ("10.1109/tvcg.2024.3514858" in paper["doi"]): paper["type"] = "journal pres. @ IEEE VIS" # will be presented at VIS

def filterAndShortenJournalNames(journalName = ""):
    publicationVenue = journalName
    if publicationVenue == 'Graphics and Visual Computing': publicationVenue = 'Computers & Graphics' # this was the open-access version of C&G which now is a separate journal, and this only affects a single article anyway
    if publicationVenue == 'ACM Transactions on Graphics': publicationVenue = 'ACM ToG' # shortening
    if publicationVenue == 'Computer Graphics Forum': publicationVenue = 'Wiley CGF' # shortening
    if publicationVenue == 'Computer-Aided Design': publicationVenue = 'Elsevier CAD' # shortening
    if publicationVenue == 'Computers & Graphics': publicationVenue = 'Elsevier C&G' # shortening
    if publicationVenue == 'IEEE Transactions on Visualization and Computer Graphics': publicationVenue = 'IEEE TVCG' # shortening
    if publicationVenue == 'ACM SIGGRAPH Asia Conference Papers': publicationVenue = 'SIGGRAPH conf.' # shortening
    if publicationVenue == 'ACM SIGGRAPH Conference Papers': publicationVenue = 'SIGGRAPH conf.' # shortening
    return publicationVenue

def generateColorArrayFromColorScheme(sourceColorScheme, lightenFactor=0.5, colorsReverse = False):
    source_color_scheme = sourceColorScheme
    source_color_scheme2 = ""
    addLightenedColors = False

    # this allows us to merge two color schemes, even potentially with additional lightening
    if ("_plus_" in sourceColorScheme):
        source_color_scheme = sourceColorScheme.split("_plus_")[0]
        source_color_scheme2 = sourceColorScheme.split("_plus_")[1]
        if ("_lightened" in sourceColorScheme): addLightenedColors = True

    # this new "tableau20matching" color scheme uses the colors from "tableau20", but in the order they were used in "tableau10"
    if (sourceColorScheme == "tableau20matching"): source_color_scheme = "tableau20"
    tableau20MatchingColorNumberMapping = {0: 0, 1: 1, 2: 2, 3: 3, 4: 10, 5: 11, 6: 8, 7: 9, 8: 4, 9: 5, 10: 6, 11: 7, 12: 16, 13: 17, 14: 14, 15: 15, 16: 18, 17: 19, 18: 12, 19: 13} # map colors to matching pairs
    # this new "tableau20matching_lightened" color scheme does the same as the "tableau20matching" one, but adds a lightened version after each color
    if (sourceColorScheme == "tableau20matching_lightened"):
        source_color_scheme = "tableau20"
        addLightenedColors = True
    # this new "tableau10paired" color scheme uses the colors from "tableau10", but re-orders them such that each pair of colors (except the last) forms a visually match (i.e., they appear to belong together)
    if (sourceColorScheme == "tableau10paired"): source_color_scheme = "tableau10"
    tableau10PairedColorNumberMapping = {0: 0, 1: 3, 2: 2, 3: 1, 4: 8, 5: 5, 6: 6, 7: 4, 8: 7, 9: 9}
    # this new "tableau10paired_lightened" color scheme does the same as the "tableau10paired" one, but adds a lightened version after each color
    if (sourceColorScheme == "tableau10paired_lightened"):
        source_color_scheme = "tableau10"
        addLightenedColors = True
    # this new "tableau10lightened" color scheme does the same as the "tableau10" one, but adds a lightened version after each color
    if (sourceColorScheme == "tableau10lightened"):
        source_color_scheme = "tableau10"
        addLightenedColors = True

    # first get the array of real colors from Vega
    originalColorArray = vegaPalletData[source_color_scheme]

    originalColorArray2 = []
    if (source_color_scheme2 != ""):
        originalColorArray2 = vegaPalletData[source_color_scheme2]

    # build the default color mapping scheme: to use the same colors as in the source schemes
    colorMapping = {}
    baseIndex = len(originalColorArray)
    for i in range(0, len(originalColorArray)): colorMapping[i] = i
    if (source_color_scheme2 != ""):
        for i in range(0, len(originalColorArray2)): colorMapping[i + baseIndex] = i
    # then replace colors in certain cases (as setup above)
    if (sourceColorScheme == "tableau20matching") or (sourceColorScheme == "tableau20matching_lightened"): colorMapping = tableau20MatchingColorNumberMapping
    if (sourceColorScheme == "tableau10paired") or (sourceColorScheme == "tableau10paired_lightened"): colorMapping = tableau10PairedColorNumberMapping

    # then assemble the actual color array
    colorArray = []
    for i in range(0, len(originalColorArray)):
        color = originalColorArray[colorMapping[i]]
        if addLightenedColors:
            colorRgb = hex_to_rgb(color)
            lighterColor = lighten_color(r = colorRgb[0], g = colorRgb[1], b = colorRgb[2], factor=lightenFactor)
            lighterColorHex = rgb_to_hex(lighterColor[0], lighterColor[1], lighterColor[2])
            if (colorsReverse):
                colorArray.append(lighterColorHex)
                colorArray.append(color)
            else:
                colorArray.append(color)
                colorArray.append(lighterColorHex)
        else:
            colorArray.append(color)
    if (source_color_scheme2 != ""):
        for i in range(baseIndex, baseIndex + len(originalColorArray2)):
            color = originalColorArray2[colorMapping[i]]
            if addLightenedColors:
                colorRgb = hex_to_rgb(color)
                lighterColor = lighten_color(r = colorRgb[0], g = colorRgb[1], b = colorRgb[2], factor=lightenFactor)
                lighterColorHex = rgb_to_hex(lighterColor[0], lighterColor[1], lighterColor[2])
                if (colorsReverse):
                    colorArray.append(lighterColorHex)
                    colorArray.append(color)
                else:
                    colorArray.append(color)
                    colorArray.append(lighterColorHex)
            else:
                colorArray.append(color)
    
    return colorArray

def plotTimeSeriesPublicationData(dataToPlot, baseName = "replicability", dataField = "venue", cTitleSpecifier = "", yTitleSpecifier = "", colorScheme = "tableau10", legendColumns = 10, visPadding = 5, legendOffset = 10, labelAngle=0, chartsToPlot = ["all"], addTicksBetweenYears = False, addNoteBelowLegend = False, noteXOffset = 33):
    altairData = pd.DataFrame(dataToPlot)
    cTitle = dataField
    if cTitleSpecifier != "": cTitle = cTitleSpecifier
    yTitle = 'published papers'
    if yTitleSpecifier != "": yTitle = yTitleSpecifier
    xTitle = 'publication year'
    xTitle = None # we don't really need a title

    # if ("all" in chartsToPlot) or ("stackedareagraph" in chartsToPlot):
    if ("stackedareagraph" in chartsToPlot): # only if requested explicitly, for now we don't need the stacked area graphs, and some are confusing, too
        chart = alt.Chart(altairData).mark_area().encode(
            x = alt.X('year:N', title=xTitle, sort=None).axis(labelAngle=labelAngle),
            y = alt.Y('sum(count):Q', title=yTitle), #.stack('zero'),
            # order=alt.Order('year:N'), # this is a hack: order the stack by something that is identical for all, so then the order of the color scheme is used
            order=alt.Order('order:Q', sort='ascending'),
            color = alt.Color(dataField + ':N', title=cTitle, sort=None) #.scale(scheme=colorScheme)
        ).configure_range(
            category=alt.RangeScheme(generateColorArrayFromColorScheme(colorScheme))
        ).configure_view(
            strokeOpacity=0 # this removes the gray box around the plot
        ).properties(
            padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding},
            width=500,
            height=300
        ).configure_legend(orient='bottom', direction='horizontal', columns=legendColumns, offset=legendOffset, titleLimit=0, labelLimit=myLabelLimit)

        chart.save(baseName + '-stackedareagraph.pdf')

    if ("all" in chartsToPlot) or ("stackedbargraph" in chartsToPlot):
        chart = alt.Chart(altairData).mark_bar().encode(
            x = alt.X('year:N', title=xTitle, sort=None).axis(tickWidth=0, labelAngle=labelAngle),
            y = alt.Y('sum(count):Q', title=yTitle).stack('zero'),
            order=alt.Order('year:N'), # this is a hack: order the stack by something that is identical for all, so then the order of the color scheme is used
            color = alt.Color(dataField + ':N', title=cTitle, sort=None) #.scale(scheme=colorScheme)
        ).configure_range(
            category=alt.RangeScheme(generateColorArrayFromColorScheme(colorScheme))
        ).configure_view(
            strokeOpacity=0 # this removes the gray box around the plot
        ).properties(
            padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding},
            width=500,
            height=300
        ).configure_legend(orient='bottom', direction='horizontal', columns=legendColumns, offset=legendOffset, titleLimit=0, labelLimit=myLabelLimit)

        chart.save(baseName + '-stackedbargraph.pdf')

    if ("all" in chartsToPlot) or ("stackedbargraph-normalized" in chartsToPlot):
        chart = alt.Chart(altairData).mark_bar().encode(
            x = alt.X('year:N', title=xTitle, sort=None).axis(tickWidth=0, labelAngle=labelAngle),
            y = alt.Y('sum(count):Q', title=yTitle).stack("normalize"),
            order=alt.Order('year:N'), # this is a hack: order the stack by something that is identical for all, so then the order of the color scheme is used
            color = alt.Color(dataField + ':N', title=cTitle, sort=None) #.scale(scheme=colorScheme)
        ).configure_range(
            category=alt.RangeScheme(generateColorArrayFromColorScheme(colorScheme))
        ).configure_view(
            strokeOpacity=0 # this removes the gray box around the plot
        ).properties(
            padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding},
            width=500,
            height=300
        ).configure_legend(orient='bottom', direction='horizontal', columns=legendColumns, offset=legendOffset, titleLimit=0, labelLimit=myLabelLimit)

        chart.save(baseName + '-stackedbargraph-normalized.pdf')

    # if ("all" in chartsToPlot) or ("singlebargraphs" in chartsToPlot):
    if ("singlebargraphs" in chartsToPlot): # only if requested explicitly, for now we do not need the single bar graphs
        chart = alt.Chart(altairData).mark_bar().encode(
            x = alt.X('year:N', title=xTitle, sort=None).axis(tickWidth=0, labelAngle=labelAngle),
            y = alt.Y('sum(count):Q', title=yTitle),
            color = alt.Color(dataField + ':N', title=cTitle, sort=None), #.scale(scheme=colorScheme)
            row=dataField + ':N'
        ).configure_range(
            category=alt.RangeScheme(generateColorArrayFromColorScheme(colorScheme))
        ).configure_view(
            strokeOpacity=0 # this removes the gray box around the plot
        ).properties(
            padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding},
            width=500,
            height=300
        ).configure_legend(orient='bottom', direction='horizontal', columns=legendColumns, offset=legendOffset, titleLimit=0, labelLimit=myLabelLimit)

        chart.save(baseName + '-singlebargraphs.pdf')

    if ("all" in chartsToPlot) or ("groupedbargraph" in chartsToPlot):
        chart = alt.Chart(altairData).mark_bar().encode(
            x = alt.X('year:N', title=xTitle, sort=None).axis(tickWidth=0, labelAngle=labelAngle),
            y = alt.Y('count:Q', title=yTitle),
            color = alt.Color(dataField + ':N', title=cTitle, sort=None), #.scale(scheme=colorScheme)
            xOffset=alt.XOffset(dataField + ':N', sort=None)
        )
        if (addTicksBetweenYears):
            # add vertical tick marks between the years for better reading
            # this is a total hack, we create another chart but don't actually display it, neither its axis, and only get the tick marks from it at year boundaries
            years = altairData['year'].tolist()
            yearsUnique = []
            for yearString in years:
                yearNumber = int(yearString.replace('in press', str(current_year + 1)))
                if not yearNumber in yearsUnique: yearsUnique.append(yearNumber)
            startYear = yearsUnique[0]
            endYear = yearsUnique[-1]
            lines = (
                alt.Chart(altairData).mark_rule().encode(
                    x = alt.X("year:Q", axis=None, title=None).axis(ticks=True, labels=False, grid=False, domain=False, orient='bottom',tickCount=endYear-startYear+2).scale(domain=[startYear - 0.1, endYear + 1.1]),
                    color= alt.value("#ffffff"),
                    size=alt.value(0.0)
                )
            )
            chart = chart+lines # layer the two charts
        # rest of processing
        chart = chart.configure_range(
            category=alt.RangeScheme(generateColorArrayFromColorScheme(colorScheme))
        ).configure_view(
            strokeOpacity=0 # this removes the gray box around the plot
        ).properties(
            padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding},
            width=500,
            height=300
        ).configure_legend(orient='bottom', direction='horizontal', columns=legendColumns, offset=legendOffset, titleLimit=0, labelLimit=myLabelLimit)
        if (addNoteBelowLegend):
            chart = chart.properties(title=alt.TitleParams( # this way of adding a note below the legend is also a total hack because there is no other way to add a text field there
                ['Please note that the colors/entries per year always follow the order of the legend.'],
                baseline='bottom',
                orient='bottom',
                anchor='start',
                fontWeight='normal',
                fontSize=10,
                dy=13, dx=noteXOffset
            ))

        chart.save(baseName + '-groupedbargraph.pdf')

    if ("all" in chartsToPlot) or ("linegraph" in chartsToPlot):
        chart = alt.Chart(altairData).mark_line().encode(
            x = alt.X('year:N', title=xTitle, sort=None).axis(tickWidth=0, labelAngle=labelAngle),
            y = alt.Y('count:Q', title=yTitle),
            color = alt.Color(dataField + ':N', title=cTitle, sort=None) #.scale(scheme=colorScheme)
        ).configure_range(
            category=alt.RangeScheme(generateColorArrayFromColorScheme(colorScheme))
        ).configure_view(
            strokeOpacity=0 # this removes the gray box around the plot
        ).properties(
            padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding},
            width=500,
            height=300
        ).configure_legend(orient='bottom', direction='horizontal', columns=legendColumns, offset=legendOffset, titleLimit=0, labelLimit=myLabelLimit)

        chart.save(baseName + '-linegraph.pdf')

def digitToNameSequence(number):
    # Define a dictionary to map the digit to its English name
    digit_names = {
        0: 'Zero',
        1: 'One',
        2: 'Two',
        3: 'Three',
        4: 'Four',
        5: 'Five',
        6: 'Six',
        7: 'Seven',
        8: 'Eight',
        9: 'Nine'
    }
    
    number_str = str(number) # Convert the number to a string
    english_names = '' # Initialize an empty string to store the English names
    
    for digit in number_str: # Iterate over each digit in the number
        digit = int(digit) # Convert the digit back to an integer
        name = digit_names.get(digit) # Lookup the English name of the digit from the dictionary
        english_names += name # Append the English name to the result string
    
    return english_names

#####################################
# read in external verification files (DOIs of published visualization papers)
#####################################

# read the dois of the IEEE VIS papers from vispubdata (as csv file)
visPubDataDois = []
visPubDataConferenceYears = {}
visPubDataAuthorsDeduped = {}
visPubDataMostRecentYear = 0
with open('input/vispubdata.csv', 'r', encoding="utf-8") as csvfile:
    # create a CSV reader object
    reader = csv.DictReader(csvfile)
    # iterate over the rows
    for row in reader:
        doi = row['DOI'].lower()
        year = int(row['Year'])
        visPubDataDois.append(doi)
        visPubDataConferenceYears[doi] = year
        visPubDataAuthorsDeduped[doi] = row['AuthorNames-Deduped'].split(';') # AuthorNames-Deduped,AuthorNames
        if (year > visPubDataMostRecentYear): visPubDataMostRecentYear = year

# when vispubdata is not current, we can also use TVCG's CSV export of the VIS issues to add the missing data
tvcgFilenamesList = glob.glob('input/tvcg-[0-9][0-9][0-9][0-9]-vol-[0-9][0-9]-no-[0-9][0-9].csv')
for tvcgFilename in tvcgFilenamesList:
    with open(tvcgFilename, 'r', encoding="utf-8") as csvfile:
        # create a CSV reader object
        reader = csv.DictReader(csvfile)
        # iterate over the rows
        for row in reader:
            tvcgDoi = row['DOI'].lower()
            if tvcgDoi not in visPubDataDois: # so that we do not duplicate the loaded dois
                year = int(row['Publication Year']) - 1 # the year in the data is the year of publication in TVCG, not presentation at VIS, so we need to deduct 1
                visPubDataDois.append(tvcgDoi)
                visPubDataConferenceYears[doi] = year # TVCG now publishes always in the year following the conference
                if (year > visPubDataMostRecentYear): visPubDataMostRecentYear = year

# another alternative: a manually created spreadsheet of accepted VIS papers (I added this mainly for the BELIV paper submission)
acceptedVisPapersFilenamesList = glob.glob('input/vis-[0-9][0-9][0-9][0-9].csv')
for acceptedVisPapersFilename in acceptedVisPapersFilenamesList:
    with open(acceptedVisPapersFilename, 'r', encoding="utf-8") as csvfile:
        # create a CSV reader object
        reader = csv.DictReader(csvfile)
        # iterate over the rows
        for row in reader:
            visDoi = row['DOI'].lower()
            if visDoi not in visPubDataDois: # so that we do not duplicate the loaded dois (should not happen if we use fake DOIs)
                year = int(row['Year']) # the year in the data is the year of presentation at VIS
                visPubDataDois.append(visDoi)
                visPubDataConferenceYears[visDoi] = year
                if (year > visPubDataMostRecentYear): visPubDataMostRecentYear = year

# when done with all loading of proper VIS papers, count the totals of papers per year and output strings
listOfVispubDataYears = list(set(val for val in visPubDataConferenceYears.values()))
for year in listOfVispubDataYears:
    papersThatYear = sum(value == year for value in visPubDataConferenceYears.values())
    paperNumbersOutputString += "\\newcommand{\\TotalIeeeVisPapersIn" + intToRoman(year) + "}{" + str(papersThatYear) + "}\n"

# read the dois of the IEEE VIS journal presentations (as csv file)
visJournalPresentationDois = []
visJournalPresentationMostRecentYear = 0
visTVCGJournalPresentationConferenceYears = {}
with open('input/vis_journal_presentations.csv', 'r', encoding="utf-8") as csvfile:
    # create a CSV reader object
    reader = csv.DictReader(csvfile)
    # iterate over the rows
    for row in reader:
        tvcgDoi = row['doi'].lower()
        visJournalPresentationDois.append(tvcgDoi)
        year = int(row['year'])
        if (row['journal'] == "TVCG"): # only for TVCG papers
            visTVCGJournalPresentationConferenceYears[tvcgDoi] = year # the year of the presentation
        if (year > visJournalPresentationMostRecentYear): visJournalPresentationMostRecentYear = year

# when done with all loading of proper VIS journal papers, count the totals of TVCG journal papers per year and output strings
listOfTVCGJournalPresentationYears = list(set(val for val in visTVCGJournalPresentationConferenceYears.values()))
for year in listOfTVCGJournalPresentationYears:
    papersThatYear = sum(value == year for value in visTVCGJournalPresentationConferenceYears.values())
    paperNumbersOutputString += "\\newcommand{\\TotalIeeeVisTVCGJournalPapersIn" + intToRoman(year) + "}{" + str(papersThatYear) + "}\n"

# read the dois of the PacificVis TVCG papers (as csv file)
pacificVisTvcgDois = []
pacificVisTvcgMostRecentYear = 0
with open('input/pacificvis_tvcg.csv', 'r', encoding="utf-8") as csvfile:
    # create a CSV reader object
    reader = csv.DictReader(csvfile)
    # iterate over the rows
    for row in reader:
        pacificVisTvcgDois.append(row['doi'].lower())
        year = int(row['year'])
        if (year > pacificVisTvcgMostRecentYear): pacificVisTvcgMostRecentYear = year

# read the dois of the EuroVis journal presentation papers (as csv file)
pacificVisJournalPresentationDois = []
pacificVisJournalPresentationMostRecentYear = 0
with open('input/pacificvis_journal_presentations.csv', 'r', encoding="utf-8") as csvfile:
    # create a CSV reader object
    reader = csv.DictReader(csvfile)
    # iterate over the rows
    for row in reader:
        pacificVisJournalPresentationDois.append(row['doi'].lower())
        year = int(row['year'])
        if (year > pacificVisJournalPresentationMostRecentYear): pacificVisJournalPresentationMostRecentYear = year


# read the dois of the EuroVis journal presentation papers (as csv file)
euroVisJournalPresentationDois = []
euroVisJournalPresentationMostRecentYear = 0
with open('input/eurovis_journal_presentations.csv', 'r', encoding="utf-8") as csvfile:
    # create a CSV reader object
    reader = csv.DictReader(csvfile)
    # iterate over the rows
    for row in reader:
        euroVisJournalPresentationDois.append(row['doi'].lower())
        year = int(row['year'])
        if (year > euroVisJournalPresentationMostRecentYear): euroVisJournalPresentationMostRecentYear = year
# for 2024 and onward, we just use the bibtex export from the EG DL, converted to CSV
with open('input/eurovis.csv', 'r', encoding="utf-8") as csvfile:
    # create a CSV reader object
    reader = csv.DictReader(csvfile)
    # iterate over the rows
    for row in reader:
        euroVisJournalPresentationDois.append(row['doi'].lower())
        year = int(row['year'])
        if (year > euroVisJournalPresentationMostRecentYear): euroVisJournalPresentationMostRecentYear = year

# read the dois of the VCBM journal (C&G) papers (as csv file)
vcbmJournalDois = []
vcbmJournalMostRecentYear = 0
with open('input/vcbm_cag.csv', 'r', encoding="utf-8") as csvfile:
    # create a CSV reader object
    reader = csv.DictReader(csvfile)
    # iterate over the rows
    for row in reader:
        vcbmJournalDois.append(row['doi'].lower())
        year = int(row['conf. year'])
        if (year > vcbmJournalMostRecentYear): vcbmJournalMostRecentYear = year

# read the dois of the C&G visualization-topic special issue papers (as csv file)
cagVisSpecialIssueDois = []
cagVisSpecialIssueMostRecentYear = 0
with open('input/envirvis_cag.csv', 'r', encoding="utf-8") as csvfile:
    # create a CSV reader object
    reader = csv.DictReader(csvfile)
    # iterate over the rows
    for row in reader:
        cagVisSpecialIssueDois.append(row['doi'].lower())
        year = int(row['conf. year'])
        if (year > cagVisSpecialIssueMostRecentYear): cagVisSpecialIssueMostRecentYear = year
with open('input/eurova_cag.csv', 'r', encoding="utf-8") as csvfile:
    # create a CSV reader object
    reader = csv.DictReader(csvfile)
    # iterate over the rows
    for row in reader:
        cagVisSpecialIssueDois.append(row['doi'].lower())
        year = int(row['conf. year'])
        if (year > cagVisSpecialIssueMostRecentYear): cagVisSpecialIssueMostRecentYear = year
with open('input/molva_cag.csv', 'r', encoding="utf-8") as csvfile:
    # create a CSV reader object
    reader = csv.DictReader(csvfile)
    # iterate over the rows
    for row in reader:
        cagVisSpecialIssueDois.append(row['doi'].lower())
        year = int(row['conf. year'])
        if (year > cagVisSpecialIssueMostRecentYear): cagVisSpecialIssueMostRecentYear = year

# read the dois of the proper EuroVis papers (as xlsx file)
euroVisPaperDois = []
euroVisPaperMostRecentYear = 0
with pd.ExcelFile('input/EuroVisFull_CGF.xlsx') as xls:
    sheetX = xls.parse(0) # select the first sheet
    targetCellName = 'dc.identifier.doi[]'
    numberOfRows = len(sheetX[targetCellName])
    for i in range(0, numberOfRows):
        doi = sheetX[targetCellName][i]
        year = int(sheetX['dc.date.issued[en_US]'][i])
        abstract = str(sheetX['dc.description.abstract[en_US]'][i])
        if (len(abstract) > 0) and (abstract != 'nan'): # avoid including frontmatter that has no abstract
            if ((type(doi) == str) and (doi != 0) and (doi != '')): euroVisPaperDois.append(doi)
            else:
                doi = sheetX['dc.identifier.uri[en_US]'][i].replace('http://dx.doi.org/', '')
                if ((not 'handle' in doi) and ('10.1111/' in doi)):
                    euroVisPaperDois.append(doi)
                # else: # this is just for double-checking, could be added to a verbose mode
                #     print('Incorrect EuroVis DOI: ' + doi)
            if (year > euroVisPaperMostRecentYear): euroVisPaperMostRecentYear = year
# for 2024 and onward, we just use the bibtex export from the EG DL, converted to CSV
with open('input/eurovis.csv', 'r', encoding="utf-8") as csvfile:
    # create a CSV reader object
    reader = csv.DictReader(csvfile)
    # iterate over the rows
    for row in reader:
        euroVisPaperDois.append(row['doi'].lower())
        year = int(row['year'])
        if (year > euroVisPaperMostRecentYear): euroVisPaperMostRecentYear = year

# read the dois of the EuroVis STAR papers (as xlsx file)
with pd.ExcelFile('input/EuroVisSTARS_CGF.xlsx') as xls:
    sheetX = xls.parse(0) # select the first sheet
    targetCellName = 'dc.identifier.doi[]'
    numberOfRows = len(sheetX[targetCellName])
    for i in range(0, numberOfRows):
        doi = sheetX[targetCellName][i]
        year = int(sheetX['dc.date.issued[]'][i])
        abstract = str(sheetX['dc.description.abstract[en_US]'][i])
        if (len(abstract) > 0) and (abstract != 'nan'): # avoid including frontmatter that has no abstract
            if ((type(doi) == str) and (doi != 0) and (doi != '')): euroVisPaperDois.append(doi)
            else:
                doi = sheetX['dc.identifier.uri[]'][i].replace('http://dx.doi.org/', '')
                if ((not 'handle' in doi) and ('10.1111/' in doi)):
                    euroVisPaperDois.append(doi)
                # else: # this is just for double-checking, could be added to a verbose mode
                #     print('Incorrect EuroVis DOI: ' + doi)
            if (year > euroVisPaperMostRecentYear): euroVisPaperMostRecentYear = year

#####################################
# rest of processing
#####################################

updatingGrsiDataFromWeb = False # we will only do this for the first run of the script in a day, otherwise we use the stored data
# this variable will also be used for determining if we should update the extra data for the papers from the digital libraries

# this will be the list that records all data
paperList = []
paperCounter = 0
if useLocalDataOnly:
    print("Loading already existing JSON file from disk (repository version) ...")
    with open(dataOutputSubdirectury + "grsi_paper_data.json", "r", encoding='utf-8') as f:
        paperList = json.load(f)
    unmarkPapers(paperList)  # this is, of course, old data: we redo it below
    paperCounter = len(paperList)
    with open(dataOutputSubdirectury + "grsi_metadata.json", "r", encoding='utf-8') as f:
        grsiMetaData = json.load(f)
    # if we use the local data, then also use the date of this local data as the time stamp
    data_date_day = grsiMetaData["data_download_day"]
    data_date_month = grsiMetaData["data_download_month"]
    data_date_year = grsiMetaData["data_download_year"]
    formatted_date = f"{data_date_year}{data_date_month:02d}{data_date_day:02d}"
else:
    if (not (os.path.isfile(pathOfTheScript + "/" + formatted_date + " grsi paper data.json"))):
        # if we have not yet downloaded/scraped today's data, then get the data from the web
        print("Getting the current data from the web ...")
        updatingGrsiDataFromWeb = True
        page = urlopen('https://www.replicabilitystamp.org/').read()
        soup = BeautifulSoup(page, features="lxml")

        for anchor in soup.body.findAll('section', attrs={'class': 'spotlight'}):
            paperCounter += 1
            paperItem = {}
            paperItem['counter'] = paperCounter
            paperItem['is_vis'] = False # by default
            x = anchor.find('div', attrs={'class': 'content'})

            title = str(x.find_next("h3").find_next("a").get_text())
            title = title.replace("Towards Efficieant Novel View Synthesis", "Towards Efficient Novel View Synthesis")
            paperItem['title'] = title.strip()
            if paperItem['title'][-1] == '.': paperItem['title'] = paperItem['title'][:-1] # cleaning up

            # doi data clean-up
            doi = str(x.findAll("a")[3].get('href'))
            doi = doi.replace("https://doi.org/", "")
            doi = doi.replace("https://doi.ieeecomputersociety.org/", "")
            doi = re.sub(pattern=r"https://diglib\.eg\.org(?::443)?/handle/10\.1111/cgf(\d+)", repl=r"10.1111/cgf.\1", string=doi)
            doi = doi.replace("https://dl.acm.org/doi/", "")
            # some manual doi assignments because the GRSI page occasionally only provided Google searches instead of a real DOI at the beginning
            # please note to replace the '%20' in the Google search links with a ' ' (manually or via a .replace("%20", " ") call as in the examples); otherwise the replacement does not work
            doi = doi.replace("http://www.google.com/search?q=DiffFit:%20Visually-Guided%20Differentiable%20Fitting%20of%20Molecule%20Structures%20to%20a%20Cryo-EM%20Map".replace("%20", " "), "10.1109/TVCG.2024.3456404")
            doi = doi.replace("%20", " ") # in case we copy-pasted the link from the website
            doi = re.sub(pattern=r"http(?:s)?://www\.google\.com/search.*", repl=r"NOT_ASSIGNED_YET", string=doi) # automatically assign the NOT_ASSIGNED_YET tag for remaining Google searches (once assigned but not yet on GRSI page add a manual override as above)
            paperItem['doi'] = doi.lower()
            # print a warning if the doi does not check out
            if (doi[0:3] != "10."): print("WARNING: The DOI we read from GRSI page that does not seem to formatted correctly for a DOI: " + doi)

            grsiUrl = str(x.findAll("a")[1].get('href'))
            paperItem['grsi_url'] = "https://www.replicabilitystamp.org/" + grsiUrl

            journalName = str(x.findAll("a")[2].get_text().strip())
            paperItem['journal'] = journalName

            repoUrl = str(x.findAll("a")[4].get('href'))
            paperItem['repo_url'] = repoUrl

            repoArchiveUrl = ""
            if (len(x.findAll("a")) > 5):
                repoArchiveUrl = str(x.findAll("a")[5].get('href'))
            paperItem['repo_archive_url'] = repoArchiveUrl

            y = anchor.find('div', attrs={'class': 'image'})
            imageUrl = str(y.findAll("img")[0].get('src'))
            paperItem['image_url'] = "https://www.replicabilitystamp.org/" + imageUrl

            authors = str(x.find_next("p")).split("\n")[1].lstrip().split('<br/>')[0].rstrip() # this is now the list of authors per paper

            # some systematic fixes
            if (authors[-1] == '.'): authors = authors[:-1] # remove trailing dots (somewhat common)
            if (authors[-1] == ','): authors = authors[:-1] # remove trailing commas (somewhat common)

            # some ad-hoc author name fixes (easier than finding general solutions, if there even are any)
            if doi == '10.1145/3528223.3530124': authors = authors.replace('Alexandre Mercier-Aubin, Alexander Winter, David I.W. Levin, and Paul G. Kry', 'Alexandre Mercier-Aubin, Paul G. Kry, Alexandre Winter, David I. W. Levin')
            if doi == '10.1016/j.cag.2022.07.015': authors = authors.replace("Ariel Caputo, Marco Emporio, Andrea Giachetti, Marco Cristani, Guido Borghi, Andrea D'Eusanio, Minh-Quan Le, Hai-Dang Nguyen, Minh-Triet Tran, F. Ambellan, M. Hanik, E. Nava-Yazdani, C. von Tycowicz", "Marco Emporio, Ariel Caputo, Andrea Giachetti, Marco Cristani, Guido Borghi, Andrea D’Eusanio, Minh-Quan Le, Hai-Dang Nguyen, Minh-Triet Tran, Felix Ambellan, Martin Hanik, Esfandiar Nava-Yazdani, Christoph von Tycowicz")
            authors = authors.replace('\u200b', '')
            authors = re.sub(pattern=r"(\w),(\w)", repl=r"\1, \2", string=authors) # we need spaces after commas
            authors = authors.replace('Chen, Shu-Yu and Su, Wanchao and Gao, Lin and Xia, Shihong and Fu, Hongbo', 'Shu-Yu Chen and Wanchao Su and Lin Gao and Shihong Xia and Hongbo Fu')
            authors = authors.replace('Bora Yalçıner(1), Ahmet Oğuz Akyüz (1) ((1)Middle East Technical University, Computer Engineering Department)', 'Bora Yalçıner, Ahmet Oğuz Akyüz')
            authors = authors.replace(' (*Joint first authors)', '')
            authors = authors.replace('*', '')
            authors = authors.replace('D. Mlakar, M. Winter, P. Stadlbauer, H.-P. Seidel, M. Steinberger, R. Zayer', 'Daniel Mlakar, Martin Winter, Pascal Stadlbauer, Hans-Peter Seidel, Markus Steinberger, Rhaleb Zayer')
            authors = authors.replace('   (F# code by Martin Sarov)', '')
            authors = authors.replace('F. Ambellan, M. Hanik, E. Nava-Yazdani, C. von Tycowicz', 'Felix Ambellan, Martin Hanik, Esfandiar Nava-Yazdani, Christoph von Tycowicz')
            authors = authors.replace('Suzi Kim,Sunghee Choi', 'Suzi Kim, Sunghee Choi')
            authors = authors.replace('Viekash V K', 'Viekash Vinoth Kumar')
            authors = authors.replace('Yandong Guo Nihar Bagewadi', 'Yandong Guo, Nihar Bagewadi')
            authors = authors.replace('Gao Lin, Yang Jie, Wu Tong, Yuan Yu-Jie, Fu Hongbo, Lai, Yu-Kun, Zhang Hao(Richard)', 'Lin Gao, Jie Yang, Tong Wu, Yu-Jie Yuan, Hongbo Fu, Yu-Kun Lai, Hao Zhang')
            authors = authors.replace('ZHONGSHI JIANG, ZIYI ZHANG, YIXIN HU, TESEO SCHNEIDER, DENIS ZORIN, DANIELE PANOZZO', 'Zhongshi Jiang, Ziyi Zhang, Yixin Hu, Teseo Schneider, Denis Zorin, Daniele Panozzo')
            authors = authors.replace('Guillaume Lavoue', 'Guillaume Lavoué')
            authors = authors.replace('Felix Knoeppel', 'Felix Knöppel')
            authors = authors.replace('Clement Lemeunier', 'Clément Lemeunier')
            authors = authors.replace('Eric Guerin', 'Eric Guérin')
            authors = authors.replace('Eric Gurin', 'Eric Guérin')
            authors = authors.replace('Loic Barthe', 'Loïc Barthe')
            authors = authors.replace('Jean-Sbastien Franco', 'Jean-Sébastien Franco')
            authors = authors.replace('Johannes Schoning', 'Johannes Schöning')
            authors = authors.replace('Peter Konig', 'Peter König')
            authors = authors.replace('Jurgen Bernard', 'Jürgen Bernard')
            authors = authors.replace('Katharina Wnsche', 'Katharina Wünsche')
            authors = authors.replace('Torsten Mller', 'Torsten Möller')
            authors = authors.replace('Peter Schroeder', 'Peter Schröder')
            authors = authors.replace('Rudiger Westermann', 'Rüdiger Westermann')
            authors = authors.replace('Simon T. Perrault', 'Simon Tangi Perrault')
            authors = authors.replace('Stephen Kobourov', 'Stephen G. Kobourov')
            authors = authors.replace('Thomas Mller', 'Thomas Müller')
            authors = authors.replace('Lonni Besancon', 'Lonni Besançon')
            authors = authors.replace('Stephane Gosset', 'Stéphane Gosset')
            authors = authors.replace('Robert S Laramee', 'Robert S. Laramee')
            authors = authors.replace('Salles V.G. Magalhães', 'Salles V. G. Magalhães')
            authors = authors.replace('Charlie C.L. Wang', 'Charlie C. L. Wang')
            authors = authors.replace('David I.W. Levin', 'David I. W. Levin')
            authors = authors.replace('Marcus V.A. Andrade', 'Marcus V. A. Andrade')
            authors = authors.replace('Boudewijn P.F. Lelieveldt', 'Boudewijn P. F. Lelieveldt')
            authors = authors.replace('Martin Nollenburg', 'Martin Nöllenburg')
            authors = authors.replace('Florian Schaefer', 'Florian Schäfer')
            authors = authors.replace('Remi Allegre', 'Rémi Allègre')
            authors = authors.replace('Jorg Peters', 'Jörg Peters')
            authors = authors.replace('Rdiger Westermann', 'Rüdiger Westermann')
            authors = authors.replace('Mihai Bce', 'Mihai Bâce')
            authors = authors.replace('Alex Buerle', 'Alex Bäuerle')
            authors = authors.replace('Emanuele Rodola', 'Emanuele Rodolà')
            authors = authors.replace('Jonas Martinez', 'Jonàs Martínez')
            authors = authors.replace('Juliane Mueller', 'Juliane Müller') # Juliane Müller-Sielaff https://orcid.org/0000-0002-8279-0901
            authors = authors.replace('Juliane Mller', 'Juliane Müller') # same person
            authors = authors.replace('Lidija Comic', 'Lidija Čomić')
            authors = authors.replace('Renate Gruner', 'Renate Grüner')
            authors = authors.replace('Kestutis Karciauskas', 'Kȩstutis Karčiauskas')
            authors = authors.replace('Kęstutis Karčiauskas', 'Kȩstutis Karčiauskas')
            authors = authors.replace('Rafal K. Mantiuk', 'Rafał K. Mantiuk')
            authors = authors.replace('Gabriela Molina', 'Gabriela Molina León')
            authors = authors.replace('Gabriela Molina León León', 'Gabriela Molina León') # fix the potential duplication of the second last name
            authors = authors.replace('Marti Hearst', 'Marti A. Hearst')
            authors = authors.replace('Vinicius da Silva', 'Vinícius da Silva')
            authors = authors.replace('Helio Lopes', 'Hélio Lopes')
            authors = authors.replace('Andrew McNutt', 'Andrew M. McNutt')
            authors = authors.replace('Nikos Papadakis', 'Nikolaos Papadakis')
            authors = authors.replace('Jol Randrianandrasana', 'Joël Randrianandrasana')
            authors = authors.replace('Annemarie Moigne', 'Anne-Marie Moigne')
            authors = authors.replace('Elie Michel', 'Élie Michel')
            authors = authors.replace('Wei Jiang', 'Jiang Wei')
            authors = authors.replace('Yana Nehme', 'Yana Nehmé')
            authors = authors.replace('Alberto Cannavo', 'Alberto Cannavò')
            authors = authors.replace('Silvia Sellan', 'Silvia Sellán')
            authors = authors.replace('Yagiz Aksoy', 'Yağiz Aksoy')
            authors = authors.replace('Yongjin Liu', 'Yong-Jin Liu')
            authors = authors.replace('Fabian Prada', 'Fabián Prada')
            authors = authors.replace('Stefano Zappala', 'Stefano Zappalà')
            authors = authors.replace('Jungyu Yang', 'Jingyu Yang')
            authors = authors.replace('Jakub Vasicek', 'Jakub Vašíček')
            authors = authors.replace('Marta Nunez-Garcia', 'Marta Nuñez-Garcia')
            authors = authors.replace('Francisco Alarcon', 'Francisco Alarcón')
            authors = authors.replace('Lluis Mont', 'Lluís Mont')
            authors = authors.replace('Corrado Cali', 'Corrado Calì')
            authors = authors.replace('Jeremie Dumas', 'Jérémie Dumas')
            authors = authors.replace('Milos Hasan', 'Miloš Hašan')
            authors = authors.replace('Arsene Perard-Gayot', 'Arsène Pérard-Gayot')
            authors = authors.replace('Roland Leissa', 'Roland Leißa')
            authors = authors.replace('George Brown', 'George E. Brown')
            authors = re.sub(pattern=r"Cindy Xiong(?: Bearfield)?", repl=r"Cindy Xiong Bearfield", string=authors) # same person, name change due to marriage (I assume)
            authors = authors.replace('Jianjun Zhang', 'Jian Jun Zhang')
            authors = authors.replace('LORENZO DIAZZI, DANIELE PANOZZO, AMIR VAXMAN, MARCO ATTENE', 'Lorenzo Diazzi, Daniele Panozzo, Amir Vaxman, Marco Attene')
            authors = authors.replace('Lois Paulin', 'Loïs Paulin')
            authors = authors.replace('Thomas Hollt', 'Thomas Höllt')
            authors = authors.replace('Hao Huanga', 'Hao Huang')
            authors = authors.replace('Shuaihang Yuana', 'Shuaihang Yuan')
            authors = authors.replace('Yu Haoa', 'Yu Hao')
            authors = authors.replace('Yağiz Aksoy', 'Yağız Aksoy')
            authors = authors.replace('Matt I.B. Oddo', 'Matt I. B. Oddo')
            authors = authors.replace('Dennis Bukenberger', 'Dennis R. Bukenberger')
            authors = authors.replace('Rafael Azevedo', 'Rafael V. Azevedo')
            authors = authors.replace('Joao Rulff', 'João Rulff')
            authors = authors.replace('Tamal Dey', 'Tamal K. Dey')
            authors = authors.replace('Alex Bronstein', 'Alex M. Bronstein')
            authors = authors.replace('Michael Bronstein', 'Michael M. Bronstein')
            authors = authors.replace('Scott Mitchell', 'Scott A. Mitchell')

            # make the author list reporting consistent
            authors = authors.replace(' ; ', ', ')
            authors = authors.replace('; ', ', ')
            authors = authors.replace(';', ', ')
            authors = authors.replace(', and ', ', ')
            authors = authors.replace(' and ', ', ')
            authors = authors.replace(' , ', ', ')
            authors = authors.replace('  ', ' ')

            paperItem['authors'] = authors # save the filtered authors list
            paperList.append(paperItem) # then save the data in the list

    else:
        # otherwise we have today's data already, so load it
        print("Loading already existing JSON file from disk ...")
        with open(formatted_date + " grsi paper data.json", "r", encoding='utf-8') as f:
            paperList = json.load(f)
        unmarkPapers(paperList)  # this is, of course, old data: we redo it below
        paperCounter = len(paperList)

# record the date of data download
data_date = datetime.datetime.strptime(formatted_date + " 14:00:00", '%Y%m%d %H:%M:%S')
if (grsiMetaData["data_download_month"] != 5):
    paperNumbersOutputString += "\\newcommand{\\GrsiDataCurrentAsOf}{" + data_date.strftime("%b.~%d, %Y").replace("~0", "~") + "}\n"
else:
    paperNumbersOutputString += "\\newcommand{\\GrsiDataCurrentAsOf}{" + data_date.strftime("%b~%d, %Y").replace("~0", "~") + "}\n"
paperNumbersOutputString += "\\newcommand{\\GrsiDataCurrentAsOfLong}{" + data_date.strftime("%B~%d, %Y").replace("~0", "~") + "}\n"

# prepare the data for the author counting
authorCounts = {}
for paper in paperList:
    authors = paper['authors']
    authors = authors.replace(' Jr.', u'\u00A0Jr.') # last conversion, important later for the sorting (replacement with &nbsp;)

    # now single-out the authors
    for author in re.split(', and | , |, | and | ; |; ', authors):
        authorFiltered = author.lstrip().rstrip().replace('​', '')
        if authorFiltered in authorCounts.keys():
            authorCounts[authorFiltered] = authorCounts[authorFiltered] + 1
        else:
            authorCounts[authorFiltered] = 1

#######################################################
#######################################################
# do the author counting and then the output
#######################################################
#######################################################
authorPlaces = {}
authorVisPapers = {}
visCounter = 0
visAuthorCounter = 0
visKeywordPlusManualPapersCount = 0
authorCountsSortedByAuthors = {}
authorCountsSortedByNumbers = {}
authorVisNovisHistogramData = { bin : 0 for bin in range(0, numberOfAuhorHistogramBins) } # create the histogram bins, with a given number of bins
authorVisNovisHistogramDataTwoPlus = { bin : 0 for bin in range(0, numberOfAuhorHistogramBins) } # create the histogram bins, with a given number of bins
with open(formatted_date + " current-list.txt", "w", encoding='utf-8') as f:
    authorCountsSortedByAuthors = dict(sorted(authorCounts.items(), key=lambda x: (x[0].split(' ')[-1], x[0]), reverse=False))
    authorCountsSortedByNumbers = dict(sorted(authorCountsSortedByAuthors.items(), key=lambda x: x[1], reverse=True))

    place = 0
    currentNumber = 0
    countPerPlace = 1

    print("Total: " + str(len(authorCountsSortedByNumbers)) + " authors.", file=f)
    paperNumbersOutputString += "\\newcommand{\\GrsiTotalAuthors}{" + str(len(authorCountsSortedByNumbers)) + "}\n"
    print("Total: " + str(paperCounter) + " papers.", file=f)
    paperNumbersOutputString += "\\newcommand{\\GrsiTotalPapers}{" + str(paperCounter) + "}\n"
    print("", file=f)

    # mark all vis papers to be able to check by person
    unmarkPapers(paperList)
    markPapersByDoi(paperList, visPubDataDois, "is_vis")
    markPapersByDoi(paperList, visJournalPresentationDois, "is_vis")
    markPapersByDoi(paperList, pacificVisTvcgDois, "is_vis")
    markPapersByDoi(paperList, pacificVisJournalPresentationDois, "is_vis")
    markPapersByDoi(paperList, euroVisPaperDois, "is_vis")
    markPapersByDoi(paperList, euroVisJournalPresentationDois, "is_vis")
    markPapersByDoi(paperList, vcbmJournalDois, "is_vis")
    markPapersByDoi(paperList, cagVisSpecialIssueDois, "is_vis")
    markVisPapersByKeywords(paperList)

    print("===============\nSorted by rank:\n===============", file=f)
    for author in authorCountsSortedByNumbers.keys():
        if (currentNumber != authorCounts[author]):
            currentNumber = authorCounts[author]
            place += countPerPlace
            countPerPlace = 0
        authorPlaces[author] = place
        
        # count the author's vis papers
        authorVisPaperCount = 0
        for paper in paperList:
            if (author in paper["authors"]):
                if (paper["is_vis"]): authorVisPaperCount += 1
        authorVisPapers[author] = authorVisPaperCount
        visPercentage = 100.0*float(authorVisPapers[author])/float(authorCounts[author])

        # figure out the data for the binning by vis percentage
        visPercentageBin = math.floor(visPercentage * 0.01 * float(numberOfAuhorHistogramBins))
        visPercentageBin = numberOfAuhorHistogramBins-1 if (visPercentageBin >= numberOfAuhorHistogramBins) else visPercentageBin
        authorVisNovisHistogramData[visPercentageBin] += 1
        if (authorCounts[author] > 1): # the second histogram only for authors with more than one papers
            authorVisNovisHistogramDataTwoPlus[visPercentageBin] += 1
        
        prefixString = ""
        postfixString = ""
        if (visPercentage >= 50.0):
            prefixString = "***** "
            postfixString = " *****"
            visAuthorCounter += 1
        else:
            prefixString = "      "

        paperString = " paper"
        if (authorCounts[author] > 1): paperString = " papers"

        visPapersString = " " + str(authorVisPapers[author]) + " vis papers"
        if (authorVisPapers[author] == 1): visPapersString = visPapersString[:-1]
        if (authorVisPapers[author] > 0): visPapersString += " (" + "%.1f" % visPercentage + "% of their papers)"

        print(prefixString + author.replace(u'\u00A0', ' ') + ": " + str(authorCounts[author]) + paperString + " (" + str(place) + numberExtension(place) + " place) --" + visPapersString + postfixString, file=f)
        countPerPlace += 1
    paperNumbersOutputString += "\\newcommand{\\GrsiTotalVisAuthors}{" + str(visAuthorCounter) + "}\n"

    print("\n=============================\nSorted by author's last name:\n=============================", file=f)
    for author in authorCountsSortedByAuthors.keys():
        place = authorPlaces[author]
        visPercentage = 100.0*float(authorVisPapers[author])/float(authorCounts[author])
        
        prefixString = ""
        postfixString = ""
        if (visPercentage >= 50.0):
            prefixString = "***** "
            postfixString = " *****"
        else:
            prefixString = "      "

        paperString = " paper"
        if (authorCounts[author] > 1): paperString = " papers"

        visPapersString = " " + str(authorVisPapers[author]) + " vis papers"
        if (authorVisPapers[author] == 1): visPapersString = visPapersString[:-1]
        if (authorVisPapers[author] > 0): visPapersString += " (" + "%.1f" % visPercentage + "% of their papers)"

        print(prefixString + author.replace(u'\u00A0', ' ') + ": " + str(authorCounts[author]) + paperString + " (" + str(place) + numberExtension(place) + " place) --" + visPapersString + postfixString, file=f)
        countPerPlace += 1


    ############################################
    ### proper IEEE VIS papers
    ############################################
    unmarkPapers(paperList)
    doiPaddingCount = 25
    print("\n\n=================================", file=f)
    print("Analysis for visualization papers", file=f)
    print("=================================", file=f)

    # check if a paper is a IEEE vis paper
    markPapersByDoi(paperList, visPubDataDois, "is_vis", "IEEE VIS")

    # count the IEEE vis papers
    oldVisCounter = 0
    visCounter = 0
    for paper in paperList:
        if (paper["is_vis"]): visCounter += 1

    # print IEEE vis papers
    print("\nIEEE VIS papers (only those we know were accepted directly to the conference, up to the conference in " + str(visPubDataMostRecentYear) + ", via vispubdata DOIs): " + str(visCounter - oldVisCounter) + " papers", file=f)
    paperNumbersOutputString += "\\newcommand{\\GrsiIeeeVisPapersCount}{" + str(visCounter - oldVisCounter) + "}\n"
    paperNumbersOutputString += "\\newcommand{\\GrsiIeeeVisPapersLastYear}{" + str(visPubDataMostRecentYear) + "}\n"
    visPapersPerYear = {}
    for year in range(2017, current_year): visPapersPerYear[year] = 0 # just to ensure that we have all years since 2017
    for paper in paperList:
        if ((paper["is_vis"]) and (paper["doi"] in visPubDataDois)):
            print("https://doi.org/" + str(paper["doi"].ljust(doiPaddingCount) + " -- " + str(paper["title"])), file=f)
            year = visPubDataConferenceYears[paper["doi"]]
            if year in visPapersPerYear.keys(): visPapersPerYear[year] += 1
            else: visPapersPerYear[year] = 1
    for year in visPapersPerYear.keys(): paperNumbersOutputString += "\\newcommand{\\GrsiIeeeVisPapersIn" + intToRoman(year) + "}{" + str(visPapersPerYear[year]) + "}\n"

    ############################################
    ### journal paper presentations at IEEE VIS
    ############################################

    # check if a paper was presented at IEEE
    markPapersByDoi(paperList, visJournalPresentationDois, "is_vis", "journal pres. @ IEEE VIS")

    # maked by keyword
    oldVisCounter = visCounter
    visCounter = 0
    for paper in paperList:
        if (paper["is_vis"]): visCounter += 1

    # print IEEE VIS journal presentations
    print("\nIEEE VIS TVCG journal presentations (up to the conference in " + str(visJournalPresentationMostRecentYear) + ", and some planned ones we know of): " + str(visCounter - oldVisCounter) + " papers", file=f)
    paperNumbersOutputString += "\\newcommand{\\GrsiIeeeVisJournalPresentationsCount}{" + str(visCounter - oldVisCounter) + "}\n"
    paperNumbersOutputString += "\\newcommand{\\GrsiIeeeVisJournalPresentationsLastYear}{" + str(visJournalPresentationMostRecentYear) + "}\n"
    
    visTVCGJournalPapersPerYear = {}
    for year in range(2017, current_year): visTVCGJournalPapersPerYear[year] = 0 # just to ensure that we have all years since 2017
    for paper in paperList:
        if ((paper["is_vis"]) and (paper["doi"] in visJournalPresentationDois)):
            print("https://doi.org/" + str(paper["doi"].ljust(doiPaddingCount) + " -- " + str(paper["title"])), file=f)
            if paper["doi"] in visTVCGJournalPresentationConferenceYears.keys(): # there may also be CG&A papers in the list of visJournalPresentationDois
                year = visTVCGJournalPresentationConferenceYears[paper["doi"]]
                if year in visTVCGJournalPapersPerYear.keys(): visTVCGJournalPapersPerYear[year] += 1
                else: visTVCGJournalPapersPerYear[year] = 1
    onlyTvcgJournalPresentations = 0 # this count may be different from the value above once CG&A also starts awarding stamps
    for year in visTVCGJournalPapersPerYear.keys():
        onlyTvcgJournalPresentations += visTVCGJournalPapersPerYear[year]
        paperNumbersOutputString += "\\newcommand{\\GrsiIeeeVisTVCGJournalPapersIn" + intToRoman(year) + "}{" + str(visTVCGJournalPapersPerYear[year]) + "}\n"
    paperNumbersOutputString += "\\newcommand{\\GrsiIeeeVisTvcgJournalPresentationsCount}{" + str(onlyTvcgJournalPresentations) + "}\n"

    ############################################
    ### proper PacificVis TVCG papers
    ############################################

    # check if a paper was a PacificVis TVCG paper
    markPapersByDoi(paperList, pacificVisTvcgDois, "is_vis", "PacificVis TVCG")

    # count all papers so far
    oldVisCounter = visCounter
    visCounter = 0
    for paper in paperList:
        if (paper["is_vis"]): visCounter += 1

    # print PacificVis TVCG paper
    print("\nIEEE PacificVis TVCG papers (up to the conference in " + str(pacificVisTvcgMostRecentYear) + "): " + str(visCounter - oldVisCounter) + " papers", file=f)
    paperNumbersOutputString += "\\newcommand{\\GrsiPacificVisTvcgPapersCount}{" + str(visCounter - oldVisCounter) + "}\n"
    paperNumbersOutputString += "\\newcommand{\\GrsiPacificVisTvcgPapersLastYear}{" + str(pacificVisTvcgMostRecentYear) + "}\n"
    for paper in paperList:
        if ((paper["is_vis"]) and (paper["doi"] in pacificVisTvcgDois)): print("https://doi.org/" + str(paper["doi"].ljust(doiPaddingCount) + " -- " + str(paper["title"])), file=f)

    ############################################
    ### journal paper presentations at PacificVis
    ############################################

    # check if a paper was presented at PacificVis
    markPapersByDoi(paperList, pacificVisJournalPresentationDois, "is_vis", "journal pres. @ PacificVis")

    # count all papers so far
    oldVisCounter = visCounter
    visCounter = 0
    for paper in paperList:
        if (paper["is_vis"]): visCounter += 1

    # print PacificVis journal presentations
    print("\nPacificVis journal presentations (up to the conference in " + str(pacificVisJournalPresentationMostRecentYear) + "): " + str(visCounter - oldVisCounter) + " papers", file=f)
    paperNumbersOutputString += "\\newcommand{\\GrsiPacificVisJournalPresentationsCount}{" + str(visCounter - oldVisCounter) + "}\n"
    paperNumbersOutputString += "\\newcommand{\\GrsiPacificVisJournalPresentationsLastYear}{" + str(pacificVisJournalPresentationMostRecentYear) + "}\n"
    for paper in paperList:
        if ((paper["is_vis"]) and (paper["doi"] in pacificVisJournalPresentationDois)): print("https://doi.org/" + str(paper["doi"].ljust(doiPaddingCount) + " -- " + str(paper["title"])), file=f)

    ############################################
    ### proper EuroVis papers
    ############################################

    # check if a paper was a EuroVis CGF paper
    markPapersByDoi(paperList, euroVisPaperDois, "is_vis", "EuroVis")

    # count all papers so far
    oldVisCounter = visCounter
    visCounter = 0
    for paper in paperList:
        if (paper["is_vis"]): visCounter += 1

    # print proper EuroVis papers
    print("\nproper EuroVis papers/STARs (up to the conference in " + str(euroVisPaperMostRecentYear) + "): " + str(visCounter - oldVisCounter) + " papers", file=f)
    paperNumbersOutputString += "\\newcommand{\\GrsiEuroVisPapersCount}{" + str(visCounter - oldVisCounter) + "}\n"
    paperNumbersOutputString += "\\newcommand{\\GrsiEuroVisPapersLastYear}{" + str(euroVisPaperMostRecentYear) + "}\n"
    for paper in paperList:
        if ((paper["is_vis"]) and (paper["doi"] in euroVisPaperDois)): print("https://doi.org/" + str(paper["doi"].ljust(doiPaddingCount) + " -- " + str(paper["title"])), file=f)

    ############################################
    ### journal paper presentations at EuroVis
    ############################################

    # check if a paper was presented at EuroVis
    markPapersByDoi(paperList, euroVisJournalPresentationDois, "is_vis", "journal pres. @ EuroVis")

    # count all papers so far
    oldVisCounter = visCounter
    visCounter = 0
    for paper in paperList:
        if (paper["is_vis"]): visCounter += 1

    # print EuroVis journal presentation papers
    print("\nEuroVis journal presentations (up to the conference in " + str(euroVisJournalPresentationMostRecentYear) + "): " + str(visCounter - oldVisCounter) + " papers", file=f)
    paperNumbersOutputString += "\\newcommand{\\GrsiEuroVisJournalPresentationsCount}{" + str(visCounter - oldVisCounter) + "}\n"
    paperNumbersOutputString += "\\newcommand{\\GrsiEuroVisJournalPresentationsLastYear}{" + str(euroVisJournalPresentationMostRecentYear) + "}\n"
    for paper in paperList:
        if ((paper["is_vis"]) and (paper["doi"] in euroVisJournalPresentationDois)): print("https://doi.org/" + str(paper["doi"].ljust(doiPaddingCount) + " -- " + str(paper["title"])), file=f)

    ############################################
    ### VCBM journal papers (in C&G)
    ############################################

    # check if a paper was a VCBM journal paper
    markPapersByDoi(paperList, vcbmJournalDois, "is_vis", "VCBM C&G")

    # count all papers so far
    oldVisCounter = visCounter
    visCounter = 0
    for paper in paperList:
        if (paper["is_vis"]): visCounter += 1

    # print EuroVis journal presentation papers
    print("\nVCBM journal papers (up to the conference in " + str(vcbmJournalMostRecentYear) + "): " + str(visCounter - oldVisCounter) + " papers", file=f)
    paperNumbersOutputString += "\\newcommand{\\GrsiVcbmCagPapersCount}{" + str(visCounter - oldVisCounter) + "}\n"
    paperNumbersOutputString += "\\newcommand{\\GrsiVcbmCagPapersLastYear}{" + str(vcbmJournalMostRecentYear) + "}\n"
    for paper in paperList:
        if ((paper["is_vis"]) and (paper["doi"] in vcbmJournalDois)): print("https://doi.org/" + str(paper["doi"].ljust(doiPaddingCount) + " -- " + str(paper["title"])), file=f)

    ############################################
    ### C&G special issue papers on VIS conferences
    ############################################

    # check if a paper was a C&G special issue paper
    markPapersByDoi(paperList, cagVisSpecialIssueDois, "is_vis", "C&G special issue")

    # count all papers so far
    oldVisCounter = visCounter
    visCounter = 0
    for paper in paperList:
        if (paper["is_vis"]): visCounter += 1

    # print EuroVis journal presentation papers
    print("\nC&G special issue papers (up to the respective conferences in " + str(cagVisSpecialIssueMostRecentYear) + "): " + str(visCounter - oldVisCounter) + " papers", file=f)
    paperNumbersOutputString += "\\newcommand{\\GrsiCagSpecialIssuesPapersCount}{" + str(visCounter - oldVisCounter) + "}\n"
    paperNumbersOutputString += "\\newcommand{\\GrsiCagSpecialIssuesPapersLastYear}{" + str(cagVisSpecialIssueMostRecentYear) + "}\n"
    for paper in paperList:
        if ((paper["is_vis"]) and (paper["doi"] in cagVisSpecialIssueDois)): print("https://doi.org/" + str(paper["doi"].ljust(doiPaddingCount) + " -- " + str(paper["title"])), file=f)

    ############################################
    ### filter by keywords in the title (and add specific papers)
    ############################################

    # check if a paper is a visusalization paper
    markVisPapersByKeywords(paperList)

    # count all the visualization papers maked by keyword
    visCounter = 0
    for paper in paperList:
        if ("type" in paper.keys()) and (paper["type"] == "keyword"): visCounter += 1

    # print visualization papers maked by keyword
    print("\nadditional papers on visualization topics identified by keyword: " + str(visCounter) + " papers", file=f)
    paperNumbersOutputString += "\\newcommand{\\GrsiVisByKeywordPapersCount}{" + str(visCounter) + "}\n"
    visByKeywordCount = visCounter
    for paper in paperList:
        if ("type" in paper.keys()) and (paper["type"] == "keyword"):
            print("https://doi.org/" + str(paper["doi"].ljust(doiPaddingCount) + " -- " + str(paper["title"])), file=f)
            paperKeywordPapersOutputString += "\\item \\href{https://doi.org/" + paper["doi"] + "}{doi: " + paper["doi"] + "}\n"

    # count the visualization papers maked manually
    visCounter = 0
    for paper in paperList:
        if ("type" in paper.keys()) and (paper["type"] == "manual"): visCounter += 1

    # print visualization papers maked manually
    print("\nadditional manually selected papers that could not be identified by keyword: " + str(visCounter) + " papers", file=f)
    paperNumbersOutputString += "\\newcommand{\\GrsiVisManuallyMarkedPapersCount}{" + str(visCounter) + "}\n"
    paperNumbersOutputString += "\\newcommand{\\GrsiVisKeywordPlusManualPapersCount}{" + str(visCounter + visByKeywordCount) + "}\n"
    visKeywordPlusManualPapersCount = visCounter + visByKeywordCount
    for paper in paperList:
        if ("type" in paper.keys()) and (paper["type"] == "manual"): print("https://doi.org/" + str(paper["doi"].ljust(doiPaddingCount) + " -- " + str(paper["title"])), file=f)

    # count the visualization papers
    visCounter = 0
    for paper in paperList:
        if (paper["is_vis"]): visCounter += 1

    # print visualization papers
    print("\npapers on visualization topics (all of the above): " + str(visCounter) + " papers (may be larger than the sum of the above since we manually re-classified some of the papers to come from more recent VIS or to be presented there in the future)", file=f)
    for paper in paperList:
        if (paper["is_vis"]): print("https://doi.org/" + str(paper["doi"].ljust(doiPaddingCount) + " -- " + str(paper["title"])), file=f)

    print("\n=========================================", file=f)
    print("Papers apparently not about visualization", file=f)
    print("=========================================", file=f)

    # print TVCG papers that are not in the list of visualization papers yet
    print("\nremaining TVCG papers *apparently* not on visualization topics (but some may be presented at IEEE VIS in the future)", file=f)
    for paper in paperList:
        if ( (paper["is_vis"] == False) and ("tvcg." in paper["doi"]) ): print("https://doi.org/" + str(paper["doi"].ljust(doiPaddingCount) + " -- " + str(paper["title"])), file=f)

    # print CGF papers that are not in the list of visualization papers yet
    print("\nremaining CGF papers *apparently* not on visualization topics", file=f)
    for paper in paperList:
        if ( (paper["is_vis"] == False) and ("cgf." in paper["doi"]) ): print("https://doi.org/" + str(paper["doi"].ljust(doiPaddingCount) + " -- " + str(paper["title"])), file=f)

    # print C&G papers that are not in the list of visualization papers yet
    print("\nremaining C&G papers *apparently* not on visualization topics", file=f)
    for paper in paperList:
        if ( (paper["is_vis"] == False) and ("j.cag." in paper["doi"]) ): print("https://doi.org/" + str(paper["doi"].ljust(doiPaddingCount) + " -- " + str(paper["title"])), file=f)

    # print TOG papers that are not in the list of visualization papers yet
    print("\nremaining TOG journal or SIGGRAPH (Asia) conference papers *apparently* not on visualization topics", file=f)
    for paper in paperList:
        if ( (paper["is_vis"] == False) and ("10.1145/" in paper["doi"]) ): print("https://doi.org/" + str(paper["doi"].ljust(doiPaddingCount) + " -- " + str(paper["title"])), file=f)

    # print all othger papers that are not in the list of visualization papers yet
    print("\nremaining papers *apparently* not on visualization topics", file=f)
    for paper in paperList:
        if ( (paper["is_vis"] == False) and not ("10.1145/" in paper["doi"]) and not ("j.cag." in paper["doi"]) and not ("cgf." in paper["doi"]) and not ("tvcg." in paper["doi"]) ): print("https://doi.org/" + str(paper["doi"].ljust(doiPaddingCount) + " -- " + str(paper["title"])), file=f)

    f.close()

# now that we know what is visualization, add the summary to the top of the file
with open(formatted_date + " current-list.txt", "r", encoding='utf-8') as f:
    lines = f.readlines()
    f.close()
lines[1] = lines[1].rstrip() + "\nVisualization papers: " + str(visCounter) + " (i.e., " + str(round(float(visCounter)/float(len(paperList)) * 100.0, 1)) + "%).\n"  # Modify second line with newline
paperNumbersOutputString += "\\newcommand{\\GrsiTotalVisPapers}{" + str(visCounter) + "}\n"
paperNumbersOutputString += "\\newcommand{\\GrsiVisKeywordPlusManualPapersPercentage}{" + str(round(float(visKeywordPlusManualPapersCount)/float(visCounter) * 100.0, 1)) + "}\n"
paperNumbersOutputString += "\\newcommand{\\GrsiPercentageVisPapers}{" + str(round(float(visCounter)/float(len(paperList)) * 100.0, 1)) + "}\n"
with open(formatted_date + " current-list.txt", "w", encoding='utf-8') as f:
    f.writelines(lines)
    f.close()

unmarkPapers(paperList, ["counter"], [None]) # remove the counters for writing
with open(formatted_date + " grsi paper data.json", "w", encoding='utf-8') as f:
    json.dump(paperList, f, indent=4)
with open(dataOutputSubdirectury + "grsi_metadata.json", "w", encoding='utf-8') as f:
    json.dump(grsiMetaData, f, indent=4)

#######################################################
#######################################################
# get/update additional data from DLs
#######################################################
#######################################################
    
# first check if we have all extra data updated, and if not try to update it
with open(dataOutputSubdirectury + "extended_paper_data.json", "r", encoding='utf-8') as f:
    paperListExtended = json.load(f)
    f.close()

# each of the following defines a function to query the data from the publisher's DL APIs, and then return a data item
import query_crossref
import query_acm
import query_elsevier
import query_ieee
# if True: # this line would only be for testing/debugging
if updatingGrsiDataFromWeb: # only then do we need to check (i.e., first run of the day, when we updated the data from the Web)
    # get the needed API keys
    with open("api-keys.json", "r", encoding='utf-8') as f:
        config = json.load(f)
        f.close()
    apiKeyIeee = config['apikey-ieee']
    apiKeyElsevier = config['apikey-elsevier']

    extraDataWasUpdated = False
    for entry in paperList:
        doi = entry["doi"].lower()

        needToUpdateData = False
        oldEntry = {}
        
        if not (doi in paperListExtended.keys()):
            # print("extra data not yet collected for doi " + doi)
            needToUpdateData = True
        else:
            # check if the data is complete
            if (paperListExtended[doi]['volume'] == '') or (paperListExtended[doi]['pages'] == '') or (paperListExtended[doi]['number_of_pages'] < 1 ) or (paperListExtended[doi]['abstract'] == ''):
                # print("!! extra data not yet complete for doi " + doi)
                needToUpdateData = True
                oldEntry = paperListExtended[doi]
        
        if (needToUpdateData) and (doi[0:3] == "10."):
            extraDataWasUpdated = True
            print("We will now try to get or update the extra data for doi " + doi)
            
            newEntry = {}

            # ACM
            if ("10.1145/" in doi):
                # print("This is an ACM paper, so we use the ACM API")
                if (downloadAcmFromCrossref):
                    newEntry = query_crossref.generateEntryForDoi(doi)
                else:
                    newEntry = query_acm.generateEntryForDoi(doi)
            # IEEE
            if ("10.1109/" in doi):
                # print("This is an IEEE paper, so we use the IEEE API")
                newEntry = query_ieee.generateEntryForDoi(doi, apiKeyIeee)
            # Elsevier
            if ("10.1016/" in doi):
                # print("This is an Elsevier paper, so we use the Elsevier API")
                newEntry = query_elsevier.generateEntryForDoi(doi, apiKeyElsevier)
            # Wiley (Crossref?)
            if ("10.1111/" in doi):
                # print("This is a Wiley paper, so we use the Crossref API")
                newEntry = query_crossref.generateEntryForDoi(doi)
                
            if (not bool(newEntry)): print("WARNING: No new data generated when looking up paper (doi: " + doi + "). Please check.")
            else: 
                if bool(oldEntry): # if we had old data already, ensure that we are not loosing any data we had previously (maybe manually) collected
                    for dataItem in oldEntry.keys(): # all genral items
                        if not(dataItem in newEntry.keys()):
                            newEntry[dataItem] = oldEntry[dataItem]
                    for authorOld, authorNew in zip(oldEntry["authors"],newEntry["authors"]): # the list of all authors
                        for dataItem in authorOld.keys(): # all author items
                            if not(dataItem in authorNew.keys()):
                                authorNew[dataItem] = authorOld[dataItem]
                    
                paperListExtended[doi] = newEntry # add or update the data for the doi
                if not("countries" in newEntry.keys()):
                    print("Remember to add the country information to the entry " + doi + ".")

            # for all of them, wait for a bit to avoid triggering any issues with the APIs
            time.sleep(0.5)

    # save the appended database
    if extraDataWasUpdated:
        with open(dataOutputSubdirectury + "extended_paper_data.json", "w", encoding='utf-8') as f:
            json.dump(paperListExtended, f, indent=4)
            f.close()

differenceOfPaperEntries = len(paperList) - len(paperListExtended)
paperNumbersOutputString += "\\newcommand{\\GrsiDifferenceInPaperDatabases}{" + str(differenceOfPaperEntries) + "}\n"

#######################################################
#######################################################
# visualization/plots
#######################################################
#######################################################
if exportVisualizations:
    print("Now for the data analysis and visualization ...")

    # then extract the data we want to visualize, first overall
    journalsAndYears = {'IEEE TVCG': {}, 'ACM ToG': {}, 'Wiley CGF': {}, 'Elsevier C&G': {}, 'Elsevier CAD': {}, 'SIGGRAPH conf.': {}, 'Software Impacts': {}} # with pre-sorting
    earliestYear = grsiMetaData["data_download_year"]
    latestYear = grsiMetaData["data_download_year"]
    for paper in paperList:
        doi = paper["doi"]

        if doi in paperListExtended.keys():
            paperExtended = paperListExtended[doi]
            publicationYear = paperExtended["publication_year"]
            publicationVenue = filterAndShortenJournalNames(paperExtended["journal"])
            if not (publicationVenue in journalsAndYears.keys()): journalsAndYears[publicationVenue] = {}

            if publicationYear in journalsAndYears[publicationVenue].keys(): journalsAndYears[publicationVenue][publicationYear] = journalsAndYears[publicationVenue][publicationYear] + 1
            else: journalsAndYears[publicationVenue][publicationYear] = 1

            if publicationYear < earliestYear: earliestYear = publicationYear
            if publicationYear > latestYear: # ignore the fake in-press year (grsiMetaData["data_download_year"] + 1000)
                if publicationYear != grsiMetaData["data_download_year"] + 1000: latestYear = publicationYear

    order = 0
    dataToPlot = []
    for publicationVenue in journalsAndYears.keys():
        # sort the dictionary
        journalsAndYears[publicationVenue] = dict(sorted(journalsAndYears[publicationVenue].items()))
        order += 1

        # collect all the data for visualization
        listOfYears = list(range(earliestYear, latestYear + 1)) # all the real years, including the latest one yet without the in-press papers
        listOfYears.append(grsiMetaData["data_download_year"] + 1000) # and now do not forget our fake "in-press" year
        for year in listOfYears:
            dataItem = {}
            dataItem["journal"] = publicationVenue
            dataItem["order"] = order
            dataItem["year"] = str(year)
            dataItem["count"] = 0 # as a fall-back, in case there were no publications from this venue in that year
            if year == grsiMetaData["data_download_year"] + 1000:
                dataItem["year"] = "in press"
            if year in journalsAndYears[publicationVenue].keys(): dataItem["count"] = journalsAndYears[publicationVenue][year]
            dataToPlot.append(dataItem)

    plotTimeSeriesPublicationData(dataToPlot, baseName = graphOutputSubdirectury + "replicability_all-by-journal", dataField = "journal", cTitleSpecifier = "journal or conference", yTitleSpecifier = "published journal papers w/ GRS", visPadding = visPadding, legendColumns = 5, chartsToPlot = ["all"], addTicksBetweenYears = True, addNoteBelowLegend = True, noteXOffset = 33)

    # now let's do that again and overwrite the line graph file with the nan hack (see below; which would fail the aggregated plots)
    order = 0
    dataToPlot = []
    for publicationVenue in journalsAndYears.keys():
        # sort the dictionary
        journalsAndYears[publicationVenue] = dict(sorted(journalsAndYears[publicationVenue].items()))
        order += 1

        # collect all the data for visualization
        listOfYears = list(range(earliestYear, latestYear + 1)) # all the real years, including the latest one yet without the in-press papers
        listOfYears.append(grsiMetaData["data_download_year"] + 1000) # and now do not forget our fake "in-press" year
        for year in listOfYears:
            dataItem = {}
            dataItem["journal"] = publicationVenue
            dataItem["order"] = order
            dataItem["year"] = str(year)
            dataItem["count"] = 0 # as a fall-back, in case there were no publications from this venue in that year
            if year == grsiMetaData["data_download_year"] + 1000:
                dataItem["year"] = "in press"
                dataItem["count"] = nan # only for in-press journals do we not want a value plotted if it is 0
            if year in journalsAndYears[publicationVenue].keys(): dataItem["count"] = journalsAndYears[publicationVenue][year]
            dataToPlot.append(dataItem)

    plotTimeSeriesPublicationData(dataToPlot, baseName = graphOutputSubdirectury + "replicability_all-by-journal", dataField = "journal", cTitleSpecifier = "journal or conference", yTitleSpecifier = "published journal papers w/ GRS", visPadding = visPadding, legendColumns = 5, chartsToPlot = ["linegraph"], addTicksBetweenYears = True, addNoteBelowLegend = True, noteXOffset = 33)

    # see how visualization contribution changes over the years    
    visualizationAndYears = {'papers on visualization topics': {}, 'papers not on visualization topics': {}} # with pre-sorting
    dataToPlot = []
    earliestYear = grsiMetaData["data_download_year"]
    latestYear = grsiMetaData["data_download_year"]
    for paper in paperList:
        doi = paper["doi"]
        visType = list(visualizationAndYears.keys())[1]
        if paper["is_vis"]: visType = list(visualizationAndYears.keys())[0]

        if doi in paperListExtended.keys():
            paperExtended = paperListExtended[doi]
            publicationYear = paperExtended["publication_year"]
            if not (visType in visualizationAndYears.keys()): visualizationAndYears[visType] = {}

            if publicationYear in visualizationAndYears[visType].keys(): visualizationAndYears[visType][publicationYear] = visualizationAndYears[visType][publicationYear] + 1
            else: visualizationAndYears[visType][publicationYear] = 1

            if publicationYear < earliestYear: earliestYear = publicationYear
            if publicationYear > latestYear: # ignore the fake in-press year (grsiMetaData["data_download_year"] + 1000)
                if publicationYear != grsiMetaData["data_download_year"] + 1000: latestYear = publicationYear

    order = 0
    for visType in visualizationAndYears.keys():
        # sort the dictionary
        visualizationAndYears[visType] = dict(sorted(visualizationAndYears[visType].items()))
        order += 1

        # collect all the data for visualization
        listOfYears = list(range(earliestYear, latestYear + 1)) # all the real years, including the latest one yet without the in-press papers
        listOfYears.append(grsiMetaData["data_download_year"] + 1000) # and now do not forget our fake "in-press" year
        for year in listOfYears:
            dataItem = {}
            dataItem["is_vis"] = visType
            dataItem["order"] = order
            dataItem["year"] = str(year)
            if year == grsiMetaData["data_download_year"] + 1000: dataItem["year"] = "in press"
            dataItem["count"] = 0 # as a fall-back, in case there were no publications from this venue in that year
            if year in visualizationAndYears[visType].keys(): dataItem["count"] = visualizationAndYears[visType][year]
            dataToPlot.append(dataItem)

    plotTimeSeriesPublicationData(dataToPlot, baseName = graphOutputSubdirectury + "replicability_all-by-visualization", dataField = "is_vis", cTitleSpecifier = "paper classification (by presentation venue and keywords/manual)", yTitleSpecifier = "published journal papers w/ GRS", visPadding = visPadding)

    # now visualize visualization, first by journal
    visJournalListSorted = ['IEEE TVCG', 'ACM ToG', 'Wiley CGF', 'Elsevier C&G'] # with pre-sorting
    journalsAndYears = {}
    for venue in visJournalListSorted: # base the dictionary this time on the list (easier in case we later need to add another journal to the list)
        journalsAndYears[venue] = {}
    earliestYear = grsiMetaData["data_download_year"]
    latestYear = grsiMetaData["data_download_year"]
    for paper in paperList:
        doi = paper["doi"]

        if (doi in paperListExtended.keys()) and (paper["is_vis"]):
            paperExtended = paperListExtended[doi]
            publicationYear = paperExtended["publication_year"]
            publicationVenue = filterAndShortenJournalNames(paperExtended["journal"])
            if not (publicationVenue in journalsAndYears.keys()): journalsAndYears[publicationVenue] = {}

            if publicationYear in journalsAndYears[publicationVenue].keys(): journalsAndYears[publicationVenue][publicationYear] = journalsAndYears[publicationVenue][publicationYear] + 1
            else: journalsAndYears[publicationVenue][publicationYear] = 1

            if publicationYear < earliestYear: earliestYear = publicationYear
            if publicationYear > latestYear: # ignore the fake in-press year (grsiMetaData["data_download_year"] + 1000)
                if publicationYear != grsiMetaData["data_download_year"] + 1000: latestYear = publicationYear

    order = 0
    dataToPlot = []
    for publicationVenue in journalsAndYears.keys():
        # sort the dictionary
        journalsAndYears[publicationVenue] = dict(sorted(journalsAndYears[publicationVenue].items()))
        order += 1

        # collect all the data for visualization
        listOfYears = list(range(earliestYear, latestYear + 1)) # all the real years, including the latest one yet without the in-press papers
        listOfYears.append(grsiMetaData["data_download_year"] + 1000) # and now do not forget our fake "in-press" year
        for year in listOfYears:
            dataItem = {}
            dataItem["journal"] = publicationVenue
            dataItem["order"] = order
            dataItem["year"] = str(year)
            dataItem["count"] = 0 # as a fall-back, in case there were no publications from this venue in that year
            if year == grsiMetaData["data_download_year"] + 1000:
                dataItem["year"] = "in press"
            if year in journalsAndYears[publicationVenue].keys(): dataItem["count"] = journalsAndYears[publicationVenue][year]
            dataToPlot.append(dataItem)

    plotTimeSeriesPublicationData(dataToPlot, baseName = graphOutputSubdirectury + "replicability_visualization-by-journal", dataField = "journal", cTitleSpecifier = "journal", yTitleSpecifier = "published visualization journal papers w/ GRS", visPadding = visPadding, chartsToPlot = ["all"], addTicksBetweenYears = True, addNoteBelowLegend = True, noteXOffset = 33)

    # now let's do that again and overwrite the line graph file with the nan hack (see below; which would fail the aggregated plots)
    order = 0
    dataToPlot = []
    for publicationVenue in journalsAndYears.keys():
        # sort the dictionary
        journalsAndYears[publicationVenue] = dict(sorted(journalsAndYears[publicationVenue].items()))
        order += 1

        # collect all the data for visualization
        listOfYears = list(range(earliestYear, latestYear + 1)) # all the real years, including the latest one yet without the in-press papers
        listOfYears.append(grsiMetaData["data_download_year"] + 1000) # and now do not forget our fake "in-press" year
        for year in listOfYears:
            dataItem = {}
            dataItem["journal"] = publicationVenue
            dataItem["order"] = order
            dataItem["year"] = str(year)
            dataItem["count"] = 0 # as a fall-back, in case there were no publications from this venue in that year
            if year == grsiMetaData["data_download_year"] + 1000:
                dataItem["year"] = "in press"
                dataItem["count"] = nan # only for in-press journals do we not want a value plotted if it is 0
            if year in journalsAndYears[publicationVenue].keys(): dataItem["count"] = journalsAndYears[publicationVenue][year]
            dataToPlot.append(dataItem)

    plotTimeSeriesPublicationData(dataToPlot, baseName = graphOutputSubdirectury + "replicability_visualization-by-journal", dataField = "journal", cTitleSpecifier = "journal", yTitleSpecifier = "published visualization journal papers w/ GRS", visPadding = visPadding, chartsToPlot = ["linegraph"], addTicksBetweenYears = True, addNoteBelowLegend = True, noteXOffset = 33)

    # merge the keywords and manual
    for paper in paperList:
        if ("type" in paper.keys()) and ((paper["type"] == "manual") or (paper["type"] == "keyword")):
            paper["type"] = "keyword/manual"

    # the same visualizations again by journal, but split into papers presented at vis venues and others only classified by keyword/manually
    separationString = ': '
    visVenueName = 'vis classification by presentation venue'
    keywordName = 'vis classification by keyword/manual'
    journalsAndYears = {}
    for venue in visJournalListSorted: # base the dictionary this time on the list (easier in case we later need to add another journal to the list)
        journalsAndYears[venue + separationString + visVenueName] = {}
        journalsAndYears[venue + separationString + keywordName] = {}
    earliestYear = grsiMetaData["data_download_year"]
    latestYear = grsiMetaData["data_download_year"]
    for paper in paperList:
        doi = paper["doi"]

        if (doi in paperListExtended.keys()) and (paper["is_vis"]):
            paperExtended = paperListExtended[doi]
            publicationYear = paperExtended["publication_year"]
            if paper["type"] == "keyword/manual":
                publicationVenue = filterAndShortenJournalNames(paperExtended["journal"]) + separationString + keywordName
            else:
                publicationVenue = filterAndShortenJournalNames(paperExtended["journal"]) + separationString + visVenueName
            if not (publicationVenue in journalsAndYears.keys()): journalsAndYears[publicationVenue] = {}

            if publicationYear in journalsAndYears[publicationVenue].keys(): journalsAndYears[publicationVenue][publicationYear] = journalsAndYears[publicationVenue][publicationYear] + 1
            else: journalsAndYears[publicationVenue][publicationYear] = 1

            if publicationYear < earliestYear: earliestYear = publicationYear
            if publicationYear > latestYear: # ignore the fake in-press year (grsiMetaData["data_download_year"] + 1000)
                if publicationYear != grsiMetaData["data_download_year"] + 1000: latestYear = publicationYear

    order = 0
    dataToPlot = []
    for publicationVenue in journalsAndYears.keys():
        # sort the dictionary
        journalsAndYears[publicationVenue] = dict(sorted(journalsAndYears[publicationVenue].items()))
        order += 1

        # collect all the data for visualization
        listOfYears = list(range(earliestYear, latestYear + 1)) # all the real years, including the latest one yet without the in-press papers
        listOfYears.append(grsiMetaData["data_download_year"] + 1000) # and now do not forget our fake "in-press" year
        for year in listOfYears:
            dataItem = {}
            dataItem["journal"] = publicationVenue
            dataItem["order"] = order
            dataItem["year"] = str(year)
            dataItem["count"] = 0 # as a fall-back, in case there were no publications from this venue in that year
            if year == grsiMetaData["data_download_year"] + 1000:
                dataItem["year"] = "in press"
            if year in journalsAndYears[publicationVenue].keys(): dataItem["count"] = journalsAndYears[publicationVenue][year]
            dataToPlot.append(dataItem)
    
    plotTimeSeriesPublicationData(dataToPlot, baseName = graphOutputSubdirectury + "replicability_visualization-by-journal_plus_type", dataField = "journal", cTitleSpecifier = "journal", yTitleSpecifier = "published visualization journal papers w/ GRS", visPadding = visPadding, colorScheme = "tableau20matching", legendColumns = 2, chartsToPlot = ["all"], addTicksBetweenYears = True, addNoteBelowLegend = True, noteXOffset = 33)

    # now let's do that again and overwrite the line graph file with the nan hack (see below; which would fail the aggregated plots)
    order = 0
    dataToPlot = []
    for publicationVenue in journalsAndYears.keys():
        # sort the dictionary
        journalsAndYears[publicationVenue] = dict(sorted(journalsAndYears[publicationVenue].items()))
        order += 1

        # collect all the data for visualization
        listOfYears = list(range(earliestYear, latestYear + 1)) # all the real years, including the latest one yet without the in-press papers
        listOfYears.append(grsiMetaData["data_download_year"] + 1000) # and now do not forget our fake "in-press" year
        for year in listOfYears:
            dataItem = {}
            dataItem["journal"] = publicationVenue
            dataItem["order"] = order
            dataItem["year"] = str(year)
            dataItem["count"] = 0 # as a fall-back, in case there were no publications from this venue in that year
            if year == grsiMetaData["data_download_year"] + 1000:
                dataItem["year"] = "in press"
                dataItem["count"] = nan # this is a hack to get correct line graphs: only for in-press journals do we not want a value plotted if it is 0
            if year in journalsAndYears[publicationVenue].keys(): dataItem["count"] = journalsAndYears[publicationVenue][year]
            dataToPlot.append(dataItem)
    
    plotTimeSeriesPublicationData(dataToPlot, baseName = graphOutputSubdirectury + "replicability_visualization-by-journal_plus_type", dataField = "journal", cTitleSpecifier = "journal", yTitleSpecifier = "published visualization journal papers w/ GRS", visPadding = visPadding, colorScheme = "tableau20matching", legendColumns = 2, chartsToPlot = ["linegraph"], addTicksBetweenYears = True, addNoteBelowLegend = True, noteXOffset = 33)

    # the same visualizations again by journal but aggregated (without years), and again split into papers presented at vis venues and others only classified by keyword/manually
    separationString = ': '
    visVenueName = 'vis classification by presentation venue'
    keywordName = 'vis classification by keyword/manual'
    journalsOnly = {}
    for venue in visJournalListSorted: # base the dictionary this time on the list (easier in case we later need to add another journal to the list)
        journalsOnly[venue + separationString + visVenueName] = 0
        journalsOnly[venue + separationString + keywordName] = 0

    for paper in paperList:
        doi = paper["doi"]

        if (doi in paperListExtended.keys()) and (paper["is_vis"]):
            paperExtended = paperListExtended[doi]
            publicationYear = paperExtended["publication_year"]
            if paper["type"] == "keyword/manual":
                publicationVenue = filterAndShortenJournalNames(paperExtended["journal"]) + separationString + keywordName
            else:
                publicationVenue = filterAndShortenJournalNames(paperExtended["journal"]) + separationString + visVenueName
            if not (publicationVenue in journalsOnly.keys()): journalsOnly[publicationVenue] = 0

            journalsOnly[publicationVenue] += 1

    # determine some numbers for the paper
    for venue in visJournalListSorted:
        paperNumbersOutputString += "\\newcommand{\\GrsiVisPapersIn" + venue.replace(" ", "").replace("&", "a") + "Total}{" + str(journalsOnly[venue + separationString + visVenueName] + journalsOnly[venue + separationString + keywordName]) + "}\n"
        paperNumbersOutputString += "\\newcommand{\\GrsiVisPapersIn" + venue.replace(" ", "").replace("&", "a") + "Presentation}{" + str(journalsOnly[venue + separationString + visVenueName]) + "}\n"
        paperNumbersOutputString += "\\newcommand{\\GrsiVisPapersIn" + venue.replace(" ", "").replace("&", "a") + "KeywordManual}{" + str(journalsOnly[venue + separationString + keywordName]) + "}\n"
        paperNumbersOutputString += "\\newcommand{\\GrsiVisPapersIn" + venue.replace(" ", "").replace("&", "a") + "PercentagePresentation}{" + str(round(float(journalsOnly[venue + separationString + visVenueName])/float(journalsOnly[venue + separationString + visVenueName] + journalsOnly[venue + separationString + keywordName]) * 100.0, 1)) + "}\n"

    dataToPlot = []
    order = 0
    for publicationVenue in journalsOnly.keys():
        # collect all the data for visualization
        order += 1
        listOfYears = list(range(earliestYear, latestYear + 1)) # all the real years, including the latest one yet without the in-press papers
        listOfYears.append(grsiMetaData["data_download_year"] + 1000) # and now do not forget our fake "in-press" year
        dataItem = {}
        dataItem["journal"] = publicationVenue
        dataItem["order"] = order
        dataItem["year"] = publicationVenue.split(separationString)[0] # this is a hack, because the function called below usually splits things by year, and we want to split by original journal
        dataItem["count"] = journalsOnly[publicationVenue]
        dataToPlot.append(dataItem)

    plotTimeSeriesPublicationData(dataToPlot, baseName = graphOutputSubdirectury + "replicability_visualization-by-journal_plus_type_aggregated", dataField = "journal", cTitleSpecifier = "journal", yTitleSpecifier = "published visualization journal papers w/ GRS", visPadding = visPadding, colorScheme = "tableau20matching", legendColumns = 2, chartsToPlot = ["stackedbargraph", "stackedbargraph-normalized"])

    # now visualize visualization, then by type
    # pre-sorting the order in which we want things
    journalsAndYears = {'IEEE VIS': {}, 'journal pres. @ IEEE VIS': {}, 'EuroVis': {}, 'journal pres. @ EuroVis': {}, 'PacificVis TVCG': {}, 'journal pres. @ PacificVis': {}, 'VCBM C&G': {}, 'C&G special issue': {}, 'keyword/manual': {}}
    earliestYear = grsiMetaData["data_download_year"]
    latestYear = grsiMetaData["data_download_year"]
    for paper in paperList:
        doi = paper["doi"]

        if (doi in paperListExtended.keys()) and (paper["is_vis"]):
            paperExtended = paperListExtended[doi]
            publicationYear = paperExtended["publication_year"]
            publicationType = paper["type"]
            if not (publicationType in journalsAndYears.keys()): journalsAndYears[publicationType] = {}

            if publicationYear in journalsAndYears[publicationType].keys(): journalsAndYears[publicationType][publicationYear] = journalsAndYears[publicationType][publicationYear] + 1
            else: journalsAndYears[publicationType][publicationYear] = 1

            if publicationYear < earliestYear: earliestYear = publicationYear
            if publicationYear > latestYear: # ignore the fake in-press year (grsiMetaData["data_download_year"] + 1000)
                if publicationYear != grsiMetaData["data_download_year"] + 1000: latestYear = publicationYear

    order = 0
    dataToPlot = []
    for publicationType in journalsAndYears.keys():
        # sort the dictionary
        journalsAndYears[publicationType] = dict(sorted(journalsAndYears[publicationType].items()))
        order += 1

        # collect all the data for visualization
        listOfYears = list(range(earliestYear, latestYear + 1)) # all the real years, including the latest one yet without the in-press papers
        listOfYears.append(grsiMetaData["data_download_year"] + 1000) # and now do not forget our fake "in-press" year
        for year in listOfYears:
            dataItem = {}
            dataItem["type"] = publicationType
            dataItem["order"] = order
            dataItem["year"] = str(year)
            dataItem["count"] = 0 # as a fall-back, in case there were no publications from this venue in that year
            if year == grsiMetaData["data_download_year"] + 1000:
                dataItem["year"] = "in press"
            if year in journalsAndYears[publicationType].keys(): dataItem["count"] = journalsAndYears[publicationType][year]
            dataToPlot.append(dataItem)

    plotTimeSeriesPublicationData(dataToPlot, baseName = graphOutputSubdirectury + "replicability_visualization-by-type", dataField = "type", cTitleSpecifier = "classified as visualization by ...", yTitleSpecifier = "published visualization journal papers w/ GRS", colorScheme = "tableau20", legendColumns = 4, visPadding = visPadding, chartsToPlot = ["all"], addTicksBetweenYears = True, addNoteBelowLegend = True, noteXOffset = 33)

    # now let's do that again and overwrite the line graph file with the nan hack (see below; which would fail the aggregated plots)
    order = 0
    dataToPlot = []
    for publicationType in journalsAndYears.keys():
        # sort the dictionary
        journalsAndYears[publicationType] = dict(sorted(journalsAndYears[publicationType].items()))
        order += 1

        # collect all the data for visualization
        listOfYears = list(range(earliestYear, latestYear + 1)) # all the real years, including the latest one yet without the in-press papers
        listOfYears.append(grsiMetaData["data_download_year"] + 1000) # and now do not forget our fake "in-press" year
        for year in listOfYears:
            dataItem = {}
            dataItem["type"] = publicationType
            dataItem["order"] = order
            dataItem["year"] = str(year)
            dataItem["count"] = 0 # as a fall-back, in case there were no publications from this venue in that year
            # some events did not exist before a given time
            if ((publicationType == 'journal pres. @ PacificVis') and (year < 2024)) or ((publicationType == 'VCBM C&G') and (year < 2018)) or ((publicationType == 'C&G special issue') and (year < 2020)):
                dataItem["count"] = nan # then no values exist
            if year == grsiMetaData["data_download_year"] + 1000:
                dataItem["year"] = "in press"
                dataItem["count"] = nan # only for in-press journals do we not want a value plotted if it is 0
            if year in journalsAndYears[publicationType].keys(): dataItem["count"] = journalsAndYears[publicationType][year]
            dataToPlot.append(dataItem)

    plotTimeSeriesPublicationData(dataToPlot, baseName = graphOutputSubdirectury + "replicability_visualization-by-type", dataField = "type", cTitleSpecifier = "classified as visualization by ...", yTitleSpecifier = "published visualization journal papers w/ GRS", colorScheme = "tableau20", legendColumns = 4, visPadding = visPadding, chartsToPlot = ["linegraph"], addTicksBetweenYears = True, addNoteBelowLegend = True, noteXOffset = 33)

    # pie chart that compares the vis content from the rest, for all journals
    journalsAndCounts = {}
    # pre-fill the data table so that we have the order of the jorunal we ultimatiely want
    for journal in ['IEEE TVCG', 'ACM ToG', 'Wiley CGF', 'Elsevier C&G', 'Elsevier CAD', 'SIGGRAPH conf.', 'Software Impacts']:
        journalsAndCounts[journal] = { "journal": journal, "is_vis": 0, "not_vis": 0 }
    for paper in paperList:
        doi = paper["doi"]
        if (doi in paperListExtended.keys()):
            paperExtended = paperListExtended[doi]
            journal = filterAndShortenJournalNames(paperExtended["journal"])
            if not (journal in journalsAndCounts.keys()): journalsAndCounts[journal] = { "journal": journal, "is_vis": 0, "not_vis": 0 }

            if (paper["is_vis"]): journalsAndCounts[journal]["is_vis"] = journalsAndCounts[journal]["is_vis"] + 1
            else: journalsAndCounts[journal]["not_vis"] = journalsAndCounts[journal]["not_vis"] + 1

    color_number = 0
    colors = generateColorArrayFromColorScheme("tableau10lightened", lightenFactor=0.4)
    dataToPlot = { "journal": [], "value": [], "order": [], "order2": [] }
    for journal in journalsAndCounts:
        dataToPlot["journal"].append(journalsAndCounts[journal]["journal"] + "–is vis (" + str(round(100.0 * journalsAndCounts[journal]["is_vis"] / (journalsAndCounts[journal]["is_vis"] + journalsAndCounts[journal]["not_vis"]), 1)) + "%)")
        dataToPlot["value"].append(journalsAndCounts[journal]["is_vis"])
        dataToPlot["order"].append(color_number * 2)
        dataToPlot["order2"].append(color_number)
        dataToPlot["journal"].append(journalsAndCounts[journal]["journal"] + "–not vis (" + str(round(100.0 * journalsAndCounts[journal]["not_vis"] / (journalsAndCounts[journal]["is_vis"] + journalsAndCounts[journal]["not_vis"]), 1)) + "%)")
        dataToPlot["value"].append(journalsAndCounts[journal]["not_vis"])
        dataToPlot["order"].append(color_number * 2 + 1)
        dataToPlot["order2"].append(len(journalsAndCounts) + color_number)
        color_number += 1

    source = pd.DataFrame(dataToPlot)
    pieChart = alt.Chart(source).mark_arc().encode(
        theta = alt.Theta("value:Q"),
        color = alt.Color("journal:N", sort=None, title="journals (incl. their vis %’s)"),
        order = alt.Order("order:Q")
    ).configure_range(
        category=alt.RangeScheme(colors)
    ).properties(
        padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding}
    )
    pieChart.save(graphOutputSubdirectury + 'replicability_visualization-piechart-by-journal.pdf')

    source = pd.DataFrame(dataToPlot)
    pieChart = alt.Chart(source).mark_arc().encode(
        theta = alt.Theta("value:Q"),
        color = alt.Color("journal:N", sort=None, title="journals (incl. their vis %’s)"),
        order = alt.Order("order2:Q")
    ).configure_range(
        category=alt.RangeScheme(colors)
    ).properties(
        padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding}
    )
    pieChart.save(graphOutputSubdirectury + 'replicability_visualization-piechart-by-vis-status.pdf')

    # the same data, but using the plotTimeSeriesPublicationData function, such that we get an aggregated view
    separationString = '–'
    dataToPlot_old = dataToPlot
    dataToPlot = []
    order = 0
    for i in range(0, len(dataToPlot_old["journal"])):
        # collect all the data for visualization
        order += 1
        dataItem = {}
        dataItem["journal"] = dataToPlot_old["journal"][i]
        dataItem["order"] = order
        dataItem["year"] = dataToPlot_old["journal"][i].split(separationString)[0] # this is a hack, because the function called below usually splits things by year, and we want to split by original journal
        dataItem["count"] = dataToPlot_old["value"][i]
        dataToPlot.append(dataItem)

    plotTimeSeriesPublicationData(dataToPlot, baseName = graphOutputSubdirectury + "replicability_all-by-journal_aggregated", dataField = "journal", cTitleSpecifier = "journal", yTitleSpecifier = "published journal papers w/ GRS", visPadding = visPadding, colorScheme = "tableau20matching", legendColumns = 2, labelAngle = -20, chartsToPlot = ["stackedbargraph", "stackedbargraph-normalized"])

    # the same data again, but with all non-vis counts moved to the vis counts, so that we just see the summary
    separationString = '–'
    dataToPlot_old = dataToPlot
    dataToPlot = []
    order = 0
    for i in range(0, len(dataToPlot_old)):
        # collect all the data for visualization
        if dataToPlot_old[i]["journal"].split(separationString)[1].split(" ")[0] == "is":
            order += 1
            dataItem = {}
            dataItem["journal"] = dataToPlot_old[i]["journal"].split(separationString)[0]
            dataItem["order"] = order
            dataItem["year"] = dataToPlot_old[i]["year"]
            dataItem["count"] = dataToPlot_old[i]["count"] + dataToPlot_old[i+1]["count"]
            dataToPlot.append(dataItem)

    plotTimeSeriesPublicationData(dataToPlot, baseName = graphOutputSubdirectury + "replicability_all-by-journal_aggregated_plain", dataField = "journal", cTitleSpecifier = "journal", yTitleSpecifier = "published journal papers w/ GRS", visPadding = visPadding, colorScheme = "tableau10", legendColumns = 5, labelAngle = -20, chartsToPlot = ["stackedbargraph", "stackedbargraph-normalized"])

    # now we want to see the numbers and percentages of replicability for our significant venues
    visVenuesAndReplicability = {}
    startYear = 2016 # it does not make sense before, since the GRSI starts in 2016 (but there do not seem to be vis papers among the GRSI papers in 2016, and the official start is 2017)
    endYear = grsiMetaData["data_download_year"] # the current year of the data
    venues = ['IEEE VIS', 'journal pres. @ IEEE VIS', 'EuroVis', 'journal pres. @ EuroVis', 'PacificVis TVCG', 'journal pres. @ PacificVis', 'VCBM C&G', 'C&G special issue']
    for venue in venues:
        visVenuesAndReplicability[venue] = {}
        for year in range(startYear, endYear + 1):
            visVenuesAndReplicability[venue][year] = {}
            visVenuesAndReplicability[venue][year]["is_replicable"] = 0
            visVenuesAndReplicability[venue][year]["not_replicable"] = 0
    dataToPlot = []
    replicableDois = []
    for paper in paperList:
        doi = paper["doi"]
        if doi[0:3] == "10.": replicableDois.append(doi)

    # pure VIS papers from vispubdata
    vispubdataLoadedDoisForChecking = []
    with open('input/vispubdata.csv', 'r', encoding="utf-8") as csvfile:
        venue = venues[0]
        # create a CSV reader object
        reader = csv.DictReader(csvfile)
        # iterate over the rows
        for row in reader:
            paperDoi = row['DOI'].lower()
            vispubdataLoadedDoisForChecking.append(paperDoi)
            year = int(row['Year']) # this year is the year of presentation at VIS, not article publication, so what we want
            if year >= startYear and year <= endYear:
                if paperDoi in replicableDois: visVenuesAndReplicability[venue][year]["is_replicable"] += 1
                else:  visVenuesAndReplicability[venue][year]["not_replicable"] += 1
        csvfile.close()

    # when vispubdata is not current, we can also use TVCG's CSV export of the VIS issues to add the missing data
    tvcgFilenamesList = glob.glob('input/tvcg-[0-9][0-9][0-9][0-9]-vol-[0-9][0-9]-no-[0-9][0-9].csv')
    for tvcgFilename in tvcgFilenamesList:
        with open(tvcgFilename, 'r', encoding="utf-8") as csvfile:
            # create a CSV reader object
            reader = csv.DictReader(csvfile)
            # iterate over the rows
            for row in reader:
                paperDoi = row['DOI'].lower()
                if paperDoi not in vispubdataLoadedDoisForChecking: # so that we do not duplicate the loaded dois
                    vispubdataLoadedDoisForChecking.append(paperDoi)
                    year = int(row['Publication Year']) - 1 # the year in the data is the year of publication in TVCG, not presentation at VIS, so we need to deduct 1
                    if year >= startYear and year <= endYear:
                        if paperDoi in replicableDois: visVenuesAndReplicability[venue][year]["is_replicable"] += 1
                        else:  visVenuesAndReplicability[venue][year]["not_replicable"] += 1
            csvfile.close()

    # another alternative: a manually created spreadsheet of accepted VIS papers (I added this mainly for the BELIV paper submission)
    acceptedVisPapersFilenamesList = glob.glob('input/vis-[0-9][0-9][0-9][0-9].csv')
    for acceptedVisPapersFilename in acceptedVisPapersFilenamesList:
        with open(acceptedVisPapersFilename, 'r', encoding="utf-8") as csvfile:
            # create a CSV reader object
            reader = csv.DictReader(csvfile)
            # iterate over the rows
            for row in reader:
                visDoi = row['DOI'].lower()
                if visDoi not in vispubdataLoadedDoisForChecking: # so that we do not duplicate the loaded dois (should not happen if we use fake DOIs)
                    vispubdataLoadedDoisForChecking.append(visDoi)
                    year = int(row['Year']) # the year in the data is the year of presentation at VIS
                    if year >= startYear and year <= endYear:
                        if visDoi in replicableDois: visVenuesAndReplicability[venue][year]["is_replicable"] += 1
                        else:  visVenuesAndReplicability[venue][year]["not_replicable"] += 1
            csvfile.close()


    # IEEE VIS journal presentations
    with open('input/vis_journal_presentations.csv', 'r', encoding="utf-8") as csvfile:
        venue = venues[1]
        # create a CSV reader object
        reader = csv.DictReader(csvfile)
        # iterate over the rows
        for row in reader:
            paperDoi = row['doi'].lower()
            year = int(row['year']) # this year is the year of presentation at VIS, not article publication, so what we want
            if year >= startYear and year <= endYear:
                if paperDoi in replicableDois: visVenuesAndReplicability[venue][year]["is_replicable"] += 1
                else:  visVenuesAndReplicability[venue][year]["not_replicable"] += 1
        csvfile.close()

    # PacificVis TVCG papers
    with open('input/pacificvis_tvcg.csv', 'r', encoding="utf-8") as csvfile:
        venue = venues[4]
        # create a CSV reader object
        reader = csv.DictReader(csvfile)
        # iterate over the rows
        for row in reader:
            paperDoi = row['doi'].lower()
            year = int(row['year'])
            if year >= startYear and year <= endYear:
                if paperDoi in replicableDois: visVenuesAndReplicability[venue][year]["is_replicable"] += 1
                else:  visVenuesAndReplicability[venue][year]["not_replicable"] += 1
        csvfile.close()

    # PacificVis journal presentations
    with open('input/pacificvis_journal_presentations.csv', 'r', encoding="utf-8") as csvfile:
        venue = venues[5]
        # create a CSV reader object
        reader = csv.DictReader(csvfile)
        # iterate over the rows
        for row in reader:
            paperDoi = row['doi'].lower()
            year = int(row['year'])
            if year >= startYear and year <= endYear:
                if paperDoi in replicableDois: visVenuesAndReplicability[venue][year]["is_replicable"] += 1
                else:  visVenuesAndReplicability[venue][year]["not_replicable"] += 1
        csvfile.close()

    # EuroVis journal presentations
    with open('input/eurovis_journal_presentations.csv', 'r', encoding="utf-8") as csvfile:
        venue = venues[3]
        # create a CSV reader object
        reader = csv.DictReader(csvfile)
        # iterate over the rows
        for row in reader:
            paperDoi = row['doi'].lower()
            year = int(row['year'])
            if year >= startYear and year <= endYear:
                if paperDoi in replicableDois: visVenuesAndReplicability[venue][year]["is_replicable"] += 1
                else:  visVenuesAndReplicability[venue][year]["not_replicable"] += 1
        csvfile.close()

    # proper EuroVis papers
    with pd.ExcelFile('input/EuroVisFull_CGF.xlsx') as xls:
        venue = venues[2]
        sheetX = xls.parse(0) # select the first sheet
        targetCellName = 'dc.identifier.doi[]'
        numberOfRows = len(sheetX[targetCellName])
        for i in range(0, numberOfRows):
            paperDoi = sheetX[targetCellName][i]
            year = int(sheetX['dc.date.issued[en_US]'][i])
            abstract = str(sheetX['dc.description.abstract[en_US]'][i])
            if (len(abstract) > 0) and (abstract != 'nan'): # avoid including frontmatter that has no abstract
                if not ((type(doi) == str) and (doi != 0) and (doi != '')):
                    paperDoi = sheetX['dc.identifier.uri[en_US]'][i].replace('http://dx.doi.org/', '')
                if year >= startYear and year <= endYear:
                    if paperDoi in replicableDois: visVenuesAndReplicability[venue][year]["is_replicable"] += 1
                    else:  visVenuesAndReplicability[venue][year]["not_replicable"] += 1
        xls.close()
    # for 2024 and onward, we just use the bibtex export from the EG DL, converted to CSV
    with open('input/eurovis.csv', 'r', encoding="utf-8") as csvfile:
        venue = venues[2]
        # create a CSV reader object
        reader = csv.DictReader(csvfile)
        # iterate over the rows
        for row in reader:
            paperDoi = row['doi'].lower()
            year = int(row['year'])
            if year >= startYear and year <= endYear:
                if paperDoi in replicableDois: visVenuesAndReplicability[venue][year]["is_replicable"] += 1
                else:  visVenuesAndReplicability[venue][year]["not_replicable"] += 1
        csvfile.close()

    # EuroVis STAR papers, we'll consider them as normal EuroVis papers
    with pd.ExcelFile('input/EuroVisSTARS_CGF.xlsx') as xls:
        venue = venues[2]
        sheetX = xls.parse(0) # select the first sheet
        targetCellName = 'dc.identifier.doi[]'
        numberOfRows = len(sheetX[targetCellName])
        for i in range(0, numberOfRows):
            paperDoi = sheetX[targetCellName][i]
            year = int(sheetX['dc.date.issued[]'][i])
            abstract = str(sheetX['dc.description.abstract[en_US]'][i])
            if (len(abstract) > 0) and (abstract != 'nan'): # avoid including frontmatter that has no abstract
                if not ((type(doi) == str) and (doi != 0) and (doi != '')):
                    paperDoi = sheetX['dc.identifier.uri[]'][i].replace('http://dx.doi.org/', '')
                if year >= startYear and year <= endYear:
                    if paperDoi in replicableDois: visVenuesAndReplicability[venue][year]["is_replicable"] += 1
                    else:  visVenuesAndReplicability[venue][year]["not_replicable"] += 1
        xls.close()

    # VCBM journal papers (C&G)
    with open('input/vcbm_cag.csv', 'r', encoding="utf-8") as csvfile:
        venue = venues[6]
        # create a CSV reader object
        reader = csv.DictReader(csvfile)
        # iterate over the rows
        for row in reader:
            paperDoi = row['doi'].lower()
            year = int(row['conf. year'])
            if year >= startYear and year <= endYear:
                if paperDoi in replicableDois: visVenuesAndReplicability[venue][year]["is_replicable"] += 1
                else:  visVenuesAndReplicability[venue][year]["not_replicable"] += 1
        csvfile.close()

    # C&G special issue papers on VIS venues
    with open('input/envirvis_cag.csv', 'r', encoding="utf-8") as csvfile:
        venue = venues[7]
        # create a CSV reader object
        reader = csv.DictReader(csvfile)
        # iterate over the rows
        for row in reader:
            paperDoi = row['doi'].lower()
            year = int(row['conf. year'])
            if year >= startYear and year <= endYear:
                if paperDoi in replicableDois: visVenuesAndReplicability[venue][year]["is_replicable"] += 1
                else:  visVenuesAndReplicability[venue][year]["not_replicable"] += 1
        csvfile.close()
    with open('input/eurova_cag.csv', 'r', encoding="utf-8") as csvfile:
        venue = venues[7]
        # create a CSV reader object
        reader = csv.DictReader(csvfile)
        # iterate over the rows
        for row in reader:
            paperDoi = row['doi'].lower()
            year = int(row['conf. year'])
            if year >= startYear and year <= endYear:
                if paperDoi in replicableDois: visVenuesAndReplicability[venue][year]["is_replicable"] += 1
                else:  visVenuesAndReplicability[venue][year]["not_replicable"] += 1
        csvfile.close()
    with open('input/molva_cag.csv', 'r', encoding="utf-8") as csvfile:
        venue = venues[7]
        # create a CSV reader object
        reader = csv.DictReader(csvfile)
        # iterate over the rows
        for row in reader:
            paperDoi = row['doi'].lower()
            year = int(row['conf. year'])
            if year >= startYear and year <= endYear:
                if paperDoi in replicableDois: visVenuesAndReplicability[venue][year]["is_replicable"] += 1
                else:  visVenuesAndReplicability[venue][year]["not_replicable"] += 1
        csvfile.close()

    venues = ['IEEE VIS', 'journal pres. @ IEEE VIS', 'EuroVis', 'journal pres. @ EuroVis', 'PacificVis TVCG', 'journal pres. @ PacificVis', 'VCBM C&G', 'C&G special issue']
    colors = generateColorArrayFromColorScheme("tableau10paired_lightened", lightenFactor=0.5)
    dataToPlot = []
    yearCountCheck = {}
    for year in range(startYear, endYear + 1): yearCountCheck[year] = 0
    for venue in venues: # must be less than the numbers of colors in the scheme
        for year in range(startYear, endYear + 1):
            count1 = visVenuesAndReplicability[venue][year]["is_replicable"]
            count2 = visVenuesAndReplicability[venue][year]["not_replicable"]
            yearCountCheck[year] += count1 + count2
            # remove data points for when events did not happen (yet)
            if (count1 == 0) and (count2 == 0): # if there was no papers, then the event did not happen and there could also not have been a GRS for its papers
                count1 = nan
                count2 = nan
            dataToPlot.append({"venue": venue, "name": venue + ": w/ GRS", "year": year, "replicable": True, "count": count1})#, "order": color_number * 2, "order2": color_number})
            dataToPlot.append({"venue": venue, "name": venue + ": w/o GRS", "year": year, "replicable": False, "count": count2})#, "order": color_number * 2 + 1, "order2": len(venues) + color_number})
    altairData = pd.DataFrame(dataToPlot)

    chart = alt.Chart(altairData).mark_bar().encode(
        x = alt.X('year:N', title=None).axis(tickWidth=0, labelAngle=0),#domain=False, 
        y = alt.Y('sum(count):Q', title='published visualization journal papers'),
        color = alt.Color('name:N', sort=None, title="visualization venues"),
        xOffset=alt.XOffset('venue:N', sort=None),
        order = alt.Order("venue:Q")
    )
    # add vertical tick marks between the years for better reading
    # this is a total hack, we create another chart but don't actually display it, neither its axis, and only get the tick marks from it at year boundaries
    lastYearEmptyOffset = 0
    if (yearCountCheck[endYear] == 0): lastYearEmptyOffset = -1
    lines = (
        alt.Chart(altairData).mark_rule().encode(
            x = alt.X("year:Q", axis=None, title=None).axis(ticks=True, labels=False, grid=False, domain=False, orient='bottom',tickCount=endYear - startYear + 2 + lastYearEmptyOffset).scale(domain=[startYear - 0.1, endYear + lastYearEmptyOffset + 1.1]),
            color= alt.value("#ffffff"),
            size=alt.value(0.0)
        )
    )
    chart = chart+lines # layer the two charts
    # rest of processing
    chart = chart.configure_range(
        category=alt.RangeScheme(colors)
    ).configure_legend(orient='right', direction='vertical'
    ).configure_view(strokeWidth=0).properties(
        padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding},
        width=600,
        height=300
    ).properties(title=alt.TitleParams( # this way of adding a note below the legend is also a total hack because there is no other way to add a text field there
        ['Please note that the colors/entries'],
        subtitle=['always follow the order of the legend.'], # this hack limits the note to two lines only, unfortunately, multiline is not supported by PDF export
        baseline='bottom',
        orient='bottom',
        anchor='start',
        fontWeight='normal',
        subtitleFontWeight='normal',
        fontSize=10,
        subtitleFontSize=10,
        dy=-80, dx=657 # emprirically found, should remain the same as long as the width and height in configure_view stay the same
    ))

    chart.save(graphOutputSubdirectury + 'replicability_visualization-by-venue-stackedbargraph.pdf')

    chart = alt.Chart(altairData, width={"step": 15}).mark_bar().encode(
        x = alt.X('year:N', title=None).axis(tickWidth=0, labelAngle=0),#domain=False, 
        y = alt.Y('sum(count):Q', title='published visualization journal papers').stack("normalize"),
        color = alt.Color('name:N', sort=None, title="visualization venues"),
        xOffset=alt.XOffset('venue:N', sort=None),
        order = alt.Order("venue:Q")
    )
    # add vertical tick marks between the years for better reading
    # this is a total hack, we create another chart but don't actually display it, neither its axis, and only get the tick marks from it at year boundaries
    lines = (
        alt.Chart(altairData).mark_rule().encode(
            x = alt.X("year:Q", axis=None, title=None).axis(ticks=True, labels=False, grid=False, domain=False, orient='bottom',tickCount=endYear - startYear + 2 + lastYearEmptyOffset).scale(domain=[startYear - 0.1, endYear + lastYearEmptyOffset + 1.1]),
            color= alt.value("#ffffff"),
            size=alt.value(0.0)
        )
    )
    chart = chart+lines # layer the two charts
    # rest of processing
    chart = chart.configure_range(
        category=alt.RangeScheme(colors)
    ).configure_legend(orient='right', direction='vertical'
    ).configure_view(strokeWidth=0).properties(
        padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding},
        width=600,
        height=300
    ).properties(title=alt.TitleParams( # this way of adding a note below the legend is also a total hack because there is no other way to add a text field there
        ['Please note that the colors/entries'],
        subtitle=['always follow the order of the legend.'],
        baseline='bottom',
        orient='bottom',
        anchor='start',
        fontWeight='normal',
        subtitleFontWeight='normal',
        fontSize=10,
        subtitleFontSize=10,
        dy=-80, dx=666 # emprirically found, should remain the same as long as the width and height in configure_view stay the same
    ))
    chart.save(graphOutputSubdirectury + 'replicability_visualization-by-venue-stackedbargraph-normalized.pdf')

    dataToPlot = []
    for venue in venues: # redo the data for the line graph, because this is not stacked
        for year in range(startYear, endYear + 1):
            count1 = visVenuesAndReplicability[venue][year]["is_replicable"]
            count2 = visVenuesAndReplicability[venue][year]["not_replicable"] + visVenuesAndReplicability[venue][year]["is_replicable"]
            # remove data points for when events did not happen (yet)
            if (count2 == 0): # if there was no papers, then the event did not happen and there could also not have been a GRS for its papers
                count1 = nan
                count2 = nan
            dataToPlot.append({"venue": venue, "name": venue + ": w/ GRS", "year": year, "replicable": True, "count": count1})#, "order": color_number * 2, "order2": color_number})
            dataToPlot.append({"venue": venue, "name": venue + ": all papers", "year": year, "replicable": False, "count": count2})#, "order": color_number * 2 + 1, "order2": len(venues) + color_number})
    altairData = pd.DataFrame(dataToPlot)

    chart = alt.Chart(altairData, width={"step": 15}).mark_line().encode(
        x = alt.X('year:N', title=None).axis(tickWidth=0, labelAngle=0),#domain=False, 
        y = alt.Y('sum(count):Q', title='published visualization journal papers'),
        color = alt.Color('name:N', sort=None, title="visualization venues"),
        order = alt.Order("venue:Q")
    ).configure_range(
        category=alt.RangeScheme(colors)
    ).configure_legend(orient='right', direction='vertical', titleLimit=0, labelLimit=myLabelLimit
    ).configure_view(strokeWidth=0).properties(
        padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding},
        width=600,
        height=300
    )
    chart.save(graphOutputSubdirectury + 'replicability_visualization-by-venue-linegraph.pdf')

    # histogram of GRS per person for vis people
    dataToPlotAll = []
    dataToPlotVis = []
    lastPaperCount = 0
    newDataItemAll = {}
    newDataItemVis = {}
    for author in reversed(authorCountsSortedByNumbers):
        # authorCount = authorCountsSortedByNumbers[author]
        if authorCountsSortedByNumbers[author] > lastPaperCount:
            if bool(newDataItemAll):
                dataToPlotAll.append(newDataItemAll)
                newDataItemAll = {}
            if bool(newDataItemVis):
                dataToPlotVis.append(newDataItemVis)
                newDataItemVis = {}
            lastPaperCount = authorCountsSortedByNumbers[author]
            newDataItemAll['paper_count'] = lastPaperCount
            newDataItemAll['people']= 0
            newDataItemVis['paper_count'] = lastPaperCount
            newDataItemVis['people']= 0
        newDataItemAll['people'] += 1
        # if (authorCount == 8 or authorCount == 9):
        #     print(author + ": " + str(authorCount) + " - " + str(authorCounts[author]) + " - " + str(newDataItemAll['people']))
        visPercentage = 100.0*float(authorVisPapers[author])/float(authorCounts[author])
        if (visPercentage >= 50.0): newDataItemVis['people'] += 1
    dataToPlotAll.append(newDataItemAll)
    dataToPlotVis.append(newDataItemVis)

    altairData = pd.DataFrame(dataToPlotAll)
    chart = alt.Chart(altairData).mark_bar(size=20).encode(
        x = alt.X('paper_count:Q', axis=alt.Axis(title='GRS stamps per person', grid=False)).scale(domain=[0.5, dataToPlotAll[-1]['paper_count'] + 0.5]),
        y = alt.Y('people:Q', title='# of GRS authors, logarithmic').scale(type="log", domain=[0.9, topLimitAuthorPlots])
    ).configure_view(strokeWidth=0).properties(
        padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding},
        width=400,
        height=300
    )
    chart.save(graphOutputSubdirectury + 'replicability_all-histogram-stamps-per-person.pdf')

    altairData = pd.DataFrame(dataToPlotVis)
    chart = alt.Chart(altairData).mark_bar(size=20).encode(
        x = alt.X('paper_count:Q', axis=alt.Axis(title='GRS stamps per person', grid=False)).scale(domain=[0.5, dataToPlotVis[-1]['paper_count'] + 0.5]),
        y = alt.Y('people:Q', title='# of GRS visualization authors (≥ 50% vis papers), log.').scale(type="log", domain=[0.9, topLimitAuthorPlots])
    ).configure_view(strokeWidth=0).properties(
        padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding},
        width=400,
        height=300
    )
    chart.save(graphOutputSubdirectury + 'replicability_visualization-histogram-stamps-per-person.pdf')

    # histogram of vis percentages per person
    dataToPlot = []
    binCounter = 0
    for bin in list(authorVisNovisHistogramData.keys()):
        newDataItem = {}
        lowerEnd = round(float(binCounter) * 100.0 / float(numberOfAuhorHistogramBins), 1)
        upperEnd = round(float(binCounter + 1) * 100.0 / float(numberOfAuhorHistogramBins), 1)
        newDataItem['bin_range'] = str(lowerEnd) + "%–" + str(upperEnd) + "%"
        newDataItem['people'] = authorVisNovisHistogramData[bin]
        dataToPlot.append(newDataItem)
        binCounter += 1

    altairData = pd.DataFrame(dataToPlot)
    chart = alt.Chart(altairData).mark_bar(size=20).encode(
        x = alt.X('bin_range:N', axis=alt.Axis(title="percentage range of visualization papers per author", grid=False, labelAngle=-25), sort=None), #.scale(domain=[0.5, float(binCounter) + 0.5]),
        y = alt.Y('people:Q', title='# of authors, logarithmic').scale(type="log", domain=[0.9, topLimitAuthorPlots])
    ).configure_view(strokeWidth=0).properties(
        padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding},
        width=400,
        height=300
    )
    chart.save(graphOutputSubdirectury + 'replicability-histogram-people-vis-percentages.pdf')

    altairData = pd.DataFrame(dataToPlot)
    chart = alt.Chart(altairData).mark_bar(size=20).encode(
        x = alt.X('bin_range:N', axis=alt.Axis(title="percentage range of visualization papers per author", grid=False, labelAngle=-25), sort=None), #.scale(domain=[0.5, float(binCounter) + 0.5]),
        y = alt.Y('people:Q', title='# of authors')#.scale(type="log", domain=[0.9, topLimitAuthorPlots])
    ).configure_view(strokeWidth=0).properties(
        padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding},
        width=400,
        height=300
    )
    chart.save(graphOutputSubdirectury + 'replicability-histogram-people-vis-percentages-nolog.pdf')

    # histogram of vis percentages per person
    dataToPlot = []
    binCounter = 0
    for bin in list(authorVisNovisHistogramDataTwoPlus.keys()):
        newDataItem = {}
        lowerEnd = round(float(binCounter) * 100.0 / float(numberOfAuhorHistogramBins), 1)
        upperEnd = round(float(binCounter + 1) * 100.0 / float(numberOfAuhorHistogramBins), 1)
        newDataItem['bin_range'] = str(lowerEnd) + "%–" + str(upperEnd) + "%"
        newDataItem['people'] = authorVisNovisHistogramDataTwoPlus[bin]
        dataToPlot.append(newDataItem)
        binCounter += 1

    altairData = pd.DataFrame(dataToPlot)
    chart = alt.Chart(altairData).mark_bar(size=20).encode(
        x = alt.X('bin_range:N', axis=alt.Axis(title="percentage range of visualization papers per author (≥ 2 papers)", grid=False, labelAngle=-25), sort=None), #.scale(domain=[0.5, float(binCounter) + 0.5]),
        y = alt.Y('people:Q', title='# of authors, logarithmic').scale(type="log", domain=[0.9, topLimitAuthorPlots])
    ).configure_view(strokeWidth=0).properties(
        padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding},
        width=400,
        height=300
    )
    chart.save(graphOutputSubdirectury + 'replicability-histogram-people-vis-percentages-multiple-papers.pdf')

    altairData = pd.DataFrame(dataToPlot)
    chart = alt.Chart(altairData).mark_bar(size=20).encode(
        x = alt.X('bin_range:N', axis=alt.Axis(title="percentage range of visualization papers per author (≥ 2 papers)", grid=False, labelAngle=-25), sort=None), #.scale(domain=[0.5, float(binCounter) + 0.5]),
        y = alt.Y('people:Q', title='# of authors')#.scale(type="log", domain=[0.9, topLimitAuthorPlots])
    ).configure_view(strokeWidth=0).properties(
        padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding},
        width=400,
        height=300
    )
    chart.save(graphOutputSubdirectury + 'replicability-histogram-people-vis-percentages-multiple-papers-nolog.pdf')

    # load country names for visualization (from https://github.com/lukes/ISO-3166-Countries-with-Regional-Codes/blob/master/all/all.csv)
    countryNames = {}
    countryNamesSentence = {}
    with open('input/country-names.csv', 'r', encoding="utf-8") as csvfile:
        # create a CSV reader object
        reader = csv.DictReader(csvfile)
        # iterate over the rows
        for row in reader:
            countryNames[row['alpha-2']] = row['name'] \
                .replace('United States of America', 'United States') \
                .replace('United Kingdom of Great Britain and Northern Ireland', 'UK') \
                .replace('Korea, Republic of', 'South Korea') \
                .replace('Taiwan, Province of China', 'Taiwan') \
                .replace('Viet Nam', 'Vietnam') \
                .replace('Czechia', 'Czech Republic')
            countryNamesSentence[row['alpha-2']] = countryNames[row['alpha-2']] \
                .replace('United States', 'the United States') \
                .replace('Netherlands', 'the Netherlands') \
                .replace('Czech Republic', 'the Czech Republic') \
                .replace('UK', 'the UK') \
                .replace('United Arab Emirates', 'the United Arab Emirates')
        csvfile.close()

    # analyze the contributions by country (all of GRSI)
    # need new color palette based on the code below
    # see color schemes at https://vega.github.io/vega/docs/schemes/
    # base the colors on "category10" which are nice, solid colors
    # then lighten the colors step by step, in 3 additional steps, like with "category20b" (maybe also use one darkening step first)
    # basically use modulo to figure out which iteration we are in, and then decide to darken or lighten the color
    # geneate at least 40 colors, maybe even 50 (even though categorial schemes should not have more than 10 colors, but since these are sorted this does not matter)
    # another alternative is to combine "category20b" and "category20c" to a single scale, which we actulally now do below
    colorsGrsiPerCountry = generateColorArrayFromColorScheme("category20b_plus_category20c")

    grsiPerCountryProportional = {}
    grsiPerCountrySum = {}
    papersWithContryInformation = 0.0
    for paperIndex in paperListExtended.keys():
        doi = paperListExtended[paperIndex]["doi"]
        authors = paperListExtended[paperIndex]["authors"]
        contributionPerAuthor = 1.0 / len(authors)
        countryAlreadyCountedForPaper = {}
        paperHasCountryInfo = False
        for author in authors:
            if "countries" in author.keys(): # we may not have the whole information for everyone
                paperHasCountryInfo = True
                contributionOfSingleAuthorCountry = contributionPerAuthor / len(author["countries"])
                for country in author["countries"]:
                    if not (country in grsiPerCountryProportional.keys()): grsiPerCountryProportional[country] = 0.0
                    if not (country in grsiPerCountrySum.keys()): grsiPerCountrySum[country] = 0
                    grsiPerCountryProportional[country] += contributionOfSingleAuthorCountry
                    # grsiPerCountrySum[country] += 1
                    if not (country in countryAlreadyCountedForPaper.keys()):
                        countryAlreadyCountedForPaper[country] = 1
                        grsiPerCountrySum[country] += 1
        if paperHasCountryInfo: papersWithContryInformation += 1.0

    if bool(grsiPerCountryProportional):
        grsiPerCountryProportional = dict(sorted(grsiPerCountryProportional.items(), key=lambda kv: kv[1], reverse = True))
        dataToPlot = []
        order = 0
        for country in grsiPerCountryProportional.keys():
            dataItem = {}
            dataItem['country'] = countryNames[country] + " (" + str(round(100.0 * grsiPerCountryProportional[country]/papersWithContryInformation, 1)) + "%)"
            dataItem['value'] = grsiPerCountryProportional[country]
            dataItem['order'] = order
            order += 1
            paperNumbersOutputString += "\\newcommand{\\GrsiCountryPieChartOverallNo" + digitToNameSequence(order) + "Name}{" + countryNamesSentence[country] + "}\n"
            paperNumbersOutputString += "\\newcommand{\\GrsiCountryPieChartOverallNo" + digitToNameSequence(order) + "Percentage}{" + str(round(100.0 * grsiPerCountryProportional[country]/papersWithContryInformation, 1)) + "}\n"
            dataToPlot.append(dataItem)

        source = pd.DataFrame(dataToPlot)
        pieChart = alt.Chart(source).mark_arc().encode(
            theta = alt.Theta("value:Q"),
            color = alt.Color("country:N", sort=None, title="proportional GRSI country contribution (all)"),#.scale(scheme="tableau20"),
            order = alt.Order("order:Q")
        ).configure_range(
           category=alt.RangeScheme(colorsGrsiPerCountry)
        ).properties(
            padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding}
        ).configure_legend(columns=2, symbolLimit=50, titleLimit=0, labelLimit=myLabelLimit)
        pieChart.save(graphOutputSubdirectury + 'replicability_all-piechart-by-country-proportional.pdf')

        grsiPerCountrySum = dict(sorted(grsiPerCountrySum.items(), key=lambda kv: kv[1], reverse = True))
        dataToPlot = []
        order = 0
        for country in grsiPerCountrySum.keys():
            dataItem = {}
            dataItem['country'] = countryNames[country] + " (" + str(grsiPerCountrySum[country]) + ")"
            dataItem['value'] = grsiPerCountrySum[country]
            dataItem['order'] = order
            order += 1
            dataToPlot.append(dataItem)

        source = pd.DataFrame(dataToPlot)
        pieChart = alt.Chart(source).mark_arc().encode(
            theta = alt.Theta("value:Q"),
            color = alt.Color("country:N", sort=None, title="absolute GRSI country contribution (all)"),#.scale(scheme="tableau20"),
            order = alt.Order("order:Q")
        ).configure_range(
           category=alt.RangeScheme(colorsGrsiPerCountry)
        ).properties(
            padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding}
        ).configure_legend(columns=2, symbolLimit=50, titleLimit=0, labelLimit=myLabelLimit)
        pieChart.save(graphOutputSubdirectury + 'replicability_all-piechart-by-country-absolute.pdf')

        colorsGrsiPerCountryLookup = {}
        colorsGrsiPerCountryThresholded = []
        colorsGrsiPerCountryWholeListIndex = 0
        if makeMainPieChartsComparable:
            # before we continue, we need to decide on a single color map for all thresholded pie charts
            # that means first we figure out which countries we need to take care of (hack: manual specification with some intention on the color matching to the extended tableau10 scale)
            countriesBeyondThreshold = ["US", "NL", "CN", "IT", "FR", "DE", "GB", "CA", "SG", "IL", "SE", "AT", "NO"] # , "BR", "IN" in the order of the color map as it comes next
            # this means we need at least 12 hues that are not gray, so tableau10 is not good enouch (and its last entry is essentually gray), but let's still start with it
            colorsGrsiPerCountryWholeList = generateColorArrayFromColorScheme("tableau10")[0:9]
            # add some more colors we can use
            colorsGrsiPerCountryWholeList.append('#2ea3b8') # manually specified to match tableau10 stile, but as another unique color
            colorsGrsiPerCountryWholeList.append('#7864b9') # manually specified to match tableau10 stile, but as another unique color
            colorsGrsiPerCountryWholeList.append('#9fac33') # manually specified to match tableau10 stile, but as another unique color
            colorsGrsiPerCountryWholeList.append('#bf518a') # manually specified to match tableau10 stile, but as another unique color
            colorsGrsiPerCountryWholeList += generateColorArrayFromColorScheme("set3")[0:8] # emergency pastel colors for if more countries need to be shown (not ideal color choice)
            colorsGrsiPerCountryWholeList += generateColorArrayFromColorScheme("set3")[10:12] # emergency pastel colors for if more countries need to be shown (not ideal color choice)
            # now let's generate a county-color lookup list
            for country in countriesBeyondThreshold: # this assumes that we have more colors in colorsGrsiPerCountryWholeList than countries in countriesBeyondThreshold
                colorsGrsiPerCountryLookup[country] = colorsGrsiPerCountryWholeList[colorsGrsiPerCountryWholeListIndex]
                colorsGrsiPerCountryWholeListIndex += 1

        # thresholded version for the proportional one
        if makeMainPieChartsComparable: colorsGrsiPerCountryThresholded = []
        else: colorsGrsiPerCountryThresholded = generateColorArrayFromColorScheme("tableau10")
        grsiPerCountryProportional = dict(sorted(grsiPerCountryProportional.items(), key=lambda kv: kv[1], reverse = True))
        dataToPlot = []
        order = 0
        otherContribution = 0.0
        otherCount = 0
        for country in grsiPerCountryProportional.keys():
            if makeMainPieChartsComparable:
                if country in colorsGrsiPerCountryLookup.keys(): colorsGrsiPerCountryThresholded.append(colorsGrsiPerCountryLookup[country])
                else: 
                    if (colorsGrsiPerCountryWholeListIndex < len(colorsGrsiPerCountryWholeList)):
                        colorsGrsiPerCountryLookup[country] = colorsGrsiPerCountryWholeList[colorsGrsiPerCountryWholeListIndex]
                        colorsGrsiPerCountryWholeListIndex += 1
                        colorsGrsiPerCountryThresholded.append(colorsGrsiPerCountryLookup[country])
                    else:             
                        colorsGrsiPerCountryThresholded.append(neutralGray) # this is the fallback position if we ran out of colors
            dataItem = {}
            proportion = grsiPerCountryProportional[country]/papersWithContryInformation
            if (proportion >= countryPieChartThreshold * 0.01):
                dataItem['country'] = countryNames[country] + " (" + str(round(100.0 * proportion, 1)) + "%)"
                dataItem['value'] = grsiPerCountryProportional[country]
                dataItem['order'] = order
                dataToPlot.append(dataItem)
            else:
                if (dataToPlot[-1]['country'] != "other"): # if needed create the "other" entry
                    dataItem['country'] = "other"
                    dataItem['value'] = 0.0
                    dataItem['order'] = order
                    dataToPlot.append(dataItem)
                    colorsGrsiPerCountryThresholded[order] = neutralGray # the "other" category gets a neutral gray
                # at this point the last item should be the "other" item, only need to update the value
                dataToPlot[-1]['value'] += grsiPerCountryProportional[country]
                otherContribution += proportion
                otherCount += 1
            order += 1
        # at the end update the name with the sum of the contribution
        dataToPlot[-1]['country'] = str(otherCount) + " other countries < " + str(countryPieChartThreshold) + "% each (" + str(round(100.0 * otherContribution, 1)) + "%)"

        source = pd.DataFrame(dataToPlot)
        pieChart = alt.Chart(source).mark_arc().encode(
            theta = alt.Theta("value:Q"),
            color = alt.Color("country:N", sort=None, title="proportional GRSI country contribution (all)"),#.scale(scheme="tableau20"),
            order = alt.Order("order:Q")
        ).configure_range(
           category=alt.RangeScheme(colorsGrsiPerCountryThresholded)
        ).properties(
            padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding}
        ).configure_legend(columns=1, symbolLimit=50, titleLimit=0, labelLimit=myLabelLimit)
        pieChart.save(graphOutputSubdirectury + 'replicability_all-piechart-by-country-thresholded-proportional.pdf')

    # analyze the contributions by country (only visualization)

    # first copy tableau20
    colorsGrsiPerCountryVsualization = generateColorArrayFromColorScheme("tableau20")
    # some additional pastel colors
    for newColor in ["#617957", "#a5d0a3", "#dfdfa1", "#fefad7", "#55a5be", "#a2d9ed"]: colorsGrsiPerCountryVsualization.append(newColor)
        
    grsiPerCountryProportional = {}
    grsiPerCountrySum = {}
    papersWithContryInformation = 0
    for paper in paperList:
        doi = paper["doi"]
        if paper['is_vis'] and doi in paperListExtended.keys():
            authors = paperListExtended[doi]["authors"]
            contributionPerAuthor = 1.0 / len(authors)
            countryAlreadyCountedForPaper = {}
            paperHasCountryInfo = False
            for author in authors:
                if "countries" in author.keys(): # we may not have the whole information for everyone
                    paperHasCountryInfo = True
                    contributionOfSingleAuthorCountry = contributionPerAuthor / len(author["countries"])
                    for country in author["countries"]:
                        if not (country in grsiPerCountryProportional.keys()): grsiPerCountryProportional[country] = 0.0
                        if not (country in grsiPerCountrySum.keys()): grsiPerCountrySum[country] = 0
                        grsiPerCountryProportional[country] += contributionOfSingleAuthorCountry
                        # grsiPerCountrySum[country] += 1
                        if not (country in countryAlreadyCountedForPaper.keys()):
                            countryAlreadyCountedForPaper[country] = 1
                            grsiPerCountrySum[country] += 1
            if paperHasCountryInfo: papersWithContryInformation += 1
    
    if bool(grsiPerCountryProportional):
        grsiPerCountryProportional = dict(sorted(grsiPerCountryProportional.items(), key=lambda kv: kv[1], reverse = True))
        dataToPlot = []
        order = 0
        for country in grsiPerCountryProportional.keys():
            dataItem = {}
            dataItem['country'] = countryNames[country] + " (" + str(round(100.0 * grsiPerCountryProportional[country]/papersWithContryInformation, 1)) + "%)"
            dataItem['value'] = grsiPerCountryProportional[country]
            dataItem['order'] = order
            order += 1
            paperNumbersOutputString += "\\newcommand{\\GrsiCountryPieChartVisNo" + digitToNameSequence(order) + "Name}{" + countryNamesSentence[country] + "}\n"
            paperNumbersOutputString += "\\newcommand{\\GrsiCountryPieChartVisNo" + digitToNameSequence(order) + "Percentage}{" + str(round(100.0 * grsiPerCountryProportional[country]/papersWithContryInformation, 1)) + "}\n"
            dataToPlot.append(dataItem)

        source = pd.DataFrame(dataToPlot)
        pieChart = alt.Chart(source).mark_arc().encode(
            theta = alt.Theta("value:Q"),
            color = alt.Color("country:N", sort=None, title="proportional GRSI country contribution (vis.)"),#.scale(scheme="tableau20"),
            order = alt.Order("order:Q")
        ).configure_range(
           category=alt.RangeScheme(colorsGrsiPerCountryVsualization)
        ).properties(
            padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding}
        ).configure_legend(columns=2, symbolLimit=50, titleLimit=0, labelLimit=myLabelLimit)
        pieChart.save(graphOutputSubdirectury + 'replicability_visualization-piechart-by-country-proportional.pdf')

        grsiPerCountrySum = dict(sorted(grsiPerCountrySum.items(), key=lambda kv: kv[1], reverse = True))
        dataToPlot = []
        order = 0
        for country in grsiPerCountrySum.keys():
            dataItem = {}
            dataItem['country'] = countryNames[country] + " (" + str(grsiPerCountrySum[country]) + ")"
            dataItem['value'] = grsiPerCountrySum[country]
            dataItem['order'] = order
            order += 1
            dataToPlot.append(dataItem)

        source = pd.DataFrame(dataToPlot)
        pieChart = alt.Chart(source).mark_arc().encode(
            theta = alt.Theta("value:Q"),
            color = alt.Color("country:N", sort=None, title="absolute GRSI country contribution (vis.)"),#.scale(scheme="tableau20"),
            order = alt.Order("order:Q")
        ).configure_range(
           category=alt.RangeScheme(colorsGrsiPerCountryVsualization)
        ).properties(
            padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding}
        ).configure_legend(columns=2, symbolLimit=50, titleLimit=0, labelLimit=myLabelLimit)
        pieChart.save(graphOutputSubdirectury + 'replicability_visualization-piechart-by-country-absolute.pdf')

        # thresholded version for the proportional one
        if makeMainPieChartsComparable: colorsGrsiPerCountryThresholded = []
        else: colorsGrsiPerCountryThresholded = generateColorArrayFromColorScheme("tableau10")
        grsiPerCountryProportional = dict(sorted(grsiPerCountryProportional.items(), key=lambda kv: kv[1], reverse = True))
        dataToPlot = []
        order = 0
        otherContribution = 0.0
        otherCount = 0
        for country in grsiPerCountryProportional.keys():
            if makeMainPieChartsComparable:
                if country in colorsGrsiPerCountryLookup.keys(): colorsGrsiPerCountryThresholded.append(colorsGrsiPerCountryLookup[country])
                else: 
                    if (colorsGrsiPerCountryWholeListIndex < len(colorsGrsiPerCountryWholeList)):
                        colorsGrsiPerCountryLookup[country] = colorsGrsiPerCountryWholeList[colorsGrsiPerCountryWholeListIndex]
                        colorsGrsiPerCountryWholeListIndex += 1
                        colorsGrsiPerCountryThresholded.append(colorsGrsiPerCountryLookup[country])
                    else:             
                        colorsGrsiPerCountryThresholded.append(neutralGray) # this is the fallback position if we ran out of colors
            dataItem = {}
            proportion = grsiPerCountryProportional[country]/papersWithContryInformation
            if (proportion >= countryPieChartThreshold * 0.01):
                dataItem['country'] = countryNames[country] + " (" + str(round(100.0 * proportion, 1)) + "%)"
                dataItem['value'] = grsiPerCountryProportional[country]
                dataItem['order'] = order
                dataToPlot.append(dataItem)
            else:
                if (dataToPlot[-1]['country'] != "other"): # if needed create the "other" entry
                    dataItem['country'] = "other"
                    dataItem['value'] = 0.0
                    dataItem['order'] = order
                    dataToPlot.append(dataItem)
                    colorsGrsiPerCountryThresholded[order] = neutralGray # the "other" category gets a neutral gray
                # at this point the last item should be the "other" item, only need to update the value
                dataToPlot[-1]['value'] += grsiPerCountryProportional[country]
                otherContribution += proportion
                otherCount += 1
            order += 1
        # at the end update the name with the sum of the contribution
        dataToPlot[-1]['country'] = str(otherCount) + " other countries < " + str(countryPieChartThreshold) + "% each (" + str(round(100.0 * otherContribution, 1)) + "%)"

        source = pd.DataFrame(dataToPlot)
        pieChart = alt.Chart(source).mark_arc().encode(
            theta = alt.Theta("value:Q"),
            color = alt.Color("country:N", sort=None, title="proportional GRSI country contribution (vis.)"),#.scale(scheme="tableau20"),
            order = alt.Order("order:Q")
        ).configure_range(
           category=alt.RangeScheme(colorsGrsiPerCountryThresholded)
        ).properties(
            padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding}
        ).configure_legend(columns=1, symbolLimit=50, titleLimit=0, labelLimit=myLabelLimit)
        pieChart.save(graphOutputSubdirectury + 'replicability_visualization-piechart-by-country-thresholded-proportional.pdf')

    # analyze the contributions by country (all of GRSI, but only by senior author)
    grsiPerCountryProportional = {}
    grsiPerCountrySum = {}
    papersWithContryInformation = 0.0
    for paperIndex in paperListExtended.keys():
        doi = paperListExtended[paperIndex]["doi"]
        authors = paperListExtended[paperIndex]["authors"]
        countryAlreadyCountedForPaper = {}
        paperHasCountryInfo = False
        author = authors[-1] # we assume that the last author is the senior author
        if "countries" in author.keys(): # we may not have the whole information for everyone
            paperHasCountryInfo = True
            contributionOfSingleAuthorCountry = 1.0 / len(author["countries"])
            for country in author["countries"]:
                if not (country in grsiPerCountryProportional.keys()): grsiPerCountryProportional[country] = 0.0
                if not (country in grsiPerCountrySum.keys()): grsiPerCountrySum[country] = 0
                grsiPerCountryProportional[country] += contributionOfSingleAuthorCountry
                # grsiPerCountrySum[country] += 1
                if not (country in countryAlreadyCountedForPaper.keys()):
                    countryAlreadyCountedForPaper[country] = 1
                    grsiPerCountrySum[country] += 1
        if paperHasCountryInfo: papersWithContryInformation += 1.0

    if bool(grsiPerCountryProportional):
        grsiPerCountryProportional = dict(sorted(grsiPerCountryProportional.items(), key=lambda kv: kv[1], reverse = True))
        dataToPlot = []
        order = 0
        for country in grsiPerCountryProportional.keys():
            dataItem = {}
            dataItem['country'] = countryNames[country] + " (" + str(round(100.0 * grsiPerCountryProportional[country]/papersWithContryInformation, 1)) + "%)"
            dataItem['value'] = grsiPerCountryProportional[country]
            dataItem['order'] = order
            order += 1
            paperNumbersOutputString += "\\newcommand{\\GrsiCountryPieChartOverallSeniorNo" + digitToNameSequence(order) + "Name}{" + countryNamesSentence[country] + "}\n"
            paperNumbersOutputString += "\\newcommand{\\GrsiCountryPieChartOverallSeniorNo" + digitToNameSequence(order) + "Percentage}{" + str(round(100.0 * grsiPerCountryProportional[country]/papersWithContryInformation, 1)) + "}\n"
            dataToPlot.append(dataItem)

        source = pd.DataFrame(dataToPlot)
        pieChart = alt.Chart(source).mark_arc().encode(
            theta = alt.Theta("value:Q"),
            color = alt.Color("country:N", sort=None, title="proportional GRSI country contrib. (all, last authors)"),#.scale(scheme="tableau20"),
            order = alt.Order("order:Q")
        ).configure_range(
           category=alt.RangeScheme(colorsGrsiPerCountry)
        ).properties(
            padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding}
        ).configure_legend(columns=2, symbolLimit=50, titleLimit=0, labelLimit=myLabelLimit)
        pieChart.save(graphOutputSubdirectury + 'replicability_all-piechart-by-country-senior-only-proportional.pdf')

        grsiPerCountrySum = dict(sorted(grsiPerCountrySum.items(), key=lambda kv: kv[1], reverse = True))
        dataToPlot = []
        order = 0
        for country in grsiPerCountrySum.keys():
            dataItem = {}
            dataItem['country'] = countryNames[country] + " (" + str(grsiPerCountrySum[country]) + ")"
            dataItem['value'] = grsiPerCountrySum[country]
            dataItem['order'] = order
            order += 1
            dataToPlot.append(dataItem)

        source = pd.DataFrame(dataToPlot)
        pieChart = alt.Chart(source).mark_arc().encode(
            theta = alt.Theta("value:Q"),
            color = alt.Color("country:N", sort=None, title="absolute GRSI country contrib. (all, last authors)"),#.scale(scheme="tableau20"),
            order = alt.Order("order:Q")
        ).configure_range(
           category=alt.RangeScheme(colorsGrsiPerCountry)
        ).properties(
            padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding}
        ).configure_legend(columns=2, symbolLimit=50, titleLimit=0, labelLimit=myLabelLimit)
        pieChart.save(graphOutputSubdirectury + 'replicability_all-piechart-by-country-senior-only-absolute.pdf')

        # thresholded version for the proportional one
        if makeMainPieChartsComparable: colorsGrsiPerCountryThresholded = []
        else: colorsGrsiPerCountryThresholded = generateColorArrayFromColorScheme("tableau10")
        grsiPerCountryProportional = dict(sorted(grsiPerCountryProportional.items(), key=lambda kv: kv[1], reverse = True))
        dataToPlot = []
        order = 0
        otherContribution = 0.0
        otherCount = 0
        for country in grsiPerCountryProportional.keys():
            if makeMainPieChartsComparable:
                if country in colorsGrsiPerCountryLookup.keys(): colorsGrsiPerCountryThresholded.append(colorsGrsiPerCountryLookup[country])
                else: 
                    if (colorsGrsiPerCountryWholeListIndex < len(colorsGrsiPerCountryWholeList)):
                        colorsGrsiPerCountryLookup[country] = colorsGrsiPerCountryWholeList[colorsGrsiPerCountryWholeListIndex]
                        colorsGrsiPerCountryWholeListIndex += 1
                        colorsGrsiPerCountryThresholded.append(colorsGrsiPerCountryLookup[country])
                    else:             
                        colorsGrsiPerCountryThresholded.append(neutralGray) # this is the fallback position if we ran out of colors
            dataItem = {}
            proportion = grsiPerCountryProportional[country]/papersWithContryInformation
            if (proportion >= countryPieChartThreshold * 0.01):
                dataItem['country'] = countryNames[country] + " (" + str(round(100.0 * proportion, 1)) + "%)"
                dataItem['value'] = grsiPerCountryProportional[country]
                dataItem['order'] = order
                dataToPlot.append(dataItem)
            else:
                if (dataToPlot[-1]['country'] != "other"): # if needed create the "other" entry
                    dataItem['country'] = "other"
                    dataItem['value'] = 0.0
                    dataItem['order'] = order
                    dataToPlot.append(dataItem)
                    colorsGrsiPerCountryThresholded[order] = neutralGray # the "other" category gets a neutral gray
                # at this point the last item should be the "other" item, only need to update the value
                dataToPlot[-1]['value'] += grsiPerCountryProportional[country]
                otherContribution += proportion
                otherCount += 1
            order += 1
        # at the end update the name with the sum of the contribution
        dataToPlot[-1]['country'] = str(otherCount) + " other countries < " + str(countryPieChartThreshold) + "% each (" + str(round(100.0 * otherContribution, 1)) + "%)"

        source = pd.DataFrame(dataToPlot)
        pieChart = alt.Chart(source).mark_arc().encode(
            theta = alt.Theta("value:Q"),
            color = alt.Color("country:N", sort=None, title="proportional GRSI country contribution (all, last authors)"),#.scale(scheme="tableau20"),
            order = alt.Order("order:Q")
        ).configure_range(
           category=alt.RangeScheme(colorsGrsiPerCountryThresholded)
        ).properties(
            padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding}
        ).configure_legend(columns=1, symbolLimit=50, titleLimit=0, labelLimit=myLabelLimit)
        pieChart.save(graphOutputSubdirectury + 'replicability_all-piechart-by-country-senior-only-thresholded-proportional.pdf')

    grsiPerCountryProportional = {}
    grsiPerCountrySum = {}
    papersWithContryInformation = 0
    for paper in paperList:
        doi = paper["doi"]
        countryAlreadyCountedForPaper = {}
        if paper['is_vis'] and doi in paperListExtended.keys():
            authors = paperListExtended[doi]["authors"]
            paperHasCountryInfo = False
            author = authors[-1]
            if "countries" in author.keys(): # we may not have the whole information for everyone
                paperHasCountryInfo = True
                contributionOfSingleAuthorCountry = 1.0 / len(author["countries"])
                for country in author["countries"]:
                    if not (country in grsiPerCountryProportional.keys()): grsiPerCountryProportional[country] = 0.0
                    if not (country in grsiPerCountrySum.keys()): grsiPerCountrySum[country] = 0
                    grsiPerCountryProportional[country] += contributionOfSingleAuthorCountry
                    # grsiPerCountrySum[country] += 1
                    if not (country in countryAlreadyCountedForPaper.keys()):
                        countryAlreadyCountedForPaper[country] = 1
                        grsiPerCountrySum[country] += 1
            if paperHasCountryInfo: papersWithContryInformation += 1
    
    if bool(grsiPerCountryProportional):
        grsiPerCountryProportional = dict(sorted(grsiPerCountryProportional.items(), key=lambda kv: kv[1], reverse = True))
        dataToPlot = []
        order = 0
        for country in grsiPerCountryProportional.keys():
            dataItem = {}
            dataItem['country'] = countryNames[country] + " (" + str(round(100.0 * grsiPerCountryProportional[country]/papersWithContryInformation, 1)) + "%)"
            dataItem['value'] = grsiPerCountryProportional[country]
            dataItem['order'] = order
            order += 1
            paperNumbersOutputString += "\\newcommand{\\GrsiCountryPieChartVisSeniorNo" + digitToNameSequence(order) + "Name}{" + countryNamesSentence[country] + "}\n"
            paperNumbersOutputString += "\\newcommand{\\GrsiCountryPieChartVisSeniorNo" + digitToNameSequence(order) + "Percentage}{" + str(round(100.0 * grsiPerCountryProportional[country]/papersWithContryInformation, 1)) + "}\n"
            dataToPlot.append(dataItem)

        source = pd.DataFrame(dataToPlot)
        pieChart = alt.Chart(source).mark_arc().encode(
            theta = alt.Theta("value:Q"),
            color = alt.Color("country:N", sort=None, title="proportional GRSI country contrib. (vis., last authors)"),#.scale(scheme="tableau20"),
            order = alt.Order("order:Q")
        ).configure_range(
           category=alt.RangeScheme(colorsGrsiPerCountryVsualization)
        ).properties(
            padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding}
        ).configure_legend(columns=2, symbolLimit=50, titleLimit=0, labelLimit=myLabelLimit)
        pieChart.save(graphOutputSubdirectury + 'replicability_visualization-piechart-by-country-senior-only-proportional.pdf')

        grsiPerCountrySum = dict(sorted(grsiPerCountrySum.items(), key=lambda kv: kv[1], reverse = True))
        dataToPlot = []
        order = 0
        for country in grsiPerCountrySum.keys():
            dataItem = {}
            dataItem['country'] = countryNames[country] + " (" + str(grsiPerCountrySum[country]) + ")"
            dataItem['value'] = grsiPerCountrySum[country]
            dataItem['order'] = order
            order += 1
            dataToPlot.append(dataItem)

        source = pd.DataFrame(dataToPlot)
        pieChart = alt.Chart(source).mark_arc().encode(
            theta = alt.Theta("value:Q"),
            color = alt.Color("country:N", sort=None, title="absolute GRSI country contrib. (vis., last authors)"),#.scale(scheme="tableau20"),
            order = alt.Order("order:Q")
        ).configure_range(
           category=alt.RangeScheme(colorsGrsiPerCountryVsualization)
        ).properties(
            padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding}
        ).configure_legend(columns=2, symbolLimit=50, titleLimit=0, labelLimit=myLabelLimit)
        pieChart.save(graphOutputSubdirectury + 'replicability_visualization-piechart-by-country-senior-only-absolute.pdf')

        # thresholded version for the proportional one
        if makeMainPieChartsComparable: colorsGrsiPerCountryThresholded = []
        else: colorsGrsiPerCountryThresholded = generateColorArrayFromColorScheme("tableau10")
        grsiPerCountryProportional = dict(sorted(grsiPerCountryProportional.items(), key=lambda kv: kv[1], reverse = True))
        dataToPlot = []
        order = 0
        otherContribution = 0.0
        otherCount = 0
        for country in grsiPerCountryProportional.keys():
            if makeMainPieChartsComparable:
                if country in colorsGrsiPerCountryLookup.keys(): colorsGrsiPerCountryThresholded.append(colorsGrsiPerCountryLookup[country])
                else: 
                    if (colorsGrsiPerCountryWholeListIndex < len(colorsGrsiPerCountryWholeList)):
                        colorsGrsiPerCountryLookup[country] = colorsGrsiPerCountryWholeList[colorsGrsiPerCountryWholeListIndex]
                        colorsGrsiPerCountryWholeListIndex += 1
                        colorsGrsiPerCountryThresholded.append(colorsGrsiPerCountryLookup[country])
                    else:             
                        colorsGrsiPerCountryThresholded.append(neutralGray) # this is the fallback position if we ran out of colors
            dataItem = {}
            proportion = grsiPerCountryProportional[country]/papersWithContryInformation
            if (proportion >= countryPieChartThreshold * 0.01):
                dataItem['country'] = countryNames[country] + " (" + str(round(100.0 * proportion, 1)) + "%)"
                dataItem['value'] = grsiPerCountryProportional[country]
                dataItem['order'] = order
                dataToPlot.append(dataItem)
            else:
                if (dataToPlot[-1]['country'] != "other"): # if needed create the "other" entry
                    dataItem['country'] = "other"
                    dataItem['value'] = 0.0
                    dataItem['order'] = order
                    dataToPlot.append(dataItem)
                    colorsGrsiPerCountryThresholded[order] = neutralGray # the "other" category gets a neutral gray
                # at this point the last item should be the "other" item, only need to update the value
                dataToPlot[-1]['value'] += grsiPerCountryProportional[country]
                otherContribution += proportion
                otherCount += 1
            order += 1
        # at the end update the name with the sum of the contribution
        dataToPlot[-1]['country'] = str(otherCount) + " other countries < " + str(countryPieChartThreshold) + "% each (" + str(round(100.0 * otherContribution, 1)) + "%)"

        source = pd.DataFrame(dataToPlot)
        pieChart = alt.Chart(source).mark_arc().encode(
            theta = alt.Theta("value:Q"),
            color = alt.Color("country:N", sort=None, title="proportional GRSI country contribution (vis., last authors)"),#.scale(scheme="tableau20"),
            order = alt.Order("order:Q")
        ).configure_range(
           category=alt.RangeScheme(colorsGrsiPerCountryThresholded)
        ).properties(
            padding={"left": visPadding, "right": visPadding, "bottom": visPadding+visPaddingBottomExtra, "top": visPadding}
        ).configure_legend(columns=1, symbolLimit=50, titleLimit=0, labelLimit=myLabelLimit)
        pieChart.save(graphOutputSubdirectury + 'replicability_visualization-piechart-by-country-senior-only-thresholded-proportional.pdf')

if doNameChecking:
    # some additional analysis to check for name spelling (to clean the data we got from GRSI): compare names from to DL entries
    for paper in paperList:
        doi = paper["doi"]
        if doi in paperListExtended.keys():
            authorsGrsi = paper["authors"].split(", ")
            authorsDL = paperListExtended[doi]["authors"]
            authorsDLString = ""
            for author in authorsDL:
                authorsDLString = authorsDLString + author["given"] + " "
                authorsDLString = authorsDLString + author["family"] + ", "
            authorsDLString = authorsDLString[:-2]

            if len(authorsGrsi) != len(authorsDL):
                print("Author number does match for paper: " + doi)
                print("  Authors from GRSI: " + paper["authors"])
                print("  Authors from DL: " + authorsDLString)
            else:
                # there are the same number of people in both lists, so then we need to check if they are identical
                authorsDL = authorsDLString.split(", ")
                for authorGrsi, authorDl in zip(authorsGrsi, authorsDL):
                    if (authorGrsi != authorDl) and (authorDl[1] != '.'): # some DLs abreviate the first names, and this does not help
                        print("For doi " + doi + " we found a mismatch between \"" + authorGrsi + "\" (GRSI) and \"" + authorDl + "\" (DL).")
                        # print("GRSI: \"" + str(authorsGrsi) + "\"; DL: \"" + str(authorsDL) + "\"")
                        # smallestLength = len(authorGrsi)
                        # if (len(authorDl) < smallestLength): smallestLength = len(authorDl)
                        # for i in range(0, smallestLength):
                        #     if authorGrsi[i] != authorDl[i]: print(str(i) + ": " + authorGrsi[i] + "--" + authorDl[i])

    # some additional analysis to check for name spelling (to clean the data we got from GRSI): compare to de-duped names from VisPubData
    for paper in paperList:
        doi = paper["doi"]
        if doi in visPubDataAuthorsDeduped.keys():
            for nameVPD, nameGRSI in zip(visPubDataAuthorsDeduped[doi], paper["authors"].split(", ")):
                nameVPD_withoutNumbers = re.sub(pattern=r"(.*) \d\d\d\d", repl=r"\1", string=nameVPD)
                if nameVPD_withoutNumbers != nameGRSI:
                    print('Found difference between names between VisPubData data and GRSI (ignoring the numbers): ' + nameVPD_withoutNumbers + ' <-> ' + nameGRSI)

# print the IEEE papers that are currently in press still (for a report to Han-Wei)
if doPrintTVCGInPressDetails:
    print("TVCG papers currently in press:")
    for paper in paperList:
        doi = paper["doi"]
        if ("10.1109/" in doi) and (paperListExtended[doi]['publication_year'] > grsiMetaData["data_download_year"]):
            print("* " + doi + ": " + paperListExtended[doi]['title'] + " (GRSI: " + paper["grsi_url"] + ")")

if doAbstractCheckingForKeywords:
    # check for visualization keywords in the paper abstracts
    print("Checking for vis keywords in the abstracts of papers we have not itentified as vis yet")
    for paper in paperList:
        doi = paper["doi"]

        reportVisKeywordInAbstract = False

        if (paper["is_vis"] == False) and (doi in paperListExtended.keys()):
            if ("visualization" in paperListExtended[doi]['abstract'].lower()): reportVisKeywordInAbstract = True
            if ("visualisation" in paperListExtended[doi]['abstract'].lower()): reportVisKeywordInAbstract = True
            if ("visualizing" in paperListExtended[doi]['abstract'].lower()): reportVisKeywordInAbstract = True
            if ("visualising" in paperListExtended[doi]['abstract'].lower()): reportVisKeywordInAbstract = True
            if ( ("visual" in paperListExtended[doi]['abstract'].lower()) and ("analytics" in paperListExtended[doi]['abstract'].lower()) ): reportVisKeywordInAbstract = True
            if ( ("visual" in paperListExtended[doi]['abstract'].lower()) and ("analysis" in paperListExtended[doi]['abstract'].lower()) ): reportVisKeywordInAbstract = True
            if ("visual representation" in paperListExtended[doi]['abstract'].lower()): reportVisKeywordInAbstract = True
            if ("data exploration" in paperListExtended[doi]['abstract'].lower()): reportVisKeywordInAbstract = True
            if ("visual exploration" in paperListExtended[doi]['abstract'].lower()): reportVisKeywordInAbstract = True
            if ("graph drawing" in paperListExtended[doi]['abstract'].lower()): reportVisKeywordInAbstract = True
            if ("parallel coordinates" in paperListExtended[doi]['abstract'].lower()): reportVisKeywordInAbstract = True
            if ("scatterplot" in paperListExtended[doi]['abstract'].lower()): reportVisKeywordInAbstract = True
            if ("choropleth" in paperListExtended[doi]['abstract'].lower()): reportVisKeywordInAbstract = True
            if ("cartogram" in paperListExtended[doi]['abstract'].lower()): reportVisKeywordInAbstract = True
            if ("star glyph" in paperListExtended[doi]['abstract'].lower()): reportVisKeywordInAbstract = True
            if ("glyph design" in paperListExtended[doi]['abstract'].lower()): reportVisKeywordInAbstract = True
            if ("line graph" in paperListExtended[doi]['abstract'].lower()): reportVisKeywordInAbstract = True
            if ("streamgraph" in paperListExtended[doi]['abstract'].lower()): reportVisKeywordInAbstract = True
            if ("focus+context" in paperListExtended[doi]['abstract'].lower()): reportVisKeywordInAbstract = True
            # if ("topology" in paperListExtended[doi]['abstract'].lower()): reportVisKeywordInAbstract = True # not good: some graphics papers also captured
            if ("t-sne" in paperListExtended[doi]['abstract'].lower()): reportVisKeywordInAbstract = True
            if ("high-dimensional data" in paperListExtended[doi]['abstract'].lower()): reportVisKeywordInAbstract = True

        if reportVisKeywordInAbstract:
            print("https://doi.org/" + doi + " (" + paper["title"] + ") is not marked but has vis keywords in the abstract")

if doVerifyCountryInformation:
    # check for visualization keywords in the paper abstracts
    print("Checking for missing country information")
    for paper in paperListExtended.keys():
        doi = paperListExtended[paper]["doi"]
        if not("countries" in paperListExtended[doi].keys()):
            print("Counties info missing for entry " + doi + ", please add it to " + dataOutputSubdirectury + "extended_paper_data.json.")

if doExportNumbersForPaper:
    print("Writing the extracted numbers into a tex file for the paper")
    with open(paperNumbersOutputFile, "w") as text_file:
        text_file.write(paperNumbersOutputString)
    print("Writing the extracted keyword-marked papers into a tex file for the paper")
    with open(paperKeywordPapersOutputFile, "w") as text_file:
        text_file.write(paperKeywordPapersOutputString)

if (doCopyPlotsAccordingToFugureNumbers) and (exportVisualizations):
    shutil.copy(graphOutputSubdirectury + 'replicability_visualization-by-venue-stackedbargraph.pdf', paperFiguresOutputSubdirectury + 'figure01.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_all-by-journal-linegraph.pdf', paperFiguresOutputSubdirectury + 'figure02.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_all-by-journal_aggregated-stackedbargraph.pdf', paperFiguresOutputSubdirectury + 'figure03.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_all-by-journal_aggregated_plain-stackedbargraph.pdf', paperFiguresOutputSubdirectury + 'figure03_merged.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_all-by-visualization-stackedbargraph.pdf', paperFiguresOutputSubdirectury + 'figure04.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_visualization-by-journal_plus_type_aggregated-stackedbargraph.pdf', paperFiguresOutputSubdirectury + 'figure05.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_visualization-by-journal_plus_type-stackedbargraph.pdf', paperFiguresOutputSubdirectury + 'figure06.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_visualization-by-type-groupedbargraph.pdf', paperFiguresOutputSubdirectury + 'figure07.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_visualization-by-venue-stackedbargraph-normalized.pdf', paperFiguresOutputSubdirectury + 'figure08.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_all-histogram-stamps-per-person.pdf', paperFiguresOutputSubdirectury + 'figure09a.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_visualization-histogram-stamps-per-person.pdf', paperFiguresOutputSubdirectury + 'figure09b.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability-histogram-people-vis-percentages.pdf', paperFiguresOutputSubdirectury + 'figure10a.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability-histogram-people-vis-percentages-multiple-papers.pdf', paperFiguresOutputSubdirectury + 'figure10b.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_all-piechart-by-country-thresholded-proportional.pdf', paperFiguresOutputSubdirectury + 'figure11a.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_visualization-piechart-by-country-thresholded-proportional.pdf', paperFiguresOutputSubdirectury + 'figure11b.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_all-piechart-by-country-senior-only-thresholded-proportional.pdf', paperFiguresOutputSubdirectury + 'figure12a.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_visualization-piechart-by-country-senior-only-thresholded-proportional.pdf', paperFiguresOutputSubdirectury + 'figure12b.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_visualization-by-venue-linegraph.pdf', paperFiguresOutputSubdirectury + 'figure13.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_all-by-journal-groupedbargraph.pdf', paperFiguresOutputSubdirectury + 'figure14.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_all-by-journal_aggregated-stackedbargraph-normalized.pdf', paperFiguresOutputSubdirectury + 'figure15.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_visualization-piechart-by-vis-status.pdf', paperFiguresOutputSubdirectury + 'figure16a.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_visualization-piechart-by-journal.pdf', paperFiguresOutputSubdirectury + 'figure16b.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_all-by-visualization-stackedbargraph-normalized.pdf', paperFiguresOutputSubdirectury + 'figure17.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_visualization-by-journal_plus_type_aggregated-stackedbargraph-normalized.pdf', paperFiguresOutputSubdirectury + 'figure18.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_visualization-by-journal_plus_type-stackedbargraph-normalized.pdf', paperFiguresOutputSubdirectury + 'figure19.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_visualization-by-type-stackedbargraph.pdf', paperFiguresOutputSubdirectury + 'figure20.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_visualization-by-type-stackedbargraph-normalized.pdf', paperFiguresOutputSubdirectury + 'figure21.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability-histogram-people-vis-percentages-nolog.pdf', paperFiguresOutputSubdirectury + 'figure22a.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability-histogram-people-vis-percentages-multiple-papers-nolog.pdf', paperFiguresOutputSubdirectury + 'figure22b.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_all-piechart-by-country-proportional.pdf', paperFiguresOutputSubdirectury + 'figure23a.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_all-piechart-by-country-absolute.pdf', paperFiguresOutputSubdirectury + 'figure23b.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_all-piechart-by-country-senior-only-proportional.pdf', paperFiguresOutputSubdirectury + 'figure24a.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_all-piechart-by-country-senior-only-absolute.pdf', paperFiguresOutputSubdirectury + 'figure24b.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_visualization-piechart-by-country-proportional.pdf', paperFiguresOutputSubdirectury + 'figure25a.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_visualization-piechart-by-country-absolute.pdf', paperFiguresOutputSubdirectury + 'figure25b.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_visualization-piechart-by-country-senior-only-proportional.pdf', paperFiguresOutputSubdirectury + 'figure26a.pdf')
    shutil.copy(graphOutputSubdirectury + 'replicability_visualization-piechart-by-country-senior-only-absolute.pdf', paperFiguresOutputSubdirectury + 'figure26b.pdf')

# copy the final GRSI data file to the respective output directory
shutil.copy(formatted_date + " grsi paper data.json", dataOutputSubdirectury + "grsi_paper_data.json")
