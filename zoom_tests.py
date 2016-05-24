import unittest
from zoomout import ZoomOut

class ZoomOutTest(unittest.TestCase):

    def setUp(self):
        self.zoomout = ZoomOut(0)
        self.ids = []

    def tearDown(self):
        for id in self.ids:
            self.zoomout.remove_from_drive(id)

    def test_collect_zoom_meetings(self):
        meetings = self.zoomout.collect_zoom_meetings()
        self.assertTrue(len(meetings) > 0)
        self.assertTrue('recording' in meetings[0])
        self.assertTrue('meeting_number' in meetings[0]['recording'])
        for meeting in meetings:
            self.assertTrue('host' in meeting)
            self.assertTrue('email' in meeting['host'])

    def test_add_folder_with_meta(self):
            host = dict(email='my@email.address.edu', id='12345')
            host_username = 'ben.thompson'
            top_folder = self.zoomout.find_or_create_top_folder(host, host_username)
            self.ids.append(top_folder['id'])
            q_top_folder = self.zoomout.drive.files().list(q="mimeType = 'application/vnd.google-apps.folder' and appProperties has { key='zoomUserId' and value='" + host['id'] + "'} ").execute()['files']
            self.assertTrue(q_top_folder[0]['id'] == top_folder['id'])
            top_folder_2 = self.zoomout.find_or_create_top_folder(host, host_username)
            self.assertTrue(q_top_folder[0]['id'] == top_folder_2['id'])

    def test_archived_meetings(self):
        archived_meetings = self.zoomout.collect_archived_meetings()

if __name__ == '__main__':
    unittest.main()
