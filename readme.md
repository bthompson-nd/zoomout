# ZoomOut

A portable script for archiving your Zoom Cloud Recordings in your Google domain, written for Python2.7.10
(but later should probably work). Written at the University of Notre Dame by Benjamin J. Thompson

---

## How to Use It

### Get API keys from a Zoom account.
If you're doing this for your entire domain, make sure the Zoom account has sufficient privileges to query the
 recorded meetings of all users. On the Zoom website, go to the **My Profile** link on the sidebar, then click the
  **My Settings** tab on the profile page. Down at the bottom you should see **Integration Authentication**. Note the
  key and secret.

### Get Service Account Credentials in JSON format from Google.
Create a project in the Google Developer Console, turn on access to the Drive API, and in the Credentials screen,
conjure up a Service Account. Google will present a one-time download button to take the credentials in JSON. You'll
also need to go into the Admin panel and grant the service account access to the Drive scope: `https://www.googleapis.com/auth/drive`

### Install the Script and Environment Variables
Clone this repository or download the latest version as a ZIP from GitHub. You can install the requirements globally
 if you wish, but I prefer to create a virtual environment around the script like so:

    $ git clone https://github.com/ndoit/zoomout.git
    $ virtualenv zoomout
    $ cd zoomout
    $ source bin/activate
    $ pip install -r requirements.txt
    
That will make sure the requisite dependencies are installed, including the Google API Client library.

The environment that runs the script will
 need some environment variables set:
 
 * `ZOOM_API_KEY`: The "key" from the Zoom profile settings page
 * `ZOOM_API_SECRET`: The "Secret" from the Zoom profile settings page
 * `GOOGLE_AUTH_JSON`: The path to the Google service account credentials JSON file you downloaded
 * `ZOOMOUT_MESSAGING_JSON`: A short JSON file containing a `share` key with a string value with whatever message you
 want to have sent to the host of a meeting whenever the collected recordings of a meeting are shared with them.
 * `ZOOMOUT_DONEFILE_PATH`: This script is going to deposit a blank file to indicate that it has finished in case
 you have another process in your environment that will act after the archiving of Zoom content has finished. In my case,
 that was another script in the crontab that would delete the donefile and then shut down the cloud server instance
 the script just ran on.
 
 ### Running ZoomOut as a Module
 
 If you want, you can set the above environment variables and then fire up the interactive interpreter inside your
 virtualenv. You would then be able to do something like this:
 
    >>> import zoomout
    >>> zo = zoomout.ZoomOut(48)
    >>> zo.