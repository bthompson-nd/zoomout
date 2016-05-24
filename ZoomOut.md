
# zoomout Module


## Functions

##### `log(string)` 

> Prints a string to stdout, prepended with a date in the format %Y-%m-%d %H:%M:%S



## zoomout.ZoomOut Objects



##### `__init__(self, limit)` 

> Initializer for the ZoomOut class, takes an integer parameter 'limit' that sets the maximum age for Zoom
> recordings before they are downloaded, archived in Google, and deleted.



##### `authorize_with_drive()` 

> Runs the authorization routine for a Google service account. Uses a JSON keyfile client_secrets.json
>         :return: Resource object for interacting with Drive API v3



##### `collect_archived_meetings(self)` 

> Retrieves file list from Google Drive. Returns a list of file names. Returns an array of meeting ids in string form



##### `drive_file_exists(self, zoom_file_id)` 

> Checks to see if a file with a given Zoom file id exists among the archived Zoom files. The file id is stored in an appProperties field called zoomFileId.
> 
> zoom_file_id: UUID for the file from Zoom
> 
> Returns True or False



##### `find_or_create_meeting_folder(self, folder_name, zoom_meeting_id, top_folder, host)` 

> Finds or creates the folder for a given meeting
> 
>         folder_name: A text name for the folder
> 
>         zoom_meeting_id: The meeting ID from Zoom
> 
>         top_folder: The top level folder dedicated to that user's meeting recordings.
> 
>         host: Dict holding details about the host
> 
>         Returns meeting_folder



##### `find_or_create_top_folder(self, host, host_username)` 

> Finds or creates the top level folder all of a user's recorded meetings will go in.
> 
>         host: the host dict from our meetings array
> 
>         host_username: host email stripped of '@' and anything after it
> 
>         Returns top_folder



##### `load_messaging(self)` 

> Loads specialized messaging if you provide it in a JSON file whose location is determined by ZOOMOUT_MESSAGING_JSON.
> File must include a key/value pair with the key "share". Returns nothing. It sets the class variable called messaging



##### `main(self)` 

> The main method. Executes if you execute 'python zoomout.py 48'. Numeric argument is optional.



##### `remove_from_drive(self, document_id)` 

> Removes the file from Google Drive
> 
>         document_id: Google Drive fileId
> 
>         Returns nothing



##### `share_document(self, document_id, user, message)` 

> Appends a permission to the file
> 
>         document_id: Google Drive fileId
> 
>         user: Host of the Zoom meeting, an email address
> 
>         message: String containing a message that will go to the user in the sharing alert
> 
>         Returns the Drive API's response. When successful, that is a "drive_service" object that you can make API calls on.



##### `upload_to_drive(self, parent_id, filename)` 

> Uploads the file to Google Drive.
> 
>         filename: A filepath to a file like '123abc.MP4'.
> 
>         parent_id: Google Drive document id of the parent folder
> 
>         Returns the Google Drive API's response to the Upload request


