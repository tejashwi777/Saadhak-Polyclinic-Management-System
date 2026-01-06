# clinic/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('doctor', 'Doctor'),
        ('receptionist', 'Receptionist'),
        ('patient', 'Patient'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='patient')

    def __str__(self):
        return self.username


class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    specialization = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)

    def __str__(self):
        return self.user.username
# clinic/models.py

class Patient(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # Add null=True and blank=True to allow registration without these fields
    phone = models.CharField(max_length=15, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True) 
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.user.username

    def __str__(self):
        full_name = f"{self.user.first_name} {self.user.last_name}".strip()
        return full_name if full_name else self.user.username
class Appointment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    PAYMENT_CHOICES = (
        ('unpaid', 'Unpaid'),
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('waived', 'Waived'),
    )
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    date = models.DateField()
    time = models.TimeField()
    symptoms = models.TextField(
        blank=True, 
        null=True, 
        help_text="Patient-reported symptoms or reason for visit."
    ) 
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(
        max_length=20, 
        choices=PAYMENT_CHOICES, 
        default='unpaid'
    ) 

    def __str__(self):
        return f"{self.patient.user.username} with {self.doctor.user.username} on {self.date}"

    # --- CRITICAL MODEL VALIDATION ---
    def clean(self):
        # Validation 1: Status/Payment consistency check (e.g., cannot be paid if cancelled)
        if self.status == 'cancelled' and self.payment_status == 'paid':
             raise ValidationError(
                "A cancelled appointment cannot have a 'Paid' payment status. Set to 'Unpaid' or 'Waived'."
            )
            
    class Meta:
        # CRITICAL: Ensures no two appointments share the exact same doctor, date, and time.
        unique_together = (('doctor', 'date', 'time'),) 
        ordering = ['date', 'time']

class Prescription(models.Model):
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE)
    medicine = models.TextField()
    instructions = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Prescription for {self.appointment.patient.user.username}"

class LabReport(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, blank=True, null=True)
    report_file = models.FileField(upload_to='lab_reports/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Lab Report for {self.patient.user.username}"

class Invoice(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)

    def get_total_amount(self):
        return sum(item.amount for item in self.items.all())

    def __str__(self):
        return f"Invoice #{self.id} - {self.patient}"

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(
        Invoice,
        related_name="items",
        on_delete=models.CASCADE
    )
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.description

class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    subject = models.CharField(max_length=200)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message from {self.sender.username} to {self.receiver.username}"

class Schedule(models.Model):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return f"{self.doctor.user.username} on {self.date} from {self.start_time} to {self.end_time}"
        
    # --- CRITICAL MODEL VALIDATION ---
    def clean(self):
        # Validation 1: Time order check
        if self.start_time >= self.end_time:
            raise ValidationError("Schedule end time must be strictly after start time.")
        
        # Validation 2: Schedule Overlap Check (Database Level Enforcement)
        # Look for existing schedules for the same doctor on the same day
        overlap = Schedule.objects.filter(
            doctor=self.doctor,
            date=self.date,
        ).exclude(pk=self.pk) # Exclude the current schedule instance if editing
        
        # Overlap criteria: (Existing Start < New End) AND (Existing End > New Start)
        overlapping_schedules = overlap.filter(
            start_time__lt=self.end_time,
            end_time__gt=self.start_time
        )
        
        if overlapping_schedules.exists():
             raise ValidationError("This schedule overlaps with an existing schedule for the doctor on this date.")
        
    class Meta:
        # Optional, but useful: ensures no two schedules are identical (though clean() handles overlap better)
        unique_together = ('doctor', 'date', 'start_time', 'end_time')
        ordering = ['date', 'start_time']

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.message

class Bill(models.Model):
    PAYMENT_STATUS = (
        ('paid', 'Paid'),
        ('unpaid', 'Unpaid'),
    )

    patient = models.ForeignKey('Patient', on_delete=models.CASCADE)
    appointment = models.ForeignKey('Appointment', on_delete=models.SET_NULL, null=True, blank=True)

    consultation_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    lab_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    medicine_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    total_amount = models.DecimalField(max_digits=8, decimal_places=2)
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS, default='unpaid')

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Bill #{self.id} - {self.patient}"