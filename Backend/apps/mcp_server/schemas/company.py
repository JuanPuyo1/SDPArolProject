"""Schemas for company profile and company-user-directory tools."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GetCompanyInfoInput(BaseModel):
    """Look up the caller's own company profile (no single-machine scope required)."""

    customer_id: str = Field(
        ...,
        min_length=1,
        description='Tenant identity: Django username or numeric user id as string.',
    )


class GetCompanyInfoOutput(BaseModel):
    company_id: str
    company_name: str
    country: str
    sector: str
    city: str
    currency: str
    locale: str


class ListCompanyUsersInput(BaseModel):
    """List teammates in the caller's own company (no single-machine scope required)."""

    customer_id: str = Field(
        ...,
        min_length=1,
        description='Tenant identity: Django username or numeric user id as string.',
    )


class CompanyUserSummary(BaseModel):
    """Non-sensitive teammate fields only -- never email, password, or other
    account internals (see README/plan: any company user may query the
    directory, but only these fields)."""

    user_id: str
    username: str
    job_title: str
    visibility: str


class ListCompanyUsersOutput(BaseModel):
    users: list[CompanyUserSummary]
