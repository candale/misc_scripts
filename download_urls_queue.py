import os
import queue
import shutil
import requests
import subprocess
from datetime import date
from threading import Semaphore, Thread, Event, Lock

from concurrent.futures import ThreadPoolExecutor, wait

from urllib.parse import urlparse


DAY_LANG = {
    'Monday': 'Luni',
    'Tuesday': 'Marti',
    'Wednesday': 'Miercuri',
    'Thursday': 'Joi',
    'Friday': 'Vineri',
    'Saturday': 'Sambata',
    'Sunday': 'Duminica'
}


ROOT_DIR = '.'
CONCURRENT_DOWNLOADS = 4
CONCURRENT_UPLOADS = 6

semaphore = Semaphore(value=CONCURRENT_DOWNLOADS)


def get_disk_locations(url):
    path = urlparse(url).path
    *_, year, month, day_with_number = path.split('/')
    number_in_day = 1
    if '.' in day_with_number:
        day, number_in_day = day_with_number.split('.')
    else:
        day = day_with_number

    happened_at = date(year=int(year), month=int(month), day=int(day))
    day_name = DAY_LANG[happened_at.strftime('%A')]
    dir_location = '{}/{}/{}/'.format(ROOT_DIR, year, month)
    file_name = '{}.{}.Part.{}.ts'.format(day, day_name, number_in_day)
    local_name = os.path.join(dir_location, file_name)
    tmp_local_name = local_name + '.part'

    return local_name, tmp_local_name, dir_location


def download_file(url, upload_queue, stats):
    local_name, tmp_local_name, dir_location = get_disk_locations(url)

    if stats.was_downloaded(local_name):
        print('Skipping because already downloaded: {}'.format(url))
        return

    if os.path.isdir(dir_location) is False:
        os.makedirs(dir_location)

    print('Downloading url {}'.format(url))
    with requests.get(url, stream=True) as r:
        with open(tmp_local_name, 'wb') as f:
            shutil.copyfileobj(r.raw, f)

    os.rename(tmp_local_name, local_name)
    print(f'Put work for upload on file {local_name}')
    upload_queue.put(local_name, block=True, timeout=None)
    stats.incr('downloaded')


def make_webdav_dir(dir_path, webdav_url, basic_auth_string):
    print(f'Making path {dir_path}')
    the_path = ''
    for component in filter(None, map(lambda x: x.strip(), dir_path.split('/'))):
        if the_path:
            the_path = f'{the_path}/{component}'
        else:
            the_path = component

        curl_command = [
            f"curl",
            f'-k',
            f'-X',
            f'MKCOL',
            f"-u",
            f"{basic_auth_string}",
            f"{webdav_url}/Online Content Storage/Video/Arhiva/{the_path}",
        ]

        subprocess.run(
            curl_command, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)


def upload_file(file_path, webdav_url, basic_auth_string):
    webdav_url = webdav_url.strip('/')
    clean_file_path = file_path.lstrip('./')
    dir_structure = os.path.dirname(clean_file_path)
    make_webdav_dir(dir_structure, webdav_url, basic_auth_string)
    curl_command = [
        "curl",
        '-k',
        '--fail',
        "-u",
        basic_auth_string,
        "-T",
        file_path,
        f"{webdav_url}/Online Content Storage/Video/Arhiva/{clean_file_path}",
    ]

    print(f'Uploading {file_path}')
    result = subprocess.run(curl_command)

    return result.returncode == 0


def get_pending_uploads(with_partial=False):
    paths = []

    def should_include(file_name):
        return file_name.endswith('.ts')

    for root, dirs, files in os.walk(ROOT_DIR):
        paths.extend([os.path.join(root, file) for file in files if file.endswith('.ts')])

    return paths


def upload_file_daemon_and_del(work_queue: queue.Queue, work_done, stats):
    webdav_url = 'https://hub.bisericairis.ro/remote.php/dav/files/{username}/'
    basic_auth = 'username:pass'

    print('Waiting to upload jobs')
    while not work_done.is_set():
        try:
            upload_path = work_queue.get(timeout=1)
        except queue.Empty:
            continue

        print(f'Doing upload for {upload_path}')
        was_success = upload_file(upload_path, webdav_url, basic_auth)
        if was_success is False:
            stats.write_upload_failed(upload_path)
            stats.incr('failed_upload')

        os.remove(upload_path)
        work_queue.task_done()

        stats.write_upload_success(upload_path)
        stats.incr('uploaded')


class Stats:

    def __init__(self, video_count):
        self.stats = {
            'video_count': video_count,
            'downloaded': 0,
            'uploaded': 0,
            'failed_download': 0,
            'failed_upload': 0,
        }
        self._times_called = 0

        self.downloaded_hashes = set()
        if os.path.exists('upload.success.log'):
            with open('upload.success.log', 'r') as f:
                self.downloaded_hashes = set(
                    filter(None, [self.video_path_hash(path) for path in f])
                )

        self._upload_success_log = open('upload.success.log', 'a')
        self._upload_fail_log = open('upload.fail.log', 'a')

        self._upload_success_lock = Lock()
        self._upload_fail_lock = Lock()
        self._incr_lock = Lock()
        self._hash_lock = Lock()

    def video_path_hash(self, path):
        return path.strip().lstrip('./')

    def was_downloaded(self, path):
        with self._hash_lock:
            return self.video_path_hash(path) in self.downloaded_hashes

    def incr(self, key):
        with self._incr_lock:
            self.stats[key] += 1

            self._times_called += 1
            if self._times_called % 10 == 0:
                print('=== STATS ===', self.stats)

    def write_upload_success(self, line):
        with self._upload_success_lock:
            self._upload_success_log.write(line + '\n')
            self._upload_success_log.flush()

    def write_upload_failed(self, line):
        with self._upload_fail_lock:
            self._upload_fail_log.write(line + '\n')
            self._upload_fail_log.flush()


def run():
    urls = list(filter(None, map(lambda x: x.strip(), open('urls.txt', 'r'))))
    upload_queue = queue.Queue(maxsize=CONCURRENT_UPLOADS)
    work_done = Event()

    upload_daemons = []
    stats = Stats(len(urls))

    for thread_number in range(CONCURRENT_DOWNLOADS * 2):
        upload_daemon = Thread(
            target=upload_file_daemon_and_del,
            args=(upload_queue, work_done, stats)
        )

        upload_daemon.start()
        upload_daemons.append(upload_daemon)

    download_futures = []
    with ThreadPoolExecutor(max_workers=CONCURRENT_DOWNLOADS) as executor:
        print('Filling up download queue')
        for url in urls:
            download_futures.append(
                executor.submit(download_file, url.strip(), upload_queue, stats))

        print('Waiting on tasks to be completed ...')
        wait(download_futures)

    print('Draining queue')
    upload_queue.join()
    print('Setting work done')
    work_done.set()

    print('Brining upload daemons home')
    for upload_daemon in upload_daemons:
        upload_daemon.join()

    print('All done. Thank you.')
