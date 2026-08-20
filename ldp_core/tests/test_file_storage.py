import base64

from django.core.files.base import ContentFile
from django.test import TestCase

from ldp_core.models import FileData
from ldp_core.storage import PortableDatabaseFileStorage


class PortableDatabaseFileStorageTests(TestCase):
    key = "ldp_core.filedata/content/filename/mimetype/profile photo.png"
    payload = b"portable-image-content"

    def setUp(self):
        self.storage = PortableDatabaseFileStorage()
        FileData.objects.create(
            content=base64.b64encode(self.payload).decode("ascii"),
            filename=self.key,
            mimetype="image/png",
        )

    def test_download_serves_forward_slash_database_key(self):
        response = self.client.get(self.storage.url(self.key))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(response.content, self.payload)

    def test_backslash_key_is_canonicalized(self):
        windows_key = self.key.replace("/", "\\")

        self.assertTrue(self.storage.exists(windows_key))
        with self.storage.open(windows_key) as stored_file:
            self.assertEqual(stored_file.read(), self.payload)

    def test_new_upload_uses_forward_slashes(self):
        saved_name = self.storage.save(
            "ldp_core.filedata\\content\\filename\\mimetype\\new image.png",
            ContentFile(b"new-image", name="new image.png"),
        )

        self.assertNotIn("\\", saved_name)
        self.assertTrue(FileData.objects.filter(filename=saved_name).exists())
        with self.storage.open(saved_name) as stored_file:
            self.assertEqual(stored_file.read(), b"new-image")

    def test_delete_accepts_backslash_key(self):
        self.storage.delete(self.key.replace("/", "\\"))

        self.assertFalse(FileData.objects.filter(filename=self.key).exists())

    def test_malformed_key_does_not_exist(self):
        self.assertFalse(self.storage.exists("not-a-storage-key"))
