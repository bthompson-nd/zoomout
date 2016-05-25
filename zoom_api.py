import requests
from time import sleep
import json

class ZoomApi:
    def __init__(self, api_key, api_secret):
        """Initializer for ZoomApi object. Takes api_key and api_secret parameters."""
        self.api_key = api_key
        self.api_secret = api_secret

    def list_users(self):
        """Queries the /v1/user/list endpoint and returns the array of users from the response."""
        page = 0
        max_page = 0
        users = []
        while page < 1 or page < max_page:
            page += 1
            response = requests.post('https://api.zoom.us/v1/user/list',
                          data=dict(
                                  api_key=self.api_key,
                                  api_secret=self.api_secret,
                                  page_number=page,
                                  page_size=300))
            sleep(0.1)
            if response.status_code == 200:
                content = json.loads(response.content)
                max_page = content['page_count']
                if not 'users' in content:
                    print(content)
                    return
                for user in content['users']:
                    users.append(user)
            else:
                print(response)
                return
        return users

    def list_recordings(self, userid):
        """Fetches the recordings from /v1/recording/list and returns the "meetings" array"""
        page = 0
        max_page = 0
        meetings = []
        while page < 1 or page < max_page:
            page += 1
            response = requests.post('https://api.zoom.us/v1/recording/list',
                             data=dict(
                                 api_key=self.api_key,
                                 api_secret=self.api_secret,
                                 page_number=page,
                                 page_size=300,
                                 host_id=userid))
            sleep(0.1)
            if response.status_code == 200:
                content = json.loads(response.content)
                max_page = content['page_count'] if 'page_count' in content else 1
                if not 'meetings' in content:
                    print(content)
                    break
                for meeting in content['meetings']:
                    meetings.append(meeting)
            else:
                print(response)
        return meetings

    def collect_meetings(self):
        """Retrieve user list from Zoom. Will iterate through all, looking for aging meeting recordings. Returns an array of Zoom meetings
        """
        user_list = self.list_users()
        meetings = []
        for user in user_list:
            user_recordings = self.list_recordings(user['id'])
            for recording in user_recordings:
                meetings.append(dict(host=user, recording=recording))
        return meetings

    def delete_recording(self, meeting_id, file_id):
        """Deletes a Zoom recording, leaving the meeting history in place."""
        response = requests.post('https://api.zoom.us/v1/recording/delete',
                                 data=dict(
                                     api_key=self.api_key,
                                     api_secret=self.api_secret,
                                     meeting_id=meeting_id,
                                     file_id=file_id
                                 ))
        sleep(0.1)
        return response