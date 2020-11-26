# -*- coding: utf-8 -*-
import re
import sqlite3
import collections
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import requests
import distance
import urllib3

urllib3.disable_warnings()

DATABASE_LOCAL = sqlite3.connect('../app/db.sqlite3', check_same_thread=False)
sqlite3_cursor = DATABASE_LOCAL.cursor()

origins = [
    "http://localhost.tiangolo.com",
    "https://localhost.tiangolo.com",
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://10.21.3.156:8000",
    "https://10.21.3.156:8000",
    "10.21.3.156",
    "10.21.3.156:8000"
]

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def sql_insert(link_, title_, data):
    """Adding new entries to the database: (link, title, text)"""
    sqlite3_cursor.execute("""INSERT OR IGNORE INTO scan (link, title, text) VALUES (?,?,?)""", (link_, title_, data))
    DATABASE_LOCAL.commit()


def search_by_words():
    """Uploading entries from the database: (link, title, text)"""
    sqlite3_cursor.execute("""select link, title, text from scan""")
    data = sqlite3_cursor.fetchall()
    return data


def shorter_link(link):
    """Removing prefixes from links"""
    if link[:8] == 'https://':
        link = link[8:]
    elif link[:7] == 'http://':
        link = link[7:]
    if link[:4] == 'www.':
        link = link[4:]
    if link[:4] == 'www.':
        link = link[4:]
    if link[-1] == '/':
        link = link[:-1]
    return link


def get_data_from_response(link):
    """Extracting data (title, text) from a response"""
    try:
        response = requests.get(link, timeout=60, verify=False).content.decode('utf-8')
        title = re.search(r'<title>(.*?)</title>', response).group(0)[7:-8]
        data = re.sub(r'\<(.*?)\>|\n', '', response)
        data = re.sub(r'<script>(.*?)</script>', '', data)
        data = re.sub(r'\s{2,}', ' ', data).replace('"', "'")
        return title, data
    except:
        pass


@app.get('/index/')
async def input_link(q: str = Query(None, min_length=4, description='Input in this query your link',
                                    regex="http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+")):
    """Adding new links for processing (http://127.0.0.1:8000/index/?q={valid url})"""
    if q:
        title, data = get_data_from_response(q)
        q = shorter_link(q)
        try:
            sql_insert(q, title, data)
            depth = 3
            url_list_depth = [[] for i in range(0, depth + 1)]
            url_list_depth[0].append(f'https://{q}')
            for depth_i in range(0, depth):
                for links in url_list_depth[depth_i]:
                    domain = re.search(r'^((http[s]?):\/)?\/?([^:\/\s]+)', links).group(3)
                    try:
                        response = requests.get(links, verify=False, timeout=60).content.decode('utf-8')
                    except Exception as e:
                        print(e)
                    outside_links = list(set(map(lambda link: link[1],
                                                 re.findall(r'(<a.*href=\")(htt.*?)(\")', response))))
                    inside_links = list(set(map(lambda link: f'https://{domain}{link[1]}',
                                                re.findall(r'(<a.*href=\")(/\w+.*?)(\")', response))))
                    inside_links.extend(outside_links)
                    for link in inside_links:
                        flag = False
                        for item in url_list_depth:
                            for l in item:
                                if link == l:
                                    flag = True
                        try:
                            if link is not None and flag is False and link not in url_list_depth[depth_i + 1] and len(
                                    requests.get(link, verify=False, timeout=60).history) == 0:
                                url_list_depth[depth_i + 1].append(link)
                                try:
                                    title, data = get_data_from_response(link)
                                    url_new = shorter_link(link)
                                    sql_insert(url_new, title, data)
                                except:
                                    print('Link already in DB')
                        except:
                            print('connection error')
            return url_list_depth
        except Exception as e:
            print(e)
    return "Please, enter new link"


@app.get('/search/')
async def search(q: str = Query('', min_length=4, description='Поиск')):
    """Get entries with searched words http://127.0.0.1:8000/search/?q={words}"""
    data_rows = search_by_words()
    similarity = {}
    for data_row in data_rows:
        similarity[distance.levenshtein(q.lower(), data_row[2].lower())] = {"link": f'https://{data_row[0]}',
                                                                            "title": data_row[1]}
    ordered_dict = collections.OrderedDict(sorted(similarity.items(), reverse=False))
    result_list = list(map(lambda x: ordered_dict[x], list(ordered_dict)))
    # Less is better
    return result_list[:11]
