Introduction
============

Provides methods to sync content from Vimeo API

Features
============
- Synchronization between Vimeo API and Plone content.
- Connection with the Vimeo API is separated from the Plone content sync. 
- Other API connections can be plugged into the sync. The main sources of data for this project are Vimeo videos and therefore the Vimeo API. 
- Vimeo videos are created using `wildcard.media`_.
- Compatible with Python 3 and Plone 5.2.x

Architecture
============
- There are two main parts: API connection and the Sync Manager. Both operate independently from each other.
- API connection: This is the module that connects with the Vimeo API and returns the requested data. No changes are made to the data. The data should not be processed at this point. Implemented methods: get_showcase_by_id, get_showcase_videos, get_video_by_id
- Sync mechanism: This is the connection with Plone. It maps the results from an API into a content type in Plone. Implements all CRUD operations for the Video content type based on the results from the api. For this project the mapping is done between the Vimeo API and a Video content type.



Installation
===================
If you are using zc.buildout and the plone.recipe.zope2instance recipe to manage your project, you can do this:
Add collective.vimeosyncmanager to the list of eggs to install, e.g.::

	[buildout]
		…
		eggs =
			…
			collective.vimeosyncmanager

How to use method as a cron job?
=======================================================
Add to your buildout.cfg::

	zope-conf-additional = 
	<clock-server> 
		method /SiteName/vimeo_sync 
		period 60 
		user username-to-invoke-method-with
		password password-for-user 
		host localhost 
	</clock-server>

Dependencies
===============
- `vimeo`_
- `wildcard.media`_

The following dependencies are not required unless the creation of pictures and translations is requested.

- plone.namedfile
- plone.app.multilingual 

.. _wildcard.media: https://github.com/collective/wildcard.media
.. _vimeo: https://github.com/vimeo/vimeo.py
