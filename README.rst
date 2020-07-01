Introduction
============

Provides methods to sync content from Vimeo API

Features
============
- Synchronization between Vimeo API and Plone content.
- Vimeo videos are created using `wildcard.media`_.
- Connection with the Vimeo API separated from the content sync. 
- Other API connections can be plugged into the sync. The main sources of data for this project are Vimeo videos. 
- Compatible with Python 3 and Plone 5.2.x

.. _wildcard.media: https://github.com/collective/wildcard.media

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
- vimeo
- wildcard.media

The following dependencies are not required unless the creation of pictures and translations is requested.

- plone.namedfile
- plone.app.multilingual 
