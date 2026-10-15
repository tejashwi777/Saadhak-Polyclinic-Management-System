# clinic/urls.py

from django.urls import path
from . import views
from django.contrib.auth import views as auth_views



urlpatterns = [
    # 1. THE ROOT (Homepage)
    path('', views.home_page, name='home'),

    # 2. THE LOGIN PATHS (Give them distinct URLs)
    path('clinic-admin-login/', views.admin_login, name='admin_login'),    
    path('login/', views.user_login, name='user_login'), # This is your main login
    
    # Use 'login' as a shortcut name for 'user_login' if you want
    path('signin/', views.user_login, name='login'), 

    path('register/', views.register_user, name='register_user'),
    path('logout/', views.user_logout, name='user_logout'),
    

    

    # 🌟 NEW: PASSWORD RESET PATHS 🌟
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(template_name='registration/password_reset_form.html'), 
         name='password_reset'),
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), 
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'), 
         name='password_reset_confirm'),
    path('password-reset-complete/', 
         auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), 
         name='password_reset_complete'),
    # ---------- DASHBOARDS ----------
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('doctor-dashboard/', views.doctor_dashboard, name='doctor_dashboard'),
    path('receptionist-dashboard/', views.receptionist_dashboard, name='receptionist_dashboard'),
    path('patient-dashboard/', views.patient_dashboard, name='patient_dashboard'),

    # ---------- PATIENT MANAGEMENT ----------
    path('patients/', views.patient_list, name='patient_list'),
    path('patients/create/', views.patient_register, name='patient_register'),
    # This is for Patient Profile MANAGEMENT (by Admin/Receptionist)
    path('patients/<int:patient_id>/profile/', views.patient_profile, name='patient_profile'), 
    
    # --- Detail Views ---
    path('patients/<int:patient_id>/detail/', views.patient_detail, name='patient_detail'),
    path('doctors/<int:doctor_id>/detail/', views.doctor_detail, name='doctor_detail'),

    # ---------- DOCTOR MANAGEMENT ----------
    path('doctors/', views.doctor_list, name='doctor_list'),
    path('doctors/create/', views.doctor_register, name='doctor_register'),

    # ---------- APPOINTMENTS ----------
    path('appointments/', views.appointment_list, name='appointment_list'), 
    path('appointments/create/', views.book_appointment, name='book_appointment'),
    path('appointments/<int:pk>/', views.appointment_detail, name='appointment_detail'),
    path('appointments/dashboard/', views.appointment_dashboard, name='appointment_dashboard'),
    path('appointments/delete/<int:pk>/', views.delete_appointment, name='delete_appointment'),
    path('appointments/<int:pk>/status/<str:status>/', views.update_appointment_status, name='update_appointment_status'),
    path('appointments/edit/<int:pk>/', views.edit_appointment, name='edit_appointment'),
path('appointments/events/', views.get_calendar_events, name='get_calendar_events'),
    path('appointments/', views.appointment_list, name='appointment_list'),
    # ---------- DOCTOR SCHEDULE ----------
    path('doctor/schedule/', views.doctor_schedule, name='doctor_schedule'),

    

path('prescriptions/', views.prescription_list, name='prescription_list'),
# Use 'appointment_pk' here for consistency with the views.py implementation:
path('prescriptions/create/<int:appointment_pk>/', views.prescription_create, name='prescription_create'),
path('appointments/<int:appointment_pk>/prescribe/', views.prescription_create, name='prescription_create'),

    # ---------- LAB REPORTS ----------
    path('labreports/', views.labreport_list, name='labreport_list'),
    path('labreports/upload/', views.labreport_upload, name='labreport_upload'),

    # ---------- MESSAGING ----------
    path('messages/', views.message_list, name='message_list'),
    path('messages/send/', views.message_send, name='message_send'),

    # ---------- NOTIFICATIONS ----------
    path('notifications/', views.notifications_list, name='notifications_list'),
    path('receptionist/notifications/', views.receptionist_notifications, name='receptionist_notifications'),

    # ---------- BILLING ----------
    path('billing/', views.billing_list, name='billing_list'),
    path('billing/create/', views.billing_create, name='billing_create'),

    # ---------- INVOICES ----------
    path('create-invoice/', views.create_invoice, name='create_invoice'),
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoices/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    
    path('send-test-email/', views.send_test_email, name='send_test_email'),
    
    # ====================================================================
    # === PROFILE VIEWS (CRITICAL FIX FOR 404 URL CONFLICT) ===
    # ====================================================================
    
    path('admin-profile/', views.admin_profile_view, name='admin_profile'), 
    path('doctor-profile/', views.doctor_profile_view, name='doctor_profile'),
    path('patient-self-profile/', views.patient_profile_view, name='patient_self_profile'), 
    path('receptionist-profile/', views.receptionist_profile_view, name='receptionist_profile'),
    path('users/', views.user_list, name='user_list'),
    path('password-change/', auth_views.PasswordChangeView.as_view(template_name='registration/password_change_form.html'), name='password_change'),
    path('password-change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='registration/password_change_done.html'), name='password_change_done'),
]