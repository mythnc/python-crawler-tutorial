#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import datetime
import random
import requests
import lxml
from pyquery import PyQuery as pq
from pymongo import MongoClient, DESCENDING


mongo_client = MongoClient()
ptt_db = mongo_client.beauty_board_db
article_col = ptt_db.beauty_article_col
beauty_url = "http://www.ptt.cc/bbs/Beauty/index.html"

conditions = {}


def get_requests_data(url):
    while True:
        try:
            r = requests.get(url)
            s = pq(r.text)
            if '503' in s('title').text():
                continue
            return s
        except lxml.etree.XMLSyntaxError:
            pass


def get_article_metadata_lists(one_ptt_url):
    """all article urls in one page,
    including metadata (push and title)
    """
    s = get_requests_data(one_ptt_url)

    s = s('.r-ent')
    article_metadata = []
    for i in range(len(s)):
        metadata = {}
        article = s.eq(i)
        relative_article_url = article('.title a').attr("href")
        if relative_article_url and relative_article_url.startswith('/bbs'):
            metadata['url'] = relative_article_url.split('/')[-1][:-5]
            metadata['push'] = trans_push_format(article('.nrec').text())
            metadata['title'] = article('.title').text()
            article_metadata.append(metadata)

    return article_metadata


def trans_push_format(push_text):
    if not push_text:
        return 0
    elif push_text == u'爆':
        return 100
    elif push_text.startswith('X'):
        return -1
    else:
        return int(push_text)


def get_max_pages(ptt_index_url):
    """the page number the board has
    """
    s = get_requests_data(ptt_index_url)

    pull_right_urls = pq(s('div.btn-group.pull-right > a')[1]).\
        attr("href").split("index")[1].split(".")
    max_page = int(pull_right_urls[0])
    return max_page + 1


def get_all_pages_url(ptt_index_url):
    """accroding get_max_pages,
    generate each page url
    index, index0, index1, ... ,
    index == indexMax
    """
    max_page = get_max_pages(ptt_index_url)
    url_head = ptt_index_url.split('index')[0]
    all_urls = ["{}index{}.html".format(url_head, i) for i in range(max_page)]
    all_urls.append(ptt_index_url)
    return all_urls


def get_article_data(article_url):
    url = 'http://www.ptt.cc/bbs/Beauty/{}.html'.format(article_url)

    s = get_requests_data(url)

    data = {}
    metadata = s('.article-meta-value')
    if len(metadata) != 4:
        return data

    urls = s('#main-content > a').map(lambda i, e: pq(this).text())
    pic_urls = []
    for url in urls:
        if url.endswith('.gif'):
            continue

        if url.endswith('.jpg') or url.endswith('.png'):
            if 'xuite' in url:
                get_xuite_img(pic_urls, url)
            else:
                pic_urls.append(url)
        elif 'imgur' in url and '/a/' not in url:
            get_imgur_img(pic_urls, url)
        elif 'picmoe.net' in url:
            get_picmoe_img(pic_urls, url)

    date = trans_article_date_format(metadata.eq(3).text())
    if not date:
        return data

    if pic_urls:
        data['pic'] = pic_urls
        data['date'] = date
    return data


def trans_article_date_format(article_date):
    print(article_date)
    trans_month_format = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4,
                          'May': 5, 'Jun': 6, 'Jul': 7, 'Aug': 8,
                          'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}
    date_info = article_date.split()
    if len(date_info) != 5:
        return None

    month = trans_month_format.get(date_info[1], None)
    if not month:
        return None

    time_info = date_info[3].split(':')
    if len(time_info) != 3:
        return None

    year = int(date_info[-1])
    day = int(date_info[2])
    time = [int(t) for t in time_info]

    return datetime.datetime(year, month, day, *time)


def get_xuite_img(pic_urls, url):
    r = requests.get(url)
    s = pq(r.text)
    url = s('#photo_img_640').attr('src')
    pic_urls.append(url)


def get_imgur_img(pic_urls, url):
    url = url.split('#')[0]
    urls = []
    if ',' in url or '&' in url:
        if ',' in url:
            url = url.split(',')
        if '&' in url:
            url = url.split('&')
        urls = url[:1] + ['http://imgur.com/{}'.format(x) for x in url[1:]]
        urls = ['{}.jpg'.format(u) for u in urls]
        pic_urls += urls
    else:
        pic_urls.append(url + ".jpg")


def get_picmoe_img(pic_urls, url):
    if '.jpg' in url:
        i = url.find('.jpg')
        url = '{}.jpg'.format(url[:i])
        pic_urls.append(url)
        return
    pic = 'http://picmoe.net/src/{}s.jpg'.format(url.split('id=')[1])
    pic_urls.append(pic)


def query(conditions=conditions):
    push_number = conditions['push_number']
    keyword = conditions['keyword']
    post_number = conditions['post_number']

    if keyword:
        nodes = list(article_col.find({'title': {'$regex': keyword}})
                     .sort('date', DESCENDING).limit(post_number))
        for node in nodes:
            i = random.randint(0, len(node['pic'])-1)
            node['pic'] = node['pic'][i]
        return nodes

    if push_number:
        result = article_col.find({'push': {'$gte': push_number}}).\
            sort('date', DESCENDING)
    else:
        result = article_col.find().sort('date', DESCENDING)

    if post_number:
        result = result.limit(post_number)

    nodes = list(result)
    for node in nodes:
        i = random.randint(0, len(node['pic'])-1)
        node['pic'] = node['pic'][i]
    return nodes


def gen_html(nodes):
    print('<!DOCTYPE HTML>')
    print('<head><meta charset="UTF-8"></head>')
    print('<body>')
    for node in nodes:
        print('<a href="{url}" target="_blank">原始文章</a>'.format(**node))
        print('<br>')
        print('<img src="{pic}" alt="" height="" width="">'.format(**node))
        print('<br>')
        print('<br>')
    print('</body>')


def set_condition(push_number=None, keyword=None, post_number=100):
    conditions['push_number'] = push_number
    conditions['keyword'] = keyword  # unicode problem u'xxxx'
    conditions['post_number'] = post_number


def save_all_articles_to_db(limit=None, update=False):
    all_page_urls = get_all_pages_url(beauty_url)
    if limit:
        all_page_urls = all_page_urls[:limit+1]
    elif update:
        all_page_urls = all_page_urls[-35:]
    for page_url in reversed(all_page_urls):
        print(page_url)
        article_metadata = get_article_metadata_lists(page_url)
        for metadata in article_metadata:
            article_data = get_article_data(metadata['url'])
            if article_data:
                article_data.update(metadata)
                print(article_data['url'])
                article_col.update({'url': article_data['url']},
                                   article_data, upsert=True)


set_condition()

if __name__ == '__main__':
    # requests.packages.urllib3.disable_warnings()
    save_all_articles_to_db(update=True)
    # nodes = query()
    # gen_html(nodes)