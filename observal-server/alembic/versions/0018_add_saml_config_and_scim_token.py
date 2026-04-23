"""Add SAML config, SCIM token tables, and SSO fields on users.

Revision ID: 0018
Revises: 0017
Create Date: 2026-04-23
"""

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS saml_configs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            idp_entity_id TEXT NOT NULL,
            idp_sso_url TEXT NOT NULL,
            idp_slo_url TEXT,
            idp_x509_cert TEXT NOT NULL,
            sp_entity_id TEXT NOT NULL,
            sp_acs_url TEXT NOT NULL,
            sp_private_key_enc TEXT NOT NULL,
            sp_x509_cert TEXT NOT NULL,
            jit_provisioning BOOLEAN NOT NULL DEFAULT TRUE,
            default_role TEXT NOT NULL DEFAULT 'user',
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(org_id)
        );
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS scim_tokens (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(org_id, token_hash)
        );
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'auth_provider'
            ) THEN
                ALTER TABLE users ADD COLUMN auth_provider TEXT NOT NULL DEFAULT 'local';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'sso_subject_id'
            ) THEN
                ALTER TABLE users ADD COLUMN sso_subject_id TEXT;
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS scim_tokens;")
    op.execute("DROP TABLE IF EXISTS saml_configs;")
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'auth_provider'
            ) THEN
                ALTER TABLE users DROP COLUMN auth_provider;
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'sso_subject_id'
            ) THEN
                ALTER TABLE users DROP COLUMN sso_subject_id;
            END IF;
        END
        $$;
    """)
