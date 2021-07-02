# This Python file uses the following encoding: utf-8
import sys
import time
from urllib.parse import urlencode, parse_qsl

import feedparser
from bs4 import BeautifulSoup

import xbmcplugin
import xbmcgui
import xbmcaddon
from resources.lib import addon_cache

addon = xbmcaddon.Addon()
addon_id = addon.getAddonInfo('id')
addon_version = addon.getAddonInfo('version')
addon_fanart = addon.getAddonInfo('fanart')
addon_icon = addon.getAddonInfo('icon')
addon_path = addon.getAddonInfo('path')
language = addon.getLocalizedString


def addon_log(string):
    xbmc.log("[{0}-{1}]: {2}".format(addon_id, addon_version, string), level=debug_level)


def display_main():
    """ display the main plugin directory """
    add_dir(language(30002), 'twit_live', addon_icon, 'twit_live')
    display_shows('active')
    add_dir(language(30010), 'retired_shows', addon_icon, 'retired_shows')


def display_shows(show_type):
    """ parse shows and add plugin directories """
    items = addon_cache.get_shows(show_type)
    for i in items[show_type]:
        if content_type == 'video':
            feed_url = i['video_feed']
        else:
            feed_url = i['audio_feed']
        add_dir(i['title'], feed_url, i['art'], 'rss_feed', {'plot': i['plot']}, i['art'])


def get_rss_feed(feed_url, iconimage):
    """ parse the rss feed for the episode directory of a show """
    feed = feedparser.parse(feed_url)
    for i in feed['entries']:
        art = None
        if 'media_thumbnail' in i:
            art = i['media_thumbnail'][0]['url']
        if art is None:
            art = iconimage
        info = {'duration': duration_to_seconds(i['itunes_duration']),
                'aired': time.strftime('%Y/%m/%d', i['published_parsed'])}
        soup = BeautifulSoup(i['content'][0]['value'], 'html.parser')
        info['plot'] = soup.get_text()
        stream_url = i['id']
        if not stream_url.startswith('http'):
            stream_url = i['media_content'][0]['url']
        add_dir(i['title'], stream_url, art, 'resolved_url', info, iconimage)


def duration_to_seconds(duration_string):
    """ helper function for get_rss_feed, converts duration string to seconds"""
    seconds = None
    if duration_string and len(duration_string.split(':')) >= 2:
        d = duration_string.split(':')
        if len(d) == 3:
            seconds = (((int(d[0]) * 60) + int(d[1])) * 60) + int(d[2])
        else:
            seconds = (int(d[0]) * 60) + int(d[1])
    elif duration_string:
        try:
            seconds = int(duration_string)
        except ValueError:
            addon_log('Not able to int duration_string: {}'.format(duration_string))
    return seconds


def twit_live():
    """" resolve url for the live stream """
    if content_type == 'audio':
        resolved_url = 'http://twit.am/listen'
    elif addon.getSetting('twit_live') == '0':
        resolved_url = 'http://iphone-streaming.ustream.tv/uhls/1524/streams/live/iphone/playlist.m3u8'
    else:
        resolved_url = 'plugin://plugin.video.youtube/play/?video_id={}'.format(addon_cache.get_youtube_id())
    return resolved_url


def set_resolved_url(resolved_url):
    addon_log(f'SetResolvedUrl called with url {resolved_url}')
    success = False
    if resolved_url:
        success = True
    else:
        resolved_url = ''
    item = xbmcgui.ListItem(path=resolved_url)
    xbmcplugin.setResolvedUrl(int(sys.argv[1]), success, item)


def add_dir(name, url, icon, dir_mode, info=None, fanart=None):
    if info is None:
        info = {}
    item_params = {'name': name.encode('utf-8'), 'url': url, 'mode': dir_mode,
                   'icon': icon, 'content_type': content_type}
    plugin_url = '{0}?{1}'.format(sys.argv[0], urlencode(item_params))
    listitem = xbmcgui.ListItem(name)
    listitem.setArt({'thumb': icon})
    is_folder = True
    if dir_mode in ['resolved_url', 'twit_live']:
        is_folder = False
        listitem.setProperty('IsPlayable', 'true')
    if fanart is None:
        fanart = addon_fanart
    listitem.setArt({'fanart': fanart})
    info_type = 'video'
    if content_type == 'audio':
        info_type = 'music'
    listitem.setInfo(type=info_type, infoLabels=info)
    xbmcplugin.addDirectoryItem(int(sys.argv[1]), plugin_url, listitem, is_folder)


debug = addon.getSetting('debug')
debug_level = xbmc.LOGDEBUG
if debug == 'true':
    debug_level = xbmc.LOGINFO

params = {k: v for k, v in parse_qsl(sys.argv[2][1:])}

addon_log(addon_cache.check_for_updates())

if 'content_type' in params and params['content_type'] == 'audio':
    content_type = 'audio'
else:
    content_type = 'video'

mode = None
if 'mode' in params:
    mode = params['mode']
    addon_log('Mode: {0}, Name: {1}, URL: {2}'.format(params['mode'], params['name'], params['url']))

if mode is None:
    addon_log('Display main plugin directory')
    display_main()
    xbmcplugin.setContent(int(sys.argv[1]), 'tvshows')
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'retired_shows':
    display_shows('retired')
    xbmcplugin.setContent(int(sys.argv[1]), 'tvshows')
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'rss_feed':
    get_rss_feed(params['url'], params['icon'])
    xbmcplugin.setContent(int(sys.argv[1]), 'episodes')
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'resolved_url':
    set_resolved_url(params['url'])

elif mode == 'twit_live':
    set_resolved_url(twit_live())
