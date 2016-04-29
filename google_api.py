from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
from httplib2 import Http


class GoogleApi:
    def __init__(self, json_file, delegate):
        scopes = ['https://www.googleapis.com/auth/drive.file']
        credentials = ServiceAccountCredentials.from_json_keyfile_name(json_file, scopes)
        delegated_credentials = credentials.create_delegated(delegate)
        http_auth = delegated_credentials.authorize(Http())
        this.drive_service = build('drive', 'v3', http=http_auth)

    def upload(self, filename):
        #Perform a resumable upload
        #Start with a call to /upload creating the filename and metadata
