from django.urls import path
from .views import CreateCategoria, GetAllCategorias, GetCategoria, UpdateCategoria, DeactivateCategoria,DeleteCategoria, SeedCategoriasAccesorios, DeleteSeedCategoriasAccesorios

urlpatterns = [
    path('categorias/', GetAllCategorias.as_view(), name='get_all_categorias'),
    path('categorias/create/', CreateCategoria.as_view(), name='create_categoria'),
    path('categorias/seed-accesorios/', SeedCategoriasAccesorios.as_view(), name='seed_categorias_accesorios'),
    path('categorias/delete-seed-accesorios/', DeleteSeedCategoriasAccesorios.as_view(), name='delete_seed_categorias_accesorios'),
    path('categorias/<int:id>/', GetCategoria.as_view(), name='get_categoria'),
    path('categorias/update/<int:id>/', UpdateCategoria.as_view(), name='update_categoria'),
    path('categorias/deactivate/<int:id>/', DeactivateCategoria.as_view(), name='deactivate_categoria'),
    path('categorias/delete/<int:id>/', DeleteCategoria.as_view(), name='delete-categoria'),
]
