"""list_company_users — teammate directory for the caller's own company.

Deliberately exposes only non-sensitive fields (username, job title, role) --
never email, password, or other account internals.
"""

from django.contrib.auth import get_user_model

from apps.mcp_server.schemas.company import (
    CompanyUserSummary,
    ListCompanyUsersInput,
    ListCompanyUsersOutput,
)
from apps.mcp_server.scoping import ScopeError, resolve_customer


def list_company_users(params: ListCompanyUsersInput) -> ListCompanyUsersOutput:
    user = resolve_customer(params.customer_id)
    if user.company_id is None:
        raise ScopeError('User is not assigned to a company.', code='FORBIDDEN')

    User = get_user_model()
    qs = User.objects.filter(company_id=user.company_id).order_by('username')
    users = [
        CompanyUserSummary(
            user_id=u.user_id,
            username=u.username,
            job_title=u.job_title,
            visibility=u.visibility,
        )
        for u in qs
    ]
    return ListCompanyUsersOutput(users=users)
