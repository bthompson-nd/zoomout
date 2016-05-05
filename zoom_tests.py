import unittest
from zoom_archiver import ZoomArchiver
import os


class ZoomArchiverTest(unittest.TestCase):

    def setUp(self):
        self.zoomarchiver = ZoomArchiver()
        self.ids = []

    def tearDown(self):
        for id in self.ids:
            self.zoomarchiver.remove_from_drive(id)

    def test_collect_zoom_meetings(self):
        meetings = self.zoomarchiver.collect_zoom_meetings()
        self.assertTrue(len(meetings) > 0)
        self.assertTrue('recording' in meetings[0])
        self.assertTrue('meeting_number' in meetings[0]['recording'])
        for meeting in meetings:
            self.assertTrue('host' in meeting)
            self.assertTrue('email' in meeting['host'])

    def test_ZA_upload_to_drive(self):
        for filename in [f for f in os.listdir('.') if '.zip' in f]:
            print("Uploading {0}".format(filename))
            response = self.zoomarchiver.upload_to_drive(filename)
            self.assertTrue('mimeType' in response)
            self.assertTrue('kind' in response)
            self.assertTrue('id' in response)
            self.assertTrue('name' in response)
            if 'id' in response:
                self.ids.append(response['id'])

            share_response = self.zoomarchiver.share_document(response['id'], 'ben.thompson@gtest.nd.edu')
            self.assertTrue('role' in share_response and share_response['role'] == 'writer')
            self.assertTrue('type' in share_response and share_response['type'] == 'user')

    def test_archived_meetings(self):
        archived_meetings = self.zoomarchiver.collect_archived_meetings()
        print(archived_meetings)

if __name__ == '__main__':
    unittest.main()
