# This Python file uses the following encoding: utf-8
import os
import sys
import time

try:
    from urllib import urlencode, unquote_plus
except ImportError:
    # for python3
    from urllib.parse import urlencode, unquote_plus

import feedparser
import SimpleDownloader as Downloader
from bs4 import BeautifulSoup
import requests

import xbmcplugin
import xbmcgui
import xbmcaddon
from resources import addon_cache

addon = xbmcaddon.Addon()
addon_id = addon.getAddonInfo('id')
addon_version = addon.getAddonInfo('version')
addon_fanart = addon.getAddonInfo('fanart')
addon_icon = addon.getAddonInfo('icon')
addon_path = xbmc.translatePath(addon.getAddonInfo('path')).encode('utf-8')
language = addon.getLocalizedString


def addon_log(string):
    xbmc.log("[%s-%s]: %s" % (addon_id, addon_version, string), level=debug_level)


def display_shows(show_type):
    """ parse shows and add plugin directories """
    items = addon_cache.get_shows(show_type)
    for i in items[show_type]:
        if content_type == 'video':
            feed_url = i['video_feed']
        else:
            feed_url = i['audio_feed']
        add_dir(i['title'], feed_url, i['art'], 'rss_feed', {'plot': i['plot']}, i['art'])


def display_main():
    """ display the main directory """
    live_icon = os.path.join(addon_path, 'resources', 'live.png')
    add_dir(language(30002), 'twit_live', live_icon, 'twit_live')
    display_shows('active')
    add_dir(language(30036), 'retired_shows', addon_icon, 'retired_shows')


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
            addon_log('Not able to int duration_string: %s' % duration_string)
    return seconds


def download_file(stream_url, title):
    """ thanks/credit to TheCollective for SimpleDownloader module"""
    path = addon.getSetting('download')
    if path == "":
        xbmc.executebuiltin("Notification(%s,%s,10000,%s)"
                            % (language(30038), language(30037), addon_icon))
        addon.openSettings()
        path = addon.getSetting('download')
    if path == "":
        return
    addon_log('######### Download #############')
    file_downloader = Downloader.SimpleDownloader()
    invalid_chars = ['>', '<', '*', '/', '\\', '?', '.']
    for i in invalid_chars:
        title = title.replace(i, '')
    name = '%s.%s' % (title.replace(' ', '_'), stream_url.split('.')[-1])
    addon_log('Title: %s - Name: %s' % (title, name))
    download_params = {"url": stream_url, "download_path": path, "Title": title}
    addon_log(str(download_params))
    file_downloader.download(name, download_params)
    addon_log('################################')


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
    success = False
    if resolved_url:
        success = True
    else:
        resolved_url = ''
    item = xbmcgui.ListItem(path=resolved_url)
    xbmcplugin.setResolvedUrl(int(sys.argv[1]), success, item)


def add_dir(name, url, iconimage, dir_mode, info=None, fanart=None):
    if info is None:
        info = {}
    item_params = {'name': name.encode('utf-8'), 'url': url, 'mode': dir_mode,
                   'iconimage': iconimage, 'content_type': content_type}
    plugin_url = '%s?%s' % (sys.argv[0], urlencode(item_params))
    listitem = xbmcgui.ListItem(name, iconImage=iconimage, thumbnailImage=iconimage)
    if name == language(30002):
        context_menu = [(language(30033),
                         'RunPlugin(plugin://plugin.video.twit/?'
                         'mode=ircchat&name=ircchat&url=live_chat)')]
        listitem.addContextMenuItems(context_menu)
    isfolder = True
    if dir_mode in ['resolved_url', 'twit_live']:
        isfolder = False
        listitem.setProperty('IsPlayable', 'true')
    if dir_mode is 'resolved_url':
        context_menu = [(language(30035),
                         'RunPlugin(plugin://plugin.video.twit/?'
                         'mode=download&name=%s&url=%s)' % (name, url))]
        listitem.addContextMenuItems(context_menu)
    if fanart is None:
        fanart = addon_fanart
    listitem.setProperty('Fanart_Image', fanart)
    info_type = 'video'
    if content_type == 'audio':
        info_type = 'music'
    listitem.setInfo(type=info_type, infoLabels=info)
    xbmcplugin.addDirectoryItem(int(sys.argv[1]), plugin_url, listitem, isfolder)


def run_ircchat():
    # check chat args
    nickname = addon.getSetting('nickname')
    username = addon.getSetting('username')
    if not nickname or not username:
        xbmc.executebuiltin('Notification(%s, %s,10000,%s)' %
                            ('IrcChat', language(30024), addon_icon))
        addon.openSettings()
        nickname = addon.getSetting('nickname')
        username = addon.getSetting('username')
    if not nickname or not username:
        return
    # run ircchat script
    xbmc.executebuiltin(
        'RunScript(script.ircchat, run_irc=True&nickname=%s&username=%s'
        '&password=%s&host=irc.twit.tv&channel=twitlive)' %
        (nickname, username, addon.getSetting('password')))


debug = addon.getSetting('debug')
debug_level = xbmc.LOGDEBUG
if debug == 'true':
    addon_cache.cache.dbg = True
    debug_level = xbmc.LOGNOTICE

try:
    params = {i.split('=')[0]: i.split('=')[1] for
              i in unquote_plus(sys.argv[2])[1:].split('&')}
except IndexError:
    params = None

addon_log(addon_cache.check_for_updates())

if 'content_type' in params and params['content_type'] == 'audio':
    content_type = 'audio'
else:
    content_type = 'video'

mode = None
if 'mode' in params:
    mode = params['mode']
    addon_log('Mode: {0}, Name: {1}, URL: {2}'.format(params['mode'], params['name'], params['url']))
else:
    addon_log('Get root directory')

if mode is None:
    display_main()
    xbmcplugin.setContent(int(sys.argv[1]), 'tvshows')
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'retired_shows':
    display_shows('retired')
    xbmcplugin.setContent(int(sys.argv[1]), 'tvshows')
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'rss_feed':
    get_rss_feed(params['url'], params['iconimage'])
    xbmcplugin.setContent(int(sys.argv[1]), 'episodes')
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'resolved_url':
    set_resolved_url(params['url'])

elif mode == 'download':
    download_file(params['url'], params['name'])

elif mode == 'twit_live':
    set_resolved_url(twit_live())
    xbmc.sleep(1000)
    if addon.getSetting('run_chat') == 'true':
        run_ircchat()

elif mode == 'ircchat':
    run_ircchat()
