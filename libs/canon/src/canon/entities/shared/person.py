"""Person entity and subject awareness mixins."""

from __future__ import annotations

from kron.types import FK

from ..entity import ContentModel, Entity, register_entity
from .tenant import TenantAware

__all__ = ("OptSubjectAware", "Person", "PersonContent", "SubjectAware")


class PersonContent(TenantAware):
    """A person (employee, candidate, contact).

    Data subject in privacy regulations (GDPR, CCPA).
    Each tenant has their own Person records - the same real-world
    person at multiple companies = separate Person in each tenant.
    """

    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    ssn_last_four: str | None = None
    date_of_birth: str | None = None
    person_type: str = "candidate"  # candidate, employee, contact
    current_title: str | None = None
    current_company: str | None = None
    location: str | None = None

    @property
    def full_name(self) -> str:
        """Return formatted full name."""
        return f"{self.first_name} {self.last_name}"


@register_entity("persons")
class Person(Entity):
    """Entity representing a data subject."""

    content: PersonContent


class SubjectAware(ContentModel):
    """Mixin for content about a data subject (Person)."""

    subject_id: FK[Person]


class OptSubjectAware(ContentModel):
    """Mixin for content optionally about a data subject."""

    subject_id: FK[Person] | None = None
