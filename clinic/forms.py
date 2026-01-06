# clinic/forms.py
from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth.forms import UserCreationForm
from .models import (
    User, Patient, Doctor, Appointment,
    Prescription, LabReport, Invoice,
    InvoiceItem, Message, Schedule
)
import datetime 
from django.core.exceptions import ValidationError
import re
from django.contrib.auth.password_validation import validate_password

class UserRegistrationForm(forms.ModelForm):
    # Matches the screenshot's labels: Password 1 and Password 2
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="Date of Birth"
    )
    # Changed to 'password' and 'password_confirm' internally for consistency, 
    # but the labels will be shown as 'Password 1' and 'Password 2' based on the HTML.
    # We will use Password and Password_confirm in the form class for the validation logic.
    password = forms.CharField(widget=forms.PasswordInput(), label="Password 1") 
    password_confirm = forms.CharField(widget=forms.PasswordInput(), label="Password 2")

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name'] # first_name and last_name should be optional if not explicitly requested

    # --- 1. Username Validation (No Numbers, Unique Check) ---
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            # Rule: Username cannot contain numbers
            if re.search(r'\d', username):
                raise forms.ValidationError("Username cannot contain numbers.")
            
            # Rule: Uniqueness check
            if User.objects.filter(username__iexact=username).exists() and not self.instance.pk:
                 raise forms.ValidationError("This username is already taken.")
                 
        return username

    # --- 2. Date of Birth Validation (Future Date, Minimum Age) ---
    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            today = datetime.date.today()
            
            # Rule: Future Date Check
            if dob > today:
                raise forms.ValidationError("Date of Birth cannot be in the future.")
            
            # Rule: Minimum Age Check (Patient must be at least 1 year old)
            one_year_ago = today.replace(year=today.year - 1)
            if dob > one_year_ago:
                raise forms.ValidationError("Patient must be at least 1 year old for registration.")
        
        return dob

    # --- 3. Main Clean: Password Match and Strength, Email Uniqueness ---
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        email = cleaned_data.get('email')

        # Rule: Password Match Check
        if password and password_confirm and password != password_confirm:
            # We use add_error here so the error appears at the bottom of the form or near the password field
            self.add_error('password_confirm', "Passwords do not match.") 
        
        # Rule: Password Strength Check (Minimum 8 chars and complexity)
        if password:
            try:
                # This function enforces min length (8) and complexity rules
                validate_password(password, self.instance) 
            except ValidationError as errors:
                self.add_error('password', errors) 
                
        # Rule: Email Uniqueness Check
        if email and User.objects.filter(email__iexact=email).exists() and not self.instance.pk:
             self.add_error('email', "This email address is already in use.")

        return cleaned_data



class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ('phone', 'date_of_birth', 'address')
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }
        
    def clean_phone(self):
        """Ensures phone number is digits-only and a reasonable length."""
        phone = self.cleaned_data.get('phone')
        if phone:
            # Strip spaces, dashes, etc., before checking
            clean_phone = ''.join(filter(str.isdigit, phone))
            
            if len(clean_phone) < 8 or len(clean_phone) > 15:
                raise forms.ValidationError("Phone number must be between 8 and 15 digits long.")
            
            # Save the cleaned version
            return clean_phone
        return phone
    
    # Note: date_of_birth is already validated in UserRegistrationForm, but we can add 
    # a check here if staff use this form separately.
    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob and dob > datetime.date.today():
            raise forms.ValidationError("Date of Birth cannot be in the future.")
        return dob



class DoctorForm(forms.ModelForm):
    class Meta:
        model = Doctor
        fields = ('specialization', 'phone')

    def clean_phone(self):
        """Ensures phone number is digits-only and a reasonable length."""
        phone = self.cleaned_data.get('phone')
        if phone:
            clean_phone = ''.join(filter(str.isdigit, phone))
            if len(clean_phone) < 8 or len(clean_phone) > 15:
                raise forms.ValidationError("Phone number must be between 8 and 15 digits long.")
            return clean_phone
        return phone

    def clean_specialization(self):
        """Ensures specialization is not too short."""
        specialization = self.cleaned_data.get('specialization')
        if specialization and len(specialization) < 3:
            raise forms.ValidationError("Specialization name is too short.")
        return specialization


class DoctorUserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(), required=True)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password']



class AppointmentForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None) 
        super().__init__(*args, **kwargs)
        
        if user and user.role == 'patient':
            try:
                current_patient = Patient.objects.get(user=user)
                
                if 'patient' in self.fields:
                    self.fields['patient'].queryset = Patient.objects.filter(pk=current_patient.pk)
                    
                    if not self.instance.pk:
                        self.initial['patient'] = current_patient.pk
                        
            except Patient.DoesNotExist:
                pass 
            
            # Remove/Hide administrative fields a Patient shouldn't see
            self.fields.pop('patient', None)
            self.fields.pop('status', None) 
            self.fields.pop('payment_status', None) 

    class Meta:
        model = Appointment
        fields = ('patient', 'doctor', 'date', 'time', 'symptoms', 'status', 'payment_status') 
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'time': forms.TimeInput(attrs={'type': 'time'}),
            'symptoms': forms.Textarea(attrs={'rows': 3}), 
        }

    # Custom validation for past date, doctor schedule, and double-booking
    def clean(self):
        cleaned_data = super().clean()
        doctor = cleaned_data.get('doctor')
        date = cleaned_data.get('date')
        time = cleaned_data.get('time')
        
        # --- 1. Past Date Check ---
        if date and date < datetime.date.today():
            self.add_error('date', 'Appointments cannot be booked for a past date.')
            # Do not return here yet, allow other checks to add errors if necessary
        
        # --- 2 & 3. Schedule and Double-Booking Checks ---
        if doctor and date and time:
            
            # 2. Check Schedule Conflict
            try:
                doctor_full_name = doctor.user.get_full_name() or doctor.user.username
                formatted_time = time.strftime( '%I:%M %p')
                # Check if the doctor has an active schedule that covers the requested time slot
                all_schedules_today = Schedule.objects.filter(
                    doctor=doctor,
                    date=date,
                        
                )

                if not all_schedules_today.exists():
                   self.add_error(
                       'doctor',
                       f"Dr. {doctor_full_name} has no schedule set for {date.strftime('%B %d, %Y')}. Please select a different date or doctor."
                   )
                else:
                 is_available = all_schedules_today.filter(
                    start_time__lte=time,
                    end_time__gt=time
                ).exists()

                if not is_available:
                
                    self.add_error(
                        'doctor', 
                        f"Dr. {doctor_full_name} is not scheduled to work at {time.strftime('%I:%M %p')} on this date."
                    )
            except Exception as e:
                 # Should only happen if the Schedule model is missing, useful for debugging
                 print(f"Schedule availability check failed unexpectedly: {e}") 
                 self.add_error(
                        'doctor', 
                        "An error occured while checking doctor availability. Please try again"
                 )
            # 3. Check Double Booking Conflict
            existing_appointments = Appointment.objects.filter(
                doctor=doctor,
                date=date,
                time=time,
                # Exclude the current appointment if we are editing
            ).exclude(pk=self.instance.pk)

            
            if existing_appointments.exists():
                self.add_error(
                    'time', 
                    f"Dr. {doctor.user.get_full_name()} is already booked at this exact time ({time.strftime('%I:%M %p')}) on {date.strftime('%B %d, %Y')}."
                )

        return cleaned_data


class PrescriptionForm(forms.ModelForm):
    class Meta:
        model = Prescription
        fields = ('medicine', 'instructions')
        
    def clean_medicine(self):
        medicine = self.cleaned_data.get('medicine')
        if not medicine or len(medicine.strip()) < 2:
            raise forms.ValidationError("Medicine name is required.")
        return medicine

    def clean_instructions(self):
        instructions = self.cleaned_data.get('instructions')
        if not instructions or len(instructions.strip()) < 10:
            raise forms.ValidationError("Instructions must be detailed (at least 10 characters).")
        return instructions



class LabReportForm(forms.ModelForm):
    class Meta:
        model = LabReport
        fields = ('patient', 'doctor', 'report_file')

    def clean_report_file(self):
        """Checks file size and type (assuming you only accept PDFs or standard images)."""
        report_file = self.cleaned_data.get('report_file')
        if report_file:
            # Check file size (e.g., limit to 5MB)
            if report_file.size > 5 * 1024 * 1024: 
                raise forms.ValidationError("The report file must be less than 5MB.")
            
            # Check file extension/type (basic)
            name = report_file.name.lower()
            if not name.endswith(('.pdf', '.jpg', '.jpeg', '.png')):
                raise forms.ValidationError("Only PDF and image files are accepted.")
        return report_file



class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['patient', 'appointment']  # ONLY actual fields in model

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Display patient name clearly in the select dropdown
        self.fields['patient'].queryset = Patient.objects.all()
        self.fields['patient'].label_from_instance = lambda obj: f"{obj.user.first_name} {obj.user.last_name}" if obj.user.first_name else obj.user.username

    def clean(self):
        cleaned_data = super().clean()
        patient = cleaned_data.get('patient')
        appointment = cleaned_data.get('appointment')
        
        # Validation 1: Ensure Appointment belongs to Patient (if both are provided)
        if patient and appointment:
            if appointment.patient != patient:
                # Raise an error if the selected appointment is not for the selected patient
                raise forms.ValidationError(
                    "The selected appointment does not belong to the selected patient."
                )
        
        # Validation 2: Ensure an invoice isn't already created for this appointment (Unique Bill Check)
        if appointment and not self.instance.pk:
            if Invoice.objects.filter(appointment=appointment).exists():
                self.add_error(
                    'appointment',
                    "An invoice for this specific appointment has already been created."
                )

        return cleaned_data


class InvoiceItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = ('description', 'amount')

    def clean_description(self):
        description = self.cleaned_data.get('description')
        if not description or len(description.strip()) < 3:
            raise forms.ValidationError("Item description is required and must be detailed.")
        return description

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        # Validation: Check for positive amount
        if amount is not None and amount <= 0:
            raise forms.ValidationError("Invoice amount must be a positive value.")
        return amount



InvoiceItemFormSet = inlineformset_factory(
    Invoice,
    InvoiceItem,
    fields=('description', 'amount'),
    extra=1,
    can_delete=True
)



class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ('receiver', 'subject', 'content')

    def clean_subject(self):
        subject = self.cleaned_data.get('subject')
        if not subject or len(subject.strip()) < 5:
            raise forms.ValidationError("Subject must be at least 5 characters long.")
        return subject
        
    def clean_content(self):
        content = self.cleaned_data.get('content')
        if not content or len(content.strip()) < 10:
            raise forms.ValidationError("Message content must be at least 10 characters long.")
        return content



class ScheduleForm(forms.ModelForm):
    class Meta:
        model = Schedule
        fields = ('date', 'start_time', 'end_time')
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        date = cleaned_data.get('date')
        
        # Time Constraint Check
        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError(
                "End time must be after the start time for the schedule."
            )
        
        # Date Constraint Check (Ensure Schedule date is not in the past)
        if date and date < datetime.date.today():
             raise forms.ValidationError(
                "The schedule date cannot be in the past."
            )

        return cleaned_data

class PatientProfileForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ['phone', 'date_of_birth', 'address']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }        

class AdminProfileForm(forms.ModelForm):
    class Meta:
        model = User  # Uses your custom User model
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }        