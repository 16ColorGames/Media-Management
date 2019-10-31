import server_config
import podcast.podcatcher as podcatcher
import podcast.podsender as podsender
import podcast.podfeed as podfeed
import function.media as media
import server.main_server as server
import datetime
import logging
import sys
import os
import gaerun
import schedule
import threading
import time
import server_config

def update():
    podcatcher.update_feeds()
    podfeed.generate_feeds()
    media.search_locations()

def fast_update():
    media.process_requests()

def server_thread():
    logging.info("Starting server thread")
    server.start()

def update_thread():
    logging.info("Starting update thread")
    schedule.every(server_config.update_freq).hours.do(update)
    schedule.every(15).seconds.do(fast_update)
    
    media.search_locations()
    update()
    #podcatcher.update_descriptions()
    while True:
        schedule.run_pending()
        time.sleep(1)
    
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    reload(sys)
    sys.setdefaultencoding('utf8')
    u = threading.Thread(target=update_thread)
    s = threading.Thread(target=server_thread)
    u.start()
    s.start()
    
    
    #media.search_locations()