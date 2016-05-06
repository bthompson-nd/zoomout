from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
from apiclient.http import MediaFileUpload
from apiclient import errors
from zoom_api import ZoomApi
from datetime import datetime
from httplib2 import Http
import urllib2
import os
import time
import sys
import traceback


def log(string):
    print("{0} - {1}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), string))


class ZoomArchiver:
    def __init__(self, limit):
        # Establish Google Drive API
        self.drive = self.authorize_with_drive()
        # Establish Zoom API
        try:
            self.zoom = ZoomApi(
                    os.environ['ZOOM_API_KEY'],
                    os.environ['ZOOM_API_SECRET']
            )
        except KeyError:
            log("Aborting: You need to set the ZOOM_API_KEY and ZOOM_API_SECRET environment variables first.")
            exit()

        self.limit = limit

    def main(self):
        log("Starting...")
        try:
            # Collect meetings from Zoom and iterate through them...
            meetings = self.collect_zoom_meetings()
            archived = self.collect_archived_meetings()
            for meeting in meetings:
                start_time = datetime.strptime(meeting['recording']['start_time'], '%Y-%m-%dT%H:%M:%SZ')
                host = 'ben.thompson@gtest.nd.edu' ## meeting['host']['email']
                host_username = host.split('@')[0]
                now = datetime.now()
                topic = meeting['recording']['topic'] if 'topic' in meeting['recording'] else 'no topic'
                for character in ["\"", "'", "\\", "/"]:
                    topic = topic.replace(character, "")

                # If the recording is more than 30 days old, save it and upload it to Google.
                if (now - start_time).days > self.limit:
                    # Find or create user's top level folder
                    top_folder = self.find_or_create_top_folder(
                            host=host,
                            host_username=host_username)

                    # Find or create meeting's folder
                    meeting_folder_name = "{0} - {1}".format(topic, start_time)
                    meeting_folder = self.find_or_create_meeting_folder(
                            folder_name=meeting_folder_name,
                            top_folder=top_folder,
                            host=host)

                    # Iterate through recording files and save them
                    for recording_file in meeting['recording']['recording_files']:
                        filename = "{0}.{1}".format(recording_file['id'], recording_file['file_type'])
                        if filename in archived:
                            log("Skipping {0} recorded by {1}. File by this name already exists in Drive.".
                                format(filename, host))
                            continue  # Causes the loop to skip downloading this file (and all subsequent steps)

                        try:
                            # Downloads the recording file to disk
                            remote_file = urllib2.urlopen(recording_file['download_url'])
                            with open(filename, 'wb') as f:
                                while True:
                                    tmp = remote_file.read(1024)
                                    if not tmp:
                                        break
                                    f.write(tmp)
                        except Exception as exc:
                            log("Could not download the file {0} from Zoom Meeting {1} (URL {2}): {3}".
                                format(filename,
                                       meeting['id'],
                                       recording_file['download_url'],
                                       exc.message))
                            if os.path.isfile(filename):
                                os.remove(filename)
                            continue  # Causes the loop to skip uploading to Drive, sharing, and deleting from Zoom

                        try:
                            # Upload it to Drive
                            upload_response = self.upload_to_drive(meeting_folder['id'], filename)
                        except Exception as e:
                            log("Couldn't Upload {0} to Drive: {1}".format(filename, e.message))
                            if os.path.isfile(filename):
                                os.remove(filename)
                            continue  # Causes the loop to skip sharing, deleting from Zoom

                        try:
                            # Share it with the host
                            self.share_document(upload_response['id'], host)
                        except Exception as e:
                            log("Couldn't Share {0} with {1}. Deleting from Drive and from disk, and moving on. ({2})".
                                format(upload_response['name'], host, e.message)
                                )
                            if os.path.isfile(filename):
                                os.remove(filename)
                            self.drive.files().delete(fileId=upload_response['id'])
                            continue  # Causes the loop to skip deleting from Zoom

                        # try:
                        #     # Delete Zoom recording
                        #     self.zoom.delete_recording(meeting['id'])
                        # except Exception as e:
                        #     log("Couldn't Delete Meeting {0} from Zoom: {1}".format(meeting['id'], e.message))

                        # Delete local file
                        if os.path.isfile(filename):
                            os.remove(filename)
            done_file = open('done.flag', 'wb')
            done_file.write('Done')
            done_file.close()
        except Exception as e:
            ex_type, ex, tb = sys.exc_info()
            trace = traceback.format_tb(tb)
            log("Something terrible has happened. Stopping here. {0} | {1} | {2}".format(e.message, trace, ex.content))
            exit()

    def collect_zoom_meetings(self):
        """Retrieve user list from Zoom. Will iterate through all, looking for aging meeting recordings.
        :return: An array of Zoom meetings
        """

        user_list = self.zoom.list_users()
        meetings = []
        for user in user_list:
            user_recordings = self.zoom.list_recordings(user['id'])
            for recording in user_recordings:
                meetings.append(dict(host=user, recording=recording))
        return meetings

    def collect_archived_meetings(self):
        """Retrieves file list from Google Drive. Returns a list of meeting IDs.

        :return: Array of meeting ids in string form
        """
        files = self.drive.files().list().execute()['files']
        return [f['name'] for f in files]

    def upload_to_drive(self, parent_id, filename):
        """Uploads the file to Google Drive
        :param filename: A filepath to a file like '123abc.MP4'.
        :param parent_id: Google Drive document id of the parent folder
        :return: The Google Drive API's response to the Upload request
        """
        try:
            media_body = MediaFileUpload(
                    filename,
                    mimetype='application/octet-stream',
                    chunksize=1024 * 256,
                    resumable=True)
            body = {
                'name': filename,
                'description': "Zoom Recording",
                'parents': [parent_id],
                'mimeType': 'application/octet-stream'
            }
        except IOError as e:
            log("Couldn't generate upload for {0}. {1}".format(filename, e.strerror))
            return ''

        retries = 0
        request = self.drive.files().create(body=body, media_body=media_body)
        response = None

        # Upload the file
        while response is None:
            try:
                # print(http_auth.request.credentials.access_token)
                status, response = request.next_chunk()
                if status:
                    # log("Uploaded %.2f%%" % (status.progress() * 100))
                    retries = 0
            except errors.HttpError, e:
                if e.resp.status == 404:
                    log("Error 404 - Aborting")
                    exit()
                else:
                    if retries > 10:
                        log("Retries limit exceeded! Aborting")
                        exit()
                    else:
                        retries += 1
                        time.sleep(2 ** retries)
                        print "Error ({0})({1})... retrying.".format(e.resp.status, e.message)
                        continue
        return response

    def find_or_create_top_folder(self, host, host_username):
        """Finds or creates the top level folder all of a user's recorded meetings will go in
        :param host:
        :param host_username:
        :return: top_folder
        """
        user_recordings_folder_list = self.drive.files().list(q="mimeType = 'application/vnd.google-apps.folder' and name = '{0} Zoom Recorded Meetings'".format(host_username)).execute()['files']
        if len(user_recordings_folder_list) > 0:
            top_folder = user_recordings_folder_list[0]
        else:
            top_folder = self.drive.files().create(body=dict(name="{0} Zoom Recorded Meetings".format(
                                                                host_username),
                                                             mimeType="application/vnd.google-apps.folder"),
                                                   fields='id').execute()
            self.share_document(top_folder['id'], host)
        return top_folder

    def find_or_create_meeting_folder(self, folder_name, top_folder, host):
        """Finds or creates the folder for a given meeting
        :param folder_name:
        :param top_folder:
        :param host:
        :return: meeting_folder
        """
        meeting_folder_list = self.drive.files().list(q="mimeType = 'application/vnd.google-apps.folder' and name = '{0}'".format(folder_name)).execute()['files']
        if len(meeting_folder_list) < 1:
            meeting_folder = self.drive.files().create(body=dict(name=folder_name,
                                                                 parents=[top_folder['id']],
                                                                 mimeType="application/vnd.google-apps.folder"),
                                                       fields='id').execute()
            self.share_document(meeting_folder['id'], host)
        else:
            meeting_folder = meeting_folder_list[0]
        return meeting_folder

    def share_document(self, document_id, user):
        """Appends a permission to the file
        :param document_id: Google Drive fileId
        :param user: Host of the Zoom meeting, an email address
        :return: The Drive API's response
        """
        return self.drive.permissions().create(fileId=document_id,
                                               body={'emailAddress': user,
                                                     'role': 'writer',
                                                     'type': 'user'}).execute()

    def remove_from_drive(self, document_id):
        """Removes the file from Google Drive
        :param document_id: Google Drive fileId
        :return: Nothing
        """
        self.drive.files().delete(fileId=document_id).execute()

    @staticmethod
    def authorize_with_drive():
        """Runs the authorization routine for a Google service account. Uses a JSON keyfile client_secrets.json
        :return: Resource object for interacting with Drive API v3
        """
        # Authorize with Google API
        scopes = ['https://www.googleapis.com/auth/drive']
        credentials = ServiceAccountCredentials.from_json_keyfile_name('client_secrets.json', scopes)
        http_auth = credentials.authorize(Http())
        drive = build('drive', 'v3', http=http_auth)
        return drive


if __name__ == "__main__":
    try:
        lim = int(sys.argv[1])
    except ValueError as e:
        log("Correct Usage: zoom_archiver.py N   where N is an integer representing the number of days to wait before archiving a Zoom recording. Using the default 30 days...")
        lim = 30
    except IndexError as e:
        log("No argument provided. Archiving Zoom meetings older than 30 days...")
        lim = 30

    za = ZoomArchiver(limit=lim)
    za.main()
