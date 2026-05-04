from django.urls import path
from .views import *


urlpatterns = [
    path('', login_view, name='login'),
    path('dashboard/', dashboard, name='dashboard'),
    path('logout/', logout_view, name='logout'),
    path('add-admin/', add_admin, name='add_admin'),
    path('edit-admin/<int:id>/', edit_admin, name='edit_admin'),
    path('delete-admin/<int:id>/', delete_admin, name='delete_admin'),
    path('add-employee/', add_employee, name='add_employee'),
    path('add-employee/', add_employee, name='add_employee'),
path('edit-employee/<int:id>/', edit_employee, name='edit_employee'),
path('delete-employee/<int:id>/', delete_employee, name='delete_employee'),
path('service/', service, name='service'),
path('edit-service/<int:id>/', edit_service, name='edit_service'),
path('delete-service/<int:id>/', delete_service, name='delete_service'),
path('generate-bill/', generate_bill, name='generate_bill'),
path('customer-search/', customer_search, name='customer_search'),
path('clients/', client_list, name='client_list'),
path('client/<int:id>/', client_detail, name='client_detail'),
path('add-package/<int:id>/', add_package, name='add_package'),
path('edit-bill/<int:id>/', edit_bill, name='edit_bill'),
path('delete-bill/<int:id>/', delete_bill, name='delete_bill'),
path('edit-client/<int:id>/', edit_client, name='edit_client'),


]
