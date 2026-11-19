-- =====================================================================
-- Nightlife Data Scientist - Datos de demostración
-- Ejecutar después de schema.sql:
--   psql -U postgres -d nightlife_db -f Database/seed.sql
--
-- Credenciales de prueba (contraseña en texto plano, ver hash bcrypt):
--   admin@medalloclub.com     / Admin123     (Administrador)
--   promotora@medalloclub.com / Promotor123  (Promotor)
--   puerta@medalloclub.com    / Puerta123    (Puerta)
-- =====================================================================

BEGIN;

INSERT INTO usuarios (nombre, email, password_hash, rol, telefono, estado) VALUES
('Admin Principal', 'admin@medalloclub.com',
 '$2b$12$e943rpI082LXKph9DTYGkeeTwmkY3BG.wArdnv.P8JOpyvAk8.qGq', 'Administrador', '3000000000', TRUE),
('Carla Promotora', 'promotora@medalloclub.com',
 '$2b$12$J0LIg0DHtZyipIJoVpwaqe7tSHooieZ881wO.6HwcPewdbIHEPs2i', 'Promotor', '3001112233', TRUE),
('Puerta Principal', 'puerta@medalloclub.com',
 '$2b$12$qUE7akBKW5ovBi8r0g5vbekzUg9NFg2dBr5bQL4DWoj7sLcoB9c6K', 'Puerta', '3002223344', TRUE)
ON CONFLICT (email) DO NOTHING;

INSERT INTO eventos (administrador_id, nombre, fecha, aforo_maximo, estado)
SELECT id, 'Noche Retro Viernes', CURRENT_DATE + INTERVAL '2 days', 150, 'planeado'
FROM usuarios WHERE email = 'admin@medalloclub.com'
ON CONFLICT DO NOTHING;

INSERT INTO invitados (evento_id, promotor_id, nombre, qr_code, estado)
SELECT e.id, p.id, invitado.nombre, invitado.qr_code, 'pendiente'
FROM eventos e
JOIN usuarios p ON p.email = 'promotora@medalloclub.com'
CROSS JOIN (VALUES
    ('María Gómez', 'NLD-DEMO-0001'),
    ('Juan Pérez', 'NLD-DEMO-0002'),
    ('Laura Restrepo', 'NLD-DEMO-0003')
) AS invitado(nombre, qr_code)
WHERE e.nombre = 'Noche Retro Viernes'
ON CONFLICT (qr_code) DO NOTHING;

INSERT INTO comisiones (promotor_id, evento_id, porcentaje, monto, estado)
SELECT p.id, e.id, 10.00, 0, 'pendiente'
FROM usuarios p, eventos e
WHERE p.email = 'promotora@medalloclub.com' AND e.nombre = 'Noche Retro Viernes'
ON CONFLICT DO NOTHING;

COMMIT;
