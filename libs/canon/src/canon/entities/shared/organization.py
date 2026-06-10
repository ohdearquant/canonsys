"""Organization entity - companies, agencies, vendors."""

from __future__ import annotations

from ..entity import ContentModel, Entity, register_entity

__all__ = (
    "Organization",
    "OrganizationContent",
)


class OrganizationContent(ContentModel):
    """A company, agency, or vendor.

    Not tenant-scoped: organizations exist independently and may be
    referenced by multiple tenants (e.g., a vendor used by many companies).
    """

    name: str

    # Classification
    org_type: str | None = None  # employer, vendor, agency
    industry: str | None = None
    size_range: str | None = None  # 1-10, 11-50, 51-200, 201-500, 500+

    # Legal
    ein: str | None = None  # Employer Identification Number
    legal_name: str | None = None

    # Address
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str = "US"

    # Contact
    website: str | None = None
    phone: str | None = None


@register_entity("organizations")
class Organization(Entity):
    """Entity representing an organization."""

    content: OrganizationContent
