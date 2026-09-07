"""get_company_info — profile of the caller's own company."""

from apps.mcp_server.schemas.company import GetCompanyInfoInput, GetCompanyInfoOutput
from apps.mcp_server.scoping import ScopeError, resolve_customer


def get_company_info(params: GetCompanyInfoInput) -> GetCompanyInfoOutput:
    user = resolve_customer(params.customer_id)
    if user.company_id is None:
        raise ScopeError('User is not assigned to a company.', code='FORBIDDEN')

    company = user.company
    return GetCompanyInfoOutput(
        company_id=company.company_id,
        company_name=company.company_name,
        country=company.country,
        sector=company.sector,
        city=company.city,
        currency=company.currency,
        locale=company.locale,
    )
