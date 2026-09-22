
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.tienda.models import Tienda
from apps.tienda.serializers import TiendaSerializer
from core.permissions import IsSuperUser, IsAdminTienda
from .models import UserAccount
from .serializers import CustomTokenObtainPairSerializer, UserAccountSerializer, UserSerializer
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import transaction
from rest_framework.permissions import IsAuthenticated        
User = get_user_model()
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404


from rest_framework import status

class GetAllUsersAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminTienda]

    def get(self, request, tienda_id=None):
        authenticated_user = request.user

        # 🔹 Validar si existe la tienda
        if not Tienda.objects.filter(id=tienda_id).exists():
            return Response(
                {"detail": f"No existe la tienda con id {tienda_id}."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 🔹 Si no es superuser, verificar que sea admin_tienda y que la tienda solicitada sea la suya o una sucursal suya
        if not authenticated_user.is_superuser:
            is_admin = authenticated_user.tienda and authenticated_user.tienda.propietario_id == authenticated_user.id  # type: ignore
            if not is_admin:
                return Response(
                    {"detail": "Solo superuser o admin_tienda puede listar usuarios."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            # Admin solo puede listar usuarios de su tienda principal o sucursales
            tienda_solicitada = Tienda.objects.get(id=tienda_id)
            allowed_ids = {authenticated_user.tienda.id}  # type: ignore
            # agregar sucursales
            allowed_ids.update(
                Tienda.objects.filter(tienda_padre=authenticated_user.tienda).values_list("id", flat=True)  # type: ignore
            )
            # agregar tiendas donde es propietario
            allowed_ids.update(
                Tienda.objects.filter(propietario=authenticated_user).values_list("id", flat=True)
            )
            if tienda_id not in allowed_ids:
                return Response(
                    {"detail": "No tienes permiso para ver usuarios de esta tienda."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # 🔹 Listar usuarios (superuser excluye self; admin_tienda incluye self marcado como deshabilitado)
        is_admin_requester = authenticated_user.tienda and authenticated_user.tienda.propietario_id == authenticated_user.id  # type: ignore
        if authenticated_user.is_superuser:
            # Superuser ve todos, incluso los is_deleted
            users_qs = UserAccount.objects.exclude(id=authenticated_user.id).filter(is_superuser=False, tienda_id=tienda_id)
            include_self = False
        elif is_admin_requester:
            # Admin ve activos y desactivados, pero no los is_deleted
            users_qs = UserAccount.objects.filter(is_superuser=False, is_deleted=False, tienda_id=tienda_id)
            include_self = True
        else:
            users_qs = UserAccount.objects.exclude(id=authenticated_user.id).filter(is_superuser=False, is_deleted=False, tienda_id=tienda_id)
            include_self = False
        users = users_qs
        ALL_PERMISSIONS = [
            "can_make_sale",
            "can_cancel_sale",
            "can_create_inventory",
            "can_modify_inventory",
            "can_update_inventory",
            "can_delete_inventory",
            "can_create_product",
            "can_update_product",
            "can_delete_product",
            "can_create_category",
            "can_modify_category",
            "can_delete_category",
            "can_create_supplier",
            "can_modify_supplier",
            "can_delete_supplier",
            "can_create_store",
            "can_modify_store",
            "can_delete_store",
            "view_sale",
            "view_inventory",
            "view_product",
            "view_category",
            "view_supplier",
            "view_store",
            "can_create_user",
            "can_create_proveedor",
            "can_update_proveedor",
            "can_delete_proveedor",
        ]

        all_system_permissions = Permission.objects.filter(codename__in=ALL_PERMISSIONS)

        users_data = []

        for user in users:
            user_permissions = user.user_permissions.all() | Permission.objects.filter(group__user=user)
            user_permission_codenames = set(user_permissions.values_list("codename", flat=True))

            permissions_dict = {
                perm.codename: perm.codename in user_permission_codenames
                for perm in all_system_permissions
            }

            is_self = (user.id == authenticated_user.id)  # type: ignore
            # Solo si es admin_tienda y es él mismo, deshabilitar edición de permisos
            can_modify_permissions = not (include_self and is_self)

            user_data = {
                "id": user.id, # type: ignore
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "photo_url": user.photo_url,
                "date_joined": user.date_joined,
                "is_active": user.is_active,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
                "es_empleado": user.es_empleado,
                "desactivate_account": user.desactivate_account,
                "is_deleted": user.is_deleted,
                "permissions": permissions_dict,
                "user_permissions_list": list(user_permission_codenames),
                "all_permissions_meta": ALL_PERMISSIONS,
                "tienda": user.tienda.id if user.tienda else None, # type: ignore
                "tienda_nombre": user.tienda.nombre if user.tienda else None,
                "is_self": is_self,
                "can_modify_permissions": can_modify_permissions,
                "disabled": is_self and include_self,  # para atenuar en gris en frontend
            }

            users_data.append(user_data)

        return Response(users_data, status=status.HTTP_200_OK)





class GetCurrentUserAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = get_object_or_404(UserAccount, id=request.user.id)

        # 🔹 1. Definir permisos manualmente (solo codenames)
        ALL_PERMISSIONS = [
            "can_make_sale",
            "can_cancel_sale",
            "can_create_inventory",
            "can_modify_inventory",
            "can_update_inventory",
            "can_delete_inventory",
            "can_create_product",
            "can_update_product",
            "can_delete_product",
            "can_create_category",
            "can_modify_category",
            "can_delete_category",
            "can_create_supplier",
            "can_modify_supplier",
            "can_delete_supplier",
            "can_create_store",
            "can_modify_store",
            "can_delete_store",
            "view_sale",
            "view_inventory",
            "view_product",
            "view_category",
            "view_supplier",
            "view_store",
            "can_create_user",
            "can_create_proveedor",
            "can_update_proveedor",
            "can_delete_proveedor",
        ]

        # 🔹 2. Obtener todos los permisos del usuario
        user_permissions_full = user.get_all_permissions()

        # 🔹 3. Extraer solo los codenames (ejemplo: 'can_make_sale')
        user_permission_codenames = [
            perm.split('.')[1] for perm in user_permissions_full
        ]

        # 🔹 4. Crear el diccionario con True / False
        permissions_dict = {
            perm: perm in user_permission_codenames for perm in ALL_PERMISSIONS
        }
        tienda_data = (
            TiendaSerializer(
                user.tienda,
                context={"request": request}  # útil para URLs absolutas
            ).data
            if user.tienda else None
        )

        # 🔹 5. Determinar rol y si es propietario (mismo criterio que CustomTokenObtainPairView)
        if user.is_superuser:
            rol = "superuser"
        elif user.tienda and user.tienda.propietario_id == user.id:  # type: ignore
            rol = "admin_tienda"
        elif user.es_empleado:
            rol = "empleado"
        else:
            rol = "usuario"

        es_propietario = bool(user.tienda and user.tienda.propietario_id == user.id)  # type: ignore
        es_admin_tienda = es_propietario  # alias para frontend

        # 🔹 6. Construir la respuesta
        response_data = {
            'id': user.id,  # type: ignore
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'photo_url': user.photo_url,
            'date_joined': user.date_joined,
            'is_active': user.is_active,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'es_empleado': user.es_empleado,
            'desactivate_account': user.desactivate_account,
            'permissions': permissions_dict,
            'user_permissions_list': user_permission_codenames,
            'all_permissions_meta': ALL_PERMISSIONS,
            'tienda': user.tienda.id if user.tienda else None,  # type: ignore
            'tienda_nombre': user.tienda.nombre if user.tienda else None,
            'tienda_data': tienda_data,
            'rol': rol,
            'es_propietario': es_propietario,
            'es_admin_tienda': es_admin_tienda,
            'theme': user.theme,
            'navbar_type': user.navbar_type,
            'modulos_habilitados': user.modulos_habilitados,

        }

        return Response(response_data, status=status.HTTP_200_OK)
    
class CreateUserInTiendaAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminTienda]

    @transaction.atomic
    def post(self, request, tienda_id):
        # Verificar permiso admin_tienda si no es superuser
        if not request.user.is_superuser:
            is_admin = request.user.tienda and request.user.tienda.propietario_id == request.user.id  # type: ignore
            if not is_admin:
                return Response(
                    {"detail": "Solo superuser o admin_tienda puede crear usuarios."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            # Admin solo puede crear en su tienda o sucursales
            allowed_ids = {request.user.tienda.id}  # type: ignore
            allowed_ids.update(
                Tienda.objects.filter(tienda_padre=request.user.tienda).values_list("id", flat=True)  # type: ignore
            )
            allowed_ids.update(
                Tienda.objects.filter(propietario=request.user).values_list("id", flat=True)
            )
            if tienda_id not in allowed_ids:
                return Response(
                    {"detail": "No puedes crear usuarios en esta tienda."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        tienda = get_object_or_404(Tienda, id=tienda_id)

        from apps.tienda.utils import renovar_si_vencido, get_estado_limites
        renovar_si_vencido(tienda)
        # Bloqueo por límite de personal del plan (superuser bypass)
        if not request.user.is_superuser:
            estado = get_estado_limites(tienda)
            if estado["excede_personal"]:
                return Response(
                    {
                        "error": f'Límite de personal del plan alcanzado ({estado["num_personal"]}/{estado["limite_personal"]}).',
                        "uso": estado["num_personal"],
                        "limite": estado["limite_personal"],
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Clonar los datos y forzar la tienda
        data = request.data.copy()
        data["tienda"] = tienda.id  # type: ignore

        # `is_propietario` (bool o "true"/"false" por form-data): si es true,
        # el nuevo usuario pasa a ser propietario de la tienda (rol
        # admin_tienda de su misma tienda). No es campo del modelo: se retira
        # antes de validar el serializer.
        es_propietario_raw = data.pop("is_propietario", False)
        if isinstance(es_propietario_raw, list):
            es_propietario_raw = es_propietario_raw[-1] if es_propietario_raw else False
        es_propietario = (
            es_propietario_raw is True
            or (isinstance(es_propietario_raw, str) and es_propietario_raw.strip().lower() == "true")
            or (isinstance(es_propietario_raw, int) and not isinstance(es_propietario_raw, bool) and es_propietario_raw == 1)
        )
        # Validar ANTES de crear: la sucursal hereda el propietario del padre.
        if es_propietario and tienda.tienda_padre_id:
            return Response(
                {"error": "No puedes asignar propietario a una sucursal: hereda el propietario de la tienda padre."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = UserAccountSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Guardar el nuevo usuario
        user = serializer.save()
        if isinstance(user, list):  # ✅ En caso de que devuelva lista
            user = user[0]

        # Nuevo dueño de la tienda (ya validado arriba que es principal).
        # El usuario ya quedó con tienda = esta tienda, así que su rol
        # pasa a ser admin_tienda.
        if es_propietario:
            tienda.propietario = user
            tienda.save(update_fields=["propietario"])

        # 🔹 Definir los permisos (igual que en GetCurrentUserAPIView)
        ALL_PERMISSIONS = [
            "can_make_sale",
            "can_cancel_sale",
            "can_create_inventory",
            "can_modify_inventory",
            "can_update_inventory",
            "can_delete_inventory",
            "can_create_product",
            "can_update_product",
            "can_delete_product",
            "can_create_category",
            "can_modify_category",
            "can_delete_category",
            "can_create_supplier",
            "can_modify_supplier",
            "can_delete_supplier",
            "can_create_store",
            "can_modify_store",
            "can_delete_store",
            "view_sale",
            "view_inventory",
            "view_product",
            "view_category",
            "view_supplier",
            "view_store",
            "can_create_user",
            "can_create_proveedor",
            "can_update_proveedor",
            "can_delete_proveedor",
        ]

        # 🔹 Obtener los permisos reales del nuevo usuario
        user_permissions_full = user.get_all_permissions()  # type: ignore
        user_permission_codenames = [
            perm.split('.')[1] for perm in user_permissions_full
        ]

        permissions_dict = {
            perm: perm in user_permission_codenames for perm in ALL_PERMISSIONS
        }

        # 🔹 Armar la respuesta igual que en GetCurrentUserAPIView
        # (se usa `tienda` —ya actualizada si se asignó dueño— porque
        # user.tienda en memoria puede estar desactualizada).
        if user.is_superuser:
            rol_nuevo = "superuser"
        elif tienda.propietario_id is not None and tienda.propietario_id == user.id:  # type: ignore
            rol_nuevo = "admin_tienda"
        elif user.es_empleado:
            rol_nuevo = "empleado"
        else:
            rol_nuevo = "usuario"
        response_data = {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'photo_url': user.photo_url,
            'date_joined': user.date_joined,
            'is_active': user.is_active,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'es_empleado': user.es_empleado,
            'desactivate_account': user.desactivate_account,
            'permissions': permissions_dict,
            'user_permissions_list': user_permission_codenames,
            'all_permissions_meta': ALL_PERMISSIONS,
            'tienda': user.tienda.id if user.tienda else None,
            'tienda_nombre': user.tienda.nombre if user.tienda else None,
            'rol': rol_nuevo,
            'es_propietario': rol_nuevo == "admin_tienda",
        }

        return Response(
            {"message": "Usuario creado exitosamente", "usuario": response_data},
            status=status.HTTP_201_CREATED,
        )
    
class UpdateUserAPIView(APIView):
    permission_classes = [IsAuthenticated,IsAdminTienda]
    def put(self, request, id):
        user = get_object_or_404(UserAccount, id=id)
        # Admin solo puede editar usuarios de su tienda/sucursales
        if not request.user.is_superuser:
            is_admin = request.user.tienda and request.user.tienda.propietario_id == request.user.id  # type: ignore
            if not is_admin:
                return Response({"detail": "Solo superuser o admin_tienda puede actualizar usuarios."}, status=status.HTTP_403_FORBIDDEN)
            allowed_tienda_ids = {request.user.tienda.id}  # type: ignore
            allowed_tienda_ids.update(Tienda.objects.filter(tienda_padre=request.user.tienda).values_list("id", flat=True))  # type: ignore
            allowed_tienda_ids.update(Tienda.objects.filter(propietario=request.user).values_list("id", flat=True))
            if not user.tienda_id or user.tienda_id not in allowed_tienda_ids:
                return Response({"detail": "No puedes editar usuarios fuera de tu tienda."}, status=status.HTTP_403_FORBIDDEN)
            # No permitir que admin escale a superuser
            if request.data.get("is_superuser"):
                return Response({"detail": "No puedes asignar superuser."}, status=status.HTTP_403_FORBIDDEN)
        serializer = UserAccountSerializer(user, data=request.data, partial=True) 
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Usuario actualizado exitosamente",
                "user": serializer.data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




class UpdateUserPermissionsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminTienda]

    def put(self, request, user_id):
        try:
            # 🔹 Obtener el usuario
            user = UserAccount.objects.get(id=user_id)
            # 🔹 Validar scope admin_tienda
            if not request.user.is_superuser:
                is_admin = request.user.tienda and request.user.tienda.propietario_id == request.user.id  # type: ignore
                if not is_admin:
                    return Response({"detail": "Solo superuser o admin_tienda puede actualizar permisos."}, status=status.HTTP_403_FORBIDDEN)
                allowed_ids = {request.user.tienda.id}  # type: ignore
                allowed_ids.update(Tienda.objects.filter(tienda_padre=request.user.tienda).values_list("id", flat=True))  # type: ignore
                allowed_ids.update(Tienda.objects.filter(propietario=request.user).values_list("id", flat=True))
                if not user.tienda_id or user.tienda_id not in allowed_ids:
                    return Response({"detail": "No puedes modificar permisos fuera de tu tienda."}, status=status.HTTP_403_FORBIDDEN)
            # Bloquear auto-modificación de permisos (admin no puede cambiarse a sí mismo)
            if user.id == request.user.id:  # type: ignore
                return Response({"detail": "No puedes modificar tus propios permisos."}, status=status.HTTP_403_FORBIDDEN)
        except UserAccount.DoesNotExist:
            return Response(
                {"error": "Usuario no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 🔹 Extraer el permiso individual
        perm_codename = request.data.get("permiso")
        valor = request.data.get("valor")

        if not perm_codename or valor is None:
            return Response(
                {"error": "Debes enviar 'permiso' y 'valor' (true/false)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 🔹 Actualizar solo ese permiso dentro de una transacción
        with transaction.atomic():
            try:
                permiso = Permission.objects.get(codename=perm_codename)
            except Permission.DoesNotExist:
                return Response(
                    {"error": f"Permiso '{perm_codename}' no encontrado."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if valor is True or valor == "true":
                user.user_permissions.add(permiso)
            elif valor is False or valor == "false":
                user.user_permissions.remove(permiso)
            else:
                return Response(
                    {"error": "'valor' debe ser true o false."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # 🔹 Confirmar permisos actualizados
        updated_permissions = list(user.user_permissions.values_list("codename", flat=True))

        return Response(
            {
                "message": f"Permiso '{perm_codename}' actualizado correctamente.",
                "updated_permissions": updated_permissions,
            },
            status=status.HTTP_200_OK,
        )
        
        
class UpdateUserPermissionsViewLOTE(APIView):
    permission_classes = [IsAuthenticated,IsAdminTienda]
    def put(self, request, user_id):
        try:
            print("******** antes ")
            user = UserAccount.objects.get(id=user_id)
            print(user.user_permissions.values_list("codename", flat=True))
            print("******** despues ")
            # Validar scope admin_tienda si no es superuser
            if not request.user.is_superuser:
                is_admin = request.user.tienda and request.user.tienda.propietario_id == request.user.id  # type: ignore
                if not is_admin:
                    return Response({"detail": "Solo superuser o admin_tienda puede actualizar permisos en lote."}, status=status.HTTP_403_FORBIDDEN)
                allowed_ids = {request.user.tienda.id}  # type: ignore
                allowed_ids.update(Tienda.objects.filter(tienda_padre=request.user.tienda).values_list("id", flat=True))  # type: ignore
                allowed_ids.update(Tienda.objects.filter(propietario=request.user).values_list("id", flat=True))
                if not user.tienda_id or user.tienda_id not in allowed_ids:
                    return Response({"detail": "No puedes modificar permisos fuera de tu tienda."}, status=status.HTTP_403_FORBIDDEN)
            if user.id == request.user.id:  # type: ignore
                return Response({"detail": "No puedes modificar tus propios permisos."}, status=status.HTTP_403_FORBIDDEN)
        except UserAccount.DoesNotExist:
            return Response({"error": "Usuario no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        
        # Extraer los permisos enviados en el request
        permissions_data = request.data.get("permissions", {})
        if not isinstance(permissions_data, dict):
            return Response({"error": "La propiedad 'permissions' debe ser un diccionario."}, status=status.HTTP_400_BAD_REQUEST)
        

        # Validar permisos y actualizar en una transacción
        with transaction.atomic():
            for perm_codename, value in permissions_data.items():
                try:
                    # Buscar el permiso por su `codename`
                    permission = Permission.objects.get(codename=perm_codename)
                    if value:  # Si el valor es True, agregar el permiso al usuario
                        user.user_permissions.add(permission)
                    else:  # Si el valor es False, remover el permiso del usuario
                        user.user_permissions.remove(permission)
                except Permission.DoesNotExist:
                    return Response({"error": f"Permiso '{perm_codename}' no encontrado."}, status=status.HTTP_400_BAD_REQUEST)

        # Confirmar permisos actualizados
        updated_permissions = user.user_permissions.values_list("codename", flat=True)
        user.save()
        print(user.user_permissions.values_list("codename", flat=True))
        return Response({
            "message": "Permisos actualizados correctamente.",
            "updated_permissions": list(updated_permissions),
        }, status=status.HTTP_200_OK)



class ToggleUserDeletedAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminTienda]

    def patch(self, request, id):
        user = get_object_or_404(UserAccount, id=id)

        if not request.user.is_superuser:
            is_admin = request.user.tienda and request.user.tienda.propietario_id == request.user.id  # type: ignore
            if not is_admin:
                return Response({"detail": "Solo superuser o admin_tienda puede modificar usuarios."}, status=status.HTTP_403_FORBIDDEN)
            allowed_ids = {request.user.tienda.id}  # type: ignore
            allowed_ids.update(Tienda.objects.filter(tienda_padre=request.user.tienda).values_list("id", flat=True))  # type: ignore
            allowed_ids.update(Tienda.objects.filter(propietario=request.user).values_list("id", flat=True))
            if not user.tienda_id or user.tienda_id not in allowed_ids:
                return Response({"detail": "No puedes modificar usuarios fuera de tu tienda."}, status=status.HTTP_403_FORBIDDEN)

        if user.is_superuser:
            return Response({"detail": "No puedes modificar un superuser."}, status=status.HTTP_403_FORBIDDEN)

        value = request.data.get("is_deleted", None)
        new_value = not user.is_deleted if value is None else bool(value)

        user.is_deleted = new_value
        user.is_active = not new_value

        if new_value:
            deleted_tag = f"is_deleted_{user.id}"
            user.username = deleted_tag
            user.first_name = deleted_tag
            user.save()
        else:
            user.save()

        return Response({
            "message": "Estado de eliminación actualizado.",

            "id": user.id,
            "is_deleted": user.is_deleted,
            "is_active": user.is_active,
            "username": user.username,
            "first_name": user.first_name,
        }, status=status.HTTP_200_OK)


class UpdateUserBasicDataAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminTienda]

    def patch(self, request, id):
        user = get_object_or_404(UserAccount, id=id)

        # Validar scope (superuser o admin de su tienda/sucursales)
        if not request.user.is_superuser:
            is_admin = request.user.tienda and request.user.tienda.propietario_id == request.user.id  # type: ignore
            if not is_admin:
                return Response({"detail": "Solo superuser o admin_tienda puede actualizar usuarios."}, status=status.HTTP_403_FORBIDDEN)
            allowed_ids = {request.user.tienda.id}  # type: ignore
            allowed_ids.update(Tienda.objects.filter(tienda_padre=request.user.tienda).values_list("id", flat=True))  # type: ignore
            allowed_ids.update(Tienda.objects.filter(propietario=request.user).values_list("id", flat=True))
            if not user.tienda_id or user.tienda_id not in allowed_ids:
                return Response({"detail": "No puedes modificar usuarios fuera de tu tienda."}, status=status.HTTP_403_FORBIDDEN)
        if user.is_superuser:
            return Response({"detail": "No puedes modificar un superuser."}, status=status.HTTP_403_FORBIDDEN)

        # Solo se actualizan estos tres campos, sin importar is_deleted/is_active
        username = request.data.get("username")
        first_name = request.data.get("first_name")
        last_name = request.data.get("last_name")

        if username is not None:
            if not str(username):
                return Response({"error": "username no puede estar vacío."}, status=status.HTTP_400_BAD_REQUEST)
            # Sensible a mayúsculas: se guarda exacto, sin lower/strip.
            user.username = str(username)
        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name

        try:
            user.save()
        except Exception as e:
            return Response({"error": f"No se pudo guardar: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "message": "Datos básicos actualizados exitosamente.",
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_deleted": user.is_deleted,
            "is_active": user.is_active,
        }, status=status.HTTP_200_OK)

class UserPermissionsView(APIView):
    permission_classes = [IsAuthenticated,IsAdminTienda]
    def get(self, request):
        user = request.user
        all_permissions = dict(
            (perm[0], user.has_perm(f"app.{perm[0]}")) for perm in UserAccount._meta.permissions
        )
        return Response({
            "username": user.username,
            "permissions": all_permissions
        })

class AdminResetPasswordAPIView(APIView):
    permission_classes = [IsAuthenticated, IsSuperUser]

    def post(self, request, id):
        user = get_object_or_404(UserAccount, id=id)

        new_password = request.data.get("new_password")
        if not new_password:
            return Response({"error": "Debes enviar 'new_password'."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        return Response({
            "message": "Contraseña actualizada exitosamente.",
            "id": user.id,
            "username": user.username,
        }, status=status.HTTP_200_OK)
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tokens = serializer.validated_data
        user = serializer.user

        # Determinar el rol del usuario
        if user.is_superuser:
            rol = "superuser"
        elif user.tienda and user.tienda.propietario == user:
            rol = "admin_tienda"
        elif user.es_empleado:
            rol = "empleado"
        else:
            rol = "usuario"

        # Contar tiendas del usuario
        tiendas_count = user.tiendas_propias.count() if hasattr(user, 'tiendas_propias') else 0
        tienda_data = None
        tiendas_hijas_count = 0

        if user.tienda:
            from apps.tienda.serializers import TiendaSerializer
            tienda_data = TiendaSerializer(user.tienda).data
            tiendas_hijas_count = user.tienda.sucursales.filter(is_deleted=False).count()

        return Response({
            "refresh": tokens["refresh"],
            "access": tokens["access"],
            "user_id": user.id,
            "user": UserSerializer(user).data,
            "tienda": tienda_data,
            "rol": rol,
            "mis_tiendas_count": tiendas_count,
            "mis_sucursales_count": tiendas_hijas_count,
        })

class UserConfigUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        user = request.user

        theme = request.data.get("theme")
        navbar_type = request.data.get("navbar_type")
        modulos_habilitados = request.data.get("modulos_habilitados")

        if theme is not None:
            if theme not in ["light", "dark"]:
                return Response(
                    {"error": "theme debe ser 'light' o 'dark'."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.theme = theme

        if navbar_type is not None:
            if navbar_type not in ["top", "normal"]:
                return Response(
                    {"error": "navbar_type debe ser 'top' o 'normal'."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.navbar_type = navbar_type

        if modulos_habilitados is not None:
            if not isinstance(modulos_habilitados, list):
                return Response(
                    {"error": "modulos_habilitados debe ser un arreglo."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.modulos_habilitados = modulos_habilitados

        user.save()
        return Response(
            {
                "message": "Configuración actualizada exitosamente.",
                "theme": user.theme,
                "navbar_type": user.navbar_type,
                "modulos_habilitados": user.modulos_habilitados,
            },
            status=status.HTTP_200_OK,
        )


class UpdatePermissionsAPIView(APIView):

    permission_classes = [IsAuthenticated,IsAdminTienda]
    def patch(self, request, user_id):
        try:
            # Verifica que sea superuser o admin_tienda
            is_admin = request.user.is_superuser or (request.user.tienda and request.user.tienda.propietario_id == request.user.id)  # type: ignore
            if not is_admin:
                return Response(
                    {"error": "No tienes permisos para realizar esta acción."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Obtiene el usuario al que se le asignarán los permisos
            user = User.objects.get(id=user_id)

            # Si es admin_tienda, validar que el target esté en su tienda/sucursales
            if not request.user.is_superuser:
                allowed_ids = {request.user.tienda.id}  # type: ignore
                allowed_ids.update(Tienda.objects.filter(tienda_padre=request.user.tienda).values_list("id", flat=True))  # type: ignore
                allowed_ids.update(Tienda.objects.filter(propietario=request.user).values_list("id", flat=True))
                if not user.tienda_id or user.tienda_id not in allowed_ids:
                    return Response({"error": "No puedes modificar permisos fuera de tu tienda."}, status=status.HTTP_403_FORBIDDEN)
            if user.id == request.user.id:  # type: ignore
                return Response({"error": "No puedes modificar tus propios permisos."}, status=status.HTTP_403_FORBIDDEN)

            # Datos enviados en el cuerpo de la solicitud
            permissions_data = request.data  # Ejemplo: {"can_make_sale": true, "can_delete_inventory": false}

            if not isinstance(permissions_data, dict):
                return Response(
                    {"error": "Los datos enviados deben ser un diccionario."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Procesa cada permiso enviado
            for codename, has_permission in permissions_data.items():
                if not isinstance(has_permission, bool):
                    return Response(
                        {"error": f"El valor de '{codename}' debe ser un booleano."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Busca el permiso en el sistema
                try:
                    perm = Permission.objects.get(codename=codename)
                except Permission.DoesNotExist:
                    return Response(
                        {"error": f"El permiso '{codename}' no existe."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                # Asigna o elimina el permiso
                if has_permission:
                    user.user_permissions.add(perm)
                else:
                    user.user_permissions.remove(perm)

            return Response(
                {"message": "Permisos actualizados exitosamente."},
                status=status.HTTP_200_OK,
            )

        except User.DoesNotExist:
            return Response(
                {"error": "Usuario no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )