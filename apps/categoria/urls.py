from django.urls import path
from .views import CreateCategoria, GetAllCategorias, GetCategoria, UpdateCategoria, DeactivateCategoria

urlpatterns = [
    path('categorias/', GetAllCategorias.as_view(), name='get_all_categorias'),
    path('categorias/create/', CreateCategoria.as_view(), name='create_categoria'),
    path('categorias/<int:id>/', GetCategoria.as_view(), name='get_categoria'),
    path('categorias/update/<int:id>/', UpdateCategoria.as_view(), name='update_categoria'),
    path('categorias/deactivate/<int:id>/', DeactivateCategoria.as_view(), name='deactivate_categoria'),
]
