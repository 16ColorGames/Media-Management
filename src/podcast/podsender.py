# encoding: utf-8
from __future__ import print_function

from decimal import Decimal
from datetime import datetime, date, timedelta

import mysql.connector
import logging

import server_config

import sys
from string import Template
import function.email_functions as email_functions

today = date.today()
todaystr = "'" + str(today.year) + "-" + "%02d"%(today.month) + "-" + "%02d"%(today.day)  + "'"
COMMASPACE = ', '

# a temp list of subscribers. this should be pulled from the DB
subscribers = ("oa10712xbox@gmail.com", "allen@16colorgames.com")

  
def send_updates():
    # Connect with the MySQL Server
    cnx = mysql.connector.connect(user=server_config.mysqlUser, password=server_config.mysqlPassword, database=server_config.mysqlDatabase)
    # Get two cursors
    feed_cursor = cnx.cursor(dictionary=True)
    feed_query = "SELECT * FROM podcast_feeds"  # select all of our feeds
    
    feed_cursor.execute(feed_query)
    feeds = {}
    
    for row in feed_cursor:
        feeds[row['feed_id']] = row['name']
    
    print("iterating episodes for " + todaystr + ", checking ")
    episode_cursor = cnx.cursor(dictionary=True)
    episode_query = ("SELECT * FROM podcast_episodes WHERE DATE(addDate) = " + todaystr + " ORDER BY feed")
    episode_cursor.execute(episode_query)
    print(episode_cursor.statement)
    body = str()
    current_feed = "-1"
    for row in episode_cursor:
        if current_feed != row['feed']:
            body = body + feeds[row['feed']] + "\n"
            current_feed = row['feed']
        body = body + "    " + row['title'].decode("utf-8") + "\n"

    logging.info(body)
    
    subject = 'New episodes for ' + todaystr
    message_template = read_template('templates/new_podcast_email.txt')
    message = message_template.substitute(PODCAST_LIST=body)
    
    email_functions.sendEmail(subscribers, subject, message)

    cnx.close()

    
def read_template(filename):
    """This should probably be moved to functions eventually"""
    with open(filename, 'r', encoding='utf-8') as template_file:
        template_file_content = template_file.read()
    return Template(template_file_content)