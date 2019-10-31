import sys
import os
import pymongo
import server_config
import json
import urllib
import re

def process_item_full_request(request):
    myclient = pymongo.MongoClient(server_config.mongodbURL)
    mydb = myclient[server_config.mongodbDB]
    itemcol = mydb["items"]
    tagcol = mydb["tags"]
    entitycol = mydb["entities"]
    
    item = itemcol.find_one({"_id": request["Id"]})
    
    if item is None:
        return
    
    itemcol.delete_one({"_id": request["Id"]})
    
    url = "https://api.themoviedb.org/3/movie/" + item["TMDBid"] + "?api_key=" + +server_config.tmdb_api_key+"&language=en-US"
    response = urllib.urlopen(url)
    data = json.loads(response.read())
    
    item["Title"] = data["title"]
    item["IMDBid"] = data["imdb_id"]
    
    if item["Companies"] is None:
        item["Companies"] = []
    
    for genre in data["genres"]:
        gtag = tagcol.find_one({"Type":"Genre", "Name": genre["name"]})
        if gtag is None:
            gtag = tagcol.insert_one({"Type":"Genre", "Name": genre["name"})
        item["Tags"].append(gtag["_id"])
    
    for company in data["production_companies"]:
        ctag = entitycol.find_one({"TMDBid": company["id"], "Type":"Company"})
        if ctag is None:
            ctag = entitycol.insert_one({"TMDBid":company["id"],"Type":"Company","Name":company["name"]})
        item["Companies"].append(ctag["_id"])
  
    itemcol.insert_one(item)
    

def process_item_basic_request(request):
    myclient = pymongo.MongoClient(server_config.mongodbURL)
    mydb = myclient[server_config.mongodbDB]
    itemcol = mydb["items"]
    tagcol = mydb["tags"]
    
    item = itemcol.find_one({"_id": request["Id"]})
    
    if item is None:
        return
    
    itemcol.delete_one({"_id": request["Id"]})
    
    url = "https://api.themoviedb.org/3/search/movie?api_key="+server_config.tmdb_api_key+"&language=en-US&page=1&include_adult=false&query="
    
    path, file = os.path.split(item["File"])
    name, file_extension = os.path.splitext(file)
    
    x = re.search(".*\(\d{4}\)", name)
   
    if x:
        url = url + name[0:-6].rstrip().replace(' ', '%20') + "&year=" + name[-5:-1]
    else:
        url = url + name.rstrip().replace(' ', '%20')
    response = urllib.urlopen(url)
    data = json.loads(response.read())
    first = data["results"][0]
    
    tags = [tagcol.find_one({"Name":"Automatic","Type":"Admin"}).get("_id")]
    item["Tags"] = tags
    item["Title"] = first["title"]
    item["TMDBid"] = first["id"]
    
    itemcol.insert_one(item)    

def process_requests():
    myclient = pymongo.MongoClient(server_config.mongodbURL)
    mydb = myclient[server_config.mongodbDB]
    reqcol = mydb["requests"]
    
    for request in reqcol.find().limit(10):
        if request["Object"] == "Item":
            if request["Type"] == "Basic":
                process_item_basic_request(request)
                reqcol.delete_one({"_id": request["_id"]})
            elif requests["Type"] == "Full":
                process_item_full_request(request)
                reqcol.delete_one({"_id": request["_id"]})

def add_new(file, name):
    myclient = pymongo.MongoClient(server_config.mongodbURL)
    mydb = myclient[server_config.mongodbDB]
    mycol = mydb["items"]
    tagcol = mydb["tags"]
    recol = mydb["requests"]
    
    item_tags = [tagcol.find_one({"Name":"Unprocessed","Type":"Admin"}).get("_id")]
    item_dict = {"File": file,"Tags": item_tags}
    inserted = mycol.insert_one(item_dict)
    
    req_dict = {"Object": "Item", "Id": inserted.inserted_id, "Type": "Basic"}
    recol.insert_one(req_dict)
    
    

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
