import requests
from bs4 import BeautifulSoup
import json
import time

# Base URLs
base_url = "https://github.com"
wiki_index_url = "https://github.com/HumansDoNotWantImmortality/bg3-sids/wiki"

# Get the wiki index page
response = requests.get(wiki_index_url)
if response.status_code != 200:
    raise Exception(f"Failed to fetch wiki index: HTTP {response.status_code}")

soup = BeautifulSoup(response.text, 'html.parser')

# Find all links to wiki pages.
# The links we want should start with the expected path and are not the index page itself.
wiki_links = set()
for link in soup.find_all("a", href=True):
    href = link["href"]
    if href.startswith("/HumansDoNotWantImmortality/bg3-sids/wiki/") and href != "/HumansDoNotWantImmortality/bg3-sids/wiki":
        wiki_links.add(href)

wiki_links = list(wiki_links)
print(f"Found {len(wiki_links)} wiki page(s).")

wiki_data = {}

for href in wiki_links:
    page_url = base_url + href
    print(f"Fetching {page_url}...")
    page_response = requests.get(page_url)
    if page_response.status_code != 200:
        print(f"  Failed to fetch {page_url}: HTTP {page_response.status_code}")
        continue
    page_soup = BeautifulSoup(page_response.text, 'html.parser')
    # GitHub wiki pages usually put content in a <div class="markdown-body">
    content_div = page_soup.find("div", class_="markdown-body")
    if content_div:
        # Get the text content; you could also use .prettify() or .decode_contents() if you want HTML
        content = content_div.get_text(separator="\n").strip()
    else:
        content = ""
        print(f"  No content found in {page_url}")

    # Use the last part of the URL as a title key
    title = href.split("/")[-1]
    wiki_data[title] = {
        "url": page_url,
        "content": content
    }
    # Be polite with a short delay to avoid hammering GitHub's servers
    time.sleep(0.5)

# Save the wiki data to a JSON file
with open("wiki_data.json", "w", encoding="utf-8") as f:
    json.dump(wiki_data, f, ensure_ascii=False, indent=4)

print("Wiki has been converted to wiki_data.json")
