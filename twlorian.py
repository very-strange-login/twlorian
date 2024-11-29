import json
import csv
import random
from concurrent.futures import ThreadPoolExecutor
import requests
from bs4 import BeautifulSoup
import pandas as pd

# List of user agents for the scraper to use
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.90 Safari/537.36',
    'Mozilla/5.0 (Windows NT 5.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.90 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.2; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.90 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/44.0.2403.157 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36',
]

WAYBACK_BASE_URL = 'https://web.archive.org/web/0/'

def fetch_archived_links(username):
    """Fetch the archived tweet links for a given username from the Wayback Machine."""
    url = (
        f"https://web.archive.org/web/timemap/?url=https://twitter.com/{username}/"
        "&matchType=prefix&collapse=urlkey&output=json"
        "&fl=original,mimetype,timestamp,endtimestamp,groupcount,uniqcount"
        "&filter=!statuscode:[45]..&limit=100000"
    )
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        print(f"Error fetching archived links: {e}")
        return []

def scrape_tweet(archive_url, session, tweet_arr, not_found):
    """Scrape a single tweet from an archived page and print selected fields."""
    try:
        session.headers['User-Agent'] = random.choice(USER_AGENTS)
        response = session.get(archive_url)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        tweets = soup.find_all('div', attrs={'data-item-type': 'tweet'}) or \
                 soup.find_all('li', attrs={'data-item-type': 'tweet'})

        for tweet in tweets:
            tweet_obj = extract_tweet_data(tweet)
            if tweet_obj:
                tweet_arr.append(tweet_obj)
                # Print only the required fields
                print(f"Tweet Text: {tweet_obj['tweet_text']}")
                print(f"Screen Name: {tweet_obj['screen_name']}")
                print(f"Timestamp: {tweet_obj['timestamp']}")
                print("-" * 50)  # Divider for readability
    except Exception as e:
        print(f"Error scraping {archive_url}: {e}")
        not_found.append(archive_url)

def extract_tweet_data(tweet):
    """Extract tweet data from a BeautifulSoup element."""
    try:
        tweet_obj = {
            "tweet_id": tweet.get("data-item-id"),
            "screen_name": tweet.get('data-screen-name'),
            "permalink": tweet.get('data-permalink-path'),
            "tweet_text": tweet.find('p', attrs={'class': 'tweet-text'}).text,
            "user_id": tweet.get('data-user-id'),
            "timestamp": tweet.find('span', attrs={'class': '_timestamp'}).get('data-time-ms'),
            "hashtags": [
                {
                    "tag": ht.find('b').text,
                    "archived_url": ht.get('href')
                }
                for ht in tweet.find_all('a', attrs={'class': 'twitter-hashtag'})
            ],
            "links": [
                {
                    "url": li.get('data-expanded-url') or li.get('data-resolved-url-large') or li.text,
                    "archived_url": li.get('href')
                }
                for li in tweet.find_all('a', attrs={'class': 'twitter-timeline-link'})
            ]
        }
        return tweet_obj
    except AttributeError:
        return None

def save_results_to_files(username, tweet_arr):
    """Save the tweet data to JSON and CSV files."""
    with open(f"{username}_archive.json", 'w', encoding='utf-8') as json_file, \
         open(f"{username}_archive.csv", 'w', newline='', encoding='utf-8') as csv_file:
        json.dump(tweet_arr, json_file, ensure_ascii=False, indent=4)
        csv_writer = csv.writer(csv_file, delimiter=';')
        csv_writer.writerow(["tweet_id", "screen_name", "permalink", "tweet_text", "user_id", "timestamp"])
        for tweet in tweet_arr:
            csv_writer.writerow([
                tweet['tweet_id'],
                tweet['screen_name'],
                tweet['permalink'],
                tweet['tweet_text'],
                tweet['user_id'],
                tweet['timestamp']
            ])

def main():
    username = input("Enter Twitter handle: ")
    print(f"Scraping tweet history for @{username}...")

    archived_links = fetch_archived_links(username)
    if not archived_links:
        print("No archived links found.")
        return

    df = pd.DataFrame(archived_links)
    df.to_csv(f"{username}_archivelinks.csv", index=False)

    archives = [WAYBACK_BASE_URL + link for link in df.iloc[1:, 0].values]
    print(f"Number of tweets found: {len(archives)}\nArchiving tweets...")

    tweet_arr, not_found = [], []
    with ThreadPoolExecutor() as executor, requests.Session() as session:
        futures = [executor.submit(scrape_tweet, archive, session, tweet_arr, not_found) for archive in archives]
        for future in futures:
            future.result()

    print(f"Number of tweets archived: {len(tweet_arr)}")
    print(f"Number of tweets not found: {len(not_found)}")
    save_results_to_files(username, tweet_arr)

if __name__ == "__main__":
    main()
