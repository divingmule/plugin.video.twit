import addon_api as api
try:
    import StorageServer
except ImportError:
    import storageserverdummy as StorageServer


cache = StorageServer.StorageServer('plugin.video.twit-leia', 24)


def get_shows(show_type):
    return eval(cache.get(show_type))


def cache_shows():
    for show_type in ['active', 'retired']:
        cache.set(show_type, repr(api.get_shows(show_type)))
    cache.set('show_version', api.get_shows_version())


def check_version():
    version = api.get_shows_version()
    if version != cache.get('show_version'):
        cache_shows()
        return 'Shows updated!'
    else:
        return 'No updates.'


def check_for_updates():
    return cache.cacheFunction(check_version)


def get_youtube_id():
    return api.get_youtube_id()
