#reads a CSV file (expanded.csv) with book titles and authors and then searches them within the Goolgle Books API for primary and adjacent terms listed
#outputs a CSV file (results.csv) with the results of the search, including #of hits for each term and if snippers were found
#to run the code enter the command "python handoff_gbooks_search.py --input expanded.csv --output results.csv"
#Sulav Shakya
#Summer 2026 Capstone


import argparse
import csv
import re
import sys
import time

import requests

API_URL = "https://www.googleapis.com/books/v1/volumes"
API_KEY = "YOUR_API_KEY_HERE" 


#list of primary words to be searched
PRIMARY = ["handoff", "handover"]

#list of words that are not primary but are related to the topic of handoff and handover
ADJACENT = [
    "knowledge transfer",
    "maintenance programmer",
    "staff turnover",
    "technical debt",
    "tacit knowledge",
    "program comprehension",
    "cutover",
]
ALL_TERMS = PRIMARY + ADJACENT


#I had problems with Google Books API rate limiting me so I added a delay between requests
DELAY = 2 


#adds underscores to the search term so it can be used as a column name in the output csv
def code(term):

    return term.replace(" ", "_")

#API request function 
def get(params, tries=5):
    params["key"] = API_KEY
    wait = 5
    #request the API 
    for i in range(tries):
        r = requests.get(API_URL, params=params, timeout=15)
        #API call was successful
        if r.status_code == 200:
            return r

        #429 = rate limited, 500> = server error
        if r.status_code == 429 or r.status_code >= 500:
            #retry after waiting for a while
            print(f"  rate limited, waiting {wait}s...")
            time.sleep(wait)
            wait *= 2
            continue
        print(f"  request failed: {r.status_code} {r.text[:150]}")
        return None
    print("  giving up, still rate limited")
    return None

#Build search query for Google Books API and return the first result if found
def lookup_book(title, author=None):
    #Google Books syntax for searching for a book by title and author
    q = f'intitle:"{title}"'
    if author:
        q += f' inauthor:"{author}"'

    #calls get with 1 result asked for
    r = get({"q": q, "maxResults": 1})
    if not r:
        return None
    items = r.json().get("items")
    return items[0] if items else None

#searches for a snippet of text containing the search term in the book description and returns it if found
def find_snippet(volume_id, title, term):
    #Google syntax for searching for a book by title and term
    r = get({"q": f'"{term}" intitle:"{title}"', "maxResults": 5})
    if not r:
        return ""
    for item in r.json().get("items", []):

        if item.get("id") == volume_id:
            return item.get("searchInfo", {}).get("textSnippet", "")
    return ""

#counts search terms within book description
def count_hits(text, term):

    return text.lower().count(term.lower()) if text else 0

#removes HTML tags and white space from book title
def clean_title(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    return re.sub(r"\s+", " ", text).strip()

#book analysis function within the API, returns a dictionary with the results of the analysis
def analyze(title, author=None):

    row = {"title": title, "author": author or "", "found": False, "id": "", "desc_len": 0}

    #within the list of terms, create a column for each term and set the initial value to 0
    for t in ALL_TERMS:
        row[f"n_{code(t)}"] = 0


    for t in PRIMARY:

        row[f"snip_{code(t)}"] = False

    #find the book using the function 
    book = lookup_book(title, author)
    if not book:
        return row

    #book found
    row["found"] = True

    vid = book.get("id", "")
    row["id"] = vid

    #store the book description and its length in the row dictionary
    desc = book.get("volumeInfo", {}).get("description", "") or ""
    row["desc_len"] = len(desc)

    for t in ALL_TERMS:
        row[f"n_{code(t)}"] = count_hits(desc, t)

    #search text snippets for primary terms and store results in the dict
    for t in PRIMARY:

        time.sleep(DELAY)
        snippet = find_snippet(vid, title, t)

        row[f"snip_{code(t)}"] = bool(snippet)

        if snippet:
            row[f"snip_text_{code(t)}"] = snippet

    return row

#reading the CSV file with the book informaiton 
def read_csv(path):
    #try different methods of reading the CSV file
    for enc in ("utf-8-sig", "cp1252"):
        try:
            #open the file
            with open(path, newline="", encoding=enc) as f:
                #each row a dict
                reader = csv.DictReader(f)

                #create a mapping of lowercase column names to their original names
                cols = {c.lower(): c for c in reader.fieldnames}
                title_col = cols.get("title")
                author_col = cols.get("author") or cols.get("authors")

                if not title_col:
                    #no title column found, raise an error
                    raise ValueError(f"no title column found, got: {reader.fieldnames}")
                books = []
                
                #cleaning up the title and author names
                for row in reader:

                    t = clean_title(row.get(title_col, ""))
                    a = clean_title(row.get(author_col, "")) if author_col else None
                    if t:
                        books.append((t, a or None))
                return books
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"couldn't read {path} -- try saving it as UTF-8 CSV")


def main():
    p = argparse.ArgumentParser()

    #input and output CSV files 
    p.add_argument("--input", default="expanded.csv")

    p.add_argument("--output", default="results.csv")


    args = p.parse_args()

    #load book list from input file
    books = read_csv(args.input)

    print(f"loaded {len(books)} books")

    results = []
    for i, (title, author) in enumerate(books, 1):
        #printing the progress of the analysis
        print(f"[{i}/{len(books)}] {title}")
        row = analyze(title, author)
        results.append(row)

        #sum up hits for primary and adjacent terms
        if row["found"]:
            primary_hits = sum(row[f"n_{code(t)}"] for t in PRIMARY)
            adj_hits = sum(row[f"n_{code(t)}"] for t in ADJACENT)

            print(f"  found, {primary_hits} primary / {adj_hits} adjacent hits in description")
        else:
            #if the book couldnt be found
            print("  not found within Google Books API")

        #avoid rate limiting, without this for some reason Google Books API will freeze up and stop working
        time.sleep(DELAY)

    if not results:
        print("nothing to write")
        return


    #build list starting at cols
    cols = []

    for r in results:
        for k in r:
            if k not in cols:
                cols.append(k)

    #write to the output CSV
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        
        writer.writeheader()

        writer.writerows(results)

    print(f"wrote {len(results)} rows to {args.output}")


if __name__ == "__main__":
    main()