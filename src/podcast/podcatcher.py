import feedparser
import codecs
import server_config
import logging
import time
import datetime
import cfscrape
import urlparse
import os
import pathlib2
import re
import urllib
import pymongo
from slugify import slugify
from dateutil import parser


def update_feeds():
    """Connects to the database and attempts to download and catalogue new episodes"""
    myclient = pymongo.MongoClient(server_config.mongodbURL)
    mydb = myclient[server_config.mongodbDB]
    mycol = mydb["feeds"]
    for x in mycol.find():
        logging.info("{name} has id {id} and url {url}".format(name=x['name'], id=x['_id'], url=x['url']))
        retrieve_episodes(x)


def update_descriptions():
    """Connects to the database and attempts to update the desxcriptions"""
    myclient = pymongo.MongoClient(server_config.mongodbURL)
    mydb = myclient[server_config.mongodbDB]
    mycol = mydb["feeds"]
    for row in mycol.find():
        logging.info("{name} has id {id} and url {url}".format(name=row['name'], id=row['_id'], url=row['url']))
        feed = feedparser.parse( row['url'] )  # read the feed into a dict object
        try:
            if 'summary' in feed['feed']: # Some feeds are formatted incorrectly, so we must check for this manually
                mycol.update_one({"_id": row["_id"]}, {"$set": {"description": feed['feed']['summary']}})
            else:
                mycol.update_one({"_id": row["_id"]}, {"$set": {"description": "Summary not found"}})
        except Exception as inst:
            logging.error(inst)
        try:
            print(feed['feed']['image'])
            file = feed['feed']['image']['href']
            path = urlparse.urlparse(file).path
            extension = os.path.splitext(path)[1]
            pathlib2.Path(server_config.podcast_directory + "/images/").mkdir(parents=True, exist_ok=True) 
            save = server_config.podcast_directory + "/images/" + slugify(row["name"]);
            urllib.urlretrieve(file, save)
        except Exception as inst:
            logging.error(inst)


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
                    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # format the current time
                    episode_dict = {"published": pub, "added": now, "uuid": item["id"], "title": item["title"], "description": item["description"], "file": save, "feed": row["_id"]}
                    epcol.insert_one(episode_dict)
            except Exception as inst:
                logging.error("Error parsing " + item["title"])
    except Exception as inst:
        logging.error("Error parsing " + rss)
        logging.error(inst)
