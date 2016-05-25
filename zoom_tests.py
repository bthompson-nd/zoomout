import unittest
import json
from zoomout import ZoomOut

class ZoomOutTest(unittest.TestCase):

    def setUp(self):
        self.zoomout = ZoomOut(0)
        self.ids = []

    def tearDown(self):
        # for id in self.ids:
        #     self.zoomout.remove_from_drive(id)
        pass

    def test_collect_zoom_meetings(self):
        meetings = self.zoomout.zoom.collect_meetings()
        self.assertTrue(len(meetings) > 0)
        self.assertTrue('recording' in meetings[0])
        self.assertTrue('meeting_number' in meetings[0]['recording'])
        # for meeting in meetings:
        self.assertTrue('host' in meetings[0])
        self.assertTrue('email' in meetings[0]['host'])

        print("There are {} recorded zoom meetings.".format(str(len(meetings))))

    def test_add_folders_with_meta_and_file_and_share(self):
        host_email = raw_input('Input an email address for a mockup meeting host: ')
        host_id = raw_input('Input an id for the mockup meeting host: ')
        host = dict(email=host_email, id=host_id)
        host_username = host_email.split('@')[0]

        # Test that top folder creation won't make duplicates
        top_folder = self.zoomout.find_or_create_top_folder(host, host_username)
        self.ids.append(top_folder['id'])
        q_top_folder = self.zoomout.drive.files().list(q="mimeType = 'application/vnd.google-apps.folder' and appProperties has { key='zoomUserId' and value='" + host['id'] + "'} ").execute()['files']
        self.assertTrue(q_top_folder[0]['id'] == top_folder['id'])
        top_folder_2 = self.zoomout.find_or_create_top_folder(host, host_username)
        self.assertTrue(q_top_folder[0]['id'] == top_folder_2['id'])

        # Test that meeting folder creation won't make duplicates
        meeting_folder = self.zoomout.find_or_create_meeting_folder('A Test Meeting Folder', '67890', top_folder, host)
        self.ids.append(meeting_folder['id'])
        q_meeting_folder = self.zoomout.drive.files().list(q="mimeType = 'application/vnd.google-apps.folder' and appProperties has { key='zoomMeetingId' and value='67890'}").execute()['files']
        self.assertTrue(q_meeting_folder[0]['id'] == meeting_folder['id'])
        meeting_folder_2 = self.zoomout.find_or_create_meeting_folder('A Test Meeting Folder', '67890', top_folder, host)
        self.assertTrue(q_meeting_folder[0]['id'] == meeting_folder_2['id'])

        # Test that sharing works properly
        upload_result = self.zoomout.upload_to_drive(meeting_folder['id'], 'messaging.json')
        self.assertTrue(upload_result)






if __name__ == '__main__':
    unittest.main()
