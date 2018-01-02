import server_config
import function.setupDatabase as setupDatabase
import podcast.podcatcher as podcatcher
import datetime

setupDatabase.setup_sql()
podcatcher.fetch_episodes()