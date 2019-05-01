import server_config
import function.setupDatabase as setupDatabase
import podcast.podcatcher as podcatcher
import podcast.podsender as podsender
import podcast.podfeed as podfeed
import server.main_server as server
import datetime
import logging
import sys
import os
import gaerun

def main():
    podcatcher.update_feeds()
    podfeed.generate_feeds()
    
    
if __name__ == '__main__':
   # logging.basicConfig(filename=server_config.logfile,level=logging.DEBUG)
    logging.basicConfig(level=logging.DEBUG)
    args = sys.argv[1:]
    reload(sys)
    sys.setdefaultencoding('utf8')
    logging.info("Started Logging")
    print logging.getLoggerClass().root.handlers
    #gaerun.startup()
    if len(args) == 0:
        main()
    else:
        if args[0] == "server":
            server.start()
        elif args[0] == "desc":
            podcatcher.update_descriptions()