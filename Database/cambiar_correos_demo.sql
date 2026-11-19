BEGIN;

UPDATE usuarios
SET email = 'admin@medalloclub.com'
WHERE email = 'admin@nightlife-ds.com';

UPDATE usuarios
SET email = 'promotora@medalloclub.com'
WHERE email = 'carla.promotora@nightlife-ds.com';

UPDATE usuarios
SET email = 'puerta@medalloclub.com'
WHERE email = 'puerta.principal@nightlife-ds.com';

COMMIT;
