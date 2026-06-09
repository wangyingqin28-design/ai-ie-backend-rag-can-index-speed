:setvar APP_DB_NAME "getai"
:setvar APP_DB_USER "dev"
:setvar APP_DB_PASSWORD "123456"

IF DB_ID(N'$(APP_DB_NAME)') IS NULL
BEGIN
    DECLARE @createDbSql nvarchar(max) = N'CREATE DATABASE ' + QUOTENAME(N'$(APP_DB_NAME)');
    EXEC (@createDbSql);
END
GO

IF SUSER_ID(N'$(APP_DB_USER)') IS NULL
BEGIN
    DECLARE @createLoginSql nvarchar(max) =
        N'CREATE LOGIN ' + QUOTENAME(N'$(APP_DB_USER)') +
        N' WITH PASSWORD = ' + QUOTENAME(N'$(APP_DB_PASSWORD)', '''') +
        N', CHECK_POLICY = OFF, CHECK_EXPIRATION = OFF';
    EXEC (@createLoginSql);
END
GO

USE [$(APP_DB_NAME)];
GO

IF USER_ID(N'$(APP_DB_USER)') IS NULL
BEGIN
    DECLARE @createUserSql nvarchar(max) =
        N'CREATE USER ' + QUOTENAME(N'$(APP_DB_USER)') +
        N' FOR LOGIN ' + QUOTENAME(N'$(APP_DB_USER)');
    EXEC (@createUserSql);
END
GO

ALTER ROLE db_owner ADD MEMBER [$(APP_DB_USER)];
GO

SELECT
    @@VERSION AS sql_server_version,
    DB_NAME() AS database_name,
    USER_NAME() AS current_database_user;
GO
