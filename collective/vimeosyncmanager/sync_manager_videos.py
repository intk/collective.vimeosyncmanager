#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# Vimeo API sync mechanism by Andre Goncalves
#
import plone.api
import transaction
import requests
from zope.component import queryAdapter, queryMultiAdapter
from plone.uuid.interfaces import IUUID
from zope import event

# Plone dependencies
from zope.schema.interfaces import ITextLine, ITuple, IBool
from plone.app.textfield.interfaces import IRichText
from plone.app.textfield.value import RichTextValue
from zope.schema import getFieldsInOrder
from plone.event.interfaces import IEventAccessor
from datetime import datetime
from zope.component import getUtility
from plone.i18n.normalizer.interfaces import IIDNormalizer
from plone.namedfile.file import NamedBlobImage, NamedBlobFile
from plone.app.multilingual.interfaces import ITranslationManager

# Product dependencies
from collective.video.interfaces import IVideo
from eea.cache.event import InvalidateMemCacheEvent
from collective.taxonomy.interfaces import ITaxonomy
from zope.component import queryUtility

# Error handling
from .error_handling.error import raise_error

# Logging module
from .logging.logging import logger

# Utils
from .utils import str2bool, normalize_id, phonenumber_to_id
from .utils import get_datetime_today, get_datetime_future, DATE_FORMAT

class SyncManager(object):
    #
    # Init methods 
    #  
    DEFAULT_CONTENT_TYPE = "Video" # TODO: should come from settings

    DOWNLOAD_URL_TEMPLATE = "https://drive.google.com/u/1/uc?id=%s&export=download"
    MAIN_LANGUAGE = "en"
    EXTRA_LANGUAGES = ["nl"]
    TRANSLATABLE_FIELDS = ['title', 'google_ads_id', 'pictureUrl', 'image', 'taxonomy_cultural_videos']

    DEFAULT_FOLDER = "/en/videos" # TODO: should come from settings
    DEFAULT_FOLDERS = {
        "en": "/en/videos",
        "nl": "/nl/videotheek"
    }

    TAXONOMY_NAME = "taxonomy_cultural_videos" # TODO: should come from settings


    def __init__(self, options):
        self.options = options
        self.vimeo_api = self.options['api']
        self.CORE = self.options['core']

        self.taxonomy_utility = queryUtility(ITaxonomy, name='collective.taxonomy.cultural_videos')
        self.taxonomy_data = self.taxonomy_utility.data

    #
    # Sync operations 
    #
    def update_video_by_id(self, video_id, video_data=None, translate=True):

        if video_id:
            video = self.find_video(video_id)

            if not video_data:
                video_data = self.vimeo_api.get_video_by_id(video_id)

            updated_video = self.update_video(video_id, video, video_data)

            if not video_data:
                cache_invalidated = self.invalidate_cache()

            return updated_video
        else:
            return None

    def update_videos(self, create_and_unpublish=False):
        video_list = self.vimeo_api.get_all_videos()
        
        if create_and_unpublish:
            website_videos = self.get_all_videos()
            self.sync_video_list(video_list, website_videos)
        else:
            self.update_video_list(video_list)

        cache_invalidated = self.invalidate_cache()
        
        transaction.get().commit()
        
        return video_list

    #
    # CRUD operations
    #

    # UPDATE
    def update_video(self, video_id, video, video_data, translate=True):
        updated_video = self.update_all_fields(video, video_data)

        updated_video = self.publish_based_on_current_state(video)

        # DO NOT translate
        #    for extra_language in self.EXTRA_LANGUAGES:
        #        translated_video = self.translate_video(updated_video, video_id, extra_language)

        video = self.validate_video_data(video, video_data)

        logger("[Status] Video with ID '%s' is now updated. URL: %s" %(video_id, video.absolute_url()))
        return updated_video


    # TRANSLATIONS

    def translate_video(self, video, video_id, language="nl"):
        translated_video = self.check_translation_exists(video, language)

        if translated_video:
            translated_video = self.update_video_translation(video, translated_video)
            logger("[Status] '%s' translation of Video with ID '%s' is now updated. URL: %s" %(language, video_id, translated_video.absolute_url()))
        else:
            translated_video = self.create_video_translation(video, language)
            logger("[Status] Video with ID '%s' is now translated to '%s'. URL: %s" %(video_id, language, translated_video.absolute_url()))

        translated_video = self.publish_based_on_current_state(translated_video)
        translated_video = self.validate_video_data(translated_video, None)
        
        return translated_video

    def check_translation_exists(self, video, language):
        has_translation = ITranslationManager(video).has_translation(language)
        if has_translation:
            translated_video = ITranslationManager(video).get_translation(language)
            return translated_video
        else:
            return False

    def update_video_translation(self, video, translated_video):
        translated_video = self.copy_fields_to_translation(video, translated_video)
        return translated_video

    def create_video_translation(self, video, language):
        ITranslationManager(video).add_translation(language)
        translated_video = ITranslationManager(video).get_translation(language)
        translated_video = self.copy_fields_to_translation(video, translated_video)
        return translated_video

    def copy_fields_to_translation(self, video, translated_video):

        for fieldname in self.TRANSLATABLE_FIELDS:
            setattr(translated_video, fieldname, getattr(video, fieldname, ''))

        original_subjects = video.Subject()
        translated_video.setSubject(original_subjects)

        return translated_video


    # CREATE
    def create_video(self, video_id, video_data=None):
        if not video_data:
            video_data = self.vimeo_api.get_video_by_id(video_id)
        
        try:
            title = video_data['name']
            new_video_id = normalize_id(title)

            container = self.get_container()
            new_video = plone.api.content.create(container=container, type=self.DEFAULT_CONTENT_TYPE, id=new_video_id, safe_id=True, title=title)
            logger("[Status] Video with ID '%s' is now created. URL: %s" %(video_id, new_video.absolute_url()))
            updated_video = self.update_video(video_id, new_video, video_data)
        except Exception as err:
            logger("[Error] Error while creating the video ID '%s'" %(video_id), err)
            return None
    
    def create_new_videos(self, videos_data, website_data):
        new_videos = [api_id for api_id in videos_data.keys() if api_id not in website_data.keys()]
        created_videos = [self.create_video(video_id) for video_id in new_videos]
        return new_videos

    # CREATE OR UPDATE
    def sync_video_list(self, video_list, website_videos):

        website_data = self.build_website_data_dict(website_videos)

        for video in video_list.values():
            video_id = str(video.get('_id', ''))

            if video_id:
                # Update
                if video_id in website_data.keys():
                    consume_video = website_data.pop(video_id)
                    try:
                        video_data = self.update_video_by_id(video_id, video)
                    except Exception as err:
                        logger("[Error] Error while updating the video ID: %s" %(video_id), err)
                # Create
                else:
                    try:
                        new_video = self.create_video(video_id, video)
                    except Exception as err:
                        logger("[Error] Error while creating the video ID: '%s'" %(video_id), err)
            else:
                # TODO: log error
                pass
        
        if len(website_data.keys()) > 0:
            unpublished_videos = [self.unpublish_video(video_brain.getObject()) for video_brain in website_data.values()]

        return video_list

    def update_video_list(self, video_list):
        for video in video_list.values():
            video_id = video.get('_id', '')
            try:
                video_data = self.update_video_by_id(video_id, video)
            except Exception as err:
                logger("[Error] Error while requesting the sync for the video ID: '%s'" %(video_id), err)
        
        return video_list

    # GET
    def get_all_videos(self):
        results = plone.api.content.find(portal_type=self.DEFAULT_CONTENT_TYPE, Language=self.MAIN_LANGUAGE)
        return results

     # FIND
    def find_video(self, video_id):
        video_id = self.safe_value(video_id)
        result = plone.api.content.find(video_id=video_id, Language=self.MAIN_LANGUAGE)

        if result:
            return result[0].getObject()
        else:
            raise_error("videoNotFoundError", "Video with ID '%s' is not found in Plone" %(video_id))

    # DELETE
    def delete_video_by_id(self, video_id):
        obj = self.find_video(video_id=video_id)
        self.delete_video(obj)  

    def delete_video(self, video):
        plone.api.content.delete(obj=video)

    # PLONE WORKLFLOW - publish
    def publish_based_on_current_state(self, video):
        state = plone.api.content.get_state(obj=video)
        if state != "published":
            if getattr(video, 'image', None):
                updated_video = self.publish_video(video)
        else:
            if not getattr(video, 'image', None):
                updated_video = self.unpublish_video(video)

        return video

    def publish_video(self, video):
        plone.api.content.transition(obj=video, to_state="published")
        logger("[Status] Published video with ID: '%s'" %(getattr(video, 'google_ads_id', '')))
        return video

    # PLONE WORKLFLOW - unpublish
    def unpublish_video(self, video):
        plone.api.content.transition(obj=video, to_state="private")
        logger("[Status] Unpublished video with ID: '%s'" %(getattr(video, 'google_ads_id', '')))

        #translated_video = self.check_translation_exists(video, 'nl') #TODO: needs fix for language
        #if translated_video:
        #    plone.api.content.transition(obj=translated_video, to_state="private")
        #    logger("[Status] Unpublished video translation with ID: '%s'" %(getattr(video, 'google_ads_id', '')))

        return video

    def unpublish_video_by_id(self, video_id):
        obj = self.find_video(video_id=video_id)
        self.unpublish_video(obj)

    #
    # CRUD utils
    # 
    def get_video_data_from_list_by_id(self, video_brain, videos_data):
        video_id = getattr(video_brain, 'video_id', None)
        if video_id and video_id in videos_data:
            return videos_data[video_id]
        else:
            logger("[Error] Video data for '%s' cannot be found." %(video_brain.getURL()), "requestHandlingError")
            return None

    def build_website_data_dict(self, website_videos):
        website_videos_data = {}
        for website_video in website_videos:
            video_id = getattr(website_video, 'video_id', None)
            if video_id:
                website_videos_data[self.safe_value(video_id)] = website_video
            else:
                logger('[Error] Video ID value cannot be found in the brain. URL: %s' %(website_video.getURL()), 'requestHandlingError')
        return website_videos_data

    def get_container(self):
        container = plone.api.content.get(path=self.DEFAULT_FOLDER)
        return container

    # FIELDS
    def match(self, field):
        # Find match in the core
        if field in self.CORE.keys():
            if self.CORE[field]:
                return self.CORE[field]
            else:
                logger("[Warning] API field '%s' is ignored in the fields mapping" %(field), "Field ignored in mapping.")
                return False
        else:
            # log field not match
            logger("[Error] API field '%s' does not exist in the fields mapping" %(field), "Field not found in mapping.")
            return False

    def update_field(self, video, fieldname, fieldvalue):
        plonefield_match = self.match(fieldname)

        if plonefield_match:
            try:
                if not hasattr(video, plonefield_match):
                    logger("[Error] Plone field '%s' does not exist" %(plonefield_match), "Plone field not found")
                    return None

                transform_value = self.transform_special_fields(video, fieldname, fieldvalue)
                if transform_value:
                    return transform_value
                else:
                    setattr(video, plonefield_match, self.safe_value(fieldvalue))
                    return fieldvalue
                    
            except Exception as err:
                logger("[Error] Exception while syncing the API field '%s'" %(fieldname), err)
                return None
        else:
            return None

    def update_all_fields(self, video, video_data):
        self.clean_all_fields(video)
        updated_fields = [(self.update_field(video, field, video_data[field]), field) for field in video_data.keys()]
        return video

    #
    # Sanitising/validation methods
    #
    def safe_value(self, fieldvalue):
        if isinstance(fieldvalue, bool):
            return fieldvalue
        elif isinstance(fieldvalue, int):
            fieldvalue_safe = "%s" %(fieldvalue)
            return fieldvalue_safe
        else:
            return fieldvalue

    def clean_all_fields(self, video):

        # get all fields from schema
        for fieldname in self.CORE.values():
            if fieldname not in ['video_id', 'pictureUrl', 'google_ads_id']: # TODO: required field needs to come from the settings
                self.clean_field(video, fieldname)

        return video

    def clean_field(self, video, fieldname):
        try:
            setattr(video, fieldname, "")
        except:
            logger("[Error] Field '%s' type is not recognised. " %(fieldname), "Field cannot be cleaned before sync.")

        return video

    def validate_video_data(self, video, video_data):
        validated = True # Needs validation
        if validated:
            video.reindexObject(idxs=["Title", "country", "Subject"])
            transaction.get().commit()
            return video
        else:
            raise_error("validationError", "Video is not valid. Do not commit changes to the database.")

    #
    # Transform special fields
    # Special methods
    #
    def transform_special_fields(self, video, fieldname, fieldvalue):

        special_field_handler = self.get_special_fields_handlers(fieldname)
        if special_field_handler:
            special_field_value = special_field_handler(video, fieldname, fieldvalue)
            return special_field_value

        return False

    def get_special_fields_handlers(self, fieldname):
        SPECIAL_FIELDS_HANDLERS = {
            "title": self._transform_video_title,
            "type": self._transform_video_type,
            "picture": self._transform_video_picture,
            "country": self._transform_video_country
        }

        if fieldname in SPECIAL_FIELDS_HANDLERS:
            return SPECIAL_FIELDS_HANDLERS[fieldname]
        else:
            return None

    def _transform_video_title(self, video, fieldname, fieldvalue):
        setattr(video, 'title', fieldvalue)
        return fieldvalue

    def _transform_video_type(self, video, fieldname, fieldvalue):
        current_subjects = video.Subject()
        if 'frontpage' in current_subjects:
            subjects = ['frontpage', fieldvalue]
            video.setSubject(subjects)
        elif 'main-video-page' in current_subjects:
            subjects = ['main-video-page', fieldvalue]
            video.setSubject(subjects)
        else:
            video.setSubject([fieldvalue])

        taxonomy_id = self.get_taxonomy_id(fieldvalue)
        taxonomies = getattr(video, self.TAXONOMY_NAME, [])

        if not taxonomies:
            taxonomies = []

        if taxonomy_id not in taxonomies:
            taxonomies.append(taxonomy_id)
            setattr(video, self.TAXONOMY_NAME, taxonomies)
            
        return [fieldvalue]

    def _transform_video_country(self, video, fieldname, fieldvalue):
        if fieldvalue:
            all_countries = fieldvalue.split(',')
            all_countries_transform = [country.strip() for country in all_countries]
            setattr(video, 'country', all_countries_transform)
        else:
            setattr(video, 'country', [])

        return [fieldvalue]


    def get_taxonomy_id(self, taxonomy):
        taxonomy_id = None
        
        for taxonomy_name in self.taxonomy_data[self.MAIN_LANGUAGE]:
            if taxonomy in taxonomy_name:
                taxonomy_id = self.taxonomy_data[self.MAIN_LANGUAGE][taxonomy_name]
                return taxonomy_id

        return taxonomy_id


    def _transform_video_picture(self, video, fieldname, fieldvalue):
        url = fieldvalue

        current_url = getattr(video, 'pictureUrl', None)

        if url:
            if not current_url:
                image_created_url = self.add_image_to_video(url, video)
                setattr(video, 'pictureUrl', url)
            elif current_url != url:
                image_created_url = self.add_image_to_video(url, video)
                setattr(video, 'pictureUrl', url)
            else:
                setattr(video, 'pictureUrl', url)
                return url

            return url
        else:
            setattr(video, 'image', None)
            return url

    def get_drive_file_id(self, url):
        try:
            if "drive.google.com/open" in url:
                file_id = url.split("id=")[1]
                file_id = file_id.split('&')[0]
                file_id = file_id.split('?')[0]
            else:
                file_id = url.split("/")[5]
                file_id = file_id.split('&')[0]
                file_id = file_id.split('?')[0]
            return file_id
        except:
            # TODO: log error
            return None

    def generate_image_url(self, url):
        
        file_id = self.get_drive_file_id(url)

        if file_id:
            image_url = self.DOWNLOAD_URL_TEMPLATE %(file_id)
            return image_url
        else:
            # TODO: log error
            return None

    # Utils
    def download_image(self, url):
        if url:
            try:
                img_request = requests.get(url, stream=True)
                if img_request:
                    img_headers = img_request.headers.get('content-type')

                    if 'text/xml' in img_headers or "text/html" in img_headers:
                        # TODO : Log error
                        return None
                    img_data = img_request.content
                    return img_data
                else:
                    # TODO: log error
                    return None
            except:
                # TODO: log error
                return None
        else:
            return None

    def get_image_blob(self, img_data):
        if img_data:
            image_data = img_data
            img_blob = NamedBlobImage(data=image_data)

            return img_blob
        else:
            return None

    def add_image_to_video(self, url, video):
        image_id = self.get_drive_file_id(url)
        image_data = self.vimeo_api.download_media_by_id(image_id)
        image_blob = self.get_image_blob(image_data)

        if image_blob:
            setattr(video, 'image', image_blob)
            return url
        else:
            setattr(person, 'image', None)
            return url

    def invalidate_cache(self):
        """container = self.get_container()
        uid = queryAdapter(container, IUUID)
        if uid:
            event.notify(InvalidateMemCacheEvent(raw=True, dependencies=[uid]))"""
        return True





