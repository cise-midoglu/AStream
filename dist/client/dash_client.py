"""
Author:            Parikshit Juluri
Contact:           pjuluri@mail.umkc.edu 

Testing:
    import dash_client
    mpd_file = <MPD_FILE>
    dash_client.playback_duration(mpd_file, 'http://198.248.242.16:8005/')
"""

import read_mpd
import urlparse
import urllib2
import string
import random
import os
import errno
import timeit
from multiprocessing import Process, Queue

def get_mpd(url):
    """ Module to download the MPD from the URL and save it to file"""
    try:
        mpd_data = urllib2.urlopen(url).read()
    except urllib2.HTTPError, error:
        print error.code
        print "Unable to download MPD file HTTP Error.",
        return None
    except urllib2.URLError:
        print '''URLError. Unable to reach Server.  
        Check if Server active '''
        return None
    mpd_file = url.split('/')[-1]
    mpd_file_handle = open(mpd_file, 'w')
    mpd_file_handle.write(mpd_data)
    mpd_file_handle.close()
    return mpd_file

def get_domain_name(url):
    """ Module to obtain the domain name from the URL
        From : http://stackoverflow.com/questions/9626535/get-domain-name-from-url
    """
    parsed_uri = urlparse.urlparse(url)
    domain = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_uri)
    return domain

def id_generator(size=6):
    """ Module to create a random string with uppercase 
        and digits.
    """
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(size))

def download_segment(segment_url, file_identifier):
    """ Module to download the segement"""
    try:
        segment_data = urllib2.urlopen(segment_url).read()
    except urllib2.HTTPError, error:
        print error.code
        print "Unable to download DASH Segment file HTTP Error"
        return None
    parsed_uri = urlparse.urlparse(segment_url)
    segment_path = '{uri.path}'.format(uri=parsed_uri)
    while segment_path.startswith('/'):
        segment_path = segment_path[1:]
        print "SEGMENT PATH", segment_path
    segment_filename = os.path.join(file_identifier,
            segment_path)
    make_sure_path_exists(os.path.dirname(segment_filename))
    segment_file_handle = open(segment_filename, 'wb')
    segment_file_handle.write(segment_data)
    segment_file_handle.close()
    return segment_filename

def get_media(domain, media_info, file_identifier, done_queue):
    """ Download the media from the list of URL's in media
    http://toastdriven.com/blog/2008/nov/11/brief-introduction-multiprocessing/
    """
    bandwidth, media_dict = media_info
    media = media_dict[bandwidth]
    print "GET MEDIA", file_identifier
    media_start_time = timeit.default_timer()
    for segment in [media.initialization] + media.url_list:
        start_time = timeit.default_timer()
        segment_url = urlparse.urljoin(domain, segment)
        segment_file = download_segment(segment_url,
                                        file_identifier)
        elapsed = timeit.default_timer() - start_time
        if segment_file:
            done_queue.put((bandwidth, segment_url, elapsed))
        print "Downloaded Segment bandwidth %d URL %s" % (
                bandwidth, segment)
    media_download_time = timeit.default_timer() - media_start_time
    done_queue.put((bandwidth, 'STOP', media_download_time))
    return None

def make_sure_path_exists(path):
    """ Module to make sure the path exists if not create it
    """
    print "Trying to create the path", path
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise

def start_playback(mpd_file, domain):
    """ Module that downloads the MPD-FIle and download
        all the representations of the Module to download
        the MPEG-DASH media.
    """
    dp_object = read_mpd.DashPlayback()
    dp_object = read_mpd.read_mpd(mpd_file, dp_object)
    #playback_duration = dp_object.playback_duration
    #dash_audio = dp_object.audio
    print "The DASH media has %d audio representations" % (
            len(dp_object.audio))
    #dash_video = dash_playback_object.video
    print "The DASH media has %d video representations" % (
                                len(dp_object.video))
    audio_done_queue = Queue()
    video_done_queue = Queue()

    processes = []
    file_identifier = id_generator(6)
    print "FILE IDENT", file_identifier

    for bandwidth in dp_object.audio:
        # Get the list of URL's (relative location) for the audio 
        dp_object.audio[bandwidth] = read_mpd.get_url_list(
                bandwidth, dp_object.audio[bandwidth],
                dp_object.playback_duration)
        # Create a new process to download the audio stream.
        # The domain + URL from the above list gives the 
        # complete path
        # The fil-identifier is a random string used to 
        # create  a temporary folder for current session
        # Audio-done queue is used to excahnge information
        # between the process and the calling function.
        # 'STOP' is added to the queue to indicate the end 
        # of the download of the sesson
        process = Process(target=get_media, args=(domain,
                (bandwidth, dp_object.audio), 
                file_identifier,
                audio_done_queue))
        process.start()
        processes.append(process)

    for bandwidth in dp_object.video:
        dp_object.video[bandwidth] = read_mpd.get_url_list(
                bandwidth, dp_object.video[bandwidth],
                dp_object.playback_duration)
        #Create a new process to download the audio 
        #stream.
        #The domain + URL from the above list gives the
        #complete path
        #The fil-identifier is a random string used to
        #create a temporary folder for current session
        #Video-done queue is used to excahnge information
        #between the process and the calling function.
        #'STOP' is added to the queue to indicate the 
        #end of the download of the sesson

        process = Process(target=get_media, args=(domain,
                (bandwidth, dp_object.video),
                file_identifier, video_done_queue))
        process.start()
        processes.append(process)

    for process in processes:
        process.join()

    count = 0
    for queue_values in iter(video_done_queue.get, None):
        bandwidth, status, elapsed = queue_values
        if status == 'STOP':
            print "Completed download of %s in %f " % (
                    bandwidth, elapsed)
            count += 1
            if count == len(dp_object.video):
                # If the download of all the videos is done
                # the stop the
                print "Finished d/w of  all video segments"
                break

def main():
    """ Main Program wrapper"""
    url = 'http://198.248.242.16:8006/mpd/x4ukwHdACDw.mpd'
    #url = 'http://127.0.0.1:8006/mpd/x4ukwHdACDw.mpd'
    print 'Downloading MPD file from %s' % (url)
    mpd_file = get_mpd(url)
    domian = get_domain_name(url)
    print 'Starting the streaming of the mpd_file'
    if mpd_file:
        start_playback(mpd_file, domian)
main()
