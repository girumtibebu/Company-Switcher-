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

from company_switcher.constants import PRINT_FORMAT_DOCTYPES, SCOPED_DOCTYPES

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
	extra = frappe.get_hooks("company_switcher_doctypes") or []
	return set(SCOPED_DOCTYPES) | set(extra)


def get_permission_query_conditions(user=None, doctype=None):
	"""List filter for the switcher. Nothing is added while the user sees all their companies."""
	if not doctype or frappe.flags.ignore_company_switcher:
		return ""
	if doctype not in get_scoped_doctypes():
		return ""
	user = user or frappe.session.user
	if user == "Guest":
		return ""
	field = frappe.get_meta(doctype).get_field("company")
	if not field or field.fieldtype != "Link" or field.options != "Company":
		return ""
	allowed = get_allowed_companies(user)
	scope = get_scope(user)
	if set(scope) >= set(allowed):
		return ""
	values = ", ".join(frappe.db.escape(name) for name in scope)
	return f"(ifnull(`tab{doctype}`.`company`, '') = '' or `tab{doctype}`.`company` in ({values}))"


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
