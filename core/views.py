from decimal import Decimal
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .models import *
from .decorators import super_admin_required, branch_access_required
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


# ─────────────────────────────────────────────
#  HELPER: branch-filtered queryset
# ─────────────────────────────────────────────
def branch_qs(queryset, user):
    """
    Filter a queryset by the user's branch if they are a Branch Admin.
    Super Admins receive the full queryset.
    NOTE: Only use this on models that have a direct 'branch' ForeignKey.
    For BillItem, use billitem_qs() instead.
    """
    if user.is_super_admin:
        return queryset
    return queryset.filter(branch=user.branch)


def billitem_branch_qs(user):
    """
    Return a branch-filtered BillItem queryset.
    BillItem has no direct branch field; filtering goes through bill__branch.
    """
    qs = BillItem.objects.select_related('bill', 'service', 'employee')
    if user.is_super_admin:
        return qs
    return qs.filter(bill__branch=user.branch)


def service_branch_qs(user):
    """
    Return services visible to the logged-in user.
    - Branch Admin: only their branch's services.
    - Super Admin: all services.
    """
    if user.is_super_admin:
        return Service.objects.all().order_by('name')
    return Service.objects.filter(branch=user.branch).order_by('name')


# ─────────────────────────────────────────────
#  HELPER: build WhatsApp message for a bill
# ─────────────────────────────────────────────
def build_whatsapp_message(bill, customer):
    """Build the URL-encoded WhatsApp message for a given bill."""
    message = f"Hello {customer.name},\n\n"
    message += "Bill Details\n"
    message += f"Date: {bill.created_at.strftime('%d-%m-%Y %H:%M')}\n\n"
    message += "Services:\n"
    for item in bill.items.all():
        message += f"• {item.service.name} (₹{item.price}) - {item.employee.name}\n"

    # ── Discount section (only if any discount exists) ──
    items_with_discount = [i for i in bill.items.all() if i.discount > 0]
    if items_with_discount:
        message += "\nDiscount Details:\n"
        for item in items_with_discount:
            message += f"• {item.service.name} Discount: ₹{item.discount}\n"
        total_disc = sum(i.discount for i in items_with_discount)
        message += f"\nTotal Discount: ₹{total_disc}\n"

    message += f"\nTotal Amount: ₹{bill.total_amount}\n"
    payment_text = {'package': 'Package', 'cash': 'Cash'}.get(bill.payment_mode, 'Online')
    message += f"Payment Mode: {payment_text}\n"
    if customer.package_amount > 0:
        message += f"Current Package Balance: ₹{customer.package_amount}\n\n"
    message += "Thank you for visiting"
    return urllib.parse.quote(message)


# ─────────────────────────────────────────────
#  AUTH
# ─────────────────────────────────────────────
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


def logout_view(request):
    logout(request)
    return redirect('login')


# ─────────────────────────────────────────────
#  DASHBOARD
# ─────────────────────────────────────────────
@login_required
def dashboard(request):
    today = date.today()
    current_month = today.month
    current_year = today.year

    bill_qs = branch_qs(Bill.objects.all(), request.user)
    billitem_qs = billitem_branch_qs(request.user)

    # Today's Bills
    today_bills_count = bill_qs.filter(created_at__date=today).count()

    # Last Bill
    last_bill = bill_qs.order_by('-created_at').first()

    # This Month Services
    month_services = billitem_qs.filter(
        bill__created_at__month=current_month,
        bill__created_at__year=current_year
    ).count()

    # This Month Revenue
    month_revenue = bill_qs.filter(
        created_at__month=current_month,
        created_at__year=current_year
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    # Top Employee This Month
    top_employee = (
        billitem_qs
        .filter(bill__created_at__month=current_month,
                bill__created_at__year=current_year)
        .values('employee__name')
        .annotate(total=Count('id'))
        .order_by('-total')
        .first()
    )

    # Top 5 Services
    top_services = (
        billitem_qs
        .values('service__name')
        .annotate(total=Count('id'))
        .order_by('-total')[:5]
    )
    service_chart = {item['service__name']: item['total'] for item in top_services}

    # Monthly Chart data
    monthly_raw = (
        billitem_qs
        .filter(bill__created_at__year=current_year)
        .annotate(month=TruncMonth('bill__created_at'))
        .values('month', 'employee__name')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    monthly_chart = {}
    for row in monthly_raw:
        m = row['month'].strftime('%b') if row['month'] else '?'
        emp = row['employee__name']
        monthly_chart.setdefault(m, {})[emp] = row['count']

    # Daily Chart
    daily_raw = (
        billitem_qs
        .filter(bill__created_at__date=today)
        .values('employee__name')
        .annotate(count=Count('id'))
    )
    daily_chart = {r['employee__name']: r['count'] for r in daily_raw}

    # Recent Bills (last 5)
    recent_bills = bill_qs.order_by('-created_at')[:5]

    return render(request, 'dashboard.html', {
        'today_bills_count': today_bills_count,
        'last_bill': last_bill,
        'month_services': month_services,
        'month_revenue': month_revenue,
        'top_employee': top_employee,
        'service_chart': json.dumps(service_chart),
        'monthly_chart': json.dumps(monthly_chart),
        'daily_chart': json.dumps(daily_chart),
        'recent_bills': recent_bills,
        'today': today,
    })


# ─────────────────────────────────────────────
#  TODAY'S BILLS — full list page (Feature 1: date filter)
# ─────────────────────────────────────────────
@login_required
def today_bills(request):
    today = date.today()
    bill_qs = branch_qs(Bill.objects.all(), request.user)

    # ── Date filter ──
    selected_date_str = request.GET.get('bill_date', '')
    selected_date = parse_date(selected_date_str) if selected_date_str else None
    filter_date = selected_date if selected_date else today

    bills = (
        bill_qs
        .filter(created_at__date=filter_date)
        .select_related('customer')
        .prefetch_related('items__service', 'items__employee')
        .order_by('-created_at')
    )

    # Attach WhatsApp message per bill
    for bill in bills:
        bill.whatsapp_message = build_whatsapp_message(bill, bill.customer)

    total_revenue = bills.aggregate(total=Sum('total_amount'))['total'] or 0
    total_discount = bills.aggregate(total=Sum('total_discount'))['total'] or 0

    return render(request, 'today_bills.html', {
        'bills': bills,
        'today': today,
        'filter_date': filter_date,
        'selected_date': selected_date_str,
        'total_revenue': total_revenue,
        'total_discount': total_discount,
    })


# ─────────────────────────────────────────────
#  BRANCH MANAGEMENT (Super Admin only)
# ─────────────────────────────────────────────
@login_required
@super_admin_required
def manage_branches(request):
    branches = Branch.objects.all().order_by('name')

    if request.method == "POST":
        action = request.POST.get('action')

        if action == 'create':
            name = request.POST.get('name', '').strip()
            address = request.POST.get('address', '').strip()
            phone = request.POST.get('phone', '').strip()
            if not name:
                messages.error(request, "Branch name is required.")
            elif Branch.objects.filter(name__iexact=name).exists():
                messages.error(request, f"Branch '{name}' already exists.")
            else:
                Branch.objects.create(name=name, address=address, phone=phone)
                messages.success(request, f"Branch '{name}' created successfully.")
            return redirect('manage_branches')

        elif action == 'edit':
            branch_id = request.POST.get('branch_id')
            branch = get_object_or_404(Branch, id=branch_id)
            branch.name = request.POST.get('name', '').strip()
            branch.address = request.POST.get('address', '').strip()
            branch.phone = request.POST.get('phone', '').strip()
            branch.save()
            messages.success(request, "Branch updated successfully.")
            return redirect('manage_branches')

        elif action == 'toggle':
            branch_id = request.POST.get('branch_id')
            branch = get_object_or_404(Branch, id=branch_id)
            branch.is_active = not branch.is_active
            branch.save()
            status = "activated" if branch.is_active else "deactivated"
            messages.success(request, f"Branch '{branch.name}' {status}.")
            return redirect('manage_branches')

    return render(request, 'manage_branches.html', {'branches': branches})


# ─────────────────────────────────────────────
#  USER MANAGEMENT (Super Admin only)
# ─────────────────────────────────────────────
@login_required
@super_admin_required
def manage_users(request):
    users = User.objects.all().select_related('branch').order_by('mobile')
    branches = Branch.objects.filter(is_active=True)

    if request.method == "POST":
        action = request.POST.get('action')

        if action == 'create':
            mobile = request.POST.get('mobile', '').strip()
            password = request.POST.get('password', '').strip()
            is_super_admin = request.POST.get('is_super_admin') == 'on'
            branch_id = request.POST.get('branch')

            if User.objects.filter(mobile=mobile).exists():
                messages.error(request, f"User with mobile '{mobile}' already exists.")
            elif not is_super_admin and not branch_id:
                messages.error(request, "Branch Admin must be assigned to a branch.")
            else:
                branch = Branch.objects.get(id=branch_id) if branch_id else None
                user = User.objects.create_user(mobile=mobile, password=password)
                user.is_super_admin = is_super_admin
                user.is_staff = is_super_admin
                user.is_superuser = is_super_admin
                user.branch = None if is_super_admin else branch
                user.save()
                messages.success(request, f"User '{mobile}' created successfully.")
            return redirect('manage_users')

        elif action == 'edit':
            user_id = request.POST.get('user_id')
            user = get_object_or_404(User, id=user_id)
            new_mobile = request.POST.get('mobile', '').strip()
            password = request.POST.get('password', '').strip()
            is_super_admin = request.POST.get('is_super_admin') == 'on'
            branch_id = request.POST.get('branch')

            user.mobile = new_mobile
            if password:
                user.set_password(password)
            user.is_super_admin = is_super_admin
            user.is_staff = is_super_admin
            user.is_superuser = is_super_admin
            user.branch = None if is_super_admin else (Branch.objects.get(id=branch_id) if branch_id else user.branch)
            user.save()
            messages.success(request, f"User '{new_mobile}' updated successfully.")
            return redirect('manage_users')

        elif action == 'delete':
            user_id = request.POST.get('user_id')
            # Prevent self-deletion
            if str(request.user.id) == str(user_id):
                messages.error(request, "You cannot delete your own account.")
            else:
                user = get_object_or_404(User, id=user_id)
                user.delete()
                messages.success(request, "User deleted successfully.")
            return redirect('manage_users')

    return render(request, 'manage_users.html', {
        'users': users,
        'branches': branches,
    })


# ─────────────────────────────────────────────
#  LEGACY: add_admin / edit_admin / delete_admin
#  (kept for backward compatibility, super admin only)
# ─────────────────────────────────────────────
@login_required
@super_admin_required
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
@super_admin_required
def edit_admin(request, id):
    admin = get_object_or_404(User, id=id, is_superuser=True)
    if request.method == "POST":
        admin.mobile = request.POST.get('mobile')
        password = request.POST.get('password')
        if password:
            admin.set_password(password)
        admin.save()
        messages.success(request, "Admin updated successfully")
        return redirect('add_admin')
    return render(request, 'edit_admin.html', {'admin': admin})


@login_required
@super_admin_required
def delete_admin(request, id):
    admin = get_object_or_404(User, id=id, is_superuser=True)
    admin.delete()
    messages.success(request, "Admin deleted successfully")
    return redirect('add_admin')


# ─────────────────────────────────────────────
#  EMPLOYEE
# ─────────────────────────────────────────────
@login_required
def add_employee(request):
    employees = branch_qs(Employee.objects.all(), request.user).order_by('-id')

    if request.method == "POST":
        name = request.POST.get('name')
        mobile = request.POST.get('mobile')
        birth_date = request.POST.get('birth_date')

        if Employee.objects.filter(mobile=mobile).exists():
            messages.error(request, "Employee with this mobile already exists")
        else:
            emp = Employee.objects.create(
                name=name,
                mobile=mobile,
                birth_date=birth_date,
            )
            # Assign branch automatically for branch admins
            if not request.user.is_super_admin:
                emp.branch = request.user.branch
                emp.save()
            messages.success(request, "Employee added successfully")
            return redirect('add_employee')

    return render(request, 'add_employee.html', {'employees': employees})


@login_required
@branch_access_required(Employee)
def edit_employee(request, id):
    employee = get_object_or_404(Employee, id=id)
    if request.method == "POST":
        employee.name = request.POST.get('name')
        employee.mobile = request.POST.get('mobile')
        employee.birth_date = request.POST.get('birth_date')
        employee.save()
        messages.success(request, "Employee updated successfully")
        return redirect('add_employee')
    return render(request, 'edit_employee.html', {'employee': employee})


@login_required
@branch_access_required(Employee)
def delete_employee(request, id):
    employee = get_object_or_404(Employee, id=id)
    employee.delete()
    messages.success(request, "Employee deleted successfully")
    return redirect('add_employee')


# ─────────────────────────────────────────────
#  SERVICE (Feature 2: branch-specific)
# ─────────────────────────────────────────────
@login_required
def service(request):
    # Branch Admins only see their own branch services
    services = service_branch_qs(request.user).order_by('-id')
    branches = Branch.objects.filter(is_active=True) if request.user.is_super_admin else None

    if request.method == "POST":
        name = request.POST.get('name')
        price = request.POST.get('price')
        if not name or not price:
            messages.error(request, "All fields are required")
        else:
            # Super Admin can pick a branch; Branch Admin uses their own branch
            if request.user.is_super_admin:
                branch_id = request.POST.get('branch')
                branch = Branch.objects.get(id=branch_id) if branch_id else None
            else:
                branch = request.user.branch

            Service.objects.create(name=name, price=price, branch=branch)
            messages.success(request, "Service added successfully")
            return redirect('service')

    return render(request, 'service.html', {
        'services': services,
        'branches': branches,
    })


@login_required
def edit_service(request, id):
    service_obj = get_object_or_404(Service, id=id)
    # Branch admin can only edit their own branch services
    if not request.user.is_super_admin and service_obj.branch != request.user.branch:
        messages.error(request, "You do not have permission to edit this service.")
        return redirect('service')

    branches = Branch.objects.filter(is_active=True) if request.user.is_super_admin else None

    if request.method == "POST":
        service_obj.name = request.POST.get('name')
        service_obj.price = request.POST.get('price')
        if request.user.is_super_admin:
            branch_id = request.POST.get('branch')
            service_obj.branch = Branch.objects.get(id=branch_id) if branch_id else None
        service_obj.save()
        messages.success(request, "Service updated successfully")
        return redirect('service')

    return render(request, 'edit_service.html', {
        'service': service_obj,
        'branches': branches,
    })


@login_required
def delete_service(request, id):
    service_obj = get_object_or_404(Service, id=id)
    # Branch admin can only delete their own branch services
    if not request.user.is_super_admin and service_obj.branch != request.user.branch:
        messages.error(request, "You do not have permission to delete this service.")
        return redirect('service')
    service_obj.delete()
    messages.success(request, "Service deleted successfully")
    return redirect('service')


# ─────────────────────────────────────────────
#  GENERATE BILL (Feature 2 + Feature 3: branch services + editable price + discount)
# ─────────────────────────────────────────────
@login_required
def generate_bill(request):
    services = service_branch_qs(request.user)
    employees = branch_qs(Employee.objects.all(), request.user)

    if request.method == "POST":
        data = json.loads(request.body)

        name = data['name']
        mobile = data['mobile']
        payment_mode = data['payment_mode']
        items = data['items']
        total = float(data['total'])

        # Determine the branch for this bill
        bill_branch = request.user.branch  # None for super admin

        # Get or create customer scoped to branch
        customer, created = Customer.objects.get_or_create(
            mobile=mobile,
            branch=bill_branch,
            defaults={'name': name}
        )

        # PACKAGE PAYMENT LOGIC
        if payment_mode == 'package':
            if customer.package_amount < total:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Insufficient package balance'
                }, status=400)
            customer.package_amount -= Decimal(total)
            customer.save()

        # Calculate total discount across all items
        total_discount = Decimal('0')
        for item in items:
            orig = Decimal(str(item.get('original_price', item['price'])))
            final = Decimal(str(item['price']))
            disc = orig - final if orig > final else Decimal('0')
            total_discount += disc

        # Create Bill
        bill = Bill.objects.create(
            customer=customer,
            total_amount=total,
            total_discount=total_discount,
            payment_mode=payment_mode,
            branch=bill_branch,
        )

        # Bill Items — store original_price, final price, discount
        for item in items:
            orig = Decimal(str(item.get('original_price', item['price'])))
            final = Decimal(str(item['price']))
            disc = orig - final if orig > final else Decimal('0')
            BillItem.objects.create(
                bill=bill,
                service_id=item['service'],
                employee_id=item['employee'],
                original_price=orig,
                price=final,
                discount=disc,
            )

        return JsonResponse({
            'status': 'success',
            'remaining_package': float(customer.package_amount)
        })

    return render(request, 'generate_bill.html', {
        'services': services,
        'employees': employees
    })


# ─────────────────────────────────────────────
#  CUSTOMER SEARCH (branch-scoped)
# ─────────────────────────────────────────────
def customer_search(request):
    q = request.GET.get('q', '')
    customers = branch_qs(Customer.objects.all(), request.user).filter(name__icontains=q)[:5]

    data = []
    for c in customers:
        data.append({
            'name': c.name,
            'mobile': c.mobile,
            'package': float(c.package_amount)
        })
    return JsonResponse(data, safe=False)


# ─────────────────────────────────────────────
#  CLIENT LIST
# ─────────────────────────────────────────────
@login_required
def client_list(request):
    customers = branch_qs(Customer.objects.all(), request.user).order_by('name')
    paginator = Paginator(customers, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'clients.html', {'page_obj': page_obj})


# ─────────────────────────────────────────────
#  CLIENT DETAIL
# ─────────────────────────────────────────────
@login_required
@branch_access_required(Customer)
def client_detail(request, id):
    customer = get_object_or_404(Customer, id=id)

    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    bills = Bill.objects.filter(customer=customer).order_by('-created_at')

    if from_date:
        bills = bills.filter(created_at__date__gte=parse_date(from_date))
    if to_date:
        bills = bills.filter(created_at__date__lte=parse_date(to_date))

    for bill in bills:
        bill.whatsapp_message = build_whatsapp_message(bill, customer)

    return render(request, 'client_detail.html', {
        'customer': customer,
        'bills': bills,
        'from_date': from_date or '',
        'to_date': to_date or '',
    })


# ─────────────────────────────────────────────
#  ADD PACKAGE
# ─────────────────────────────────────────────
@login_required
@branch_access_required(Customer)
def add_package(request, id):
    customer = get_object_or_404(Customer, id=id)
    if request.method == "POST":
        amount = Decimal(request.POST.get('amount'))
        customer.package_amount += amount
        customer.save()
        messages.success(request, "Package amount added successfully")
    return redirect('client_detail', id=id)


# ─────────────────────────────────────────────
#  EDIT BILL (Feature 3: editable price + discount)
# ─────────────────────────────────────────────
@login_required
@branch_access_required(Bill)
def edit_bill(request, id):
    bill = get_object_or_404(Bill, id=id)
    customer = bill.customer
    services = service_branch_qs(request.user)
    employees = branch_qs(Employee.objects.all(), request.user)

    old_payment = bill.payment_mode
    old_total = bill.total_amount

    if request.method == "POST":
        if old_payment == 'package':
            customer.package_amount += old_total

        bill.items.all().delete()
        total = Decimal('0')
        total_discount = Decimal('0')

        service_ids = request.POST.getlist('service')
        employee_ids = request.POST.getlist('employee')
        prices = request.POST.getlist('price')

        for i in range(len(service_ids)):
            svc = Service.objects.get(id=service_ids[i])
            emp = Employee.objects.get(id=employee_ids[i])
            orig_price = svc.price
            # Use submitted price (editable), fallback to service price
            try:
                final_price = Decimal(str(prices[i])) if prices[i] else orig_price
            except Exception:
                final_price = orig_price
            disc = orig_price - final_price if orig_price > final_price else Decimal('0')
            total += final_price
            total_discount += disc
            BillItem.objects.create(
                bill=bill,
                service=svc,
                employee=emp,
                original_price=orig_price,
                price=final_price,
                discount=disc,
            )

        new_payment = request.POST.get('payment_mode')
        if new_payment == 'package':
            if customer.package_amount < total:
                messages.error(request, "Insufficient package balance")
                return redirect('edit_bill', id=id)
            customer.package_amount -= total

        bill.total_amount = total
        bill.total_discount = total_discount
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


# ─────────────────────────────────────────────
#  DELETE BILL
# ─────────────────────────────────────────────
@login_required
@require_POST
@branch_access_required(Bill)
def delete_bill(request, id):
    bill = get_object_or_404(Bill, id=id)
    customer_id = bill.customer.id
    if bill.payment_mode == 'package':
        bill.customer.package_amount += bill.total_amount
        bill.customer.save()
    bill.delete()
    messages.success(request, "Bill deleted successfully")
    return redirect('client_detail', id=customer_id)


# ─────────────────────────────────────────────
#  EDIT CLIENT
# ─────────────────────────────────────────────
@login_required
@branch_access_required(Customer)
def edit_client(request, id):
    customer = get_object_or_404(Customer, id=id)
    if request.method == "POST":
        customer.name = request.POST.get('name')
        customer.mobile = request.POST.get('mobile')
        customer.package_amount = request.POST.get('package_amount')
        customer.save()
        messages.success(request, "Client updated successfully")
        return redirect('client_list')
    return render(request, 'edit_client.html', {'customer': customer})
