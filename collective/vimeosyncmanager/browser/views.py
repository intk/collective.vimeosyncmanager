#!/usr/bin/env python
# -*- coding: utf-8 -*-
from Products.Five import BrowserView
from collective.vimeosyncmanager.api_modules.vimeo.videos.vimeo_api_connection import APIConnection as APIConnectionVideos

from collective.vimeosyncmanager.sync_manager_videos import SyncManager as SyncManagerVideos

from collective.vimeosyncmanager.mapping_cores.vimeo.mapping_core import CORE_VIMEO as SYNC_CORE_VIMEO


# Plone imports
from Products.statusmessages.interfaces import IStatusMessage
from zExceptions import Redirect
from plone.registry.interfaces import IRegistry
from zope.component import getUtility

#
# Product dependencies
#
from collective.vimeosyncmanager.utils import get_api_settings, get_datetime_today, get_datetime_future, clean_whitespaces
from collective.vimeosyncmanager.error_handling.error import raise_error
from collective.vimeosyncmanager.logging.logging import logger
import plone.api
from collective.taskqueue.interfaces import ITaskQueue
from collective.taskqueue import taskqueue


# Google Spreadsheets connection
import gspread
from oauth2client.service_account import ServiceAccountCredentials

import requests
from requests.auth import HTTPBasicAuth
from plone.registry import Registry
import transaction


# TESTS API


# VIMEO
def test_get_video_by_id():
    with plone.api.env.adopt_user(username="admin"):
        # Get API settings from the controlpanel
        api_settings = get_api_settings()
        
        # Create the API connection
        api_connection = APIConnectionVideos(api_settings)

        logger("[Status] Start sync video by id.")

        video_id = "5686447075"

        video = api_connection.get_video_by_id(video_id=video_id)
        print(video)

        logger("[Status] Finished sync video by id.")
        return video

# # # # # # # # # # # #
# Sync Video        # #
# # # # # # # # # # # #
class SyncVideo(BrowserView):

    def __call__(self):
        return self.sync()

    def sync(self):

        # Get the necessary information to call the api and return a response
        context_video_id = getattr(self.context, 'video_id', '')

        redirect_url = self.context.absolute_url()
        messages = IStatusMessage(self.request)

        if context_video_id:
            try:
                # Get API settings from the controlpanel
                api_settings = get_api_settings()

                # Create the API connection
                api_connection = APIConnectionVideos(api_settings)

                # Create the settings for the sync
                # Initiate the sync manager
                sync_options = {"api": api_connection, 'core': SYNC_CORE_VIMEO}
                sync_manager = SyncManagerVideos(sync_options)
                
                # Trigger the sync to update one video
                logger("[Status] Start update of single video.")
                person_data = sync_manager.update_video_by_id(video_id=context_video_id)
                logger("[Status] Finished update of single video.")
                messages.add(u"Video ID '%s' is now synced." %(context_video_id), type=u"info")
            except Exception as err:
                logger("[Error] Error while requesting the sync for the video ID: '%s'" %(context_video_id), err)
                messages.add(u"Video ID '%s' failed to sync with the api. Please contact the website administrator." %(context_video_id), type=u"error")
        else:
            messages.add(u"This video cannot be synced with the API. Video ID is missing.", type=u"error")
            logger("[Error] Error while requesting the sync for the video. Video ID is not available.", "Video ID not found.")
        

        # Redirect to the original page
        raise Redirect(redirect_url)

class SyncAllVideos(BrowserView):

    def __call__(self):
        return self.sync()

    def sync(self):

        redirect_url = self.context.absolute_url()
        messages = IStatusMessage(self.request)

        try:
            # Get API settings from the controlpanel
            api_settings = get_api_settings()

            # Create the API connection
            api_connection = APIConnectionVideos(api_settings)

            # Create the settings for the sync
            # Initiate the sync manager
            sync_options = {"api": api_connection, 'core': SYNC_CORE_VIMEO}
            sync_manager = SyncManagerVideos(sync_options)
            
            # Trigger the sync to update one video
            logger("[Status] Start update of all video.")
            person_data = sync_manager.update_videos(create_and_unpublish=True)
            logger("[Status] Finished update of all video.")
        except Exception as err:
            logger("[Error] Error while requesting the sync for all videos", err)
            messages.add(u"Sync of all videos ID failed. Please contact the website administrator.", type=u"error")

        # Redirect to the original page
        raise Redirect(redirect_url)



