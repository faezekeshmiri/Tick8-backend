"""Story 2 – Private content management (Categories, Subcategories, Flashcards)

Replaces the placeholder category/subcategory tables created in 0001 with
the full Story-2 schema and adds the flashcards table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-22
"""

from __future__ import annotations

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Remove placeholder tables & stale enum from Story 1
    # ------------------------------------------------------------------
    op.execute("DROP TABLE IF EXISTS sub_categories CASCADE")
    op.execute("DROP TABLE IF EXISTS categories CASCADE")
    op.execute("DROP TYPE IF EXISTS category_status_enum")

    # ------------------------------------------------------------------
    # 2. New enum for flashcard content type
    # ------------------------------------------------------------------
    op.execute("CREATE TYPE content_type_enum AS ENUM ('text', 'image')")

    # ------------------------------------------------------------------
    # 3. categories — title, soft-delete, timestamps
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE categories (
            id          SERIAL PRIMARY KEY,
            owner_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title       VARCHAR(200) NOT NULL,
            description TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at  TIMESTAMPTZ,
            CONSTRAINT ck_categories_title_not_blank
                CHECK (char_length(trim(title)) > 0)
        )
    """)
    op.execute("CREATE INDEX ix_categories_id         ON categories (id)")
    op.execute("CREATE INDEX ix_categories_owner_id   ON categories (owner_id)")
    op.execute("CREATE INDEX ix_categories_deleted_at ON categories (deleted_at)")

    # ------------------------------------------------------------------
    # 4. sub_categories — owner_id, title, soft-delete, timestamps
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE sub_categories (
            id          SERIAL PRIMARY KEY,
            category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
            owner_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title       VARCHAR(200) NOT NULL,
            description TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at  TIMESTAMPTZ,
            CONSTRAINT ck_sub_categories_title_not_blank
                CHECK (char_length(trim(title)) > 0)
        )
    """)
    op.execute("CREATE INDEX ix_sub_categories_id          ON sub_categories (id)")
    op.execute("CREATE INDEX ix_sub_categories_category_id ON sub_categories (category_id)")
    op.execute("CREATE INDEX ix_sub_categories_owner_id    ON sub_categories (owner_id)")
    op.execute("CREATE INDEX ix_sub_categories_deleted_at  ON sub_categories (deleted_at)")

    # ------------------------------------------------------------------
    # 5. flashcards — front/back content, ordering, soft-delete
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE flashcards (
            id              SERIAL PRIMARY KEY,
            sub_category_id INTEGER NOT NULL REFERENCES sub_categories(id) ON DELETE CASCADE,
            owner_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            front_type      content_type_enum NOT NULL DEFAULT 'text',
            front_text      TEXT,
            front_image_url VARCHAR(512),
            back_type       content_type_enum NOT NULL DEFAULT 'text',
            back_text       TEXT,
            back_image_url  VARCHAR(512),
            order_index     INTEGER NOT NULL DEFAULT 0,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at      TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX ix_flashcards_id              ON flashcards (id)")
    op.execute("CREATE INDEX ix_flashcards_sub_category_id ON flashcards (sub_category_id)")
    op.execute("CREATE INDEX ix_flashcards_owner_id        ON flashcards (owner_id)")
    op.execute(
        "CREATE INDEX ix_flashcards_order "
        "ON flashcards (sub_category_id, order_index)"
    )
    op.execute("CREATE INDEX ix_flashcards_deleted_at      ON flashcards (deleted_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS flashcards CASCADE")
    op.execute("DROP TABLE IF EXISTS sub_categories CASCADE")
    op.execute("DROP TABLE IF EXISTS categories CASCADE")
    op.execute("DROP TYPE IF EXISTS content_type_enum")

    # Restore Story-1 placeholder tables
    op.execute("CREATE TYPE category_status_enum AS ENUM ('Active', 'Archived')")
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
