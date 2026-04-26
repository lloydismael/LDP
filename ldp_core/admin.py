from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, School, Activity, Person

admin.site.register(User, UserAdmin)
admin.site.register(School)
admin.site.register(Activity)
admin.site.register(Person)
