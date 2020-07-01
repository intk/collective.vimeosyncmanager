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
from collective.vimeosyncmanager.utils import clean_whitespaces, phonenumber_to_id

# Google spreadsheet dependencies
import gspread

# API
from oauth2client.service_account import ServiceAccountCredentials
from apiclient import discovery, errors
from httplib2 import Http
from oauth2client import client, file, tools
from apiclient.http import MediaFileUpload, MediaIoBaseDownload

import os, io
import json

class APIConnection(object):

    #
    # Local definitions to the API connection
    #

    MINIMUM_SIZE = 1

    # API mapping field / column
    API_MAPPING = {
        "name": 0,
        "google_ads_id": 1,
        "picture": 4,
        "type": 7,
        "country": 9,
        "video_language": 8,
        "city": 10
    }

    #
    # Initialisation methods
    #
    def __init__(self, api_settings):
        
        self.api_settings = api_settings
        self.worksheet_name = api_settings['worksheet_name']
        self.spreadsheet_url = api_settings['spreadsheet_url']
        self.json_key = json.loads(api_settings['json_key'])
        self.scope = api_settings['scope']

        self.client = self.authenticate_api()
        self.data = self.init_spreadsheet_data()
        self.drive = self.authenticate_drive_api()


    def init_spreadsheet_data(self):

        spreadsheet = self.client.open_by_url(self.spreadsheet_url)
        worksheet = spreadsheet.worksheet(self.worksheet_name)

        raw_data = worksheet.get_all_values()
        data = self.transform_data(raw_data)
        return data


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

    # Authentication
    def authenticate_api(self): #TODO: needs validation and error handling
        creds = ServiceAccountCredentials.from_json_keyfile_dict(self.json_key, self.scope)
        client = gspread.authorize(creds)
        return client

    def authenticate_drive_api(self): #TODO: needs validation and error handling
        creds = ServiceAccountCredentials.from_json_keyfile_dict(self.json_key, self.scope)
        http = creds.authorize(Http())
        drive = discovery.build('drive', 'v3', http=http, cache_discovery=False)
        return drive

    def download_media_by_id(self, media_id):
        if media_id:
            try:
                request = self.drive.files().get_media(fileId=media_id)
                fh = io.BytesIO()

                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                fh.seek(0)
                return fh.read()
            except:
                raise_error('responseHandlingError', 'Error download the image file with ID: %s' %(media_id))
                return None
        else:
            return None

    # Transformations 
    def transform_data(self, raw_data): #TODO: needs validation and error handling
        data = {}
        if len(raw_data) > self.MINIMUM_SIZE:
            
            for row in raw_data[self.MINIMUM_SIZE:]:

                new_video = {}
                for fieldname, sheet_position in self.API_MAPPING.items():
                    new_video[fieldname] = row[sheet_position]

                google_ads_id = new_video['google_ads_id']
                new_video["_id"] = google_ads_id
                data[google_ads_id] = new_video

        return data






    






    

