from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from apps import tienda
from apps.tienda.models import Tienda
from apps.user.permissions_catalog import PERMISSIONS_META


def default_modulos_habilitados():
    return ["tiktok", "compras", "guias-de-remision"]


class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError("The Username field must be set")
        # Sensible a mayúsculas: se guarda el username exacto, sin lower/strip.
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password, **extra_fields):
        user = self.create_user(username, password, **extra_fields)
        user.is_superuser = True
        user.is_staff = True
        tienda, created = Tienda.objects.get_or_create(
        id=1,
        defaults={
            "nombre": "Tienda de Prueba",
            "direccion": "Sin direccion",
            "telefono": "000000000",
            "ruc": "00000000000",
            "activo": False,
        }
             )
        user.tienda = tienda

        user.save(using=self._db)

        # Seed portable (ORM, cualquier BD): planes iniciales + Demo
        # a todas las tiendas sin plan (incluye la de arriba).
        from apps.tienda.seeders import seed_planes
        seed_planes(using=self._db)

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
    is_deleted = models.BooleanField(default=False)
    tienda = models.ForeignKey(
       Tienda, on_delete=models.CASCADE, null=True, blank=True, related_name='users_tienda' # type: ignore
    )
    theme = models.CharField(
        max_length=10,
        choices=[("light", "Light"), ("dark", "Dark")],
        default="light",
    )
    navbar_type = models.CharField(
        max_length=10,
        choices=[("top", "Top"), ("normal", "Normal")],
        default="top",
    )
    modulos_habilitados = models.JSONField(
        default=default_modulos_habilitados,
        blank=True,
    )
    objects = UserManager()
    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["first_name","last_name"]

    class Meta:
        permissions = PERMISSIONS_META
        ordering = ["-date_created"]  # 👈 orden descendente por defecto (más recientes primero)


def __str__(self):
        return self.username



