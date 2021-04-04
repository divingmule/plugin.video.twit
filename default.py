# This Python file uses the following encoding: utf-8
import sys
import time
from urllib.parse import urlencode, parse_qsl

import feedparser
from bs4 import BeautifulSoup
import requests
import StorageServer

import xbmcplugin
import xbmcgui
import xbmcaddon

addon = xbmcaddon.Addon()
addon_id = addon.getAddonInfo('id')
addon_version = addon.getAddonInfo('version')
addon_fanart = addon.getAddonInfo('fanart')
addon_icon = addon.getAddonInfo('icon')
addon_path = addon.getAddonInfo('path')
language = addon.getLocalizedString
cache = StorageServer.StorageServer(addon_id, 24)


def addon_log(string):
    xbmc.log("[{0}-{1}]: {2}".format(addon_id, addon_version, string), level=debug_level)


def make_request(url):
    try:
        res = requests.get(url)
        if not res.status_code == requests.codes.ok:
            addon_log('Bad status code: {}'.format(res.status_code))
            res.raise_for_status()
        if not res.encoding == 'utf-8':
            res.encoding = 'utf-8'
        return res.text
    except requests.exceptions.HTTPError as error:
        addon_log('We failed to open {}.'.format(url))
        addon_log(error)


def display_main():
    """ display the main plugin directory """
    add_dir(language(30002), 'twit_live', addon_icon, 'twit_live')
    display_shows('active')
    add_dir(language(30010), 'retired_shows', addon_icon, 'retired_shows')


def display_shows(show_type):
    """ parse shows and add plugin directories """
    artwork = eval(cache.get('artwork'))
    if show_type == 'active':
        items = eval(cache.get('active'))
    else:
        items = eval(cache.get('retired'))
    for i in items:
        name = i['title']
        if name in artwork:
            art = artwork[name]
        else:
            addon_log(f'No artwork found for {name}')
            art = i['art']
        add_dir(name, i['url'], art, 'rss_feed', {'plot': i['desc']}, art)


def get_rss_feed(show_name, icon):
    """ parse the rss feed for episodes of a show """
    show_data = [i for i in eval(cache.get('active')) if show_name == i['title']]
    if not show_data:
        show_data = [i for i in eval(cache.get('retired')) if show_name == i['title']]
    feeds = show_data[0]['feeds']
    if len(feeds) == 1:
        feed_url = feeds[0]
    elif params['content_type'] == 'audio':
        feed_url = feeds[0]
    else:
        feed_url = feeds[1]
    feed = feedparser.parse(feed_url)
    for i in feed['entries']:
        title = i['title']
        art = icon
        if 'media_thumbnail' in i:
            art = i['media_thumbnail'][0]['url']
        info = {'duration': duration_to_seconds(i['itunes_duration']),
                'aired': time.strftime('%Y/%m/%d', i['published_parsed'])}
        soup = BeautifulSoup(i['content'][0]['value'], 'html.parser')
        info['plot'] = soup.get_text()
        stream_url = i['media_content'][0]['url']
        add_dir(title, stream_url, art, 'resolved_url', info, icon)


def duration_to_seconds(duration_string):
    """ helper function for get_rss_feed """
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
    def get_youtube_live_id():
        data = make_request('https://www.youtube.com/user/twit/live')
        soup = BeautifulSoup(data, 'html.parser')
        video_id = soup.find('meta', attrs={'itemprop': "videoId"})['content']
        return video_id
    if content_type == 'audio':
        resolved_url = 'http://twit.am/listen'
    elif addon.getSetting('twit_live') == '0':
        resolved_url = 'http://iphone-streaming.ustream.tv/uhls/1524/streams/live/iphone/playlist.m3u8'
    else:
        resolved_url = 'plugin://plugin.video.youtube/play/?video_id={}'.format(get_youtube_live_id())
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


def set_shows_cache():
    """ cache shows, this data rarely changes """
    xbmcgui.Dialog().notification(language(30011), language(30012), addon_icon)
    # scrape artwork urls
    artwork = dict()
    url = 'https://wiki.twit.tv/wiki/Cover_Art'
    soup = BeautifulSoup(make_request(url), 'html.parser')
    tags = soup.find_all('h3')
    for i in tags:
        if i('span', class_="mw-headline"):
            name = i.get_text()
            art_url = i.find_next('li').a['href']
            artwork[name] = art_url
    cache.set('artwork', repr(artwork))
    # scrape shows
    retired_shows = list()
    active_shows = list()
    retired_list = get_show_list('https://twit.tv/shows?shows_active=0')
    active_list = get_show_list('https://twit.tv/shows?shows_active=1')
    for name, url in retired_list:
        show = get_show(name, url)
        retired_shows.append(show)
    cache.set('retired', repr(retired_shows))
    for name, url in active_list:
        show = get_show(name, url)
        active_shows.append(show)
    cache.set('active', repr(active_shows))
    xbmcgui.Dialog().notification(language(30011), language(30013), addon_icon)
    return True


def get_show_list(shows_url):
    """ helper function for set_shows_cache """
    data = make_request(shows_url)
    soup = BeautifulSoup(data, 'html.parser')
    shows_tag = soup.find_all('div', class_="item media-object")
    shows_list = list()
    for show in shows_tag:
        show_name = show.h2.a.get_text()
        show_url = f"https://twit.tv{show.a['href']}"
        shows_list.append((show_name, show_url))
    return shows_list


def get_show(show_name, show_url):
    """ helper function for set_shows_cache """
    show_data = BeautifulSoup(make_request(show_url), 'html.parser')
    show = show_data.find('div', class_='wrapper media')
    feeds = list()
    for i in show_data.find_all('option', text='RSS'):
        feeds.append(i['value'])
    show_dict = {'art': show.img['data-borealis-srcs'].split(' ')[-1],
                 'desc': show.p.get_text(),
                 'feeds': feeds,
                 'title': show_name,
                 'url': show_url}
    return show_dict


def reset_shows_cache():
    # in case something breaks the scraper
    cache.set('cached', 'in_progress')
    cache.set('artwork_bak', cache.get('artwork'))
    cache.set('active_bak', cache.get('active'))
    cache.set('retired_bak', cache.get('retired'))
    # scrape, cache show data
    success = set_shows_cache()
    addon_log(f'Addon cache updated: {success}')
    cache.set('cached', 'True')
    cache.delete('%_bak')
    return 'True'


def check_cache():
    # check if shows have been cached
    cached = cache.get('cached')
    if cached == 'True':
        return
    elif cached == 'in_progress':
        # reset_shows_cache failed and needs to be restored
        cache.set('artwork', cache.get('artwork_bak'))
        cache.set('active', cache.get('active_bak'))
        cache.set('retired', cache.get('retired_bak'))
        cache.delete('%_bak')
        return
    else:
        # shows data needs to be cached
        addon_log('Caching add-on data')
        set_cache = set_shows_cache()
        addon_log(f'Add-on data cached: {set_cache}')
        if set_cache:
            cache.set('cached', 'True')


debug = addon.getSetting('debug')
debug_level = xbmc.LOGDEBUG
if debug == 'true':
    cache.dbg = True
    debug_level = xbmc.LOGINFO

if 'cache_plugin' in sys.argv[2]:
    # cache_plugin was called from settings
    addon_log('Resetting shows cache')
    reset_shows_cache()
    exit()

params = {k: v for k,v in parse_qsl(sys.argv[2][1:])}

if 'content_type' in params and params['content_type'] == 'audio':
    content_type = 'audio'
else:
    content_type = 'video'

mode = None
if 'mode' in params:
    mode = params['mode']
    addon_log('Mode: {0}, Name: {1}, URL: {2}'.format(params['mode'], params['name'], params['url']))

if mode is None:
    check_cache()
    addon_log('Display main plugin directory')
    display_main()
    xbmcplugin.setContent(int(sys.argv[1]), 'tvshows')
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'retired_shows':
    display_shows('retired')
    xbmcplugin.setContent(int(sys.argv[1]), 'tvshows')
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'rss_feed':
    get_rss_feed(params['name'], params['icon'])
    xbmcplugin.setContent(int(sys.argv[1]), 'episodes')
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'resolved_url':
    set_resolved_url(params['url'])

elif mode == 'twit_live':
    set_resolved_url(twit_live())
