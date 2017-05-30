import urllib
import urllib2
import os
import re
import json
import time
from datetime import datetime, timedelta
from traceback import format_exc
from urlparse import urlparse, parse_qs

import StorageServer
import SimpleDownloader as downloader
from bs4 import BeautifulSoup

import xbmcplugin
import xbmcgui
import xbmcaddon

addon = xbmcaddon.Addon()
addon_id = addon.getAddonInfo('id')
addon_version = addon.getAddonInfo('version')
addon_fanart = addon.getAddonInfo('fanart')
addon_icon = addon.getAddonInfo('icon')
addon_path = xbmc.translatePath(addon.getAddonInfo('path')
    ).encode('utf-8')
live_icon = os.path.join(addon_path, 'resources', 'live.png')
search_icon = os.path.join(addon_path, 'resources', 'search.png')
language = addon.getLocalizedString
cache = StorageServer.StorageServer("twit_api", 6)
base_url = 'https://twit.tv/api/v1.0'


def addon_log(string):
    try:
        log_message = string.encode('utf-8', 'ignore')
    except:
        log_message = 'addonException: addon_log: %s' %format_exc()
    xbmc.log("[%s-%s]: %s" %(addon_id, addon_version, log_message),
             level=xbmc.LOGNOTICE)


def make_request(url):
    headers = {'Accept': 'application/json',
               'app-id': addon.getSetting('app-id'),
               'app-key': addon.getSetting('app-key')}
    try:
        req = urllib2.Request(url, None, headers)
        response = urllib2.urlopen(req)
        data = response.read()
        response.close()
        return data
    except urllib2.URLError, e:
        addon_log( 'We failed to open "%s".' %url)
        if hasattr(e, 'reason'):
            addon_log('We failed to reach a server.')
            addon_log('Reason: %s' %e.reason)
        if hasattr(e, 'code'):
            addon_log('We failed with error code - %s.' %e.code)
            if e.code == 500:
                dialog = xbmcgui.Dialog()
                dialog.notification('API Call Limit Reached',
                                    'Wait a minute and try again',
                                    xbmcgui.NOTIFICATION_WARNING, 5000)


def shows_cache_active():
    addon_log('Getting active show_data')
    shows_data = json.loads(make_request(base_url + '/shows?shows_active=1'))
    return shows_data


def shows_cache_retired():
    addon_log('Getting retired show_data')
    shows_data = json.loads(make_request(base_url + '/shows?shows_active=0'))
    return shows_data


def episodes_cache_function(episodes_url):
    episodes_cache = {}
    try:
        episodes_cache = eval(cache.get('episodes_cache'))
    except:
        addon_log('Episodes Cache Exception: %s' %format_exc())
    if episodes_cache.has_key(episodes_url):
        addon_log('Found episodes cache')
        if episodes_cache_check(episodes_cache[episodes_url]['time']):
            return episodes_cache[episodes_url]['data']
    else:
        addon_log('Did not Find episodes_data cache')
    episodes_data = json.loads(make_request(episodes_url))
    # set cache expiration_time
    expiration_time = datetime.strftime(
        datetime.now() + timedelta(hours=3), '%Y-%m-%d-%H-%M')
    episodes_cache[episodes_url] = {'time': expiration_time,
                                    'data': episodes_data}
    cache.set('episodes_cache', repr(episodes_cache))
    return episodes_data


def episodes_cache_check(expiration_time):
    ''' episodes_cache helper function, returns True if cache is not old'''
    try:
        cache_time = datetime.strptime(expiration_time, '%Y-%m-%d-%H-%M')
    except TypeError:
        # python bug
        cache_time = datetime(*(
            time.strptime(expiration_time, '%Y-%m-%d-%H-%M')[0:6]))
    if cache_time < datetime.now():
        addon_log('Episode cache is old')
    else:
        return True


def episodes_cache_cleanup():
    '''cleanup old episodes cache once every 24 hours'''
    last_cleaned = None
    try:
        last_cleaned = cache.get('cleanup_time')
    except:
        addon_log(format_exc())
    if last_cleaned:
        try:
            cleanup_time = datetime.strptime(last_cleaned, '%Y-%m-%d-%H-%M')
        except TypeError:
            # python bug
            cleanup_time = datetime(*(
                time.strptime(last_cleaned, '%Y-%m-%d-%H-%M')[0:6]))
        if cleanup_time > datetime.now():
            addon_log('Cache cleanup was done: %s' %cleanup_time)
            return
    try:
        episodes_cache = eval(cache.get('episodes_cache'))
    except:
        addon_log('Episodes Cache Exception: %s' %format_exc())
        return
    for i in episodes_cache.keys():
        addon_log(episodes_cache[i]['time'])
        if not episodes_cache_check(episodes_cache[i]['time']):
            del(episodes_cache[i])
            addon_log('Deleting old episodes cache: %s' %i)
    cache.set('episodes_cache', repr(episodes_cache))
    cache.set('cleanup_time', datetime.strftime(datetime.now() +
        timedelta(hours=24), '%Y-%m-%d-%H-%M'))


def display_shows(filter):
    ''' parse shows cache and add directories'''
    # show_data is cached for the allotted 6 hours by the cacheFunction
    if filter == 'active':
        shows_data = cache.cacheFunction(shows_cache_active)
    else:
        shows_data = cache.cacheFunction(shows_cache_retired)
    try:
        album_art = eval(cache.get('album_art'))
    except:
        album_art = {}
    for i in shows_data['shows']:
        if i['label'] == 'All TWiT.tv Shows':
            continue
        fanart = i['coverArt']['derivatives']['twit_album_art_1400x1400']
        if not fanart.startswith('http'):
            fanart = ('https:%s' %fanart)
        album_art[i['label']] = fanart
        info = {'plotoutline': i['tagLine'],
                'plot': BeautifulSoup(i['description'], 'html.parser'
                    ).get_text(separator=' ', strip=True)}
        add_dir(i['label'], i['id'], fanart, 'episodes', info, fanart)
    cache.set('album_art', repr(album_art))


def display_main():
    ''' display the main directory '''
    add_dir(language(30000), 'all_episodes', addon_icon, 'all_episodes')
    add_dir(language(30001), 'twit_live', live_icon, 'twit_live')
    add_dir(language(30008), 'search', search_icon, 'search')
    display_shows('active')
    add_dir(language(30036), 'retired_shows', addon_icon, 'retired_shows')


def get_episodes(episodes_url, iconimage):
    ''' display episodes '''
    # for a specific show,
    # the show id is passed as episode_url for the first page
    try:
        int(episodes_url)
        episodes_url = ('%s/episodes?filter[shows]=%s&range=12&page=1' %
                        (base_url, episodes_url))
    except ValueError:
        # int error, we should have a fully formatted URL
        pass
    episodes_data = episodes_cache_function(episodes_url)
    if not episodes_data:
        return
    # caching episodes_data to resolve the stream URL after selection
    cache.set('episodes', repr(episodes_data))
    artwork = eval(cache.get('album_art'))
    for i in episodes_data['episodes']:
        show_name = i['_embedded']['shows'][0]['label']
        fanart = artwork[show_name]
        title = i['label'].encode('utf-8')
        if episodes_url == 'all_episodes' or 'episodes?range' in episodes_url:
            if not show_name.lower() in title.lower():
                title = '%s: %s' %(show_name, title)
        info = {'plotoutline': i['teaser'], 'episode': i['episodeNumber']}
        info['plot'] = BeautifulSoup(
            i['showNotes'], 'html.parser').get_text(separator=' ', strip=True)
        stream_data = None
        for x in ['video_small', 'video_large', 'video_hd', 'video_audio']:
            if i.has_key(x):
                stream_data = i[x]
                break
        if stream_data:
            info['duration'] = ((int(stream_data['hours']) * 60  +
                                   int(stream_data['minutes'])) * 60)
        try:
            d_object = datetime.strptime(i['created'],
                                         '%Y-%m-%dT%H:%M:%Sz')
        except TypeError:
            d_object = datetime(*(time.strptime(i['created'],
                                                '%Y-%m-%dT%H:%M:%Sz')[0:6]))
        info['aired'] = datetime.strftime(d_object, '%Y/%m/%d')
        episode_image = i['heroImage']['url']
        if not episode_image.startswith('http'):
            episode_image = 'https:%s' %episode_image
        add_dir(title, i['id'], episode_image, 'resolve_url', info, fanart)
    if episodes_data['_links'].has_key('next'):
        add_dir(language(30019),episodes_data['_links']['next']['href'],
                iconimage, 'episodes', {}, addon_fanart)


def get_all_episodes():
    ''' display all episodes chronologically by airingDate'''
    get_episodes(base_url + '/episodes?range=12&page=1', addon_icon)


def search_twit():
    keyboard = xbmc.Keyboard('', "Search")
    keyboard.doModal()
    if (keyboard.isConfirmed() == False):
        return
    search_string = keyboard.getText().replace(' ', '%20')
    if len(search_string) == 0:
        return
    get_search_results('%s/search/%s?range=12' %(base_url, search_string))


def get_search_results(search_url, search_string=None):
    data = json.loads(make_request(search_url))
    for i in data['search']:
        if i['type'] == 'episode':
            add_dir(i['label'], i['id'], addon_icon, 'episode',
                    info={'plot': i['body']})
        elif i['type'] == 'show':
            add_dir(i['label'], i['id'], addon_icon, 'episodes',
                    info={'plot': i['body']})
        else:
            addon_log('Unknown Type: %s' %i['type'])
    if data['_links'].has_key('next'):
        if search_string is None:
            search_string = search_url.split('/')[-1].split('?')[0]
        next = data['_links']['next']['href']
        addon_log('Next URL: %s' %next)
        index = next.find('?')
        next_url = '%s/%s%s' %(next[:index], search_string, next[index:])
        add_dir(language(30019), next_url, addon_icon, 'search_results')


def resolve_url(episode_id, download=False, cached=True):
    if cached:
        # resolve the stream url from the episodes cache
        episodes = eval(cache.get('episodes'))['episodes']
        episode = [i for i in episodes if i['id'] == int(episode_id)][0]
    else:
        data = json.loads(make_request('%s/episodes/%s' %(base_url, episode_id)))
        episode = data['episodes']

    playback_options = {'0': 'HD Video','1': 'SD Video Large',
                        '2': 'SD Video Small', '3': 'Audio'}
    stream_urls = []
    if episode.has_key('video_hd'):
        stream_urls.append(('HD Video', episode['video_hd']['mediaUrl']))
    if episode.has_key('video_large'):
        stream_urls.append(('SD Video Large',
                            episode['video_large']['mediaUrl']))
    if episode.has_key('video_small'):
        stream_urls.append(('SD Video Small',
                            episode['video_small']['mediaUrl']))
    if episode.has_key('video_audio'):
        stream_urls.append(('Audio', episode['video_audio']['mediaUrl']))
    resolved_url = None
    if not download:
        if content_type == 'audio':
            resolved_url = [i[1] for i in stream_urls if i[0] == 'Audio']
            if resolved_url:
                resolved_url = resolved_url[1]
        else:
            for i in stream_urls:
                if playback_options[addon.getSetting('playback')] == i[0]:
                    resolved_url = i[1]
                    break
    # If the prfered stream is not avaliable or for downloads,
    # we use select dialog with the avaliable streams.
    if resolved_url is None or download:
        dialog = xbmcgui.Dialog()
        ret = dialog.select(language(30002), [i[0] for i in stream_urls])
        if ret >= 0:
            resolved_url = stream_urls[ret][1]
    return resolved_url


def download_file(url, title):
    ''' thanks/credit to TheCollective for SimpleDownloader module'''
    stream_url =  resolve_url(url, True)
    path = addon.getSetting('download')
    if path == "":
        xbmc.executebuiltin("XBMC.Notification(%s,%s,10000,%s)"
                %(language(30038), language(30037), addon_icon))
        addon.openSettings()
        path = addon.getSetting('download')
    if path == "":
        return
    addon_log('######### Download #############')
    file_downloader = downloader.SimpleDownloader()
    invalid_chars = ['>', '<', '*', '/', '\\', '?', '.']
    for i in invalid_chars:
        title = title.replace(i, '')
    # the name of the file to be saved, we don't like spaces and we get
    # the proper extension from the URL
    name = '%s.%s' %(title.replace(' ', '_'), stream_url.split('.')[-1])
    addon_log('Title: %s - Name: %s' %(title, name))
    params = {"url": stream_url, "download_path": path, "Title": title}
    addon_log(str(params))
    file_downloader.download(name, params)
    addon_log('################################')


def twit_live():
    live_urls = [
        ('http://iphone-streaming.ustream.tv/uhls/1524/streams/live/'
        'iphone/playlist.m3u8'),
        ('http://hls.twit.tv/flosoft/smil:twitStreamAll.smil/'
         'playlist.m3u8'),
        'http://hls.twit.tv/flosoft/mp4:twitStream_720/playlist.m3u8',
        'http://hls.twit.tv/flosoft/mp4:twitStream_540/playlist.m3u8',
        'http://hls.twit.tv/flosoft/mp4:twitStream_360/playlist.m3u8',
        'http://twit.am/listen'
        ]
    if content_type == 'audio':
        resolved_url = live_urls[-1]
    else:
        resolved_url = live_urls[int(addon.getSetting('twit_live'))]
    return resolved_url


def set_resolved_url(resolved_url):
    success = False
    if resolved_url:
        success = True
    else:
        resolved_url = ''
    item = xbmcgui.ListItem(path=resolved_url)
    xbmcplugin.setResolvedUrl(int(sys.argv[1]), success, item)


def add_dir(name, url, iconimage, mode, info={}, fanart=None):
    item_params = {'name': name, 'url': url, 'mode': mode,
                   'iconimage': iconimage, 'content_type': content_type}
    plugin_url = '%s?%s' %(sys.argv[0], urllib.urlencode(item_params))
    listitem = xbmcgui.ListItem(name, iconImage=iconimage,
                                thumbnailImage=iconimage)
    if name == language(30001):
        contextMenu = [('Run IrcChat',
                        'RunPlugin(plugin://plugin.video.twit_api/?'
                        'mode=ircchat&name=ircchat&url=live_chat)')]
        listitem.addContextMenuItems(contextMenu)
    isfolder = True
    if mode == 'resolve_url' or mode == 'twit_live' or mode == 'episode':
        isfolder = False
        listitem.setProperty('IsPlayable', 'true')
    if mode == 'resolve_url' or mode == 'episode':
        contextMenu = [(language(30035),
                       'RunPlugin(plugin://plugin.video.twit_api/?'
                       'mode=download&name=%s&url=%s)' %(name, url))]
        listitem.addContextMenuItems(contextMenu)
    if fanart is None:
        fanart = addon_fanart
    listitem.setProperty('Fanart_Image', fanart)
    info_type = 'video'
    if content_type == 'audio':
        info_type = 'music'
    listitem.setInfo(type=info_type, infoLabels=info)
    xbmcplugin.addDirectoryItem(int(sys.argv[1]), plugin_url,
                                listitem, isfolder)


def run_ircchat():
    # check chat args
    nickname = addon.getSetting('nickname')
    username = addon.getSetting('username')
    if not nickname or not username:
        xbmc.executebuiltin('XBMC.Notification(%s, %s,10000,%s)' %
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
        (nickname, username, addon.getSetting('password'))
        )


def set_view_mode():
    view_mode = addon.getSetting('view_mode')
    if view_mode == "0":
        return
    view_modes = {
        '1': '502', # List
        '2': '51', # Big List
        '3': '500', # Thumbnails
        '4': '501', # Poster Wrap
        '5': '508', # Fanart
        '6': '504',  # Media info
        '7': '503',  # Media info 2
        '8': '515'  # Media info 3
        }
    xbmc.executebuiltin('Container.SetViewMode(%s)' %view_modes[view_mode])


def get_params():
    p = parse_qs(sys.argv[2][1:])
    for i in p.keys():
        p[i] = p[i][0]
    return p


params = get_params()

if params.has_key('content_type') and params['content_type'] == 'audio':
    content_type = 'audio'
else:
    content_type = 'video'

mode = None
try:
    mode = params['mode']
    addon_log('Mode: %s, Name: %s, URL: %s' %
              (params['mode'], params['name'], params['url']))
except:
    addon_log('Get root directory')

if mode is None:
    display_main()
    xbmcplugin.setContent(int(sys.argv[1]), 'tvshows')
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'retired_shows':
    display_shows('retired')
    xbmcplugin.setContent(int(sys.argv[1]), 'tvshows')
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'episodes':
    get_episodes(params['url'], params['iconimage'])
    xbmcplugin.setContent(int(sys.argv[1]), 'episodes')
    set_view_mode()
    episodes_cache_cleanup()
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'episode':
    set_resolved_url(resolve_url(params['url'], cached=False))
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'all_episodes':
    get_all_episodes()
    xbmcplugin.setContent(int(sys.argv[1]), 'episodes')
    set_view_mode()
    episodes_cache_cleanup()
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'search':
    search_twit()
    xbmcplugin.setContent(int(sys.argv[1]), 'episodes')
    set_view_mode()
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'search_results':
    get_search_results(params['url'])
    xbmcplugin.setContent(int(sys.argv[1]), 'episodes')
    set_view_mode()
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'resolve_url':
    set_resolved_url(resolve_url(params['url']))

elif mode == 'download':
    download_file(params['url'], params['name'])

elif mode == 'twit_live':
    set_resolved_url(twit_live())
    xbmc.sleep(1000)
    if addon.getSetting('run_chat') == 'true':
        run_ircchat()

elif mode == 'ircchat':
    run_ircchat()