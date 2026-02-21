"""Story 1 – User authentication and role management

Revision ID: 0001
Revises:
Create Date: 2026-02-21
"""

from __future__ import annotations

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TYPE user_role_enum AS ENUM ('user', 'admin')")
    op.execute("CREATE TYPE category_status_enum AS ENUM ('Active', 'Archived')")
    op.execute("CREATE TYPE verification_purpose_enum AS ENUM ('registration', 'email_change')")

    op.execute("""
        CREATE TABLE users (
            id                    SERIAL PRIMARY KEY,
            display_name          VARCHAR(100) NOT NULL,
            email                 VARCHAR(255) NOT NULL UNIQUE,
            hashed_password       VARCHAR(255) NOT NULL,
            role                  user_role_enum NOT NULL DEFAULT 'user',
            is_active             BOOLEAN NOT NULL DEFAULT TRUE,
            is_email_verified     BOOLEAN NOT NULL DEFAULT FALSE,
            avatar_url            VARCHAR(512),
            pending_email         VARCHAR(255),
            failed_login_attempts INTEGER NOT NULL DEFAULT 0,
            locked_until          TIMESTAMPTZ,
            created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_users_display_name_not_blank
                CHECK (char_length(trim(display_name)) >= 1),
            CONSTRAINT ck_users_email_not_blank
                CHECK (char_length(trim(email)) > 0),
            CONSTRAINT ck_users_hashed_password_not_blank
                CHECK (char_length(trim(hashed_password)) > 0)
        )
    """)
    op.execute("CREATE INDEX ix_users_id    ON users (id)")
    op.execute("CREATE UNIQUE INDEX ix_users_email ON users (email)")

    op.execute("""
        CREATE TABLE categories (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name        VARCHAR(120) NOT NULL,
            description VARCHAR(1024),
            status      category_status_enum NOT NULL DEFAULT 'Active',
            CONSTRAINT ck_categories_name_not_blank CHECK (char_length(trim(name)) > 0),
            CONSTRAINT uq_categories_user_name UNIQUE (user_id, name)
        )
    """)
    op.execute("CREATE INDEX ix_categories_id      ON categories (id)")
    op.execute("CREATE INDEX ix_categories_user_id ON categories (user_id)")

    op.execute("""
        CREATE TABLE sub_categories (
            id          SERIAL PRIMARY KEY,
            category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
            name        VARCHAR(120) NOT NULL,
            description VARCHAR(1024)
        )
    """)
    op.execute("CREATE INDEX ix_sub_categories_id          ON sub_categories (id)")
    op.execute("CREATE INDEX ix_sub_categories_category_id ON sub_categories (category_id)")

    op.execute("""
        CREATE TABLE refresh_tokens (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token       VARCHAR(128) NOT NULL UNIQUE,
            expires_at  TIMESTAMPTZ NOT NULL,
            remember_me BOOLEAN NOT NULL DEFAULT FALSE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ix_refresh_tokens_id      ON refresh_tokens (id)")
    op.execute("CREATE INDEX ix_refresh_tokens_user_id ON refresh_tokens (user_id)")
    op.execute("CREATE UNIQUE INDEX ix_refresh_tokens_token ON refresh_tokens (token)")

    op.execute("""
        CREATE TABLE email_verification_tokens (
            id         SERIAL PRIMARY KEY,
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token      VARCHAR(128) NOT NULL UNIQUE,
            purpose    verification_purpose_enum NOT NULL,
            new_email  VARCHAR(255),
            expires_at TIMESTAMPTZ NOT NULL,
            used       BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ix_email_verification_tokens_id      ON email_verification_tokens (id)")
    op.execute("CREATE INDEX ix_email_verification_tokens_user_id ON email_verification_tokens (user_id)")
    op.execute("CREATE UNIQUE INDEX ix_email_verification_tokens_token ON email_verification_tokens (token)")

    op.execute("""
        CREATE TABLE password_reset_tokens (
            id         SERIAL PRIMARY KEY,
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token      VARCHAR(128) NOT NULL UNIQUE,
            expires_at TIMESTAMPTZ NOT NULL,
            used       BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ix_password_reset_tokens_id      ON password_reset_tokens (id)")
    op.execute("CREATE INDEX ix_password_reset_tokens_user_id ON password_reset_tokens (user_id)")
    op.execute("CREATE UNIQUE INDEX ix_password_reset_tokens_token ON password_reset_tokens (token)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS password_reset_tokens CASCADE")
    op.execute("DROP TABLE IF EXISTS email_verification_tokens CASCADE")
    op.execute("DROP TABLE IF EXISTS refresh_tokens CASCADE")
    op.execute("DROP TABLE IF EXISTS sub_categories CASCADE")
    op.execute("DROP TABLE IF EXISTS categories CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    op.execute("DROP TYPE IF EXISTS verification_purpose_enum")
    op.execute("DROP TYPE IF EXISTS category_status_enum")
    op.execute("DROP TYPE IF EXISTS user_role_enum")
