# permissions.py
from rest_framework import permissions

class IsSuperUser(permissions.BasePermission):
 
    def has_permission(self, request, view):
        return request.user and request.user.is_superuser and request.user.is_authenticated 

    def has_object_permission(self, request, view, obj):
        return request.user and request.user.is_superuser  and request.user.is_authenticated 


from rest_framework import permissions


class HasCustomPermission(permissions.BasePermission):
    
    perm_code = None  # ejemplo: 'user.can_create_inventory'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.has_perm(self.perm_code)
        )
        
class CanMakeSalePermission(HasCustomPermission):
    perm_code = 'user.can_make_sale'

class CanCancelSalePermission(HasCustomPermission):
    perm_code = 'user.can_cancel_sale'

class CanCreateInventoryPermission(HasCustomPermission):
    perm_code = 'user.can_create_inventory'

class CanModifyInventoryPermission(HasCustomPermission):
    perm_code = 'user.can_modify_inventory'

class CanUpdateInventoryPermission(HasCustomPermission):
    perm_code = 'user.can_update_inventory'

class CanDeleteInventoryPermission(HasCustomPermission):
    perm_code = 'user.can_delete_inventory'

class CanCreateProductPermission(HasCustomPermission):
    perm_code = 'user.can_create_product'

class CanUpdateProductPermission(HasCustomPermission):
    perm_code = 'user.can_update_product'

class CanDeleteProductPermission(HasCustomPermission):
    perm_code = 'user.can_delete_product'

class CanCreateCategoryPermission(HasCustomPermission):
    perm_code = 'user.can_create_category'

class CanModifyCategoryPermission(HasCustomPermission):
    perm_code = 'user.can_modify_category'

class CanDeleteCategoryPermission(HasCustomPermission):
    perm_code = 'user.can_delete_category'

class CanCreateSupplierPermission(HasCustomPermission):
    perm_code = 'user.can_create_supplier'

class CanModifySupplierPermission(HasCustomPermission):
    perm_code = 'user.can_modify_supplier'

class CanDeleteSupplierPermission(HasCustomPermission):
    perm_code = 'user.can_delete_supplier'

class CanCreateStorePermission(HasCustomPermission):
    perm_code = 'user.can_create_store'

class CanModifyStorePermission(HasCustomPermission):
    perm_code = 'user.can_modify_store'

class CanDeleteStorePermission(HasCustomPermission):
    perm_code = 'user.can_delete_store'

class ViewSalePermission(HasCustomPermission):
    perm_code = 'user.view_sale'

class ViewInventoryPermission(HasCustomPermission):
    perm_code = 'user.view_inventory'

class ViewProductPermission(HasCustomPermission):
    perm_code = 'user.view_product'

class ViewCategoryPermission(HasCustomPermission):
    perm_code = 'user.view_category'

class ViewSupplierPermission(HasCustomPermission):
    perm_code = 'user.view_supplier'

class ViewStorePermission(HasCustomPermission):
    perm_code = 'user.view_store'

class CanCreateUserPermission(HasCustomPermission):
    perm_code = 'user.can_create_user'
class CanCreateProveedorPermission(HasCustomPermission):
    perm_code = 'user.can_create_proveedor'
class CanUpdateProveedorPermission(HasCustomPermission):
    perm_code = 'user.can_update_proveedor'
class CanDeleteProveedorPermission(HasCustomPermission):
    perm_code = 'user.can_delete_proveedor'