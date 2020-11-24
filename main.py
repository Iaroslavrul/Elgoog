# -*- coding: utf-8 -*-

import uvicorn
from fastapi import FastAPI, Query, Request
from fastapi.responses import Response
import requests
import re
import sqlite3
import distance
import collections
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

DATABASE_LOCAL = sqlite3.connect('db.sqlite3', check_same_thread=False)
sqlite3_cursor = DATABASE_LOCAL.cursor()

from fastapi.middleware.cors import CORSMiddleware

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

templates = Jinja2Templates(directory="templates")



def sql_insert(q, title_, data):
    sqlite3_cursor.execute("""INSERT INTO scan (link, title, text) VALUES (?,?,?)""", (q, title_, data))
    DATABASE_LOCAL.commit()


def search_by_words():
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


@app.get('/index/')
def input_link(q: str = Query(None, min_length=4, description='Input in this query your link',
                              regex="http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+")):
    if q:
        response = requests.get(q, timeout=30, verify=False).content.decode('utf-8')
        title = re.search(r'<title>(.*?)</title>', response).group(0)[7:-8]
        data = re.sub(r'\<(.*?)\>|\n', '', response)
        data = re.sub(r'<script>(.*?)</script>', '', data)
        data = re.sub(r'\s{2,}', ' ', data).replace('"', "'")
        if q[:8] == 'https://':
            q = q[8:]
        elif q[:7] == 'http://':
            q = q[7:]
        if q[:4] == 'www.':
            q = q[4:]
        if q[:4] == 'www.':
            q = q[4:]
        if q[-1] == '/':
            q = q[:-1]
        try:
            sql_insert(q, title, data)
            return {"condition": "Ссылка добавлена"}
        except Exception:
            return {"condition": "Эта ссылка уже есть в базе"}
        # внешние ссылки
        # links = re.findall(r'(<a.*href=\")(htt.*?)(\")', response)
        # outer_links=[]
        # for i, link in enumerate(links):
        #     try:
        #         if len(requests.get(link[1], timeout=30, verify=False).history) == 0:
        #            outer_links.append(link[1])
        #     except Exception as e:
        #         print(e)
        # return {"input link": outer_links}
    return "Start page"


@app.get('/search/', response_class=HTMLResponse)
def search(request: Request, q: str = Query('', min_length=4, description='Поиск')):
    data_rows = search_by_words()
    similarity = {}
    for data_row in data_rows:
        similarity[distance.levenshtein(q, data_row[2])] = {"link": data_row[0], "title": data_row[1]}
    od = collections.OrderedDict(sorted(similarity.items(), reverse=False))
    result_list = list(map(lambda x: od[x], list(od)))
    # Чем меньше - тем лучше
    return templates.TemplateResponse("item.html", {"request": request, "result_list": result_list[:11]})
    # return result_list[:11]



@app.get('/test/')
def test(q: str = Query(None, min_length=4, description='Input in this query your link',
                        regex="http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+")):
    depth = 3  # 3 levels
    domain = re.search(r'^((http[s]?|ftp):\/)?\/?([^:\/\s]+)', q).group(3)
    url_list_depth = [[] for i in range(0, depth + 1)]
    url_list_depth[0].append(q)
    print(domain)
    for depth_i in range(0, depth):
        for links in url_list_depth[depth_i]:
            response = requests.get(q).content.decode('utf-8')
            tags = re.findall(r'(<a.*href=\")(/\w+.*?)(\")', response)
            for link in tags:
                url_new = link[1]
                flag = False
                for item in url_list_depth:
                    for l in item:
                        if url_new == l:
                            flag = True
                url_new = f'https://{domain}{url_new}'
                if url_new is not None and flag is False and url_new not in url_list_depth[depth_i + 1] and len(
                        requests.get(url_new, verify=False, timeout=30).history) == 0:
                    url_list_depth[depth_i + 1].append(url_new)
                    print(links, "->", url_new)
    return {"search": url_list_depth}


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True, access_log=False)

# @app.get('/test/')
# def test(q: str = Query(None, min_length=4, description='Input in this query your link',
#                               regex="http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+")):
#     depth = 5  # 3 levels
#     count = 3  # amount of urls in each level
#     url_list_depth = [[] for i in range(0, depth + 1)]
#     url_list_depth[0].append(q)
#     for depth_i in range(0, depth):
#         for links in url_list_depth[depth_i]:
#             response = requests.get(q).content.decode('utf-8')
#             tags = re.findall(r'(<a.*href=\")(htt.*?)(\")', response)
#             for link in tags:
#                 url_new = link[1]
#                 flag = False
#                 for item in url_list_depth:
#                     for l in item:
#                         if url_new == l:
#                             flag = True
#
#                 if url_new is not None and "http" in url_new and flag is False:
#                     url_list_depth[depth_i + 1].append(url_new)
#                     print(links, "->", url_new)
#     return {"search": url_list_depth}
