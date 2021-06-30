import requests

api_url = 'https://lr7tqd.deta.dev/'


def call_api(url):
    headers = {'X-API-Key': '2moSoL2E.LTS87Bhnegc1PEi4tLR1uq-WTTxqRqvFh'}
    res = requests.get(url, headers=headers)
    if not res.status_code == requests.codes.ok:
        res.raise_for_status()
    return res.json()


def get_shows(show_type):
    shows_url = '{}shows/{}'.format(api_url, show_type)
    return call_api(shows_url)


def get_shows_version():
    version_url = '{}update/check'.format(api_url)
    check = call_api(version_url)
    return check['version']


def get_youtube_id():
    youtube_url = '{}youtube'.format(api_url)
    return call_api(youtube_url)['yt_id']
