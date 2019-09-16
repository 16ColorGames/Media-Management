# encoding: utf-8
from __future__ import print_function

from decimal import Decimal
from datetime import datetime, date, timedelta
import pytz

import logging

import server_config
import pymongo

import sys
import re
import pathlib2
from string import Template
from feedgen.feed import FeedGenerator
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
        
def generate_feeds():
    pathlib2.Path(server_config.podcast_directory + "/.feeds").mkdir(parents=True, exist_ok=True) 
    
    myclient = pymongo.MongoClient(server_config.mongodbURL)
    mydb = myclient[server_config.mongodbDB]
    mycol = mydb["feeds"]
    
    by_id = {}
    tags = {}
    tags['all'] = []
    
    for row in mycol.find():
        by_id[row['_id']] = row['name']
        cats = row['categories'].split(', ')
        for cat in cats:
            lcat = cat.lower()
            if lcat not in tags:
                tags[lcat] = []
            tags[lcat].append(row['_id'])
            tags['all'].append(row['_id'])
    
    for key, value in tags.iteritems():
        fg = FeedGenerator()
        fg.load_extension('podcast')
        fg.id(server_config.public_url + 'podcast/masterfeeds/' + key + '.xml')
        fg.title(key + " Master Feed")
        fg.link(href=server_config.public_url + "feeds/" + key + ".xml", rel='alternate')
        fg.subtitle('Master feed for ' + key + ' podcasts')
        
        sarr = ', '.join([str(a) for a in value])
        
        myclient = pymongo.MongoClient(server_config.mongodbURL)
        mydb = myclient[server_config.mongodbDB]
        mycol = mydb["episodes"]
        
        feeds = []
        if (key == 'all'):
            res = mycol.find().limit(300).sort([('published', -1)])
        else:
            for a in value:
                feeds.append(a)
            res = mycol.find({"feed":{"$in":feeds}})
        
        for row in res:
            fe = fg.add_entry()
            fe.id(row['uuid'])
            if(key == 'all'):
                fe.title(by_id[row['feed']] + ' | ' + remove_control_characters(row['title'].decode('utf-8')))
            else:
                fe.title(remove_control_characters(row['title'].decode('utf-8')))
            pub = datetime.strptime(row['published'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.UTC)
            fe.pubDate(pub)
            fe.description(remove_control_characters(row['description'].decode('utf-8')))
            fe.enclosure(server_config.public_url + row['file'].replace(server_config.podcast_directory,""),0,'audio/mpeg')
        
        fg.rss_str(pretty=True)
        fg.rss_file(server_config.podcast_directory + ".feeds/" + key + ".xml")