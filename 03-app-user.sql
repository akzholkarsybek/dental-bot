CREATE USER dental_bot_user WITH PASSWORD 'your_app_password';

GRANT CONNECT ON DATABASE dental_bot TO dental_bot_user;

GRANT USAGE ON SCHEMA public TO dental_bot_user;

GRANT SELECT, INSERT, UPDATE, DELETE
ON ALL TABLES IN SCHEMA public
TO dental_bot_user;

GRANT USAGE, SELECT
ON ALL SEQUENCES IN SCHEMA public
TO dental_bot_user;