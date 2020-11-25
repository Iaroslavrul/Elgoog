# -*- coding: utf-8 -*-
import re
import sqlite3
import collections
import uvicorn
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import requests
import distance
import urllib3

urllib3.disable_warnings()

DATABASE_LOCAL = sqlite3.connect('db.sqlite3', check_same_thread=False)
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


# TODO Реализовать обрезку ссылки от мусора перед инсертом

# TODO Добавить запись внутренних ссылок в отдельную базу

# TODO Дописать ф-ю поиска (post) и возврата совпадающих статей по миниматьной расхождения

# TODO Написать обработку шаблонов и выведения совпадающих пересечений

# TODO Реализовать пагинацию

# TODO Добавить рекурсивную индексацию только для внутренних ссылкок

# TODO Добавить коментарии к функциям

# TODO Добавить поиск ссылок на внутренних ссылках


def shorter_link(link):
    """Removing prefixes from links"""
    print('input link: ', link)
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
    print('output link: ', link)
    return link


def get_data_from_response(link):
    """Extracting data (title, text) from a response"""
    response = requests.get(link, timeout=30, verify=False)
    title = re.search(r'<title>(.*?)</title>', response.content.decode('utf-8')).group(0)[7:-8]
    data = re.sub(r'\<(.*?)\>|\n', '', response.content.decode('utf-8'))
    data = re.sub(r'<script>(.*?)</script>', '', data)
    data = re.sub(r'\s{2,}', ' ', data).replace('"', "'")
    return title, data


@app.get('/index/')
def input_link(q: str = Query(None, min_length=4, description='Input in this query your link',
                              regex="http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+")):
    """Adding new links for processing (http://127.0.0.1:8000/index/?q={valid url})"""
    if q:
        title, data = get_data_from_response(q)
        q = shorter_link(q)
        print("q: ", q)
        try:
            sql_insert(q, title, data)
            depth = 3
            url_list_depth = [[] for i in range(0, depth + 1)]
            url_list_depth[0].append(f'https://{q}')
            for depth_i in range(0, depth):
                for links in url_list_depth[depth_i]:
                    domain = re.search(r'^((http[s]?):\/)?\/?([^:\/\s]+)', links).group(3)
                    response = requests.get(links, verify=False, timeout=30).content.decode('utf-8')
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
                        if link is not None and flag is False and link not in url_list_depth[depth_i + 1] and len(
                                requests.get(link, verify=False, timeout=30).history) == 0:
                            url_list_depth[depth_i + 1].append(link)
                            try:
                                title, data = get_data_from_response(link)
                                url_new = shorter_link(link)
                                sql_insert(url_new, title, data)
                            except:
                                print('Link already in DB')
            return url_list_depth
        except Exception as e:
            print(e)
    return "Start page"


@app.get('/search/')
def search(q: str = Query('', min_length=4, description='Поиск')):
    """Get entries with searched words http://127.0.0.1:8000/search/?q={words}"""
    data_rows = search_by_words()
    similarity = {}
    for data_row in data_rows:
        similarity[distance.levenshtein(q, data_row[2])] = {"link": f'https://{data_row[0]}', "title": data_row[1]}
    ordered_dict = collections.OrderedDict(sorted(similarity.items(), reverse=False))
    result_list = list(map(lambda x: ordered_dict[x], list(ordered_dict)))
    # Less is better
    return result_list[:11]


# TODO add async and .lower
# TODO +выбор глубины, пагинации и сортировка
# TODO выводить описание часть текста, где были найдены пересечения


# if __name__ == "__main__":
#     uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True, access_log=False)
