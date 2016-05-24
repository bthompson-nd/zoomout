from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
from apiclient.http import MediaFileUpload
from apiclient import errors
from zoom_api import ZoomApi
from datetime import datetime
from httplib2 import Http
import urllib2
import json
import os
import time
import sys
import traceback


def log(string):
    """
    Prints a string to stdout, prepended with a date in the format %Y-%m-%d %H:%M:%S
    """
    print("{0} - {1}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), string))


class ZoomOut:
    def __init__(self, limit):
        """
        Initializer for the ZoomOut class, takes an integer parameter 'limit' that sets the maximum age for Zoom
        recordings before they are downloaded, archived in Google, and deleted.
        """
        # Set the path for the done file
        try:
            self.done_file_path = os.environ['ZOOMOUT_DONEFILE_PATH']
        except KeyError:
            log("Aborting: You need to set the ZOOMOUT_DONEFILE_PATH variable so the script knows what file to write to signal it has finished.")

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

        # Translate the limit given in hours to a limit in seconds
        self.limit = limit*60*60 if isinstance(limit, (int, long)) else 1*60*60

        # Try to load messaging from messaging.json. Goes with defaults if none present.
        self.load_messaging()  # Assigns self.messaging based on the messaging.json file or fails and keeps the default.

    def main(self):
        """
        The main method. Executes if you execute 'python zoomout.py 48'. Numeric argument is optional.
        """
        log("Starting...")
        try:
            # Collect meetings from Zoom and iterate through them...
            meetings = self.zoom.collect_meetings()
            archived = self.collect_archived_meetings()
            for meeting in meetings:
                start_time = datetime.strptime(meeting['recording']['start_time'], '%Y-%m-%dT%H:%M:%SZ')
                host = meeting['host']['email']
                host_username = host.split('@')[0]
                now = datetime.now()
                topic = meeting['recording']['topic'] if 'topic' in meeting['recording'] else '[no topic]'

                # If the recording is more than x hours old, save it and upload it to Google.
                if (now - start_time).seconds > self.limit:
                    # Find or create user's top level folder
                    top_folder = self.find_or_create_top_folder(
                            host=meeting['host'],
                            host_username=host_username)

                    # Find or create meeting's folder
                    meeting_folder_name = "{0} - {1}".format(topic, start_time)
                    meeting_folder = self.find_or_create_meeting_folder(
                            folder_name=meeting_folder_name,
                            zoom_meeting_id=meeting['recording']['meeting_number'],
                            top_folder=top_folder,
                            host=meeting['host'])

                    # Iterate through recording files and save them
                    successful_uploads = 0
                    for recording_file in meeting['recording']['recording_files']:
                        recording_file_id = recording_file['id']
                        filename = "{0}.{1}".format(recording_file_id, recording_file['file_type'])
                        if self.drive_file_exists(recording_file_id):
                            log("Skipping {0} recorded by {1}. Zoom file with this zoomFileId ({2}) in the appProperties already exists in Drive.".
                                format(filename, host, recording_file_id))
                            delete_response = self.zoom.delete_recording(
                                    meeting_id=recording_file['meeting_id'],
                                    file_id=recording_file_id)
                            if delete_response.status_code != 200:
                                log(delete_response.content)
                            if os.path.isfile(filename):
                                os.remove(filename)
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
                            successful_uploads += 1
                        except Exception as e:
                            log("Couldn't Upload {0} to Drive: {1}".format(filename, e.message))
                            if os.path.isfile(filename):
                                os.remove(filename)
                            continue  # Causes the loop to skip deleting from Zoom

                        try:
                            # Delete Zoom recording
                            self.zoom.delete_recording(
                                    meeting_id=recording_file['meeting_id'],
                                    file_id=recording_file_id)
                        except Exception as e:
                            log("Couldn't Delete Meeting {0} from Zoom: {1}".format(meeting['id'], e.message))

                        # Delete local file
                        if os.path.isfile(filename):
                            os.remove(filename)

                    # Now share the folder containing the files we just uploaded
                    if successful_uploads == len(meeting['recording']['recording_files']):
                        message = self.messaging['share']
                        self.share_document(meeting_folder['id'], host, message)
                    else:
                        log("Could not upload every recording file for meeting {0}".format(meeting_folder_name))

            done_file = open(self.done_file_path, 'wb')
            done_file.write('Done')
            done_file.close()
        except Exception as e:
            ex_type, ex, tb = sys.exc_info()
            trace = traceback.format_tb(tb)
            log("Something terrible has happened. Stopping here. {0} | {1}".format(e.message, trace))
            exit()

    def load_messaging(self):
        """
        Loads specialized messaging if you provide it in a JSON file whose location is determined by ZOOMOUT_MESSAGING_JSON.
        File must include a key/value pair with the key "share". Returns nothing. It sets the class variable called messaging
        """
        self.messaging = dict(share="Your recorded Zoom meeting is now available in your Google Drive.")
        try:
            if os.path.exists(os.environ['ZOOMOUT_MESSAGING_JSON']):
                messaging_file = open(os.environ['ZOOMOUT_MESSAGING_JSON'], 'rb')
                self.messaging = json.loads(messaging_file.read())
            else:
                log("No messaging.json file provided. Resorting to default messaging. "+
                    "Please include a JSON file called messaging.json containing a \"share\" field "+
                    "if you want to customize the message sent to the user when the files are shared on Drive.")
        except Exception as exc:
            log("File 'messaging.json' exists but something went wrong. Reverting to defaults.")

    def collect_archived_meetings(self):
        """Retrieves file list from Google Drive. Returns a list of file names. Returns an array of meeting ids in string form"""
        meeting_ids = []
        for f in self.drive.files().list().execute()['files']:
            try:
                meeting_ids.append(self.drive.files().get(fileId=f['id']).execute()['appProperties']['zoomMeetingId'])
            except Exception as exc:
                pass
        return meeting_ids

    def upload_to_drive(self, parent_id, filename):
        """Uploads the file to Google Drive.

        filename: A filepath to a file like '123abc.MP4'.

        parent_id: Google Drive document id of the parent folder

        Returns the Google Drive API's response to the Upload request
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
                status, response = request.next_chunk()
                if status:
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
        """Finds or creates the top level folder all of a user's recorded meetings will go in.

        host: the host dict from our meetings array

        host_username: host email stripped of '@' and anything after it

        Returns top_folder
        """
        user_recordings_folder_list = self.drive.files().list(q="mimeType = 'application/vnd.google-apps.folder' and appProperties has { key='zoomUserId' and value='" + str(host['id']) + "'}").execute()['files']
        if len(user_recordings_folder_list) > 0:
            top_folder = user_recordings_folder_list[0]
        else:
            top_folder = self.drive.files().create(body=dict(name="{0} Zoom Recorded Meetings".format(
                                                                host_username),
                                                             appProperties={'zoomUserId': host['id']},
                                                             mimeType="application/vnd.google-apps.folder"),
                                                   fields='id').execute()
            self.share_document(document_id=top_folder['id'], user=host['email'], message="This folder containing your recorded Zoom meetings should show in your \"Shared with Me\" view in Google Drive.")
        return top_folder

    def find_or_create_meeting_folder(self, folder_name, zoom_meeting_id, top_folder, host):
        """Finds or creates the folder for a given meeting

        folder_name: A text name for the folder

        zoom_meeting_id: The meeting ID from Zoom

        top_folder: The top level folder dedicated to that user's meeting recordings.

        host: Dict holding details about the host

        Returns meeting_folder
        """
        meeting_folder_list = self.drive.files().list(q="mimeType = 'application/vnd.google-apps.folder' and appProperties has { key='zoomMeetingId' and value='" + str(zoom_meeting_id) + "'}").execute()['files']
        if len(meeting_folder_list) < 1:
            meeting_folder = self.drive.files().create(body=dict(name=folder_name,
                                                                 parents=[top_folder['id']],
                                                                 mimeType="application/vnd.google-apps.folder",
                                                                 appProperties={'zoomMeetingId': zoom_meeting_id}),
                                                       fields='id').execute()
        else:
            meeting_folder = meeting_folder_list[0]
        return meeting_folder

    def drive_file_exists(self, zoom_file_id):
        """
        Checks to see if a file with a given Zoom file id exists among the archived Zoom files. The file id is stored in an appProperties field called zoomFileId.

        zoom_file_id: UUID for the file from Zoom

        Returns True or False
        """
        matches = self.drive.files().list(q="appProperties has { key='zoomFileId' and value='" + zoom_file_id + "'}").execute()['files']
        return len(matches) > 0

    def share_document(self, document_id, user, message):
        """Appends a permission to the file

        document_id: Google Drive fileId

        user: Host of the Zoom meeting, an email address

        message: String containing a message that will go to the user in the sharing alert

        Returns the Drive API's response. When successful, that is a "drive_service" object that you can make API calls on.
        """
        return self.drive.permissions().create(fileId=document_id,
                                               sendNotificationEmail=True,
                                               emailMessage=message,
                                               body={'emailAddress': user,
                                                     'role': 'writer',
                                                     'type': 'user'}).execute()

    def remove_from_drive(self, document_id):
        """Removes the file from Google Drive

        document_id: Google Drive fileId

        Returns nothing
        """
        self.drive.files().delete(fileId=document_id).execute()

    @staticmethod
    def authorize_with_drive():
        """Runs the authorization routine for a Google service account. Uses a JSON keyfile client_secrets.json
        :return: Resource object for interacting with Drive API v3
        """
        # Authorize with Google API
        scopes = ['https://www.googleapis.com/auth/drive']
        try:
            credentials = ServiceAccountCredentials.from_json_keyfile_name(os.environ['GOOGLE_AUTH_JSON'], scopes)
        except KeyError as exc:
            log("You need to set environment variable GOOGLE_AUTH_JSON with the path to a client secrets json file with a type value of \"service account\". {0}".format(exc.message))
            exit()
        http_auth = credentials.authorize(Http())
        drive = build('drive', 'v3', http=http_auth)
        return drive


if __name__ == "__main__":
    try:
        lim = int(sys.argv[1])
    except ValueError as e:
        log("Correct Usage: zoomout.py N   where N is an integer representing the number of days to wait before archiving a Zoom recording. Using the default 30 days...")
        lim = 1
    except IndexError as e:
        log("No argument provided. Archiving Zoom meetings over an hour old ...")
        lim = 1

    za = ZoomOut(limit=lim)
    za.main()
