-- =========================================
-- 25 PRODUCTOS - CATEGORÍA 1 (ELECTRÓNICA)
-- =========================================
INSERT INTO producto_producto (nombre, descripcion, categoria_id, sku, marca, modelo, caracteristicas, fecha_creacion, fecha_actualizacion, activo, tienda_id)
VALUES
('iPhone 14 Pro', 'Smartphone de última generación con cámara triple', 2, 'CAT1-000001', 'Apple', 'A2890', '{"color": "Negro espacial", "almacenamiento": "256GB"}', NOW(), NOW(), TRUE, 2),
('Samsung Galaxy S23', 'Teléfono inteligente con pantalla Dynamic AMOLED', 2, 'CAT1-000002', 'Samsung', 'SM-S911B', '{"color": "Crema", "almacenamiento": "128GB"}', NOW(), NOW(), TRUE, 2),
('Xiaomi Redmi Note 12', 'Smartphone gama media con gran batería', 2, 'CAT1-000003', 'Xiaomi', '2209116AG', '{"color": "Azul", "bateria": "5000mAh"}', NOW(), NOW(), TRUE, 2),
('Sony WH-1000XM5', 'Auriculares inalámbricos con cancelación de ruido', 2, 'CAT1-000004', 'Sony', 'WH1000XM5', '{"color": "Negro", "tipo": "Over-Ear"}', NOW(), NOW(), TRUE, 2),
('MacBook Air M2', 'Laptop ultraligera con chip Apple M2', 2, 'CAT1-000005', 'Apple', 'MLXY3', '{"pantalla": "13.6", "ram": "8GB"}', NOW(), NOW(), TRUE, 2),
('Dell XPS 13', 'Ultrabook con diseño premium y pantalla InfinityEdge', 2, 'CAT1-000006', 'Dell', 'XPS9320', '{"procesador": "Intel i7", "ram": "16GB"}', NOW(), NOW(), TRUE, 2),
('iPad Pro 12.9', 'Tablet profesional con pantalla Liquid Retina XDR', 2, 'CAT1-000007', 'Apple', 'A2764', '{"almacenamiento": "512GB", "color": "Plata"}', NOW(), NOW(), TRUE, 2),
('Samsung Galaxy Tab S8', 'Tablet de alto rendimiento con S Pen incluido', 2, 'CAT1-000008', 'Samsung', 'SM-X800', '{"pantalla": "11", "almacenamiento": "256GB"}', NOW(), NOW(), TRUE, 2),
('Kindle Paperwhite', 'E-reader con luz frontal regulable y resistente al agua', 2, 'CAT1-000009', 'Amazon', 'DP75SDI', '{"pantalla": "6.8", "almacenamiento": "16GB"}', NOW(), NOW(), TRUE, 2),
('GoPro Hero 11', 'Cámara deportiva 5K con estabilización avanzada', 2, 'CAT1-000010', 'GoPro', 'CHDHX-111', '{"resolucion": "5.3K", "sumergible": "10m"}', NOW(), NOW(), TRUE, 2),
('Canon EOS R7', 'Cámara mirrorless avanzada con sensor APS-C', 2, 'CAT1-000011', 'Canon', 'R7', '{"megapixeles": "32.5MP", "video": "4K"}', NOW(), NOW(), TRUE, 2),
('Nikon Z6 II', 'Cámara sin espejo de fotograma completo', 2, 'CAT1-000012', 'Nikon', 'Z6II', '{"resolucion": "24.5MP", "ISO": "100-51200"}', NOW(), NOW(), TRUE, 2),
('LG OLED C2 55', 'Smart TV con tecnología OLED y Dolby Vision', 2, 'CAT1-000013', 'LG', 'OLED55C2', '{"resolucion": "4K", "tamano": "55"}', NOW(), NOW(), TRUE, 2),
('Samsung QN90B 65', 'Smart TV Neo QLED con Mini LED', 2, 'CAT1-000014', 'Samsung', 'QN65QN90B', '{"resolucion": "4K", "tamano": "65"}', NOW(), NOW(), TRUE, 2),
('PlayStation 5', 'Consola de videojuegos de nueva generación', 2, 'CAT1-000015', 'Sony', 'CFI-1215A', '{"almacenamiento": "825GB SSD"}', NOW(), NOW(), TRUE, 2),
('Xbox Series X', 'Consola potente con soporte para 4K gaming', 2, 'CAT1-000016', 'Microsoft', 'RRT-00010', '{"almacenamiento": "1TB SSD"}', NOW(), NOW(), TRUE, 2),
('Nintendo Switch OLED', 'Consola híbrida portátil y de sobremesa', 2, 'CAT1-000017', 'Nintendo', 'HEG-001', '{"pantalla": "7 OLED", "almacenamiento": "64GB"}', NOW(), NOW(), TRUE, 2),
('Logitech MX Master 3S', 'Mouse inalámbrico avanzado para productividad', 2, 'CAT1-000018', 'Logitech', '910-006559', '{"dpi": "8000", "conexion": "Bluetooth"}', NOW(), NOW(), TRUE, 2),
('Razer BlackWidow V3', 'Teclado mecánico gamer con switches verdes', 2, 'CAT1-000019', 'Razer', 'RZ03-0354', '{"retroiluminacion": "RGB"}', NOW(), NOW(), TRUE, 2),
('Corsair K70 RGB Pro', 'Teclado mecánico para gaming competitivo', 2, 'CAT1-000020', 'Corsair', 'CH-9109410', '{"switches": "Cherry MX Red"}', NOW(), NOW(), TRUE, 2),
('Seagate BarraCuda 2TB', 'Disco duro interno de alto rendimiento', 2, 'CAT1-000021', 'Seagate', 'ST2000DM008', '{"tipo": "HDD", "capacidad": "2TB"}', NOW(), NOW(), TRUE, 2),
('Samsung 980 Pro 1TB', 'SSD NVMe de alta velocidad PCIe 4.0', 2, 'CAT1-000022', 'Samsung', 'MZ-V8P1T0B', '{"tipo": "SSD", "capacidad": "1TB"}', NOW(), NOW(), TRUE, 2),
('Western Digital My Passport 4TB', 'Disco duro portátil compacto', 2, 'CAT1-000023', 'WD', 'WDBPKJ0040BBK', '{"tipo": "HDD", "capacidad": "4TB"}', NOW(), NOW(), TRUE, 2),
('Anker PowerCore 20000', 'Batería externa de carga rápida', 2, 'CAT1-000024', 'Anker', 'A1271', '{"capacidad": "20000mAh", "puertos": "2 USB"}', NOW(), NOW(), TRUE, 2),
('Apple Watch Series 8', 'Reloj inteligente con sensor de temperatura', 2, 'CAT1-000025', 'Apple', 'A2771', '{"tamano": "45mm", "conectividad": "GPS"}', NOW(), NOW(), TRUE, 2);

-- =========================================
-- 25 PRODUCTOS - CATEGORÍA 2 (ROPA)
-- =========================================
INSERT INTO producto_producto (nombre, descripcion, categoria_id, sku, marca, modelo, caracteristicas, fecha_creacion, fecha_actualizacion, activo, tienda_id)
VALUES
('Polo Básico', 'Polo de algodón 100% en diferentes tallas', 2, 'CAT2-000001', 'Uniqlo', 'UT100', '{"color": "Blanco", "talla": "M"}', NOW(), NOW(), TRUE, 2),
('Camisa Oxford', 'Camisa formal de manga larga', 2, 'CAT2-000002', 'Zara', 'OX200', '{"color": "Celeste", "talla": "L"}', NOW(), NOW(), TRUE, 2),
('Jeans Slim Fit', 'Pantalón vaquero azul clásico', 2, 'CAT2-000003', 'Levis', '511', '{"talla": "32", "largo": "30"}', NOW(), NOW(), TRUE, 2),
('Chaqueta de Cuero', 'Chaqueta estilo biker con cierres metálicos', 2, 'CAT2-000004', 'H&M', 'LC300', '{"color": "Negro", "talla": "M"}', NOW(), NOW(), TRUE, 2),
('Zapatillas Running', 'Calzado deportivo para correr', 2, 'CAT2-000005', 'Nike', 'AirZoom', '{"color": "Rojo", "talla": "42"}', NOW(), NOW(), TRUE, 2),
('Zapatillas Casual', 'Sneakers de uso diario', 2, 'CAT2-000006', 'Adidas', 'StanSmith', '{"color": "Blanco", "talla": "41"}', NOW(), NOW(), TRUE, 2),
('Buzo Deportivo', 'Conjunto deportivo de algodón', 2, 'CAT2-000007', 'Puma', 'Track01', '{"color": "Gris", "talla": "L"}', NOW(), NOW(), TRUE, 2),
('Parka Impermeable', 'Abrigo resistente a la lluvia', 2, 'CAT2-000008', 'Columbia', 'RainTech', '{"color": "Verde oliva", "talla": "XL"}', NOW(), NOW(), TRUE, 2),
('Vestido Floral', 'Vestido de verano estampado', 2, 'CAT2-000009', 'Forever21', 'F21V100', '{"color": "Multicolor", "talla": "S"}', NOW(), NOW(), TRUE, 2),
('Falda Denim', 'Falda corta de mezclilla azul', 2, 'CAT2-000010', 'Mango', 'DNM200', '{"talla": "M"}', NOW(), NOW(), TRUE, 2),
('Blazer Slim Fit', 'Saco formal ajustado', 2, 'CAT2-000011', 'Massimo Dutti', 'MD500', '{"color": "Azul marino", "talla": "50"}', NOW(), NOW(), TRUE, 2),
('Pantalón Chino', 'Pantalón casual beige', 2, 'CAT2-000012', 'Dockers', 'CH700', '{"talla": "34", "largo": "32"}', NOW(), NOW(), TRUE, 2),
('Sudadera con Capucha', 'Hoodie unisex con bolsillo frontal', 2, 'CAT2-000013', 'Champion', 'HOOD01', '{"color": "Negro", "talla": "L"}', NOW(), NOW(), TRUE, 2),
('Short Deportivo', 'Short de poliéster transpirable', 2, 'CAT2-000014', 'Reebok', 'RBK300', '{"color": "Azul", "talla": "M"}', NOW(), NOW(), TRUE, 2),
('Abrigo Largo', 'Abrigo elegante para invierno', 2, 'CAT2-000015', 'Mango', 'AB800', '{"color": "Beige", "talla": "M"}', NOW(), NOW(), TRUE, 2),
('Polo Polo Ralph Lauren', 'Polo clásico con logo bordado', 2, 'CAT2-000016', 'Ralph Lauren', 'RL100', '{"color": "Verde", "talla": "L"}', NOW(), NOW(), TRUE, 2),
('Camiseta Gráfica', 'Camiseta con estampado moderno', 2, 'CAT2-000017', 'Pull&Bear', 'PB400', '{"color": "Negro", "talla": "S"}', NOW(), NOW(), TRUE, 2),
('Top Deportivo', 'Top para entrenamiento de alto impacto', 2, 'CAT2-000018', 'Nike', 'NTOP01', '{"color": "Rosa", "talla": "M"}', NOW(), NOW(), TRUE, 2),
('Leggings Deportivos', 'Leggings elásticos para yoga', 2, 'CAT2-000019', 'Adidas', 'ADLG01', '{"color": "Negro", "talla": "S"}', NOW(), NOW(), TRUE, 2),
('Sandalias de Cuero', 'Sandalias casuales de piel', 2, 'CAT2-000020', 'Clarks', 'CL100', '{"color": "Marron", "talla": "40"}', NOW(), NOW(), TRUE, 2),
('Botines de Gamuza', 'Calzado de gamuza para invierno', 2, 'CAT2-000021', 'Timberland', 'TB200', '{"color": "Marron claro", "talla": "43"}', NOW(), NOW(), TRUE, 2),
('Pijama de Algodón', 'Conjunto de pijama cómodo', 2, 'CAT2-000022', 'Oysho', 'PJ100', '{"talla": "M"}', NOW(), NOW(), TRUE, 2),
('Traje de Baño Bikini', 'Bikini de dos piezas con estampado tropical', 2, 'CAT2-000023', 'H&M', 'BK200', '{"talla": "S"}', NOW(), NOW(), TRUE, 2),
('Sombrero Panamá', 'Sombrero de paja estilo clásico', 2, 'CAT2-000024', 'Panama Hats', 'PH01', '{"talla": "Unica"}', NOW(), NOW(), TRUE, 2),
('Bufanda de Lana', 'Bufanda suave y cálida', 2, 'CAT2-000025', 'Burberry', 'BB100', '{"color": "Beige", "talla": "Unica"}', NOW(), NOW(), TRUE, 2);
