#!/usr/bin/python
# -*- coding: utf-8 -*-


#
# Vimeo API sync mechanism by Andre Goncalves
#

# Global dependencies
import re
import requests
import sys
from datetime import datetime
from collective.vimeosyncmanager.utils import DATE_FORMAT

try:
    from urllib.parse import urlencode
except ImportError:
    # support python 2
    from urllib import urlencode

# Product dependencies
from collective.vimeosyncmanager.error_handling.error import raise_error
from collective.vimeosyncmanager.utils import clean_whitespaces

# API
import vimeo

import os, io
import json

class APIConnection(object):

    #
    # Local definitions to the API connection
    #

    MINIMUM_SIZE = 1

    API_MAPPING = {

    }

    #
    # Initialisation methods
    #
    def __init__(self, api_settings):
        
        self.api_settings = api_settings
        
        self.showcase_id = api_settings['showcase_id']
        self.api_access_token = api_settings['api_access_token']
        self.api_client_id = api_settings['api_client_id']
        self.api_client_secret = api_settings['api_client_secret']

        self.client = self.authenticate_api()
        self.data = self.get_showcase()


    def get_showcase(self):
        return None

    def get_all_videos(self):
        #
        # Request the video list from the Vimeo API
        #
        return self.data

    def get_video_by_id(self, video_id):
        # 
        # Gets an video by ID 
        # 

        if video_id in self.data.keys():
            return self.data[video_id]
        else:
            raise_error('responseHandlingError', 'Video is not found in the Spreadsheet. ID: %s' %(video_id))

    def transfrm_data(self, raw_data):
        #
        # Transforms data from the API into a relevant format 
        #
        return raw_data

    #
    # Authentication
    #
    def authenticate_api(self): 
        client = vimeo.VimeoClient(
            token=self.api_access_token,
            key=self.api_client_id,
            secret=self.api_client_secret
        )
        return client


    #
    # Tests
    #

    def test_get_about_me(self):
        about_me = v.get('/me')
        
        # Make sure we got back a successful response.
        if about_me.status_code == 200:
            return about_me.json()
        else:
            return False


    



    






    

