from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
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
    username = models.CharField(max_length=30, unique=True)  # Campo principal para autenticación
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
    desactivate_account = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'username'  # Definir username como identificador principal
    REQUIRED_FIELDS = []  # Campos requeridos además de username

    def __str__(self):
        return self.username
