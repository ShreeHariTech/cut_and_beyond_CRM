from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models


# ─────────────────────────────────────────────
#  BRANCH
# ─────────────────────────────────────────────
class Branch(models.Model):
    name = models.CharField(max_length=150)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=15, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Branches"
        ordering = ['name']

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────
#  USER MANAGER
# ─────────────────────────────────────────────
class UserManager(BaseUserManager):
    def create_user(self, mobile, password=None, **extra_fields):
        if not mobile:
            raise ValueError("Mobile number is required")
        user = self.model(mobile=mobile, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, mobile, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_super_admin', True)
        return self.create_user(mobile, password, **extra_fields)


# ─────────────────────────────────────────────
#  USER
# ─────────────────────────────────────────────
class User(AbstractBaseUser, PermissionsMixin):
    mobile = models.CharField(max_length=10, unique=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)

    # New fields
    is_super_admin = models.BooleanField(
        default=False,
        help_text="Super admins can see and manage ALL branches."
    )
    branch = models.ForeignKey(
        Branch,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='users',
        help_text="Leave blank for Super Admins (they see all branches)."
    )

    objects = UserManager()

    USERNAME_FIELD = 'mobile'
    REQUIRED_FIELDS = []

    def __str__(self):
        role = "Super Admin" if self.is_super_admin else "Branch Admin"
        branch = self.branch.name if self.branch else "All Branches"
        return f"{self.mobile} ({role} – {branch})"


# ─────────────────────────────────────────────
#  EMPLOYEE
# ─────────────────────────────────────────────
class Employee(models.Model):
    branch = models.ForeignKey(
        Branch, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='employees'
    )
    name = models.CharField(max_length=100)
    mobile = models.CharField(max_length=10, unique=True)
    birth_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.mobile}"


# ─────────────────────────────────────────────
#  SERVICE  (branch-specific — Feature 2)
# ─────────────────────────────────────────────
class Service(models.Model):
    branch = models.ForeignKey(
        Branch,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='services',
        help_text="Leave blank to make this service available to all branches (legacy). "
                  "Set branch for branch-specific services."
    )
    name = models.CharField(max_length=150)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        branch_label = self.branch.name if self.branch else "All Branches"
        return f"{self.name} ({branch_label})"


# ─────────────────────────────────────────────
#  CUSTOMER
# ─────────────────────────────────────────────
class Customer(models.Model):
    branch = models.ForeignKey(
        Branch, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='customers'
    )
    name = models.CharField(max_length=150)
    mobile = models.CharField(max_length=10)
    package_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        # Mobile unique per branch (not globally)
        unique_together = ('branch', 'mobile')

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────
#  BILL
# ─────────────────────────────────────────────
class Bill(models.Model):
    PAYMENT_CHOICES = (
        ('cash', 'Cash'),
        ('online', 'Online'),
        ('package', 'Package'),
    )

    branch = models.ForeignKey(
        Branch, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='bills'
    )
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    total_discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Sum of all discounts across bill items."
    )
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Bill #{self.id} – {self.customer.name}"


# ─────────────────────────────────────────────
#  BILL ITEM
# ─────────────────────────────────────────────
class BillItem(models.Model):
    bill = models.ForeignKey(Bill, related_name='items', on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    original_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="The service's listed price at the time of billing."
    )
    price = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="The final (possibly edited) price charged to the customer."
    )
    discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Discount applied = original_price - price (0 if no discount)."
    )

    def __str__(self):
        return f"{self.service.name} × {self.bill}"
