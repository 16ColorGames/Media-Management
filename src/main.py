import server_config
import function.setupDatabase as setupDatabase
import podcast.podcatcher as podcatcher
import podcast.podsender as podsender
import server.main_server as server
import datetime
import logging
import sys

def main():
    logging.basicConfig(filename=server_config.logfile,level=logging.DEBUG)
    setupDatabase.setup_sql()
    podcatcher.update_feeds()
    podsender.send_updates()
    
if __name__ == '__main__':
    args = sys.argv[1:]
    reload(sys)  
    sys.setdefaultencoding('utf8')
    if len(args) == 0:
        main()
    else:
        server.start()