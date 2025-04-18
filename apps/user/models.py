from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError("The Username field must be set")
        username = username.lower()
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password, **extra_fields):
        user = self.create_user(username, password, **extra_fields)
        user.is_superuser = True
        user.is_staff = True
        user.save(using=self._db)
        return user


class UserAccount(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(max_length=30, unique=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    photo_url = models.CharField(
        max_length=255,
        default="https://res.cloudinary.com/ddksrkond/image/upload/v1688411778/default_dfvymc.webp",
    )
    date_joined = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    es_empleado = models.BooleanField(default=False)
    desactivate_account = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["first_name","last_name"]

    class Meta:
        permissions = [
            ("can_make_sale", "Puede hacer una venta"),
            ("can_cancel_sale", "Puede cancelar una venta"),
            ("can_create_inventory", "Puede crear inventario"),
            ("can_modify_inventory", "Puede modificar inventario"),
            ("can_update_inventory", "Puede actualizar inventario"),
            ("can_delete_inventory", "Puede eliminar inventario"),
            ("can_create_product", "Puede crear un producto"),
            ("can_update_product", "Puede actualizar un producto"),
            ("can_delete_product", "Puede eliminar un producto"),
            ("can_create_category", "Puede crear una categoría"),
            ("can_modify_category", "Puede modificar una categoría"),
            ("can_delete_category", "Puede eliminar una categoría"),
            ("can_create_supplier", "Puede crear proveedores"),
            ("can_modify_supplier", "Puede modificar proveedores"),
            ("can_delete_supplier", "Puede eliminar proveedores"),
            ("can_create_store", "Puede crear una tienda"),
            ("can_modify_store", "Puede modificar una tienda"),
            ("can_delete_store", "Puede eliminar una tienda"),
            ("view_sale", "Puede ver las ventas"),
            ("view_inventory", "Puede ver el inventario"),
            ("view_product", "Puede ver los productos"),
            ("view_category", "Puede ver las categorías"),
            ("view_supplier", "Puede ver los proveedores"),
            ("view_store", "Puede ver las tiendas"),
        ]


    def __str__(self):
        return self.username



