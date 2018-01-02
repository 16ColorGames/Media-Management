import feedparser
import codecs
import mysql.connector
import server_config
import logging
import time
import datetime
import wget
import urlparse
import os
import pathlib2
from slugify import slugify
from dateutil import parser
from mysql.connector import errorcode


rss_list = ["http://nightvale.libsyn.com/rss","http://lorepodcast.libsyn.com/rss","http://dungeonsandrandomness.podbean.com/feed/","https://www.patreon.com/rss/dandr?auth=7ff68df93a69a2a3b49a7c1d587d9b63","http://mythpodcast.libsyn.com/rss","https://audioboom.com/channels/4322549.rss","http://dungeonmasterblock.podbean.com/feed/","http://brennanheart.podtree.com/feed/podcast","http://djisaac.libsyn.com/rss","http://podcast.globaldedication.com/feed/","http://www.oneshotpodcast.com/category/one-shot/one-shot-podcast/feed","https://www.monstercat.com/podcast/feed.xml","http://tanis.libsyn.com/rss","http://theblacktapes.libsyn.com/rss","http://www.hardwithstyle.nl/?feed=podcast","http://aliceisntdead.libsyn.com/rss","http://goinginblind.libsyn.com/rss","http://www.majorspoilers.com/media/criticalhit.xml","http://goodmorningtheria.podbean.com/feed/","http://feeds.soundcloud.com/users/soundcloud:users:273239668/sounds.rss","http://www.hellointernet.fm/podcast?format=rss","http://rss.acast.com/danddisfornerds","http://www.unexplainedpodcast.com/episodes/?format=rss","http://rabbits.libsyn.com/rss","http://feeds.soundcloud.com/users/soundcloud:users:213324253/sounds.rss","http://rss.acast.com/themagnusarchives","http://yogpod.libsyn.com/rss","https://audioboom.com/channels/4072907.rss","https://www.unmade.fm/episodes?format=rss","http://fictional.libsyn.com/rss","http://feeds.soundcloud.com/users/soundcloud:users:323807741/sounds.rss","http://criticalrolepodcast.geekandsundry.com/feed/","http://thebuffybreakdown.podbean.com/feed/","http://rss.acast.com/plumbingthedeathstar","http://rss.acast.com/shutupasecond","http://rss.acast.com/moviemaintenance","http://roosterteeth.com/show/always-open/feed/mp3","http://roosterteeth.com/show/rt-podcast/feed/m4a","http://achievementhunter.roosterteeth.com/show/off-topic-the-achievement-hunter-podcast/feed/mp3","https://podcasts.files.bbci.co.uk/b00snr0w.rss"]


def old_fetch_all():
    f= codecs.open("guru99.txt","w+", encoding='utf8')
    for rss in rss_list:
        try:
            feed = feedparser.parse( rss )
            f.write(feed["channel"]["title"] + "\n")
            f.write(feed["channel"]["description"] + "\n")
            f.write(feed["channel"]["category"] + "\n")
            f.write("\n")
            for item in feed["items"]:
                try:
                    f.write(item["id"] + " : " + item["guid"] + "\n")
                    #f.write(item["guid"] + item["links"][1]["href"] + "\n")
                except Exception as inst:
                    logging.error("Error parsing " + item["title"])
                    logging.error(inst)
        except Exception as inst:
            logging.error("Error parsing " + rss)
            logging.error(inst)
    f.close()


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
                    path = urlparse.urlparse(file).path
                    extension = os.path.splitext(path)[1]
                    pathlib2.Path(server_config.podcast_directory + "/" + slugify(row["name"]) + "/").mkdir(parents=True, exist_ok=True) 
                    save = server_config.podcast_directory + "/" + slugify(row["name"]) + "/" + slugify(item["title"]) + extension;
                    wget.download(file, save)  
                    pub = parser.parse(item["published"]).strftime('%Y-%m-%d %H:%M:%S')  # format the publish date
                    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # format the current time
                    insert_cursor.execute(add_episode, (item["id"], item["title"], save, item["description"], row["feed_id"], pub, now))
                    cnx.commit()
            except Exception as inst:
                logging.error("Error parsing " + item["title"])
                logging.error(inst)
    except Exception as inst:
        logging.error("Error parsing " + rss)
        logging.error(inst)
        
    # commit our changes and close our handlers
    cnx.commit()
    episode_cursor.close()
    insert_cursor.close()
    cnx.close()
    