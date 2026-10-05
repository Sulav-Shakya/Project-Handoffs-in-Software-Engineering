Python script meant to scrape the Google Books API for targeted textbooks given through an external Excel file. 

-Reads a CSV file (expanded.csv) with book titles and authors and then searches them within the Goolgle Books API for primary and adjacent terms listed

-Outputs a CSV file (results.csv) with the results of the search, including #of hits for each term and if snippers were found

-To run the code enter the command "python handoff_gbooks_search.py --input expanded.csv --output results.csv"
