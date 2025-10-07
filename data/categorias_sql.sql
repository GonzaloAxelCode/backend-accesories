INSERT INTO categoria_categoria 
(nombre, descripcion, fecha_creacion, fecha_actualizacion, activo, imagen, slug, orden, parent_id, destacado, tienda_id, color, siglas_nombre_categoria, date_created)
VALUES
('Micas y Protectores de Pantalla', 'Protectores de vidrio templado e hidrogel para smartphones', NOW(), NOW(), TRUE, NULL, 'micas-protectores', 1, NULL, FALSE, 2, '#4A90E2', 'MIC', NOW()),
('Carcasas y Fundas', 'Fundas protectoras de silicona, TPU y antigolpes', NOW(), NOW(), TRUE, NULL, 'carcasas-fundas', 2, NULL, FALSE, 2, '#50E3C2', 'CAR', NOW()),
('Cargadores y Cables', 'Cargadores rápidos, inalámbricos y cables reforzados', NOW(), NOW(), TRUE, NULL, 'cargadores-cables', 3, NULL, FALSE, 2, '#F5A623', 'CRG', NOW()),
('Accesorios Varios', 'Soportes, baterías externas, auriculares y más accesorios', NOW(), NOW(), TRUE, NULL, 'accesorios-varios', 4, NULL, TRUE, 2, '#9013FE', 'ACC', NOW());
