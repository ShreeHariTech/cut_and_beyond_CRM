from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Branch, Employee, Customer, Bill, BillItem, Service


# ─────────────────────────────────────────────
#  BRANCH
# ─────────────────────────────────────────────
@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'phone')


# ─────────────────────────────────────────────
#  USER
# ─────────────────────────────────────────────
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('mobile', 'is_super_admin', 'branch', 'is_active', 'date_joined')
    list_filter = ('is_super_admin', 'is_active', 'branch')
    search_fields = ('mobile',)
    ordering = ('-date_joined',)

    fieldsets = (
        (None, {'fields': ('mobile', 'password')}),
        ('Role & Branch', {'fields': ('is_super_admin', 'branch')}),
        ('Permissions', {'fields': ('is_staff', 'is_superuser', 'is_active', 'groups', 'user_permissions')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('mobile', 'password1', 'password2', 'is_super_admin', 'branch'),
        }),
    )


# ─────────────────────────────────────────────
#  EMPLOYEE
# ─────────────────────────────────────────────
@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'mobile', 'branch', 'birth_date')
    list_filter = ('branch',)
    search_fields = ('name', 'mobile')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_super_admin or request.user.is_superuser:
            return qs
        return qs.filter(branch=request.user.branch)

    def save_model(self, request, obj, form, change):
        if not obj.branch and not request.user.is_super_admin:
            obj.branch = request.user.branch
        super().save_model(request, obj, form, change)


# ─────────────────────────────────────────────
#  SERVICE
# ─────────────────────────────────────────────
@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'created_at')
    search_fields = ('name',)


# ─────────────────────────────────────────────
#  CUSTOMER
# ─────────────────────────────────────────────
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'mobile', 'branch', 'package_amount')
    list_filter = ('branch',)
    search_fields = ('name', 'mobile')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_super_admin or request.user.is_superuser:
            return qs
        return qs.filter(branch=request.user.branch)


# ─────────────────────────────────────────────
#  BILL ITEM (inline)
# ─────────────────────────────────────────────
class BillItemInline(admin.TabularInline):
    model = BillItem
    extra = 0
    readonly_fields = ('service', 'employee', 'price')


# ─────────────────────────────────────────────
#  BILL
# ─────────────────────────────────────────────
@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'branch', 'total_amount', 'payment_mode', 'created_at')
    list_filter = ('branch', 'payment_mode', 'created_at')
    search_fields = ('customer__name', 'customer__mobile')
    inlines = [BillItemInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_super_admin or request.user.is_superuser:
            return qs
        return qs.filter(branch=request.user.branch)
