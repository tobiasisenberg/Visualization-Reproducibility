# Script and data to replicate the analysis of replicability for visualization publications

## Description

This repository provides all needed means to reproduce an analysis of the state of replicability stamps for, in particular, scientific papers in the field of visualization. The main script ([`replicability.py`](replicability.py)) produces all graphs I generated for this purpose, as well as some textual summaries and data. Then the [`paper/`](paper/) subdirectory uses the produced graphs and text to generate the paper I wrote about the analysis. At any point in time the paper can thus be updated to the state of the art of the data, by first running the script, then potentially adding some information (country of affiliations for the authors of newly added papers) and running the script one more time, before using LaTeX to compile the paper with updated graphs and numbers.

## Included (and required) datasets or files

These datasets are used to be able to analyze the replicability with respect to where they were published and to reliably be able to tell what makes a visualization paper. Currently the data is current up to 2023/2024; in the future these datasets naturally would need to be updated.
* export from [VisPubData](http://www.vispubdata.org/)'s [Google Sheets page](https://docs.google.com/spreadsheets/d/1xgoOPu28dQSSGPIp_HHQs0uvvcyLNdkMF9XtRajhhxU/) in CSV format as [`input/vispubdata.csv`](input/vispubdata.csv)
* potentially additional IEEE VIS years (that may not yet be included in [VisPubData](http://www.vispubdata.org/)) as exports from TVCG's IEEE Xplore site (open the special issue overview page on IEEE Xplore [e.g., https://ieeexplore.ieee.org/xpl/tocresult.jsp?isnumber=10373160&punumber=2945 for the IEEE VIS 2023 special issue, published as issue 01 of volume 30 in 2024], do not select anything, click the "Export" button and then "Download" to get a CSV export) in the format `input/tvcg-YYYY-vol-VV-no-NN.csv` where YYYY is the publication year of the issue (not the conference year!), VV is the volume of the issue, and NN is the issue number (e.g., [`input/tvcg-2024-vol-30-no-01.csv`](input/tvcg-2024-vol-30-no-01.csv) shows an example for the special issue of the 2023 VIS conference, but even though it is loaded it is effectively not used since VisPubData is updated to include the 2023 conference); notice: if you want to load such data do not forget to edit the csv file to remove those entries that are not papers but preface items; the script also needs to be manually adjusted at two positions to load this data
* list of journal presentations at IEEE VIS (currently up to 2023 conference) in CSV format as [`input/vis_journal_presentations.csv`](input/vis_journal_presentations.csv)
* list of EuroVis full papers (until 2023 conference) in XLSX format as [`input/EuroVisFull_CGF.xlsx`](input/EuroVisFull_CGF.xlsx)
* list of EuroVis STAR papers (until 2023 conference) in XLSX format as [`input/EuroVisSTARS_CGF.xlsx`](input/EuroVisSTARS_CGF.xlsx)
* list of EuroVis full papers from 2024 onward (currently until 2024 conference) in CSV format as [`input/eurovis.csv`](input/eurovis.csv)
* list of journal presentations at EuroVis (currently until 2024 conference) in CSV format as [`input/eurovis_journal_presentations.csv`](input/eurovis_journal_presentations.csv)
* list of TVCG papers from IEEE PacificVis (i.e., accepted PacificVis submissions that were published in TVCG; currently until 2024 conference) in CSV format as [`input/pacificvis_tvcg.csv`](input/pacificvis_tvcg.csv)
* list of journal presentations at PacificVis (currently until 2024 conference) in CSV format as [`input/pacificvis_journal_presentations.csv`](input/pacificvis_journal_presentations.csv)
* list of VCBM paper that are journal papers or appeared in a VCBM special issue call in C&G (currently until 2022 conference) in CSV format as [`input/vcbm_cag.csv`](input/vcbm_cag.csv)
* lists of C&G special issue papers on visualization venues in CSV format; currently EnvirVis (currently until 2021 conference; [`input/envirvis_cag.csv`](input/envirvis_cag.csv)), EuroVA (currently until 2022 conference; [`input/eurova_cag.csv`](input/eurova_cag.csv)), and MolVA (currently until 2022 conference; [`input/molva_cag.csv`](input/input/molva_cag.csv)), 
* list of countries with their two-letter codes in CSV format as [`input/country-names.csv`](input/country-names.csv) (from [GitHub: lukes/ISO-3166-Countries-with-Regional-Codes](https://github.com/lukes/ISO-3166-Countries-with-Regional-Codes/blob/master/all/all.csv))
* Vega's color map as [`palettes.js`](palettes.js) (local copy of https://raw.githubusercontent.com/vega/vega/v5.21.0/packages/vega-scale/src/palettes.js)

## Produced/downloaded datasets

* list of papers with GRSI award, data from the GRSI website, in JSON format as [`YYYYMMDD grsi paper data.json`](publication_data/grsi paper data.json) (to keep a copy of a given day's state) as well as a copy of this same file as [`publication_data/grsi_paper_data.json`](publication_data/grsi_paper_data.json) (constantly updated version, both are created by scraping the GRSI website)
* list of papers with GRSI award, data from the digital libraries, in JSON format as [`publication_data/extended_paper_data.json`](publication_data/extended_paper_data.json) (created by downloading, one by one, the metadata of newly published GRSI papers from the publisher's databases, to be able to access publication time, paper abstract, etc.); in this file we also collect the countries of each author's afiliation analyzed by the script (but this information needs to be manually added when new papers are found and added to this file; for details see below)
* some meta data about the data download, in particular the day of the data download as [`publication_data/grsi_metadata.json`](publication_data/grsi_metadata.json)

Versions of these two produced datasets from the time of publication of the analysis paper are included repository to facilitate the actual reproduction of the graphs from the published paper. To be able to reproduce the graphs from the paper, ensure that `useLocalDataOnly = False` is configured in the script (at the top), in which case no new data is downloaded but the data from the files are used.

## Needed API keys to be able to download data from the publishers' digital libraries

To be able to download existing and new data from some of the publishers' digital libraries it is necessary to get API keys that officially allow data download. Please go to the following websites to acquire such keys (at least for the IEEE one it takes a few days):

* Elsevier: https://dev.elsevier.com/
* IEEE: https://developer.ieee.org/Quick_Start_Guide

Then create the `api-keys.json` file that keeps these keys (template in [`api-keys-template.json`](api-keys-template.json)) end enter your respective keys:
```
{
    "apikey-elsevier": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "apikey-ieee":     "xxxxxxxxxxxxxxxxxxxxxxxx"
}
```
If only a reproduction of the paper based on the already downloaded data is the goal, then it is also sufficient to copy/rename [`api-keys-template.json`](api-keys-template.json) to `api-keys.json`.

## General prerequisites
* the API key file with valid keys mentioned above (to be created manually)
* the source dataset files mentioned above (included)
* a Python 3 installation; e.g., https://www.python.org/downloads/ or https://www.anaconda.com/download/
* dedicated Python libraries installed with `pip3` or `conda` as follows (or similar):
    * `altair`: `pip3 install altair` or `conda install -c conda-forge altair` (see https://altair-viz.github.io/)
    * `vl-convert`: `pip3 install vl-convert-python` or `conda install -c conda-forge vl-convert-python` (see https://altair-viz.github.io/user_guide/saving_charts.html)
    * `habanero`: `pip3 install habanero` or `conda install -c conda-forge habanero` (see https://github.com/sckott/habanero)
    * `elsapy`: `pip3 install elsapy` (see https://github.com/ElsevierDev/elsapy; this module does not seem to be in the list of modules conda supports by default, but the pip3 way also works for Anaconda installations)
    * `openpyxl`: `pip3 install openpyxl` or `conda install conda-forge openpyxl` (see https://pypi.org/project/openpyxl/)
    * `pycurl`: `pip3 install pycurl` or `conda install conda-forge pycurl` (see http://pycurl.io/)
    * `beautifulsoup4`: `pip3 install beautifulsoup4` or `conda install -c conda-forge beautifulsoup4` (see https://www.crummy.com/software/BeautifulSoup/ and https://anaconda.org/anaconda/beautifulsoup4; seems to be already included with recent versions of Anaconda)
    * `pandas`: `pip3 install pandas` (see https://pandas.pydata.org/docs/getting_started/install.html; already included in Anaconda)
    * a [`requirements.txt`](requirements.txt) includes all of these requirements, install them with `pip3 install -r requirements.txt`
* IEEE Xplore Python 3 API: download it from https://developer.ieee.org/Python3_Software_Development_Kit and place the `xploreapi.py` file into the main directory of the script
* `acmdownload.py` file from https://github.com/niklasekstrom/acmdownload, also placed into the main directory of the script
    * after downloading, open the `acmdownload.py` file and comment out (or just delete) the last five lines (the ones after the last defined function) like this:
    ```
    # doi = '10.5555/2387880.2387905'
    # documents_to_download = 300
    # docs = download(doi, documents_to_download)
    # info(docs[doi])
    # mostreferenced(docs, doi)
    ```

## Configuration due to publisher API issues

Unlike IEEE and Elsevier, Wiley and ACM do not provide dedicated APIs to access their data. Instead, both of them provide their data through [Crossref](https://www.crossref.org/), so by default the metadata for their papers (to figure out publication status etc.) is pulled from the [Crossref API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/a-non-technical-introduction-to-our-api/) (which does not require a dedicated API key). This data, however, has occasional issues with missing information (such as article numbers or abbreviated first names). An alternative for ACM data is to use a query of the data that the ACM provides on their webpage via the [`acmdownload` module](https://github.com/niklasekstrom/acmdownload) mentioned in the prerequisites, yet this path has the issue that repated queries lead to one's IP becoming temporarily blocked by the ACM. By default, therefore, we use the [Crossref](https://www.crossref.org/) query for ACM data, but this can be switched to the `acmdownload` method via setting the `downloadAcmFromCrossref` variable to `False` at the top of the `replicability.py` script. This latter method (i.e., direct access of ACM data) works just fine for the occasional update of an exisiting dataset but not for downloading larger amounts of data.

## Running the script

Once all prerequisites are in place, run the script simply by calling `python replicability.py`. By default, the script only reproduces the results from the paper (i.e., the plots and graphs) based on the included data snapshot. To collect also the more up-to-date current data from the digital libraries, please simply ensure that `useLocalDataOnly = False` is configured in the script (at the top), and then run the script.

## Potential needed data updates

In case new data is pulled from the web, then it is needed to also manually add the country information to the newly added sections of the [`publication_data/extended_paper_data.json`](publication_data/extended_paper_data.json) data file. Do do so, check at the bottom of the file and, for each newly added paper, add the country information to both the individual authors and the whole paper as the following JSON addition
```
,
"countries": [
    "FR",
    "DE"
]
```
using capital letters that encode one or more countries for the affiliations of an author using the [two-letter country code standard](https://www.iban.com/country-codes). In the above example the countries France and Germany are used (i.e., the author has both an affiliation located in France and another one located in Germany), with their two-letter codes `FR` and `DE`. For the whole paper, please add an entry that includes all countries of all of its authors; e.g., after the `abstract` field of the paper as in the existing entries.

## Results

The script produces a txt file with a textual analysis (`20XXXXXX current-list.txt`) as well as multiple PDF files with a graphical analysis, the latter in the [`graphs/`](graphs/) subdirectory. The script also copies some of the graph PDFs to a folder [`paper_figures/`](paper_figures/) with names according to the figure numbers in the paper and updates the JSON data files in the [`publication_data/`](publication_data/) folder.

## Notes on the results

As described above, the data on people's country/countries of affiliation is largely manually collected (from the paper PDFs or the affiliations displayed in the digital libraries), as many digital library APIs do not provide access to this information in their automatic data export. In addition, the data on affiliation is partially wrongly collected by the digital libraries (e.g., see [the last author of this publication](https://doi.org/10.1111/cgf.14487)), and if I noticed such cases then, of course, I manually corrected the entries in the [`publication_data/extended_paper_data.json`](publication_data/extended_paper_data.json) data file. Some authors are also affiliated with multi-national companies, and then I determined the country of affiliation via a manual Google search. Obviously, all of this data updating would not happen if the script is run without the manual correction and/or completing the remaining entries.

## Compiling the LaTeX paper

The paper itself can be found in the [`paper/`](paper/) folder. Simply use your typical LaTeX environment to compile the [`paper/template.tex`](paper/template.tex) main file (after having run the data script; otherwise LaTeX will complain about missing files) in the usual way (LaTeX - bibTeX - LaTeX - LaTeX). This produces the paper as [`paper/template.pdf`](paper/template.pdf) including the complete appendix. Notice that compiling the paper based on newer data than at submission time may lead to some statements in the paper no longer being valid.

## Credits

Primarily, of course, thanks to the [Graphics Replicability Stamp Initiative](https://www.replicabilitystamp.org/). Second, thanks to the [VisPubData](http://www.vispubdata.org/) project for collecting and verifying all IEEE VIS publication data as well as to [Stefanie Behnke](https://www.linkedin.com/in/stefanie-behnke-61632783/) for providing the EuroVis publication data extract from the [Computer Graphics Forum](https://www.eg.org/wp/eurographics-publications/cgf/) database and to [Ross Maciejewski](https://rmaciejewski.faculty.asu.edu/) for the list of IEEE VIS TVCG journal presentations. Also thanks to [Cody Dunne](https://dunne.dev/) for pointing out and helping to fix some issues with this documentation as well as help in debugging some deprecation warnings and weird behavior on some Python environments.