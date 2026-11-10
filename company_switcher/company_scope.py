"""Company switcher: let a user narrow Desk to some of the companies they may see.

Works on any ERPNext site with several companies, flat or in a group hierarchy
(Company > Parent Company, with Is Group ticked on the parents).

Two layers decide which company's records a user sees:

1. Access (set by an admin): the user's Company User Permissions. A permission on
   a group company covers the companies under it, as Frappe applies it. A user
   with no Company permission sees every company.
2. Scope (picked by the user in the switcher at the top left of Desk): a subset of
   the companies they have access to. Ticking a group ticks every company under
   it. Ticking everything shows everything; ticking fewer narrows company-owned
   lists and link searches to those companies.

The scope is stored as a user default, so it follows the user across devices.
The first company in the scope becomes the user's default company, so new
documents start in it.
"""

import json

import frappe
from frappe import _

from company_switcher.constants import NEVER_SCOPED, PRINT_FORMAT_DOCTYPES, SCOPED_DOCTYPES

SCOPE_KEY = "company_switcher_scope"


def get_companies():
	"""Every company with its place in the group tree."""
	return frappe.get_all(
		"Company",
		fields=["name", "abbr", "company_logo", "parent_company", "is_group", "lft", "rgt"],
		order_by="lft asc",
		ignore_permissions=True,
	)


def get_allowed_companies(user=None):
	"""Trading (non-group) companies the user may see, in tree order."""
	from frappe.permissions import get_user_permissions

	user = user or frappe.session.user
	leaves = [row.name for row in get_companies() if not row.is_group]
	permissions = get_user_permissions(user).get("Company")
	if not permissions:
		return leaves
	permitted = {row.get("doc") for row in permissions}
	return [name for name in leaves if name in permitted]


def get_scope(user=None):
	"""Companies the user chose to see; all allowed companies when they never chose."""
	user = user or frappe.session.user
	allowed = get_allowed_companies(user)
	saved = frappe.defaults.get_user_default(SCOPE_KEY, user)
	try:
		chosen = set(json.loads(saved)) if saved else set()
	except (TypeError, ValueError):
		chosen = set()
	return [name for name in allowed if name in chosen] or allowed


@frappe.whitelist()
def get_switcher():
	"""What the switcher shows: allowed companies plus the groups above them, in tree order."""
	allowed = set(get_allowed_companies())
	companies = get_companies()
	by_name = {row.name: row for row in companies}

	visible = set(allowed)
	for name in allowed:
		parent = by_name[name].parent_company
		while parent and parent in by_name and parent not in visible:
			visible.add(parent)
			parent = by_name[parent].parent_company

	rows = []
	for row in companies:
		if row.name not in visible:
			continue
		depth, parent = 0, row.parent_company
		while parent and parent in visible:
			depth += 1
			parent = by_name[parent].parent_company
		rows.append(
			{
				"name": row.name,
				"abbr": row.abbr,
				"logo": row.company_logo,
				"parent": row.parent_company if row.parent_company in visible else None,
				"is_group": bool(row.is_group),
				"depth": depth,
			}
		)
	return {"companies": rows, "scope": get_scope()}


@frappe.whitelist()
def set_scope(companies):
	"""Save the switcher choice. Group names expand to their companies; companies the user can't see are dropped."""
	if isinstance(companies, str):
		companies = json.loads(companies)
	picked = set(companies or [])
	tree = get_companies()
	for group in [row for row in tree if row.is_group and row.name in picked]:
		picked.update(row.name for row in tree if group.lft < row.lft and row.rgt < group.rgt)
	companies = [name for name in get_allowed_companies() if name in picked]
	if not companies:
		frappe.throw(_("Pick at least one company."))
	user = frappe.session.user
	frappe.defaults.set_user_default(SCOPE_KEY, json.dumps(companies), user)
	if frappe.defaults.get_user_default("Company") not in companies:
		frappe.defaults.set_user_default("company", companies[0], user)
	frappe.clear_cache(user=user)
	return get_switcher()


def get_scoped_doctypes():
	"""Kept for callers that list the doctypes; the filter itself no longer needs the list."""
	extra = frappe.get_hooks("company_switcher_doctypes") or []
	return set(SCOPED_DOCTYPES) | set(extra)


def get_permission_query_conditions(user=None, doctype=None):
	"""List filter, called for every doctype through the "*" hook."""
	if not doctype or frappe.flags.ignore_company_switcher:
		return ""
	user = user or frappe.session.user
	if user == "Guest" or doctype in NEVER_SCOPED:
		return ""
	if doctype == "Item":
		return _item_condition(user)
	if doctype == "Customer":
		return _customer_condition(user)
	field = frappe.get_meta(doctype).get_field("company")
	if not field or field.fieldtype != "Link" or field.options != "Company":
		return ""
	allowed = get_allowed_companies(user)
	scope = get_scope(user)
	if set(scope) >= set(allowed):
		return ""
	return f"(ifnull(`tab{doctype}`.`company`, '') = '' or `tab{doctype}`.`company` in ({_sql_list(scope)}))"


def _sql_list(values):
	return ", ".join(frappe.db.escape(value) for value in values)


def _sees_every_company(user):
	"""True when the user's scope covers every trading company, so nothing needs narrowing."""
	trading = {row.name for row in get_companies() if not row.is_group}
	return set(get_scope(user)) >= trading


def _item_condition(user):
	"""An item shows when no company claims it, when a company the user picked sets it up,
	or when a quotation of such a company uses it."""
	if _sees_every_company(user):
		return ""
	companies = _sql_list(get_scope(user))
	return (
		"(not exists (select 1 from `tabItem Default` d where d.parent = `tabItem`.`name`"
		" and ifnull(d.company, '') != '')"
		f" or exists (select 1 from `tabItem Default` d where d.parent = `tabItem`.`name`"
		f" and d.company in ({companies}))"
		" or exists (select 1 from `tabQuotation Item` qi join `tabQuotation` q on q.name = qi.parent"
		f" where qi.item_code = `tabItem`.`name` and q.company in ({companies})))"
	)


def _customer_condition(user):
	"""A customer shows when it has no sales yet, or has a quotation, order or invoice of a company the user picked."""
	if _sees_every_company(user):
		return ""
	companies = _sql_list(get_scope(user))
	parties = (("Quotation", "party_name"), ("Sales Order", "customer"), ("Sales Invoice", "customer"))
	no_sales = " and ".join(
		f"not exists (select 1 from `tab{doctype}` x where x.`{field}` = `tabCustomer`.`name`)"
		for doctype, field in parties
	)
	in_scope = " or ".join(
		f"exists (select 1 from `tab{doctype}` x where x.`{field}` = `tabCustomer`.`name`"
		f" and x.company in ({companies}))"
		for doctype, field in parties
	)
	return f"(({no_sales}) or {in_scope})"


def get_company_print_formats():
	"""{company: {doctype: print format}} from the Print Formats section on each Company."""
	meta = frappe.get_meta("Company")
	fields = ["name", *(field for field in PRINT_FORMAT_DOCTYPES.values() if meta.has_field(field))]
	formats = {}
	for row in frappe.get_all("Company", fields=fields, ignore_permissions=True):
		chosen = {doctype: row.get(field) for doctype, field in PRINT_FORMAT_DOCTYPES.items() if row.get(field)}
		if chosen:
			formats[row.name] = chosen
	return formats


def boot_session(bootinfo):
	if frappe.session.user == "Guest":
		return
	bootinfo.company_switcher = get_switcher()
	bootinfo.company_print_formats = get_company_print_formats()
