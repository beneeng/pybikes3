# -*- coding: utf-8 -*-
# Copyright (C) 2010-2012, eskerda <eskerda@gmail.com>
# Distributed under the AGPL license, see LICENSE.txt

import json
import operator

from .base import BikeShareSystem, BikeShareStation
from . import utils, exceptions

__all__ = ['Gbfs', 'GbfsStation']


class Gbfs(BikeShareSystem):

    def __init__(self, tag, meta, feed_url):
        # Add feed_url to meta in order to be exposed to the API
        meta['gbfs_href'] = feed_url

        super(Gbfs, self).__init__(tag, meta)
        self.feed_url = feed_url

    def update(self, scraper=None):
        if scraper is None:
            scraper = utils.PyBikesScraper()

        # Make the request to gbfs.json and convert to json
        html_data = json.loads(scraper.request(self.feed_url, raw=True).decode())

        # Create a dict with name-url pairs for easier access
        # of urls (just in case)
        feeds = {}
        for feed in html_data['data']['en']['feeds']:
            feeds[feed['name']] = feed['url']

        # Station Information and Station Status data retrieval
        station_information = json.loads(
            scraper.request(feeds['station_information'])
        )['data']['stations']
        station_status = json.loads(
            scraper.request(feeds['station_status'])
        )['data']['stations']
        # Aggregate status and information by uid
        # Note there's no guarantee that station_status has the same
        # station_ids as station_information.
        station_information = {s['station_id']: s for s in station_information}
        station_status = {s['station_id']: s for s in station_status}
        # Any station not in station_information will be ignored
        stations = [
            (station_information[uid], station_status[uid])
            for uid in list(station_information.keys())
        ]
        self.stations = []
        for info, status in stations:
            info.update(status)
            try:
                station = GbfsStation(info)
            except exceptions.StationPlannedException:
                continue
            self.stations.append(station)


class GbfsStation(BikeShareStation):

    def __init__(self, info):
        """
        Example info variable:
        {u'is_installed': 1, u'post_code': u'null', u'capacity': 31,
        u'name': u'Ft. York / Capreol Crt.', u'cross_street': u'null',
        u'num_bikes_disabled': 0, u'last_reported': 1473969337,
        u'lon': -79.395954, u'station_id': u'7000', u'is_renting': 1,
        u'num_docks_available': 26, u'num_docks_disabled': 0,
        u'address': u'Ft. York / Capreol Crt.', u'lat': 43.639832,
        u'num_bikes_available': 5, u'is_returning': 1}

        So let's extract the dataaa
        """
        super(GbfsStation, self).__init__()
        if not info['is_installed']:
            raise exceptions.StationPlannedException()

        self.name = str(info['name'])
        self.bikes = int(info['num_bikes_available'])
        self.free = int(info['num_docks_available'])
        self.latitude = float(info['lat'])
        self.longitude = float(info['lon'])
        self.extra = {
            # address is optional
            'address': info.get('address'),
            'uid': info['station_id'],
            'renting': info['is_renting'],
            'returning': info['is_returning'],
            'last_updated': info['last_reported']
        }
