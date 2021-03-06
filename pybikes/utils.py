# -*- coding: utf-8 -*-
# Copyright (C) 2010-2012, eskerda <eskerda@gmail.com>
# Distributed under the AGPL license, see LICENSE.txt

import re

import logging
import requests
from shapely.geometry import Polygon, Point, box

from pybikes.base import BikeShareStation

logger = logging.getLogger(__name__)

def str2bool(v):
    return v.lower() in ["yes", "true", "t", "1"]


def sp_capwords(word):
    blacklist = [
        'el', 'la', 'los', 'las',
        'un', 'una', 'unos', 'unas',
        'lo', 'al', 'del',
        'a', 'ante', 'bajo', 'cabe', 'con', 'contra', 'de', 'desde',
        'en', 'entre', 'hacia', 'hasta', 'mediante', 'para', 'por',
        'según', 'sin',
        # Catala | Valencia | Mallorqui
        'ses', 'sa', 'ses'
    ]
    word = word.lower()
    cap_lambda = lambda i_w: i_w[1].capitalize() if i_w[0] == 0 or i_w[1] not in blacklist else i_w[1]
    return " ".join(map(cap_lambda, enumerate(word.split())))


def clean_string(dirty):
    # Way generic strip_tags. This is unsafe in some cases, but gets the job
    # done for most inputs
    dirty = re.sub(r'<[^>]*?>', '', dirty)
    # Decode any escaped sequences
    dirty = dirty.encode('utf-8').decode('unicode_escape')
    return dirty


class PyBikesScraper(object):
    proxy_enabled = False
    last_request = None
    ssl_verification = True

    def __init__(self, cachedict=None):
        self.headers = {'User-Agent': 'PyBikes'}
        self.proxies = {}
        self.session = requests.session()
        self.cachedict = cachedict

    def setUserAgent(self, user_agent):
        self.headers['User-Agent'] = user_agent

    def request(self, url, method='GET', params=None, data=None, raw=False,
                default_encoding='UTF-8'):
        if self.cachedict and url in self.cachedict:
            return self.cachedict[url]
        response = self.session.request(
            method=method,
            url=url,
            params=params,
            data=data,
            proxies=self.getProxies(),
            headers=self.headers,
            # some endpoints might fail verification, so it's up to the spider
            # to disable it
            verify=self.ssl_verification,
        )
        if response.text is None:
            logger.debug("response to %s is: \n %s", url, response)
        data = response.text

        # Somehow requests defaults to ISO-8859-1 (when no encoding
        # specified). Put it back to UTF-8 by default
        if 'charset' not in response.headers:
            if 'Content-Type' in response.headers:
                if 'text' in response.headers['Content-Type']:
                    response.encoding = default_encoding
                    data = response.text
        if raw:
            data = response.content

        if 'set-cookie' in response.headers:
            self.headers['Cookie'] = response.headers['set-cookie']
        self.last_request = response
        if self.cachedict is not None:
            self.cachedict[url] = data
        return data

    def clearCookie(self):
        if 'Cookie' in self.headers:
            del self.headers['Cookie']

    def setProxies(self, proxies):
        self.proxies = proxies

    def getProxies(self):
        if self.proxy_enabled:
            return self.proxies
        else:
            return {}

    def enableProxy(self):
        self.proxy_enabled = True

    def disableProxy(self):
        self.proxy_enabled = False



def filter_bounds(things, key, *point_bounds):
    def default_getter(thing):
        if isinstance(thing, BikeShareStation):
            return (thing.latitude, thing.longitude)
        return (thing[0], thing[1])
    key = key or default_getter

    bounds = []
    for pb in point_bounds:
        # Assume that a 2 length bound is a square NE/SW
        if len(pb) == 2:
            bb = box(min(pb[0][0], pb[1][0]),
                     min(pb[0][1], pb[1][1]),
                     max(pb[0][0], pb[1][0]),
                     max(pb[0][1], pb[1][1]))
        else:
            bb = Polygon(pb)
        bounds.append(bb)

    for thing in things:
        point = Point(*key(thing))
        if not any(map(lambda pol: pol.contains(point), bounds)):
            continue
        yield thing
