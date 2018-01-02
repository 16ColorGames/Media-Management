import server_config
import function.setupDatabase as setupDatabase
import podcast.podcatcher as podcatcher
import datetime
import logging


def main():
    logging.basicConfig(filename=server_config.logfile,level=logging.DEBUG)
    setupDatabase.setup_sql()
    podcatcher.update_feeds()
    
if __name__ == '__main__':
    main()