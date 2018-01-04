from __future__ import print_function
import mysql.connector
import server_config
import logging
from mysql.connector import errorcode


# setup our table definitions
TABLES = {}
TABLES['podcast_feeds'] = (
    "CREATE TABLE `podcast_feeds` ("
    " `feed_id` INT NOT NULL AUTO_INCREMENT,"
    " `name` VARCHAR(255) NOT NULL,"
    " `url` VARCHAR(255) NOT NULL,"
    " `categories` TEXT NOT NULL,"
    " PRIMARY KEY (`feed_id`)"
    " ) ENGINE = InnoDB DEFAULT CHARSET=utf8")
TABLES['podcast_episodes'] = (
    "CREATE TABLE `podcast_episodes` ("
    " `id` varchar(255) NOT NULL,"
    " `title` TEXT NOT NULL,"
    " `file` TEXT NOT NULL,"
    " `description` TEXT NOT NULL,"
    " `feed` INT NOT NULL,"
    " `pubDate` DATETIME NOT NULL,"
    " `addDate` DATETIME NOT NULL,"
    " UNIQUE (`id`)"
    " ) ENGINE = InnoDB DEFAULT CHARSET=utf8")


def create_database(cursor):
    """
    This funtion will attempt to create the database defined in server_config.py
    """
    try:
        cursor.execute(
            "CREATE DATABASE {} DEFAULT CHARACTER SET 'utf8'".format(server_config.mysqlDatabase))
    except mysql.connector.Error as err:
        logging.critical("Failed creating database: {}".format(err))
        exit(1)


def setup_sql():
    """
    Attempt to connect or create out database, then attempt to create our tables as defined in TABLES
    """
    cnx = mysql.connector.connect(user=server_config.mysqlUser, password=server_config.mysqlPassword)
    cursor = cnx.cursor()
    try:
        cnx.database = server_config.mysqlDatabase  
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_BAD_DB_ERROR:
            create_database(cursor)
            cnx.database = server_config.mysqlDatabase
        else:
            logging.error(err)
            exit(1)
    for name, ddl in TABLES.iteritems():
        try:
            logging.debug("Creating table {}: ".format(name))
            cursor.execute(ddl)
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_TABLE_EXISTS_ERROR:
                logging.debug("already exists.")
            else:
                logging.error(err.msg)
        else:
            logging.debug("OK")
    cursor.close()
    cnx.close()