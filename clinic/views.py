# clinic/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q
from django.core.mail import send_mail
from django.http import HttpResponse
from django.conf import settings
from django.urls import reverse 
import datetime 
import json
from .models import Invoice
from django.template.loader import render_to_string 
from .forms import UserRegistrationForm, PatientProfileForm, AdminProfileForm
from django.http import JsonResponse

try:
    from .forms import (
        DoctorUserForm, DoctorForm, PatientForm, UserRegistrationForm, 
        AppointmentForm, ScheduleForm, PrescriptionForm, LabReportForm, 
        MessageForm, InvoiceForm, InvoiceItemForm
    )
    from .models import (
        User, Doctor, Patient, Appointment, Prescription, LabReport, 
        Schedule, Message, Notification, Invoice, InvoiceItem, Bill 
    )
except ImportError:
    # Basic fallback if custom models/forms are not yet defined
    pass 

from django.forms import modelformset_factory
from django.core.serializers import serialize


# ----------------------------------------------------
# 1. MAIN PUBLIC/USER LOGIN VIEW (Doctor, Receptionist, Patient) - CORRECTED
# ----------------------------------------------------
def user_login(request):
    """Handles login for Doctor, Receptionist, and Patient (the default public login)."""
    # If already logged in, redirect according to role
    if request.user.is_authenticated:
        return _redirect_to_dashboard(request.user)

    # Handle POST login
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user:
            # Check if an admin is trying to log in here
            if user.role == 'admin':
                messages.error(request, 'Admins must log in via the dedicated Admin Login page.')
                # This ensures ONLY the admin hits this redirect, and other users skip it.
                return redirect('admin_login') # Using URL name is better practice

            # If the user is NOT an admin (i.e., Doctor, Receptionist, Patient):
            login(request, user)
            return _redirect_to_dashboard(user)
        else:
            messages.error(request, 'Invalid username or password')

    # Uses the main 'login.html' template
    return render(request, 'clinic/login.html')


# ----------------------------------------------------
# 2. ADMIN-ONLY LOGIN VIEW
# ----------------------------------------------------
def admin_login(request):
    """Handles login ONLY for the Admin."""
    if request.user.is_authenticated:
        return _redirect_to_dashboard(request.user)

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user:
            # Enforce ADMIN role restriction for this page
            if user.role == 'admin':
                login(request, user)
                return _redirect_to_dashboard(user)
            else:
                messages.error(request, 'Access Denied: Only Administrators can use this login page.')
        else:
            messages.error(request, 'Invalid credentials.')

    # Admin uses a separate template
    return render(request, 'clinic/admin_login.html')


# Helper function (Keep this the same)
def _redirect_to_dashboard(user):
    """Redirects user based on their role."""
    if user.role == 'admin':
        return redirect('admin_dashboard')
    elif user.role == 'doctor':
        return redirect('doctor_dashboard')
    elif user.role == 'receptionist':
        return redirect('receptionist_dashboard')
    else:
        return redirect('patient_dashboard')




# ----------------------------------------------------
# 🌟 NEW: PUBLIC PATIENT REGISTRATION VIEW
# ----------------------------------------------------

def register_user(request):
    """Handles the public-facing patient registration."""
    if request.user.is_authenticated:
        return redirect('patient_dashboard')

    if request.method == 'POST':
        user_form = UserRegistrationForm(request.POST)
        
        if user_form.is_valid():
            # 1. Create the User object
            user = user_form.save(commit=False)
            user.set_password(user_form.cleaned_data['password'])
            user.role = 'patient'
            user.is_active = True
            user.save()

            # 2. Get the DOB from the form data
            dob = user_form.cleaned_data.get('date_of_birth') #

            # 3. Create the linked Patient model instance with the DOB
            # This fixes the IntegrityError!
            Patient.objects.create(user=user, date_of_birth=dob) #
            
            messages.success(request, 'Registration successful! Please log in.')
            return redirect('user_login')
        
        else:
            messages.error(request, 'Error during registration. Please check the fields.')
            
    else:
        user_form = UserRegistrationForm()

    context = {
        'user_form': user_form,
        'title': 'Sign Up', # Updated title as per your preference
    }
    return render(request, 'clinic/register.html', context)


@login_required
def user_logout(request):
    logout(request)
    return redirect('login')

# ---------- DASHBOARDS ----------

@login_required
def admin_dashboard(request):
    if request.user.role != 'admin':
        messages.error(request, 'Unauthorized access')
        return redirect('login')
    
    recent_appointments = Appointment.objects.all().order_by('-date', '-time')[:10]

    context = {
        "total_users": User.objects.count(),
        "total_patients": Patient.objects.count(),
        "total_doctors": Doctor.objects.count(),
        "total_appointments": Appointment.objects.count(),
        "recent_appointments": recent_appointments,
    }
    return render(request, "clinic/admin_dashboard.html", context)

# In clinic/views.py

@login_required
def doctor_dashboard(request):
    if request.user.role != 'doctor':
        messages.error(request, 'Unauthorized access')
        return redirect('login')

    doctor = get_object_or_404(Doctor, user=request.user)

    upcoming_appointments = Appointment.objects.filter(
        doctor=doctor
    ).filter(
        Q(status__iexact='pending') | Q(date__gte=datetime.date.today())
    ).order_by('date', 'time')

    appointments_count = upcoming_appointments.count()
    prescriptions_count = Prescription.objects.filter(appointment__doctor=doctor).count()
    labreports_count = LabReport.objects.filter(doctor=doctor).count()
    
    # 🌟 NEW LOGIC: Fetch unread notifications for the doctor
    unread_notifications = Notification.objects.filter(
        user=request.user, 
        is_read=False
    ).count()

    context = {
        'upcoming_appointments': upcoming_appointments,
        'appointments_count': appointments_count,
        'prescriptions_count': prescriptions_count,
        'labreports_count': labreports_count,
        'unread_notifications': unread_notifications, # Add this to the context
    }

    return render(request, 'clinic/doctor_dashboard.html', context)
@login_required
def receptionist_dashboard(request):
    if request.user.role != 'receptionist':
        messages.error(request, 'Unauthorized access')
        return redirect('login')
        
    total_patients = Patient.objects.count()
    total_appointments = Appointment.objects.count()
    invoices = Invoice.objects.all()

    today = datetime.date.today()
    upcoming_appointments = Appointment.objects.filter(
        Q(status__iexact='pending') | 
        Q(date__gte=today)
    ).order_by('date', 'time')
    
    context = {
        'total_patients': total_patients,
        'total_appointments': total_appointments,
        'upcoming_appointments': upcoming_appointments,
        'invoices': invoices, 
    }
    return render(request, 'clinic/receptionist_dashboard.html', context)

@login_required
def patient_dashboard(request):
    if request.user.role != 'patient':
        messages.error(request, 'Unauthorized access')
        return redirect('login')

    # FIX: Use get_or_create instead of get_object_or_404
    # This ensures a Patient record exists for the User
    patient, created = Patient.objects.get_or_create(user=request.user)

    appointments = Appointment.objects.filter(patient=patient).order_by('-date', '-time')
    prescriptions = Prescription.objects.filter(appointment__patient=patient)
    labreports = LabReport.objects.filter(patient=patient)
    
    context = {
        'patient': patient, # Good to include this in context
        'upcoming_appointments': appointments.filter(
            Q(status='pending') | Q(date__gte=datetime.date.today())
        ).order_by('date', 'time')[:5],
        'prescriptions_count': prescriptions.count(),
        'labreports_count': labreports.count(),
    }
    return render(request, 'clinic/patient_dashboard.html', context)

# ---------- DOCTOR CRUD ----------

@login_required
def doctor_list(request):
    if request.user.role != 'admin':
        messages.error(request, 'Unauthorized access')
        return redirect('login')
    doctors = Doctor.objects.all()
    return render(request, 'clinic/doctor_list.html', {'doctors': doctors})

@login_required
def doctor_register(request):
    if request.user.role != 'admin':
        messages.error(request, 'Unauthorized access')
        return redirect('login')
    if request.method == 'POST':
        user_form = DoctorUserForm(request.POST)
        doctor_form = DoctorForm(request.POST)
        if user_form.is_valid() and doctor_form.is_valid():
            user = user_form.save(commit=False)
            user.role = 'doctor'
            pwd = user_form.cleaned_data.get('password')
            user.set_password(pwd)
            user.save()
            doctor = doctor_form.save(commit=False)
            doctor.user = user
            doctor.save()
            messages.success(request, 'Doctor registered successfully')
            return redirect('doctor_list')
    else:
        user_form = DoctorUserForm()
        doctor_form = DoctorForm()
    return render(request, 'clinic/doctor_register.html', {'user_form': user_form, 'doctor_form': doctor_form})


# ---------- PATIENT CRUD ----------

@login_required
def patient_list(request):
    if request.user.role not in ['receptionist', 'admin']:
        messages.error(request, 'Unauthorized access')
        return redirect('login')
    patients = Patient.objects.all()
    return render(request, 'clinic/patient_list.html', {'patients': patients})

@login_required
def patient_register(request):
    if request.user.role != 'receptionist':
        messages.error(request, 'Unauthorized access')
        return redirect('login')

    if request.method == 'POST':
        user_form = UserRegistrationForm(request.POST)
        patient_form = PatientForm(request.POST)

        if user_form.is_valid() and patient_form.is_valid():
            user = user_form.save(commit=False)
            user.role = 'patient'
            pwd = user_form.cleaned_data.get('password')
            user.set_password(pwd)
            user.save()

            patient = patient_form.save(commit=False)
            patient.user = user
            patient.save()

            messages.success(request, 'Patient registered successfully')
            return redirect('patient_list')
    else:
        user_form = UserRegistrationForm()
        patient_form = PatientForm()

    return render(request, 'clinic/patient_register.html', {
        'user_form': user_form,
        'patient_form': patient_form
    })

@login_required
def patient_profile(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)

    if request.user.role not in ['receptionist', 'patient'] and request.user != patient.user:
        messages.error(request, 'Unauthorized access')
        return redirect('login')

    if request.method == 'POST':
        # Assuming PatientForm can update user data (e.g., first/last name) or is linked to User form
        form = PatientForm(request.POST, instance=patient)
        if form.is_valid():
            form.save()
            messages.success(request, 'Patient profile updated')
            return redirect('patient_profile', patient_id=patient.id)
    else:
        form = PatientForm(instance=patient)

    return render(
        request,
        'clinic/patient_profile.html',
        {
            'form': form,
            'patient': patient
        }
    )

# --- **FIX: NEWLY ADDED DETAIL VIEWS** ---
# These functions were missing and caused the 'NoReverseMatch' error.

# --- clinic/views.py ---

@login_required
def patient_detail(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)

    # Permission check: Admin/Receptionist, Patient self, or Doctor who has treated them
    is_authorized = (
        request.user.role in ['receptionist', 'admin'] or 
        request.user == patient.user or
        (request.user.role == 'doctor' and Appointment.objects.filter(doctor__user=request.user, patient=patient).exists())
    )
    
    if not is_authorized:
        messages.error(request, 'Unauthorized access to patient details.')
        return redirect('login') 

    # 1. Fetch Appointments
    appointments = Appointment.objects.filter(patient=patient).order_by('-date', '-time')
    
    try:
        # 2. Fetch Prescriptions (Ordered by appointment date)
        prescriptions = Prescription.objects.filter(appointment__patient=patient).order_by('-appointment__date')
        
        # 3. Fetch Lab Reports (Ordered by the correct field name 'uploaded_at')
        labreports = LabReport.objects.filter(patient=patient).order_by('-uploaded_at')
        
    except NameError:
        # Fallback if models are not correctly imported/defined
        prescriptions = [] 
        labreports = []

    context = {
        'patient': patient,
        'appointments': appointments,
        'prescriptions': prescriptions,
        'lab_reports': labreports, # <-- This key is used in the template
    }
    return render(request, 'clinic/patient_detail.html', context)
@login_required
def doctor_detail(request, doctor_id):
    doctor = get_object_or_404(Doctor, id=doctor_id)

    # Permission check: Admin/Receptionist, Doctor self, or Patient treated by them
    is_authorized = (
        request.user.role in ['receptionist', 'admin', 'doctor'] or 
        (request.user.role == 'patient' and Appointment.objects.filter(patient__user=request.user, doctor=doctor).exists())
    )

    if not is_authorized:
        messages.error(request, 'Unauthorized access to doctor details.')
        return redirect('login') 

    appointments = Appointment.objects.filter(doctor=doctor).order_by('-date', '-time')
    
    try:
        schedules = Schedule.objects.filter(doctor=doctor).order_by('date', 'start_time')
    except NameError:
        schedules = [] # Fallback if model is not correctly imported

    context = {
        'doctor': doctor,
        'appointments': appointments,
        'schedules': schedules,
    }
    return render(request, 'clinic/doctor_detail.html', context)

# ---------- APPOINTMENTS ----------


# In clinic/views.py, replace the entire book_appointment function with this:
@login_required
def book_appointment(request):
    is_patient_role = request.user.role == 'patient'
    
    if request.method == 'POST':
        # CRITICAL FIX: Pass the user to the form on POST as well
        form = AppointmentForm(request.POST, user=request.user) 
        
        if form.is_valid():
            appointment = form.save(commit=False)
            
            # Auto-assign patient if booking as a patient
            if is_patient_role and not appointment.patient_id:
                try:
                    appointment.patient = Patient.objects.get(user=request.user)
                except Patient.DoesNotExist:
                    messages.error(request, "Patient profile not found. Cannot complete booking.")
                    return redirect('patient_dashboard')
            
            appointment.save()
            
            # --- Notification Creation Logic (FIXED & IMPLEMENTED) ---
            patient_user = appointment.patient.user
            patient_name = f"{patient_user.first_name} {patient_user.last_name}".strip()
            doctor_user = appointment.doctor.user
            doctor_name = appointment.doctor.user.get_full_name() or appointment.doctor.user.username
            
            notification_message = (
                f"New Appointment: Patient {patient_name} booked for {appointment.date} at {appointment.time}. "
                f"Symptoms: {appointment.symptoms or 'Not provided'}."
            )
            
            try:
                # 🌟 FIX: Create the Notification for the Doctor
                Notification.objects.create(
                    user=doctor_user, 
                    message=notification_message,
                )
                print(f"Notification successfully created for Doctor: {doctor_user.username}")
            except Exception as e:
                messages.warning(request, "Appointment booked, but failed to notify the Doctor.")
                print(f"Error creating notification: {e}")
            
            # --- End Notification Logic ---
            
            messages.success(request, f'Appointment booked successfully with Dr. {doctor_name}.')
            return redirect('appointment_list')
    else:
        # Pass the user to the form on initial GET request
        form = AppointmentForm(user=request.user)
            
    # ------------------ RENDERING ------------------
    context = {
        'form': form,
        'is_patient_role': is_patient_role,
    }
    return render(request, 'clinic/appointment_create.html', context)

# In clinic/views.py

@login_required
def appointment_list(request):
    # This view focuses on the data needed for the list/table below the calendar.
    appointments_query = Appointment.objects.all().order_by('date', 'time')
    
    if request.user.role == 'doctor':
        doctor = get_object_or_404(Doctor, user=request.user)
        appointments = appointments_query.filter(doctor=doctor)
    elif request.user.role == 'patient':
        patient = get_object_or_404(Patient, user=request.user)
        appointments = appointments_query.filter(patient=patient)
    else:
        appointments = appointments_query 
        
    # NEW: Get the rich combined event data for the calendar
    calendar_events = get_calendar_events(request)
    
    context = {
        'appointments': appointments,
        # Pass the rich JSON data to the template
        
    }
    return render(request, 'clinic/appointment_list.html', context)
def appointment_detail(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk)
    return render(request, 'clinic/appointment_detail.html', {'appointment': appointment})

def delete_appointment(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk)
    Invoice.objects.filter(appointment=appointment).delete() 
    appointment.delete()
    messages.success(request, "Appointment and related invoices deleted successfully.")
    return redirect('appointment_list')

# In clinic/views.py



# ... other views ...

def get_calendar_events(request):
    """
    Returns a JSON list of all Appointments (foreground events) and 
    Schedules (background events for availability) for FullCalendar.
    """
    
    # 1. Fetch Schedule Events (Background)
    schedule_events = []
    schedules = Schedule.objects.all()
    for sch in schedules:
        # FullCalendar requires 'start' and 'end' for background events
        schedule_events.append({
            'start': f"{sch.date}T{sch.start_time}",
            'end': f"{sch.date}T{sch.end_time}",
            'display': 'background', # CRITICAL: Makes it a background event
            'color': '#d1e7dd',      # Light green color for availability
            'title': f"Available: {sch.doctor.user.get_full_name()}"
        })

    # The rest of the Appointment data will be handled by the existing template context 
    # OR you can merge everything here if you prefer a single API call (more complex).
    
    # For now, let's just return the schedule data to be fetched by the AJAX call.
    return JsonResponse(schedule_events, safe=False)
@login_required
def update_appointment_status(request, pk, status):
    # ... (Permission check code remains the same)
    
    appointment = get_object_or_404(Appointment, pk=pk)

    if request.user.role == 'doctor' and appointment.doctor.user != request.user:
        messages.error(request, 'You can only manage your own appointments.')
        return redirect('appointment_detail', pk=pk)

    
    valid_statuses = ['confirmed', 'completed', 'cancelled', 'pending'] # <<< ADDED 'Pending'
    
    if status in valid_statuses:
        # NOTE: Status received from URL is 'status', so we use it directly.
        appointment.status = status 
        appointment.save()
        messages.success(request, f'Appointment status updated to {status}.')
    else:
        messages.error(request, f'Invalid status provided: {status}. Valid statuses are {", ".join(valid_statuses)}.')
        
    return redirect('appointment_detail', pk=pk)

def appointment_dashboard(request):
    appointments = Appointment.objects.all().order_by('-date', '-time')

    patient_query = request.GET.get('patient')
    doctor_query = request.GET.get('doctor')
    status_query = request.GET.get('status')

    if patient_query:
        appointments = appointments.filter(
            Q(patient__user__first_name__icontains=patient_query) |
            Q(patient__user__last_name__icontains=patient_query)
        )
    if doctor_query:
        appointments = appointments.filter(
            Q(doctor__user__first_name__icontains=doctor_query) |
            Q(doctor__user__last_name__icontains=doctor_query)
        )
    if status_query:
        appointments = appointments.filter(status=status_query)

    return render(request, 'clinic/appointment_dashboard.html', {'appointments': appointments})


# ---------- DOCTOR SCHEDULE ----------

@login_required
def doctor_schedule(request):
    if request.user.role != 'doctor':
        messages.error(request, 'Unauthorized access')
        return redirect('login')
    doctor = get_object_or_404(Doctor, user=request.user)
    if request.method == 'POST':
        form = ScheduleForm(request.POST)
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.doctor = doctor
            schedule.save()
            messages.success(request, 'Schedule updated successfully')
            return redirect('doctor_schedule')
    else:
        form = ScheduleForm()
    schedules = Schedule.objects.filter(doctor=doctor).order_by('date', 'start_time')
    return render(request, 'clinic/doctor_schedule.html', {'form': form, 'schedules': schedules})

# ---------- PRESCRIPTIONS ----------

@login_required
@user_passes_test(lambda u: u.role == 'doctor')
def prescription_create(request, appointment_pk):
    """Allows a Doctor to create a prescription linked to an appointment."""
    
    appointment = get_object_or_404(Appointment, pk=appointment_pk)
    doctor = request.user.doctor # Assuming the Doctor profile is linked

    # Security Check: Ensure the doctor is associated with this appointment
    if appointment.doctor != doctor:
        messages.error(request, "You are not authorized to write a prescription for this appointment.")
        return redirect('doctor_dashboard') # Redirect to safe page

    # Optional: Check if a prescription already exists for this appointment
    if Prescription.objects.filter(appointment=appointment).exists():
         messages.info(request, "A prescription for this appointment already exists. You can edit it instead.")
         # You would redirect to an edit view here if you had one.
         # For now, we allow creation, which will likely raise a database error if you enforce uniqueness.
         
    if request.method == 'POST':
        form = PrescriptionForm(request.POST)
        if form.is_valid():
            prescription = form.save(commit=False)
            prescription.appointment = appointment
            prescription.save()
            
            # Update appointment status to 'completed' after prescribing
            appointment.status = 'completed'
            appointment.save()
            
            messages.success(request, f"Prescription recorded and Appointment #{appointment.pk} marked as completed.")
            return redirect('appointment_detail', pk=appointment.pk)
        
    else:
        form = PrescriptionForm()

    context = {
        'form': form,
        'appointment': appointment,
    }
    return render(request, 'clinic/prescription_create.html', context)

# In clinic/views.py

@login_required
def prescription_list(request):
    """
    Lists prescriptions based on the user's role:
    - Doctor: Only prescriptions they have written.
    - Patient: Only prescriptions written for them.
    - Staff/Admin: All prescriptions.
    """
    
    if request.user.role == 'doctor':
        # Filter prescriptions where the doctor field in the appointment matches the user
        prescriptions = Prescription.objects.filter(
            appointment__doctor__user=request.user
        ).select_related('appointment__patient__user', 'appointment__doctor__user').order_by('-appointment__date')
        
    elif request.user.role == 'patient':
        # Filter prescriptions where the patient field in the appointment matches the user
        prescriptions = Prescription.objects.filter(
            appointment__patient__user=request.user
        ).select_related('appointment__doctor__user').order_by('-appointment__date')
        
    elif request.user.role in ['admin', 'receptionist']:
        # Staff see all prescriptions
        prescriptions = Prescription.objects.all().select_related(
            'appointment__patient__user', 
            'appointment__doctor__user'
        ).order_by('-appointment__date')
        
    else:
        prescriptions = Prescription.objects.none() # Fallback

    context = {
        'prescriptions': prescriptions,
        'user_role': request.user.role
    }
    return render(request, 'clinic/prescription_list.html', context)

# ---------- LAB REPORTS ----------

@login_required
def labreport_upload(request):
    if request.user.role != 'doctor':
        messages.error(request, 'Unauthorized access')
        return redirect('login')
    if request.method == 'POST':
        form = LabReportForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Lab report uploaded successfully')
            return redirect('labreport_list')
    else:
        form = LabReportForm()
    return render(request, 'clinic/labreport_upload.html', {'form': form})

@login_required
def labreport_list(request):
    if request.user.role == 'doctor':
        doctor = get_object_or_404(Doctor, user=request.user)
        reports = LabReport.objects.filter(doctor=doctor)
    elif request.user.role == 'patient':
        patient = get_object_or_404(Patient, user=request.user)
        reports = LabReport.objects.filter(patient=patient)
    else:
        reports = LabReport.objects.all()
    return render(request, 'clinic/labreport_list.html', {'reports': reports})


# ---------- MESSAGING & NOTIFICATIONS ----------

@login_required
def message_send(request):
    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.sender = request.user
            message.save()
            messages.success(request, 'Message sent successfully')
            return redirect('message_list')
    else:
        form = MessageForm()
    return render(request, 'clinic/message_send.html', {'form': form})

@login_required
def message_list(request):
    received = Message.objects.filter(receiver=request.user).order_by('-timestamp')
    sent = Message.objects.filter(sender=request.user).order_by('-timestamp')
    return render(request, 'clinic/message_list.html', {'received': received, 'sent': sent})

# In clinic/views.py, replace the entire notifications_list function with this:
@login_required
def notifications_list(request):
    # This correctly filters only UNREAD notifications for the logged-in user
    notifications = Notification.objects.filter(
        user=request.user,  
        is_read=False       
    ).order_by('-created_at') 

    return render(
        request,
        'clinic/notifications.html', # Template name confirmed as notifications.html
        {'notifications': notifications}
    )

@login_required
def receptionist_notifications(request):
    if request.user.role != 'receptionist':
        messages.error(request, 'Unauthorized access')
        return redirect('login')

    notifications = Message.objects.filter(receiver=request.user).order_by('-timestamp')

    return render(
        request,
        'clinic/notifications.html',
        {'notifications': notifications}
    )


# ---------- BILLING & INVOICES ----------

@login_required
def billing_list(request):
    bills = Bill.objects.all().order_by('-created_at')
    return render(request, 'billing/billing_list.html', {'bills': bills})


@login_required
def billing_create(request):
    patients = Patient.objects.all()
    appointments = Appointment.objects.all()

    if request.method == 'POST':
        patient_id = request.POST.get('patient')
        appointment_id = request.POST.get('appointment')

        consultation_fee = float(request.POST.get('consultation_fee', 0))
        lab_fee = float(request.POST.get('lab_fee', 0))
        medicine_fee = float(request.POST.get('medicine_fee', 0))

        total = consultation_fee + lab_fee + medicine_fee

        Bill.objects.create(
            patient_id=patient_id,
            appointment_id=appointment_id if appointment_id else None,
            consultation_fee=consultation_fee,
            lab_fee=lab_fee,
            medicine_fee=medicine_fee,
            total_amount=total
        )

        return redirect('billing_list')

    return render(request, 'billing/billing_create.html', {
        'patients': patients,
        'appointments': appointments
    })

# In clinic/views.py

def create_invoice(request):
    """Handles creation of an invoice and its associated items."""
    
    InvoiceItemFormSet = modelformset_factory(
        InvoiceItem,
        fields=('description', 'amount'),
        extra=1,
        can_delete=True
    )

    if request.method == 'POST':
        invoice_form = InvoiceForm(request.POST)
        formset = InvoiceItemFormSet(request.POST, queryset=InvoiceItem.objects.none())
        
        if invoice_form.is_valid() and formset.is_valid():
            invoice = invoice_form.save(commit=False)
            
            # --- CRITICAL: Server-Side Total Calculation and Validation ---
            total_amount = 0
            has_items = False
            
            # 1. Calculate Total and ensure at least one valid item exists
            for form in formset:
                if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                    item_amount = form.cleaned_data.get('amount')
                    if item_amount:
                        total_amount += item_amount
                        has_items = True

            if not has_items:
                messages.error(request, 'Invoice must contain at least one line item with a positive amount.')
                # Re-render the form with errors
                invoice_form = InvoiceForm(request.POST) 
                formset = InvoiceItemFormSet(request.POST)
                return render(request, 'clinic/create_invoice.html', {
                    'invoice_form': invoice_form,
                    'formset': formset
                })
            
            # 2. Save the Invoice with the calculated total
            invoice.total_amount = total_amount # Assuming your Invoice model has a total_amount field
            invoice.save()
            
            # 3. Save Invoice Items
            for form in formset:
                if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                    item = form.save(commit=False)
                    item.invoice = invoice
                    item.save()
            
            messages.success(request, f'Invoice #{invoice.pk} created successfully with a total of ${total_amount:.2f}!')
            return redirect('invoice_detail', pk=invoice.pk) # Redirect to the new invoice detail page
        else:
            messages.error(request, 'Error creating invoice. Please correct the highlighted errors.')
    else:
        invoice_form = InvoiceForm()
        formset = InvoiceItemFormSet(queryset=InvoiceItem.objects.none())
        
    context = {
        'invoice_form': invoice_form,
        'formset': formset
    }
    return render(request, 'clinic/create_invoice.html', context)


def invoice_list(request):
    invoices = Invoice.objects.all().order_by('-date_created')
    
    notifications = None
    if request.user.is_authenticated and request.user.role in ['receptionist', 'doctor']:
        try:
            notifications = Notification.objects.filter(user=request.user, is_read=False).count()
        except NameError:
             pass 
    
    context = {
        'invoices': invoices,
        'notifications': notifications,
    }
    
    return render(request, 'clinic/invoice_list.html', context)

def invoice_detail(request, pk):
    # Fetch the invoice using the ID from the URL
    invoice = get_object_or_404(Invoice, pk=pk)
    # The HTML will now handle invoice.items.all automatically
    return render(request, 'clinic/invoice_detail.html', {'invoice': invoice})



# ---------- EMAIL UTILITIES (Provided by you) ----------

def send_test_email(request):
    send_mail(
        subject='Test Email from Django',
        message='Hello! This is a test email.',
        from_email='wiwispy8@gmail.com',
        recipient_list=['tejashwi777@gmail.com'],
        fail_silently=False,
    )
    return HttpResponse('Test email sent successfully!')

def send_appointment_email(patient_name, doctor_name, appointment_time, recipient_email, role='patient'):
    if role == 'patient':
        subject = "Appointment Booked Successfully"
        message = f"Hello {patient_name},\n\nYou have successfully booked an appointment with Dr. {doctor_name} on {appointment_time}.\n\nThank you!"
    elif role == 'receptionist':
        subject = f"New Appointment Booked: {patient_name}"
        message = f"Patient {patient_name} has booked an appointment with Dr. {doctor_name} at {appointment_time}."
    
    email_from = settings.EMAIL_HOST_USER
    recipient_list = [recipient_email]
    send_mail(subject, message, email_from, recipient_list)

# In clinic/views.py: Add this function

@login_required
def edit_appointment(request, pk):
    from django.shortcuts import get_object_or_404, redirect, render
    from django.contrib import messages
    
    # ------------------ Manual Security Check ------------------
    if request.user.role not in ['receptionist', 'admin']:
        messages.error(request, "You are not authorized to edit appointments.")
        return redirect('appointment_detail', pk=pk)
    # -----------------------------------------------------------

    try:
        # Ensure your models and forms are imported at the top of views.py
        from .models import Appointment
        from .forms import AppointmentForm # Assuming you have an AppointmentForm
    except ImportError:
        messages.error(request, 'Required Appointment Model or Form not found.')
        return redirect('appointment_detail', pk=pk)

    appointment = get_object_or_404(Appointment, pk=pk)

    if request.method == 'POST':
        form = AppointmentForm(request.POST, instance=appointment)
        if form.is_valid():
            form.save()
            messages.success(request, 'Appointment successfully updated.')
            return redirect('appointment_detail', pk=pk)
    else:
        form = AppointmentForm(instance=appointment)

    context = {
        'form': form,
        'appointment': appointment,
    }
    return render(request, 'clinic/edit_appointment.html', context)


# =========================================================================
# === MISSING PROFILE VIEWS AND HELPERS ADDED BELOW TO FIX AttributeError ===
# =========================================================================

# Helper function to check if the user is a Doctor
def is_doctor(user):
    return user.is_authenticated and user.role == 'doctor'

# Helper function to check if the user is a Patient
def is_patient(user):
    return user.is_authenticated and user.role == 'patient'

# Helper function to check if the user is a Receptionist
def is_receptionist(user):
    return user.is_authenticated and user.role == 'receptionist'


@login_required
@user_passes_test(is_doctor)
def doctor_profile_view(request):
    """View for Doctor to manage their profile."""
    # We fetch the Doctor object to pass any Doctor-specific data to the template
    doctor_obj = get_object_or_404(Doctor, user=request.user)
    context = {
        'title': 'Doctor Profile',
        'user_data': request.user,
        'doctor_data': doctor_obj,
    }
    return render(request, 'clinic/doctor_profile.html', context)


@login_required
@user_passes_test(is_patient)
def patient_profile_view(request):
    """View for Patient to manage their profile."""
    # We fetch the Patient object to pass any Patient-specific data to the template
    patient_obj = get_object_or_404(Patient, user=request.user)
    context = {
        'title': 'Patient Profile',
        'user_data': request.user,
        'patient_data': patient_obj,
    }
    return render(request, 'clinic/patient_profile.html', context)


@login_required
@user_passes_test(is_receptionist)
def receptionist_profile_view(request):
    """View for Receptionist to manage their profile."""
    context = {
        'title': 'Receptionist Profile',
        'user_data': request.user,
    }
    return render(request, 'clinic/receptionist_profile.html', context)

# =========================================================================
# === END OF ADDED CODE ===
# =========================================================================

def is_admin(user):
    return user.is_authenticated and user.role == 'admin'

@login_required
@user_passes_test(is_admin)
def admin_profile_view(request):
    if request.method == 'POST':
        form = AdminProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('admin_profile') # Ensure this matches your URL name
    else:
        form = AdminProfileForm(instance=request.user)

    context = {
        'title': 'Admin Profile',
        'user_data': request.user,
        'form': form  # Pass the form to the template
    }
    return render(request, 'clinic/admin_profile.html', context)
@login_required(login_url='login')
def user_list(request):
    """Displays a list of all User accounts (Admins, Doctors, Receptions, Patients)."""
    # Order by date joined or username for easier sorting
    all_users = User.objects.all().order_by('-date_joined')
    context = {'all_users': all_users}
    return render(request, 'clinic/user_list.html', context)

@login_required
def patient_profile_view(request):
    # Ensure the profile exists
    patient, created = Patient.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = PatientProfileForm(request.POST, instance=patient)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated!')
            return redirect('patient_self_profile')
    else:
        form = PatientProfileForm(instance=patient)
    
    return render(request, 'clinic/patient_profile.html', {
        'form': form,
        'patient': patient
    })

def home_page(request):
    # This renders the new, beautiful homepage
    return render(request, 'clinic/homepage.html')