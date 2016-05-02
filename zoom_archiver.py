from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
from apiclient.http import MediaFileUpload
from apiclient import errors
from zoom_api import ZoomApi
from datetime import datetime
from httplib2 import Http
import os
import time
import requests
import zipfile


def log(string):
    print("{0} - {1}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), string))


class ZoomArchiver:
    def __init__(self):
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

    def main(self):

        # Collect meetings from Zoom and iterate through them...
        meetings = self.collect_zoom_meetings()
        archived = self.collect_archived_meetings()
        for meeting in meetings:
            start_time = datetime.strptime(meeting['recording']['start_time'], '%Y-%m-%dT%H:%M:%SZ')
            host = meeting['host']['email']
            now = datetime.now()
            topic = meeting['recording']['topic'] if 'topic' in meeting['recording'] else 'no topic'
            for char in ['/', '\\', ' ']:
                topic = topic.replace(char, '_')
            meeting_number = meeting['recording']['meeting_number']
            zip_filename = "{0}-{1}.{2}".format(topic, meeting_number, 'zip')
            if zip_filename in archived:
                log("This meeting is already archived. Moving on...")
                continue
            if (now - start_time).days > 30:
                # If the recording is more than 30 days old, save it and upload it to Google.
                # Create a ZIP file with the meeting number as a name
                # Download and add each recording file to the archive
                # Save the archive
                # Upload the archive to Google Drive, as though owned by the meeting host
                with zipfile.ZipFile(zip_filename, 'w', allowZip64=True) as zf:
                    for recording_file in meeting['recording']['recording_files']:
                        filename = "{0}.{1}".format(recording_file['id'], recording_file['file_type'])
                        f = open(filename, 'wb')
                        try:
                            # Downloads the recording file to disk, inserts it into zf, and deletes the standalone file
                            remote_recording_file = requests.get(recording_file['download_url'])
                            f.write(remote_recording_file.content)
                            zf.write(filename)
                        except requests.RequestException as e:
                            log("Could not download the file {0} from Zoom Meeting {1}: {2}".
                                format(recording_file['download_url'], meeting['id'], e.message))
                        f.close()
                        os.remove(filename)
                    if len(zf.namelist()) < len(meeting['recording']['recording_files']):
                        # If we didn't get all the files, mention it and skip this one.
                        log("Failed to get all files from meeting #{0}: {1}. Skipping this meeting...".
                            format(meeting_number, topic)
                            )
                        os.remove(zip_filename)
                        continue  # Causes the loop to skip uploading to Drive, sharing, deleting from Zoom

                try:
                    # Upload it to Drive
                    upload_response = self.upload_to_drive(zip_filename)
                except Exception as e:
                    log("Couldn't Upload {0} to Drive: {1}".format(zip_filename, e.message))
                    os.remove(zip_filename)
                    continue  # Causes the loop to skip sharing, deleting from Zoom

                try:
                    # Share it with the host
                    share_response = self.share_with_host(upload_response['id'], host)
                except Exception as e:
                    log("Couldn't Share {0} with {1}. Deleting from Drive and from disk, and moving on. ({2})".
                        format(upload_response['name'], host, e.message)
                        )
                    os.remove(zip_filename)
                    self.drive.files().delete(fileId=upload_response['id'])
                    continue  # Causes the loop to skip deleting from Zoom

                # try:
                #     # Delete Zoom recording
                #     self.zoom.delete_recording(meeting['id'])
                # except Exception as e:
                #     log("Couldn't Delete Meeting {0} from Zoom: {1}".format(meeting['id'], e.message))

                # Delete local zip file
                os.remove(zip_filename)

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


    def upload_to_drive(self, zip_filename):
        """Uploads the file to Google Drive
        :param zip_filename: A filepath to a zip like 'My Meeting - 133455.zip'.
        :return: The Google Drive API's response to the Upload request
        """
        try:
            media_body = MediaFileUpload(
                    zip_filename,
                    mimetype='application/octet-stream',
                    chunksize=1024 * 256,
                    resumable=True)
            body = {
                'name': zip_filename,
                'description': "Zoom Recording",
                'mimeType': 'application/octet-stream'
            }
        except IOError as e:
            log("Couldn't generate upload for {0}. {1}".format(zip_filename, e.message))
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

    def share_with_host(self, id, host):
        """Appends a permission to the file
        :param id: Google Drive fileId
        :param host: Host of the Zoom meeting, an email address
        :return: The Drive API's response
        """
        return self.drive.permissions().create(fileId=id,
                                               body={'emailAddress': 'ben.thompson@gtest.nd.edu',
                                                     'role': 'writer',
                                                     'type': 'user'}).execute()

    def remove_from_drive(self, id):
        """Removes the file from Google Drive
        :param id: Google Drive fileId
        :return: Nothing
        """
        self.drive.files().delete(fileId=id).execute()

    def authorize_with_drive(self):
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
    za = ZoomArchiver()
    za.main()
