-- =========================================
-- 25 PRODUCTOS - ACCESORIOS CELULARES
-- Categorías alternadas (1,2,3,4)
-- Tienda = 2
-- =========================================
INSERT INTO producto_producto 
(nombre, descripcion, categoria_id, sku, marca, modelo, caracteristicas, fecha_creacion, fecha_actualizacion, activo, tienda_id)
VALUES
('Protector de Pantalla iPhone 14', 'Mica de vidrio templado anti-rasguños', 1, 'ACC-000001', 'Belkin', 'GLS14', '{"compatibilidad": "iPhone 14", "tipo": "Vidrio templado"}', NOW(), NOW(), TRUE, 2),
('Carcasa Transparente Samsung S23', 'Carcasa flexible TPU transparente', 2, 'ACC-000002', 'Spigen', 'CS23TPU', '{"compatibilidad": "Galaxy S23", "color": "Transparente"}', NOW(), NOW(), TRUE, 2),
('Cargador Rápido 25W', 'Cargador tipo C con carga rápida', 3, 'ACC-000003', 'Samsung', 'EP-TA800', '{"potencia": "25W", "puerto": "USB-C"}', NOW(), NOW(), TRUE, 2),
('Soporte Magnético para Auto', 'Soporte de celular magnético para rejilla', 4, 'ACC-000004', 'Baseus', 'MAGCAR01', '{"tipo": "Magnético", "rotacion": "360°"}', NOW(), NOW(), TRUE, 2),
('Auriculares Bluetooth TWS', 'Audífonos inalámbricos con estuche de carga', 1, 'ACC-000005', 'Xiaomi', 'RedmiBuds4', '{"autonomia": "20h", "color": "Negro"}', NOW(), NOW(), TRUE, 2),
('Cargador Inalámbrico Qi', 'Base de carga inalámbrica rápida', 2, 'ACC-000006', 'Anker', 'PowerWavePad', '{"potencia": "15W", "entrada": "USB-C"}', NOW(), NOW(), TRUE, 2),
('Carcasa Antigolpes iPhone 13', 'Carcasa con bordes reforzados', 3, 'ACC-000007', 'OtterBox', 'DEF13', '{"compatibilidad": "iPhone 13", "color": "Negro"}', NOW(), NOW(), TRUE, 2),
('Cable USB-C a Lightning 1m', 'Cable de carga rápida certificado MFI', 4, 'ACC-000008', 'Apple', 'MX0K2AM', '{"longitud": "1m", "tipo": "USB-C a Lightning"}', NOW(), NOW(), TRUE, 2),
('Mica Hidrogel Samsung A54', 'Protector flexible anti-huellas', 1, 'ACC-000009', 'Nillkin', 'HG-A54', '{"compatibilidad": "Galaxy A54", "tipo": "Hidrogel"}', NOW(), NOW(), TRUE, 2),
('Batería Externa 20000mAh', 'Power bank con carga rápida QC 3.0', 2, 'ACC-000010', 'Anker', 'A1271', '{"capacidad": "20000mAh", "puertos": "2 USB"}', NOW(), NOW(), TRUE, 2),
('Soporte de Escritorio Ajustable', 'Soporte plegable para celular y tablet', 3, 'ACC-000011', 'Ugreen', 'UG-DESK01', '{"ajustable": "Si", "material": "Aluminio"}', NOW(), NOW(), TRUE, 2),
('Carcasa con Anillo Giratorio', 'Carcasa con soporte 360°', 4, 'ACC-000012', 'Ringke', 'RING360', '{"compatibilidad": "Multimodelo", "color": "Rojo"}', NOW(), NOW(), TRUE, 2),
('Cargador Doble USB 30W', 'Cargador de pared con 2 puertos', 1, 'ACC-000013', 'Baseus', 'BS-30W', '{"puertos": "2 USB", "potencia": "30W"}', NOW(), NOW(), TRUE, 2),
('Cable USB-C 2m Reforzado', 'Cable trenzado de alta durabilidad', 2, 'ACC-000014', 'Anker', 'A8143', '{"longitud": "2m", "tipo": "USB-C"}', NOW(), NOW(), TRUE, 2),
('Carcasa Transparente iPhone 12', 'Carcasa de silicona flexible', 3, 'ACC-000015', 'Spigen', 'SP-IP12', '{"compatibilidad": "iPhone 12", "color": "Transparente"}', NOW(), NOW(), TRUE, 2),
('Mica de Privacidad iPhone 13', 'Protector de pantalla con filtro de privacidad', 4, 'ACC-000016', 'Belkin', 'PRV13', '{"compatibilidad": "iPhone 13", "tipo": "Privacidad"}', NOW(), NOW(), TRUE, 2),
('Soporte Selfie con Luz Led', 'Trípode ajustable con aro de luz', 1, 'ACC-000017', 'Xiaomi', 'SelfieLED', '{"altura": "1.6m", "luces": "LED"}', NOW(), NOW(), TRUE, 2),
('Auriculares con Cable Jack 3.5mm', 'Audífonos con micrófono incorporado', 2, 'ACC-000018', 'Sony', 'MDR-EX15AP', '{"conexion": "3.5mm", "color": "Blanco"}', NOW(), NOW(), TRUE, 2),
('Cargador para Auto 45W', 'Cargador rápido USB-C PD para auto', 3, 'ACC-000019', 'Ugreen', 'UG-CAR45', '{"puertos": "2 USB", "potencia": "45W"}', NOW(), NOW(), TRUE, 2),
('Carcasa Rugged Armor Samsung S22', 'Protección robusta antigolpes', 4, 'ACC-000020', 'Spigen', 'RUGS22', '{"compatibilidad": "Galaxy S22", "color": "Negro"}', NOW(), NOW(), TRUE, 2),
('Mica 9H Universal', 'Protector de vidrio templado genérico', 1, 'ACC-000021', 'Genérico', '9H-UNI', '{"compatibilidad": "Universal", "tipo": "Vidrio"}', NOW(), NOW(), TRUE, 2),
('Soporte de Bicicleta', 'Soporte ajustable para manubrio', 2, 'ACC-000022', 'Baseus', 'Bike01', '{"ajustable": "Si", "rotacion": "360°"}', NOW(), NOW(), TRUE, 2),
('Batería Externa 10000mAh', 'Power bank ultra compacto', 3, 'ACC-000023', 'Xiaomi', 'PB10000', '{"capacidad": "10000mAh", "puertos": "USB-C"}', NOW(), NOW(), TRUE, 2),
('Carcasa Glitter iPhone 11', 'Carcasa con brillo y diseño femenino', 4, 'ACC-000024', 'Casetify', 'GLT-IP11', '{"compatibilidad": "iPhone 11", "color": "Rosa"}', NOW(), NOW(), TRUE, 2),
('Cargador Rápido GaN 65W', 'Cargador compacto con tecnología GaN', 1, 'ACC-000025', 'Baseus', 'GAN65', '{"puertos": "USB-C + USB-A", "potencia": "65W"}', NOW(), NOW(), TRUE, 2);
