"""Employee entity - represents an employment relationship.

An Employee links to a Person (the data subject) and adds employment-specific
attributes. This separation allows:
- Same person to transition: candidate → employee → former employee
- Employment data (department, title) separate from PII (name, SSN)
- Different compliance rules for employment data vs candidate data
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from kron.types import FK

from ..entity import ContentModel, Entity, register_entity
from .person import Person
from .tenant import TenantAware

__all__ = (
    "Employee",
    "EmployeeAware",
    "EmployeeContent",
    "EmploymentStatus",
    "OptEmployeeAware",
)


class EmploymentStatus(str, Enum):
    """Employment lifecycle states."""

    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


class EmployeeContent(TenantAware):
    """Employment relationship data.

    Legal basis for data access: Employment contract (GDPR Art. 6(1)(b))
    and legitimate interest for workforce management (Art. 6(1)(f)).

    Unlike candidate data which requires explicit consent, employee data
    access is governed by the employment relationship.
    """

    # Link to the underlying Person (data subject)
    person_id: FK[Person]

    # Employment identifiers
    employee_number: str | None = None

    # Organizational
    department: str | None = None
    job_title: str | None = None
    manager_id: FK[Employee] | None = None

    # Employment dates
    hire_date: datetime | None = None
    termination_date: datetime | None = None

    # Status
    employment_status: EmploymentStatus = EmploymentStatus.ACTIVE


@register_entity("employees")
class Employee(Entity):
    """Entity representing an employment relationship.

    Compliance note: Employee data access does not require the same
    consent gates as candidate data. The employment contract provides
    the legal basis for processing employee information.
    """

    content: EmployeeContent


class EmployeeAware(ContentModel):
    """Mixin for content associated with an employee."""

    employee_id: FK[Employee]


class OptEmployeeAware(ContentModel):
    """Mixin for content optionally associated with an employee."""

    employee_id: FK[Employee] | None = None
