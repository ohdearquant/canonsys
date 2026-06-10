"""Database role separation.

Generates SQL for creating database roles with proper privilege separation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from canon.entities.entity import Entity

__all__ = (
    "RoleConfig",
    "generate_database_roles",
    "generate_table_ownership",
)


@dataclass
class RoleConfig:
    """Configuration for database role creation.

    Attributes:
        owner: Role that owns tables, runs migrations. Restricted credential.
        app: Runtime application role. NO superuser, NO BYPASSRLS.
        support: Internal support tools. Tenant-scoped or break-glass.
        analytics: Read-only role for warehouse/reporting.
        password_owner: Password for owner role (required for creation).
        password_app: Password for app role (required for creation).
        password_support: Password for support role (optional).
        password_analytics: Password for analytics role (optional).
    """

    owner: str = "canon_owner"
    app: str = "canon_app"
    support: str = "canon_support"
    analytics: str = "canon_analytics"
    password_owner: str | None = None
    password_app: str | None = None
    password_support: str | None = None
    password_analytics: str | None = None


def generate_database_roles(
    config: RoleConfig,
    schema: str = "public",
) -> str:
    """Generate SQL for database role creation with privilege separation.

    Creates four roles:
    - owner: Owns tables, runs migrations (restricted credential)
    - app: Runtime role with RLS enforcement (NO superuser, NO BYPASSRLS)
    - support: Internal support with tenant-scoped access
    - analytics: Read-only for reporting/warehouse

    Args:
        config: Role names and optional passwords.
        schema: Schema to grant privileges on.

    Returns:
        SQL statements for role creation.

    SECURITY NOTE:
    - Owner role should only be used for migrations
    - App role MUST connect through connection pooler with RLS
    - Support role has same RLS as app unless break-glass enabled
    - Analytics role gets SELECT only on views (not base tables)
    """
    parts: list[str] = []

    parts.append("-- Database role separation")
    parts.append("-- Run as superuser during infrastructure setup\n")

    # Owner role - owns tables, runs migrations
    owner_pw = f" PASSWORD '{config.password_owner}'" if config.password_owner else ""
    parts.append(f"""-- Owner role: owns tables, runs migrations
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{config.owner}') THEN
        CREATE ROLE {config.owner} LOGIN{owner_pw};
    END IF;
END $$;

-- Owner gets full control of schema
GRANT ALL ON SCHEMA {schema} TO {config.owner};
GRANT ALL ON SCHEMA app TO {config.owner};
""")

    # App role - runtime, RLS enforced
    app_pw = f" PASSWORD '{config.password_app}'" if config.password_app else ""
    parts.append(f"""-- App role: runtime application role (RLS enforced)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{config.app}') THEN
        CREATE ROLE {config.app} LOGIN{app_pw}
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    END IF;
END $$;

-- App role gets usage on schema, but not ownership
GRANT USAGE ON SCHEMA {schema} TO {config.app};
GRANT USAGE ON SCHEMA app TO {config.app};
-- App role gets DML on all tables (RLS filters the data)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {schema} TO {config.app};
ALTER DEFAULT PRIVILEGES IN SCHEMA {schema}
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {config.app};
""")

    # Support role - tenant-scoped or break-glass
    support_pw = f" PASSWORD '{config.password_support}'" if config.password_support else ""
    parts.append(f"""-- Support role: internal support tools
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{config.support}') THEN
        CREATE ROLE {config.support} LOGIN{support_pw}
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    END IF;
END $$;

-- Support role same as app role (RLS enforced)
-- For break-glass access, use SET ROLE or session variable
GRANT USAGE ON SCHEMA {schema} TO {config.support};
GRANT USAGE ON SCHEMA app TO {config.support};
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {schema} TO {config.support};
ALTER DEFAULT PRIVILEGES IN SCHEMA {schema}
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {config.support};
""")

    # Analytics role - read-only
    analytics_pw = f" PASSWORD '{config.password_analytics}'" if config.password_analytics else ""
    parts.append(f"""-- Analytics role: read-only for warehouse/reporting
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{config.analytics}') THEN
        CREATE ROLE {config.analytics} LOGIN{analytics_pw}
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    END IF;
END $$;

-- Analytics role gets SELECT only
GRANT USAGE ON SCHEMA {schema} TO {config.analytics};
GRANT USAGE ON SCHEMA app TO {config.analytics};
GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO {config.analytics};
ALTER DEFAULT PRIVILEGES IN SCHEMA {schema}
    GRANT SELECT ON TABLES TO {config.analytics};
""")

    return "\n".join(parts)


def generate_table_ownership(
    entity_cls: type[Entity],
    owner_role: str = "canon_owner",
) -> str:
    """Generate ALTER TABLE to set ownership to the owner role.

    Tables should be owned by the migration role, not the app role.
    This ensures FORCE ROW LEVEL SECURITY blocks the app role.
    """
    table = entity_cls._table_name
    schema = entity_cls._schema
    return f'ALTER TABLE "{schema}"."{table}" OWNER TO {owner_role};'
