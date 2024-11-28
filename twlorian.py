from bs4 import BeautifulSoup
import pandas as pd
import requests
import json
import csv
import random
from concurrent.futures import ThreadPoolExecutor

# List of user agents for the scraper to use
user_agent = [
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

username = input('Enter Twitter handle: ')
print('Scraping tweet history for @' + username + '...')

# Wayback Machine URL for the Twitter user's archive
url = f"https://web.archive.org/web/timemap/?url=https%3A%2F%2Ftwitter.com%2F{username}%2F&matchType=prefix&collapse=urlkey&output=json&fl=original%2Cmimetype%2Ctimestamp%2Cendtimestamp%2Cgroupcount%2Cuniqcount&filter=!statuscode%3A%5B45%5D..&limit=100000&_=1627821432372"

# Set up a session to manage requests
s = requests.Session()
s.max_redirects = 10

# Handling request and JSON decoding
try:
    resp = s.get(url)
    if resp.status_code == 200:  # Ensure the response is OK
        try:
            txt = resp.json()  # Try parsing as JSON
        except json.JSONDecodeError:
            print(f"Error decoding JSON from the response for {url}")
            print("Response content:", resp.text[:500])  # Print first 500 characters of response
            txt = []  # Set empty list to avoid further issues
    else:
        print(f"Failed to fetch data from {url}, Status Code: {resp.status_code}")
        txt = []
except requests.exceptions.RequestException as e:
    print(f"An error occurred: {e}")
    txt = []

if txt:
    df = pd.DataFrame(txt)
    df.to_csv(f"{username}_archivelinks.csv")

    links = df.iloc[1:, 0].values

    wayback = 'https://web.archive.org/web/0/'
    archives = [wayback + x for x in links]

    number_of_elements = len(archives)

    print('Number of tweets found:', number_of_elements, '\nArchiving tweets... (This could take a while.)')

    tweet_arr = []
    not_found = []

    # Create JSON and CSV file writers
    json_file = open(f"{username}_archive.json", 'a+', encoding='utf-8')
    csv_file = open(f"{username}_archive.csv", 'a+', newline='', encoding='utf-8')
    json_writer = json_file.write("[\n")
    csv_writer = csv.writer(csv_file, delimiter=';')

    def scrape_tweet(archive):
        try:
            s.headers['User-Agent'] = random.choice(user_agent)
            l = s.get(archive)
            l.encoding = 'utf-8'
            html_content = l.text
            soup = BeautifulSoup(html_content, 'html.parser')
            tweets = soup.find_all('div', attrs={'data-item-type': 'tweet'})

            if not tweets:
                tweets = soup.find_all('li', attrs={'data-item-type': 'tweet'})

            for t in tweets:
                tweet_obj = {}

                if 'data-item-id' in t.attrs:
                    tweet_obj['tweet_id'] = t.get("data-item-id")
                    tweet_container = t.find('div', attrs={'class': 'tweet'})
                    tweet_obj['screen_name'] = tweet_container.get('data-screen-name')
                    tweet_obj['permalink'] = tweet_container.get('data-permalink-path')
                    tweet_content = tweet_container.find('p', attrs={'class': 'tweet-text'})
                    tweet_obj['tweet_text'] = tweet_content.text
                    tweet_obj['user_id'] = tweet_container.get('data-user-id')
                    tweet_time = tweet_container.find('span', attrs={'class': '_timestamp'})
                    tweet_obj['timestamp'] = tweet_time.get('data-time-ms')
                    hashtags = tweet_container.find_all('a', attrs={'class': 'twitter-hashtag'})
                    tweet_obj['hashtags'] = []
                    tweet_obj['links'] = []

                    for ht in hashtags:
                        ht_obj = {'tag': ht.find('b').text, 'archived_url': ht.get('href')}
                        tweet_obj['hashtags'].append(ht_obj)

                    links = tweet_container.find_all('a', attrs={'class': 'twitter-timeline-link'})
                    for li in links:
                        li_obj = {}

                        if li.get('data-expanded-url'):
                            li_obj['url'] = li.get('data-expanded-url')
                        elif li.get('data-resolved-url-large'):
                            li_obj['url'] = li.get('data-resolved-url-large')
                        else:
                            li_obj['url'] = li.text

                        li_obj['archived_url'] = li.get('href')
                        tweet_obj['links'].append(li_obj)

                    tweet_arr.append(tweet_obj)
                    print(tweet_obj)
                    # Write tweet_obj to JSON file
                    json_writer.write(json.dumps(tweet_obj, ensure_ascii=False, sort_keys=True, indent=4) + ",\n")

                    # Write tweet_obj to CSV file
                    csv_writer.writerow([tweet_obj['tweet_id'], tweet_obj['screen_name'], tweet_obj['permalink'], tweet_obj['tweet_text'], tweet_obj['user_id'], tweet_obj['timestamp']])

        except requests.exceptions.TooManyRedirects:
            pass
        except:
            not_found.append(archive)

    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(scrape_tweet, archive) for archive in archives]

    number_found = len(tweet_arr)
    number_notfound = len(not_found)

    print('Number of tweets archived: ', number_found)
    print('Number of tweets not found: ', number_notfound)

    # Close files properly
    json_file.close()
    csv_file.close()

else:
    print("No data to process.")
