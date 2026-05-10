"""
migrate_media_to_db
-------------------
Reads every existing on-disk media file that is referenced by an
ImageField/FileField, stores it in PostgreSQL via django-db-file-storage,
and updates the model field to point to the new DB-backed location.

Usage:
    python manage.py migrate_media_to_db
"""

import mimetypes
import os

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from ldp_core.models import Activity, LeadershipAward, Person, School


class Command(BaseCommand):
    help = "Migrate on-disk media files into PostgreSQL (db_file_storage)"

    # (Model, list of ImageField names)
    FILE_FIELDS = [
        (Person, ["profile_photo", "banner"]),
        (School, ["logo", "banner"]),
        (Activity, ["banner"]),
        (LeadershipAward, ["certificate"]),
    ]

    def handle(self, *args, **options):
        media_dir = os.path.join(settings.BASE_DIR, "media")
        total_ok = 0
        total_missing = 0
        total_skip = 0

        for Model, fields in self.FILE_FIELDS:
            label = f"{Model._meta.app_label}.{Model.__name__}"
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n── {label} ──"))

            for field_name in fields:
                self.stdout.write(f"  Field: {field_name}")

                # Use values() so we get raw strings — avoids storage backend
                # trying to interpret old-style paths like 'profiles/xxx.jpg'.
                rows = (
                    Model.objects
                    .exclude(**{field_name: ""})
                    .exclude(**{f"{field_name}__isnull": True})
                    .values("pk", field_name)
                )

                for row in rows:
                    pk = row["pk"]
                    old_name = row[field_name]
                    if not old_name:
                        continue

                    # Skip rows already stored in the DB-backed format
                    if old_name.startswith("ldp_core.filedata/"):
                        total_skip += 1
                        continue

                    disk_path = os.path.join(media_dir, old_name)
                    if not os.path.exists(disk_path):
                        self.stdout.write(
                            self.style.WARNING(f"    MISSING [{pk}]: {disk_path}")
                        )
                        total_missing += 1
                        continue

                    try:
                        with open(disk_path, "rb") as f:
                            raw = f.read()

                        filename = os.path.basename(old_name)

                        # Detect MIME type from the file extension so that
                        # db_file_storage stores it correctly (it reads
                        # content.content_type at save time).
                        mime_type, _ = mimetypes.guess_type(filename)
                        if not mime_type:
                            mime_type = "application/octet-stream"

                        content = ContentFile(raw)
                        content.content_type = mime_type  # picked up by db_file_storage _save()

                        # Build a fresh FieldFile pointing to our model instance.
                        # We instantiate without going through __init__ to avoid
                        # any signal/logic side-effects.
                        instance = Model.__new__(Model)
                        instance.pk = pk
                        field = Model._meta.get_field(field_name)
                        field_file = field.attr_class(instance, field, None)

                        # Save through the db_file_storage backend; upload_to on
                        # the field is 'ldp_core.filedata/content/mimetype/filename'
                        # so the backend knows where to persist the binary.
                        field_file.save(filename, content, save=False)
                        new_name = field_file.name

                        # Write only the changed column to avoid triggering
                        # custom save() logic (e.g. School principal history).
                        Model.objects.filter(pk=pk).update(**{field_name: new_name})
                        self.stdout.write(f"    OK [{pk}]: {old_name}")
                        total_ok += 1
                    except Exception as exc:  # noqa: BLE001
                        self.stdout.write(
                            self.style.ERROR(f"    ERROR [{pk}]: {exc}")
                        )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone!  Migrated: {total_ok} | "
                f"Missing on disk: {total_missing} | "
                f"Already migrated: {total_skip}"
            )
        )
