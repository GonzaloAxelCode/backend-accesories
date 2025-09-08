INSERT INTO inventario_inventario
(producto_id, tienda_id, cantidad, stock_minimo, stock_maximo, 
 fecha_actualizacion, activo, lote, fecha_vencimiento, 
 costo_compra, costo_venta, costo_docena, costo, estado, proveedor_id, responsable_id, descripcion)
SELECT 
    p.id AS producto_id,
    t.id AS tienda_id,                         
    FLOOR(RANDOM() * (200 - 50 + 1) + 50)::int AS cantidad,
    FLOOR(1)::int AS stock_minimo,
    FLOOR(100)::int AS stock_maximo,
    NOW(),
    TRUE,
    CONCAT('Lote-', p.id),
    NOW() + ((FLOOR(RANDOM() * (730 - 180 + 1) + 180)) || ' days')::interval,
    ROUND((RANDOM() * (1000 - 200) + 200)::numeric, 2),
    ROUND((RANDOM() * (1500 - 500) + 500)::numeric, 2),
    ROUND((RANDOM() * (1200 - 400) + 400)::numeric, 2),
    ROUND((RANDOM() * (1500 - 500) + 500)::numeric, 2),
    'DISPONIBLE',
    FLOOR(RANDOM() * 3 + 1)::int AS proveedor_id,  -- aleatorio 1, 2 o 3
    1,
    'Inventario inicial generado automáticamente'
FROM producto_producto p
JOIN tienda_tienda t ON t.id = 2; -- solo inserta si la tienda existe

