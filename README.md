# Media-Management
This is a python-based webb application designed to track and manage home media libraries. The current focus is to get podcast retrieval and saving functional; other types of media will follow.

If you are planning on running your own instance, you will need the following python addons:
	rsslibraries
	mysql-connector-python
	wget
	logging
	pathlib2
	python-slugify
	jinja2
	webapp2
	webapp2_extras
	cascade
	
In addition, you will need a local instance of MySQL and a user you are comfortable giving acces to. Place your systems relevant settings in src/serverconfig.py