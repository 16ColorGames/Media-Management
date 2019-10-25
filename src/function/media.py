import sys
import os
import pymongo
import server_config
import json
import urllib
import re

def add_new(file, name):
    url = "http://www.omdbapi.com/?apikey="+server_config.omdb_api_key+"&plot=full&t="
    x = re.search(".*\(\d{4}\)", name)   
    
    myclient = pymongo.MongoClient(server_config.mongodbURL)
    mydb = myclient[server_config.mongodbDB]
    mycol = mydb["items"]
    tagcol = mydb["tags"]
    
    if x:
        url = url + name[0:-6].rstrip().replace(' ', '+') + "&y=" + name[-5:-1]
    else:
        url = url + name.rstrip().replace(' ', '+')
    response = urllib.urlopen(url)
    data = json.loads(response.read())
    if "Error" not in data:
        tags = [tagcol.find_one({"Name":"Automatic","Type":"Admin"}).get("_id")]
        if "Rated" in data:
            rating_res = tagcol.find_one({"Name": data.get("Rated"), "Type":"Rating"})
            if rating_res is None:
                tags.append(tagcol.insert_one({"Name":data.get("Rated"), "Type": "Rating"}).inserted_id)
            else:
                tags.append(rating_res["_id"])
        if "Genre" in data:
            genres = data.get("Genre").split(', ')
            for genre in genres:
                genre_res = tagcol.find_one({"Name": genre, "Type":"Genre"})
                if genre_res is None:
                    tags.append(tagcol.insert_one({"Name": genre, "Type": "Genre"}).inserted_id)
                else:
                    tags.append(genre_res['_id'])
        item_dict = {"File": file, "Title": data.get('Title'), "Tags": tags, "IMDB": data.get("imdbID"), "Description": data.get("Plot", ""), "Poster": data.get("Poster", ""), "Year":data.get("Year")}
        mycol.insert_one(item_dict)
    else:
        tags = [tagcol.find_one({"Name":"Retrieval Failed","Type":"Admin"}).get("_id")]
        item_dict = {"File": file,"Tags": tags}
        mycol.insert_one(item_dict)

def search_locations():
    myclient = pymongo.MongoClient(server_config.mongodbURL)
    mydb = myclient[server_config.mongodbDB]
    itemcol = mydb["items"]
    mycol = mydb["locations"]
    for location in mycol.find():
        entries = os.listdir(location['file'])
        for entry in entries:
            entry_full=os.path.join(location['file'],entry)
            if os.path.isdir(entry_full):
                #in first sub-folders
                subentries = os.listdir(entry_full)
                for subentry in subentries:
                    filename, file_extension = os.path.splitext(subentry)
                    if file_extension in server_config.valid_formats:
                        sub_full = os.path.join(entry_full,subentry)
                        if itemcol.find_one({"File": sub_full}) is None:
                            add_new(sub_full, filename)