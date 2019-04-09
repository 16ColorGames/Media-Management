import feedparser
import codecs
import mysql.connector
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
from slugify import slugify
from dateutil import parser
from mysql.connector import errorcode


def update_feeds():
    """Connects to the database and attempts to download and catalogue new episodes"""
    cnx = mysql.connector.connect(user=server_config.mysqlUser, password=server_config.mysqlPassword, database=server_config.mysqlDatabase)
    cursor = cnx.cursor(dictionary=True)
    feed_query = "SELECT * FROM podcast_feeds"  # select all of our feeds
    
    cursor.execute(feed_query)
    
    for row in cursor:
        logging.info("{name} has id {id} and url {url}".format(name=row['name'], id=row['feed_id'], url=row['url']))
        retrieve_episodes(row)
    
    cursor.close()
    cnx.close()


def update_descriptions():
    """Connects to the database and attempts to update the desxcriptions"""
    cnx = mysql.connector.connect(user=server_config.mysqlUser, password=server_config.mysqlPassword, database=server_config.mysqlDatabase)
    cursor = cnx.cursor(dictionary=True)
    update_cursor = cnx.cursor(dictionary=True,buffered=True)
    feed_query = "SELECT * FROM podcast_feeds"  # select all of our feeds
    logging.info("Updating desc")
    cursor.execute(feed_query)
    update_desc = ("UPDATE podcast_feeds SET description = %s WHERE feed_id = %s ")
    feeds = []
    
    for row in cursor:
        feeds.append(row)  # Clear out the cursor
    
    for row in feeds:
        logging.info("{name} has id {id} and url {url}".format(name=row['name'], id=row['feed_id'], url=row['url']))
        feed = feedparser.parse( row['url'] )  # read the feed into a dict object
        try:
            if 'summary' in feed['feed']:  # Some feeds are formatted incorrectly, so we must check for this manually
                update_cursor.execute(update_desc, (feed['feed']['summary'], row['feed_id']))
            else:
                update_cursor.execute(update_desc, ("Summary not found", row['feed_id']))
            cnx.commit()  # save our changes to the database
        except Exception as inst:
            logging.error(inst)
        try:
            print(feed['feed']['image'])
            file = feed['feed']['image']['href']
            path = urlparse.urlparse(file).path
            extension = os.path.splitext(path)[1]
            pathlib2.Path(server_config.podcast_directory + "/images/").mkdir(parents=True, exist_ok=True) 
            save = server_config.podcast_directory + "/images/" + slugify(row["name"]);
            
            wget.download(file, save)  # actually download the file here
        except Exception as inst:
            logging.error(inst)
        
    cursor.close()
    update_cursor.close()
    cnx.close()


def retrieve_episodes(row):
    cnx = mysql.connector.connect(user=server_config.mysqlUser, password=server_config.mysqlPassword, database=server_config.mysqlDatabase)
    episode_cursor = cnx.cursor(dictionary=True)
    insert_cursor = cnx.cursor()
    add_episode = ("INSERT INTO podcast_episodes "
                     "(id, title, file, description, feed, pubDate, addDate)"
                     "VALUES (%s, %s, %s, %s, %s, %s, %s)")
    current_query = "SELECT * FROM podcast_episodes WHERE feed = {}".format(row['feed_id'])
    episode_cursor.execute(current_query)
    
    # populate a list of existing episodes
    episode_ids = []
    for episode_row in episode_cursor:
        episode_ids.append(episode_row['id'])
        
    
    scraper = cfscrape.create_scraper()
    
    # iterate through episodes and attempt to download new ones
    try:
        feed = feedparser.parse( row['url'] )
        for item in feed["items"]:
            try:
                if item["id"] not in episode_ids:
                    # episode is new, fetch it
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
                    
                    cfurl = scraper.get(file).content
                    with open(save, 'wb') as f:
                        f.write(cfurl)
                    
                    #data = urllib.URLopener()
                    #data.retrieve(file, save)
                    
                    #wget.download(file, save)  # actually download the file here
                    pub = parser.parse(item["published"]).strftime('%Y-%m-%d %H:%M:%S')  # format the publish date
                    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # format the current time
                    insert_cursor.execute(add_episode, (item["id"], item["title"], save, item["description"], row["feed_id"], pub, now))
                    cnx.commit()
            except Exception as inst:
                try:
                    logging.error("Error parsing " + item["title"])
                    logging.error(inst)
                    logging.error(insert_cursor.statement)
                except Exception as inst2:
                    logging.error("Error parsing " + item["title"])
                    logging.error(inst2)
    except Exception as inst:
        logging.error("Error parsing " + rss)
        logging.error(inst)
        
    # commit our changes and close our handlers
    cnx.commit()
    episode_cursor.close()
    insert_cursor.close()
    cnx.close()
