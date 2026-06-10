"""Shared entities and awareness mixins.

Core Entities:
    Organization: Companies, agencies, vendors (not tenant-scoped)
    Tenant: Isolated workspace/account
    User: Authenticated user with system access
    Person: Data subject (candidate, employee, contact)
    Employee: Employment relationship (links to Person)
    Session: Authenticated user session

Awareness Mixins:
    TenantAware: Content scoped to a tenant
    UserAware/ActorAware: Content associated with a user
    SubjectAware: Content associated with a data subject (Person)
    EmployeeAware: Content associated with an employee
"""

from .employee import (
    Employee,
    EmployeeAware,
    EmployeeContent,
    EmploymentStatus,
    OptEmployeeAware,
)
from .organization import Organization, OrganizationContent
from .person import OptSubjectAware, Person, PersonContent, SubjectAware
from .protocols import AwareOf, is_aware_of
from .session import Session, SessionContent
from .tenant import Tenant, TenantAware, TenantContent
from .user import ActorAware, OptActorAware, User, UserAware, UserContent

__all__ = (
    # Entities
    "Employee",
    "EmployeeContent",
    "EmploymentStatus",
    "Organization",
    "OrganizationContent",
    "Person",
    "PersonContent",
    "Session",
    "SessionContent",
    "Tenant",
    "TenantContent",
    "User",
    "UserContent",
    # Awareness mixins
    "TenantAware",
    "UserAware",
    "ActorAware",
    "OptActorAware",
    "SubjectAware",
    "OptSubjectAware",
    "EmployeeAware",
    "OptEmployeeAware",
    # Protocols
    "AwareOf",
    "is_aware_of",
)
