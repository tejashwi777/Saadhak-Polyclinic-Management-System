from django.contrib import admin
from .models import User, Patient, Doctor, Appointment, Prescription, LabReport, Invoice, Message, Schedule
from django.contrib.auth.admin import UserAdmin

admin.site.register(User)
admin.site.register(Patient)
admin.site.register(Doctor)
admin.site.register(Appointment)
admin.site.register(Prescription)
admin.site.register(LabReport)
admin.site.register(Invoice)
admin.site.register(Message)
admin.site.register(Schedule)
