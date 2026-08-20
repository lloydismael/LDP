"""Cross-platform database file storage helpers.

``django-db-file-storage`` treats stored file identifiers as operating-system
paths. On Windows that changes forward slashes to backslashes before querying
the database, so files uploaded on Linux cannot be found. Database identifiers
are keys rather than local paths; this backend keeps them slash-delimited on
all platforms.
"""

from urllib.parse import urlencode

from db_file_storage.storage import DatabaseFileStorage, NameException
from django.http import HttpResponse, HttpResponseBadRequest
from django.urls import reverse
from django.utils.translation import gettext as _


class PortableDatabaseFileStorage(DatabaseFileStorage):
    """Database storage using canonical, platform-independent file keys."""

    @staticmethod
    def canonical_name(name):
        if not isinstance(name, str):
            raise NameException("A database file name must be a string.")
        return name.replace("\\", "/")

    def _get_storage_attributes(self, name):
        canonical_name = self.canonical_name(name)
        try:
            (
                model_class_path,
                content_field,
                filename_field,
                mimetype_field,
                filename,
            ) = canonical_name.split("/")
        except ValueError as exc:
            raise NameException(
                "Wrong name format. Expected "
                "<app>.<model>/<content_field>/<filename_field>/"
                "<mimetype_field>/<filename>."
            ) from exc

        return {
            "model_class_path": model_class_path,
            "content_field": content_field,
            "filename_field": filename_field,
            "mimetype_field": mimetype_field,
            "filename": filename,
        }

    def _open(self, name, mode="rb"):
        if not mode or mode[0] not in "rwab":
            raise ValueError(f"Unsupported file mode: {mode!r}")

        canonical_name = self.canonical_name(name)
        storage_attrs = self._get_storage_attributes(canonical_name)
        model_cls = self._get_model_cls(storage_attrs["model_class_path"])
        model_instance = model_cls.objects.only(
            storage_attrs["content_field"], storage_attrs["mimetype_field"]
        ).get(**{storage_attrs["filename_field"]: canonical_name})

        file_object = self._get_file_from_encoded_bytes(
            getattr(model_instance, storage_attrs["content_field"])
        )
        file_object.filename = storage_attrs["filename"]
        file_object.mimetype = getattr(
            model_instance, storage_attrs["mimetype_field"]
        )
        return file_object

    def _save(self, name, content):
        return super()._save(self.canonical_name(name), content)

    def exists(self, name):
        try:
            canonical_name = self.canonical_name(name)
            storage_attrs = self._get_storage_attributes(canonical_name)
        except NameException:
            return False

        model_cls = self._get_model_cls(storage_attrs["model_class_path"])
        return model_cls.objects.filter(
            **{storage_attrs["filename_field"]: canonical_name}
        ).exists()

    def delete(self, name):
        canonical_name = self.canonical_name(name)
        storage_attrs = self._get_storage_attributes(canonical_name)
        model_cls = self._get_model_cls(storage_attrs["model_class_path"])
        model_cls.objects.filter(
            **{storage_attrs["filename_field"]: canonical_name}
        ).delete()

    def url(self, name):
        download_url = reverse("db_file_storage.download_file")
        return f"{download_url}?{urlencode({'name': self.canonical_name(name)})}"


storage = PortableDatabaseFileStorage()


def get_file(request, add_attachment_headers=False):
    """Serve a database-backed file using portable key lookup."""
    name = request.GET.get("name")
    if not name:
        return HttpResponseBadRequest(_("Invalid request"))

    try:
        file_object = storage.open(name)
        payload = file_object.read()
    except Exception:
        return HttpResponseBadRequest(_("Invalid request"))

    response = HttpResponse(payload, content_type=file_object.mimetype)
    response["Content-Length"] = len(payload)
    if add_attachment_headers:
        response["Content-Disposition"] = (
            f'inline; filename="{file_object.filename.replace(chr(34), "")}"'
        )
    return response
