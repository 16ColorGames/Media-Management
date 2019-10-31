import sys
import os
import pymongo
import server_config
import wget
import json
import urllib
import re

def process_person_full_request(request):
    myclient = pymongo.MongoClient(server_config.mongodbURL)
    mydb = myclient[server_config.mongodbDB]
    entitycol = mydb["entities"]
    person = entitycol.find_one({"_id": request["Id"]})
    
    if person is None:
        return
    
    url = "https://api.themoviedb.org/3/person/" + str(person["TMDBid"]) + "?api_key=" + server_config.tmdb_api_key+"&language=en-US"
    response = urllib.urlopen(url)
    data = json.loads(response.read())
    
    if "profile_path" in data:
        if data["profile_path"] is not None:
            name, ext = os.path.splitext(data["profile_path"])
            profile = urllib.urlopen("https://image.tmdb.org/t/p/original/" + data["profile_path"]).read()
            with open(server_config.storage_directory+"images/"+ str(person["_id"]) + "-profile"+ext, 'wb') as f:
                f.write(profile)
    
    entitycol.update_one({"_id": request["Id"]},{"$set":{"Bio": data["biography"], "Birthday": data.get("birthday", "unknown"), "IMDBid": data["imdb_id"]}})
    
    

def process_item_cast_request(request):
    myclient = pymongo.MongoClient(server_config.mongodbURL)
    mydb = myclient[server_config.mongodbDB]
    itemcol = mydb["items"]
    entitycol = mydb["entities"]
    relcol = mydb["relations"]
    reqcol = mydb["requests"]
    
    item = itemcol.find_one({"_id": request["Id"]})
    
    if item is None:
        return
    
    itemcol.delete_one({"_id": request["Id"]})
    
    url = "https://api.themoviedb.org/3/movie/" + str(item["TMDBid"]) + "/credits?api_key=" + server_config.tmdb_api_key+"&language=en-US"
    response = urllib.urlopen(url)
    data = json.loads(response.read())

    for cast in data["cast"]:
        ctag = entitycol.find_one({"TMDBid": cast["id"], "Type":"Person"})
        if ctag is None:
            entitycol.insert_one({"TMDBid":cast["id"],"Type":"Person","Name":cast["name"]})
            ctag = entitycol.find_one({"TMDBid": cast["id"], "Type":"Person"})
            reqcol.insert_one({"Object":"Entity", "Id": ctag["_id"], "Type":"Full", "Spec":"Person"})
        relcol.update_one({"ItemId": item["_id"], "EntityId": ctag["_id"]},{"$set": {"ItemId": item["_id"], "EntityId": ctag["_id"],"Relation": "Actor", "Character": cast["character"]}},True)
 
    for crew in data["crew"]:
        ctag = entitycol.find_one({"TMDBid": cast["id"], "Type":"Person"})
        if ctag is None:
            entitycol.insert_one({"TMDBid":cast["id"],"Type":"Person","Name":cast["name"]})
            ctag = entitycol.find_one({"TMDBid": cast["id"], "Type":"Person"})
            reqcol.insert_one({"Object":"Entity", "Id": ctag["_id"], "Type":"Full", "Spec":"Person"})
        relcol.update_one({"ItemId": item["_id"], "EntityId": ctag["_id"]}, {"$set":{"ItemId": item["_id"], "EntityId": ctag["_id"],"Relation": "Crew", "Job": cast.get("job", "")}},True)
 
    itemcol.insert_one(item)

def process_item_full_request(request):
    myclient = pymongo.MongoClient(server_config.mongodbURL)
    mydb = myclient[server_config.mongodbDB]
    itemcol = mydb["items"]
    tagcol = mydb["tags"]
    entitycol = mydb["entities"]
    relcol = mydb["relations"]
    
    item = itemcol.find_one({"_id": request["Id"]})
    
    if item is None:
        return
    
    itemcol.delete_one({"_id": request["Id"]})
    
    url = "https://api.themoviedb.org/3/movie/" + item["TMDBid"] + "?api_key=" + server_config.tmdb_api_key+"&language=en-US"
    response = urllib.urlopen(url)
    data = json.loads(response.read())
    
    item["Title"] = data["title"]
    item["IMDBid"] = data["imdb_id"]
    item["Released"] = data["release_date"]
    item["Description"] = data["overview"]
    item["Tagline"] = data["tagline"]
    
    item["Tags"].append(tagcol.find_one({"Type":"Category", "Name": "Movie"}))
    
    for genre in data["genres"]:
        gtag = tagcol.find_one({"Type":"Genre", "Name": genre["name"]})
        if gtag is None:
            tagcol.insert_one({"Type":"Genre", "Name": genre["name"]})
            gtag = tagcol.find_one({"Type":"Genre", "Name": genre["name"]})
        item["Tags"].append(gtag["_id"])
    
    for company in data["production_companies"]:
        ctag = entitycol.find_one({"TMDBid": company["id"], "Type":"Company"})
        if ctag is None:
            entitycol.insert_one({"TMDBid":company["id"],"Type":"Company","Name":company["name"]})
            ctag = entitycol.find_one({"TMDBid": company["id"], "Type":"Company"})
        relcol.update_one({"ItemId": item["_id"], "EntityId": ctag["_id"]}, {"$set":{"ItemId": item["_id"], "EntityId": ctag["_id"],"Relation": "Production"}},True)
    
    if "poster_path" in data:
        name, ext = os.path.splitext(data["poster_path"])
        poster = urllib.urlopen("https://image.tmdb.org/t/p/original/" + data["poster_path"]).read()
        with open(server_config.storage_directory +"images/"+ str(item["_id"]) + "-poster"+ext, 'wb') as f:
            f.write(poster)
        
    if "backdrop_path" in data:
        name, ext = os.path.splitext(data["backdrop_path"])
        backdrop = urllib.urlopen("https://image.tmdb.org/t/p/original/" + data["backdrop_path"]).read()
        with open(server_config.storage_directory+"images/"+ str(item["_id"]) + "-backdrop"+ext, 'wb') as f:
            f.write(backdrop)
       
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
    
    try:
        first = data["results"][0]
        
        tags = [tagcol.find_one({"Name":"Automatic","Type":"Admin"}).get("_id")]
        item["Tags"] = tags
        item["Title"] = first["title"]
        item["TMDBid"] = first["id"]
        
        itemcol.insert_one(item)
    except IndexError:
        print("Search failed for " + item["File"])
        pass

def process_requests():
    myclient = pymongo.MongoClient(server_config.mongodbURL)
    mydb = myclient[server_config.mongodbDB]
    reqcol = mydb["requests"]
    
    for request in reqcol.find().limit(10):
        if request["Object"] == "Item":
            if request["Type"] == "Basic":
                process_item_basic_request(request)
                reqcol.delete_one({"_id": request["_id"]})
            elif request["Type"] == "Full":
                process_item_full_request(request)
                reqcol.delete_one({"_id": request["_id"]})
            elif request["Type"] == "Cast":
                process_item_cast_request(request)
                reqcol.delete_one({"_id": request["_id"]})
        elif request["Object"] == "Entity":
            if request["Type"] == "Full":
                if request["Spec"] == "Person":
                    process_person_full_request(request)
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
