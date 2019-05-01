from __future__ import print_function

from decimal import Decimal
from datetime import datetime, date, timedelta
import urlparse
import os
import pytz
import feedparser
import logging

from bson import ObjectId
import server_config

from dateutil import parser
import cfscrape
import pymongo
import sys
import re
import pathlib2
from string import Template
from feedgen.feed import FeedGenerator
from slugify import slugify
import re

def remove_control_characters(html):
    def str_to_int(s, default, base=10):
        if int(s, base) < 0x10000:
            return unichr(int(s, base))
        return default
    html = re.sub(ur"&#(\d+);?", lambda c: str_to_int(c.group(1), c.group(0)), html)
    html = re.sub(ur"&#[xX]([0-9a-fA-F]+);?", lambda c: str_to_int(c.group(1), c.group(0), base=16), html)
    html = re.sub(ur"[\x00-\x08\x0b\x0e-\x1f\x7f]", "", html)
    return html
  
def retrieve_episodes(row):
    myclient = pymongo.MongoClient(server_config.mongodbURL)
    mydb = myclient[server_config.mongodbDB]
    epcol = mydb["episodes"]
    
    scraper = cfscrape.create_scraper()
    try:
        feed = feedparser.parse(row['url'])
        for item in feed["items"]:
            try:
                # Fix Placeholder with actual filename
                file = item["links"][0]['href']  # rss links are all placed into a single list
                if len(item["links"]) > 1:
                    file = item["links"][1]['href'] # we will usually want the second item
                                            # but sometimes the files are misformatted

                # format the filename for saving
                path = urlparse.urlparse(file).path
                extension = os.path.splitext(path)[1]
                pathlib2.Path(server_config.podcast_directory + "/" + slugify(row["name"]) + "/").mkdir(parents=True, exist_ok=True) 
                save = server_config.podcast_directory + "/" + slugify(row["name"]) + "/" + slugify(item["title"]) + extension;
                
                if not os.path.isfile(save):
                    cfurl = scraper.get(file).content
                    with open(save, 'wb') as f:
                        f.write(cfurl)
                
                pub = parser.parse(item["published"]).strftime('%Y-%m-%d %H:%M:%S')  # format the publish date
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # format the current time
                episode_dict = {"published": pub, "added": now, "uuid": item["id"], "title": item["title"], "description": item["description"], "file": save, "feed": row["_id"]}
                epcol.insert_one(episode_dict)
            except Exception as inst:
                logging.error("Error parsing " + item["title"])
                logging.error(inst)
    except Exception as inst:
        logging.error("Error parsing ")
        logging.error(inst)
  
if __name__ == '__main__':
    myclient = pymongo.MongoClient(server_config.mongodbURL)
    mydb = myclient[server_config.mongodbDB]
    mycol = mydb["feeds"]
    
    mydict = {"name": "Yogpod", "url": "http://yogpod.libsyn.com/rss", "description": "", "categories":"talk"}
    # mycol.insert_one(mydict)
    # mycol.delete_one({"_id": ObjectId(str("5cc85ebe045aea0840768254"))})
    epcol = mydb["episodes"]
    
    epcol.delete_many({})