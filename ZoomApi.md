
# zoom_api Module


## zoom_api.ZoomApi Objects



##### `__init__(self, api_key, api_secret)` 

> Initializer for ZoomApi object. Takes api_key and api_secret parameters.



##### `collect_meetings(self)` 

> Retrieve user list from Zoom. Will iterate through all, looking for aging meeting recordings. Returns an array of Zoom meetings



##### `delete_recording(self, meeting_id, file_id)` 

> Deletes a Zoom recording, leaving the meeting history in place.



##### `list_recordings(self, userid)` 

> Fetches the recordings from /v1/recording/list and returns the "meetings" array



##### `list_users(self)` 

> Queries the /v1/user/list endpoint and returns the array of users from the response.


