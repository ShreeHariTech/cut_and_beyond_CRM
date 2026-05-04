from decimal import Decimal
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .models import *
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from django.http import HttpResponse, JsonResponse
import json
from django.utils.dateparse import parse_date
from datetime import date
import urllib.parse
from django.core.paginator import Paginator
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
from django.utils.timezone import now


def login_view(request):
    if request.method == "POST":
        mobile = request.POST.get('mobile')
        password = request.POST.get('password')

        user = authenticate(request, mobile=mobile, password=password)
        if user:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid mobile number or password")

    return render(request, 'login.html')


@login_required
def dashboard(request):

    today = date.today()
    current_month = today.month
    current_year = today.year

    # Today's Bills
    today_bills_count = Bill.objects.filter(
        created_at__date=today
    ).count()

    # Last Bill
    last_bill = Bill.objects.order_by('-created_at').first()

    # 🔥 THIS MONTH TOTAL SERVICES
    month_services = BillItem.objects.filter(
        bill__created_at__month=current_month,
        bill__created_at__year=current_year
    ).count()

    # 🔥 THIS MONTH REVENUE
    month_revenue = Bill.objects.filter(
        created_at__month=current_month,
        created_at__year=current_year
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    # 🔥 TOP EMPLOYEE THIS MONTH
    top_employee = (
        BillItem.objects
        .filter(bill__created_at__month=current_month,
                bill__created_at__year=current_year)
        .values('employee__name')
        .annotate(total=Count('id'))
        .order_by('-total')
        .first()
    )

    # 🔥 TOP 5 SERVICES
    top_services = (
        BillItem.objects
        .values('service__name')
        .annotate(total=Count('id'))
        .order_by('-total')[:5]
    )

    service_chart = {
        item['service__name']: item['total']
        for item in top_services
    }

    # 🔥 LAST 5 BILLS
    recent_bills = Bill.objects.order_by('-created_at')[:5]

    return render(request, 'dashboard.html', {
        'today_bills_count': today_bills_count,
        'last_bill': last_bill,
        'month_services': month_services,
        'month_revenue': month_revenue,
        'top_employee': top_employee,
        'service_chart': json.dumps(service_chart),
        'recent_bills': recent_bills,
    })


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def add_admin(request):
    admins = User.objects.filter(is_staff=True, is_superuser=True)

    if request.method == "POST":
        mobile = request.POST.get('mobile')
        password = request.POST.get('password')

        if User.objects.filter(mobile=mobile).exists():
            messages.error(request, "Admin already exists")
        else:
            User.objects.create_superuser(mobile=mobile, password=password)
            messages.success(request, "Admin created successfully")
            return redirect('add_admin')

    return render(request, 'add_admin.html', {'admins': admins})


@login_required
def edit_admin(request, id):
    admin = get_object_or_404(User, id=id, is_superuser=True)

    if request.method == "POST":
        mobile = request.POST.get('mobile')
        password = request.POST.get('password')

        admin.mobile = mobile
        if password:
            admin.set_password(password)

        admin.save()
        messages.success(request, "Admin updated successfully")
        return redirect('add_admin')

    return render(request, 'edit_admin.html', {'admin': admin})


@login_required

def delete_admin(request, id):

    # only superuser can delete admin
    if not request.user.is_superuser:
        messages.error(request, "Permission denied")
        return redirect('add_admin')

    admin = get_object_or_404(User, id=id, is_superuser=True)

    

    admin.delete()
    messages.success(request, "Admin deleted successfully")
    return redirect('add_admin')

@login_required
def add_employee(request):

    employees = Employee.objects.all().order_by('-id')

    if request.method == "POST":
        name = request.POST.get('name')
        mobile = request.POST.get('mobile')
        birth_date = request.POST.get('birth_date')

        if Employee.objects.filter(mobile=mobile).exists():
            messages.error(request, "Employee with this mobile already exists")
        else:
            Employee.objects.create(
                name=name,
                mobile=mobile,
                birth_date=birth_date
            )
            messages.success(request, "Employee added successfully")
            return redirect('add_employee')

    return render(request, 'add_employee.html', {
        'employees': employees
    })

@login_required
def edit_employee(request, id):
    employee = get_object_or_404(Employee, id=id)

    if request.method == "POST":
        employee.name = request.POST.get('name')
        employee.mobile = request.POST.get('mobile')
        employee.birth_date = request.POST.get('birth_date')
        employee.save()

        messages.success(request, "Employee updated successfully")
        return redirect('add_employee')

    return render(request, 'edit_employee.html', {
        'employee': employee
    })

@login_required
def delete_employee(request, id):
    employee = get_object_or_404(Employee, id=id)
    employee.delete()
    messages.success(request, "Employee deleted successfully")
    return redirect('add_employee')

@login_required
def service(request):

    services = Service.objects.all().order_by('-id')

    if request.method == "POST":
        name = request.POST.get('name')
        price = request.POST.get('price')

        if not name or not price:
            messages.error(request, "All fields are required")
        else:
            Service.objects.create(
                name=name,
                price=price
            )
            messages.success(request, "Service added successfully")
            return redirect('service')

    return render(request, 'service.html', {
        'services': services
    })

@login_required
def edit_service(request, id):
    service_obj = get_object_or_404(Service, id=id)

    if request.method == "POST":
        service_obj.name = request.POST.get('name')
        service_obj.price = request.POST.get('price')
        service_obj.save()

        messages.success(request, "Service updated successfully")
        return redirect('service')

    return render(request, 'edit_service.html', {
        'service': service_obj
    })


@login_required
def delete_service(request, id):
    service_obj = get_object_or_404(Service, id=id)
    service_obj.delete()
    messages.success(request, "Service deleted successfully")
    return redirect('service')

@login_required

def generate_bill(request):

    services = Service.objects.all()
    employees = Employee.objects.all()

    if request.method == "POST":
        data = json.loads(request.body)

        name = data['name']
        mobile = data['mobile']
        payment_mode = data['payment_mode']
        items = data['items']
        total = float(data['total'])

        # get or create customer
        customer, created = Customer.objects.get_or_create(
            mobile=mobile,
            defaults={'name': name}
        )

        # 🔐 PACKAGE PAYMENT LOGIC
        if payment_mode == 'package':
            if customer.package_amount < total:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Insufficient package balance'
                }, status=400)

            customer.package_amount -= Decimal(total)
            customer.save()


        # create bill
        bill = Bill.objects.create(
            customer=customer,
            total_amount=total,
            payment_mode=payment_mode
        )

        # bill items
        for item in items:
            BillItem.objects.create(
                bill=bill,
                service_id=item['service'],
                employee_id=item['employee'],
                price=item['price']
            )

        return JsonResponse({
            'status': 'success',
            'remaining_package': float(customer.package_amount)
        })

    return render(request, 'generate_bill.html', {
        'services': services,
        'employees': employees
    })



def customer_search(request):
    q = request.GET.get('q', '')
    customers = Customer.objects.filter(name__icontains=q)[:5]

    data = []
    for c in customers:
        data.append({
            'name': c.name,
            'mobile': c.mobile,
            'package': c.package_amount
        })

    return JsonResponse(data, safe=False)

@login_required
def client_list(request):

    customers = Customer.objects.all().order_by('name')

    paginator = Paginator(customers, 10)  # 10 clients per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'clients.html', {
        'page_obj': page_obj
    })  

@login_required
def client_detail(request, id):
    customer = get_object_or_404(Customer, id=id)
    bills = Bill.objects.filter(customer=customer).order_by('-created_at')


    for bill in bills:
        message = f"Hello {customer.name},\n\n"
        message += f"🧾 Bill Details\n"
        message += f"📅 Date: {bill.created_at.strftime('%d-%m-%Y %H:%M')}\n\n"

        message += "💇 Services:\n"
        for item in bill.items.all():
            message += f"• {item.service.name} (₹{item.price}) - {item.employee.name}\n"

        message += f"\n💰 Total Amount: ₹{bill.total_amount}\n"

        # Payment Mode Text
        if bill.payment_mode == 'package':
            payment_text = "Package"
        elif bill.payment_mode == 'cash':
            payment_text = "Cash"
        else:
            payment_text = "Online"

        message += f"💳 Payment Mode: {payment_text}\n"
        message += f"📦 Current Package Balance: ₹{customer.package_amount}\n\n"
        message += "Thank you for visiting 🙏"

        bill.whatsapp_message = urllib.parse.quote(message)

    context = {
        'customer': customer,
        'bills': bills,
    }

    return render(request, 'client_detail.html', context)

@login_required
def add_package(request, id):
    customer = get_object_or_404(Customer, id=id)

    if request.method == "POST":
        amount = request.POST.get('amount')

        # 🔥 convert to Decimal
        amount = Decimal(amount)

        customer.package_amount += amount
        customer.save()

        messages.success(request, "Package amount added successfully")

    return redirect('client_detail', id=id)


@login_required
def edit_bill(request, id):
    bill = get_object_or_404(Bill, id=id)
    customer = bill.customer
    services = Service.objects.all()
    employees = Employee.objects.all()

    old_payment = bill.payment_mode
    old_total = bill.total_amount

    if request.method == "POST":

        # 🔄 Reverse old package impact
        if old_payment == 'package':
            customer.package_amount += old_total

        # delete old bill items
        bill.items.all().delete()

        total = Decimal('0')

        service_ids = request.POST.getlist('service')
        employee_ids = request.POST.getlist('employee')

        for i in range(len(service_ids)):
            service = Service.objects.get(id=service_ids[i])
            employee = Employee.objects.get(id=employee_ids[i])

            price = service.price
            total += price

            BillItem.objects.create(
                bill=bill,
                service=service,
                employee=employee,
                price=price
            )

        new_payment = request.POST.get('payment_mode')

        # 🔄 Apply new package impact
        if new_payment == 'package':
            if customer.package_amount < total:
                messages.error(request, "Insufficient package balance")
                return redirect('edit_bill', id=id)

            customer.package_amount -= total

        bill.total_amount = total
        bill.payment_mode = new_payment

        bill.save()
        customer.save()

        messages.success(request, "Bill updated successfully")
        return redirect('client_detail', id=customer.id)

    return render(request, 'edit_bill.html', {
        'bill': bill,
        'services': services,
        'employees': employees
    })

@login_required
@require_POST
def delete_bill(request, id):
    bill = get_object_or_404(Bill, id=id)
    customer_id = bill.customer.id

    # 🔐 if bill was paid by package → refund package
    if bill.payment_mode == 'package':
        bill.customer.package_amount += bill.total_amount
        bill.customer.save()

    bill.delete()
    messages.success(request, "Bill deleted successfully")

    return redirect('client_detail', id=customer_id)

@login_required
def edit_client(request, id):
    customer = get_object_or_404(Customer, id=id)

    if request.method == "POST":
        customer.name = request.POST.get('name')
        customer.mobile = request.POST.get('mobile')
        customer.package_amount = request.POST.get('package_amount')
        customer.save()

        messages.success(request, "Client updated successfully")
        return redirect('client_list')

    return render(request, 'edit_client.html', {
        'customer': customer
    })
